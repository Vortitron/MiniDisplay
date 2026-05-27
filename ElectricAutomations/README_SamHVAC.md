# Sam HVAC (Living Room) – Two-Number Temperature Control

`sam.yaml` controls the living-room heat pump (`climate.sam`) using a "fooling" approach: it adjusts Sam's target relative to Sam's internal sensor so that Sam effectively turns heat on/off based on a remote temperature.

`DaytimeCheapHeat.yaml` manages electricity price optimisation by setting two temperature numbers that feed into `sam.yaml`.

## Two-number architecture

### `input_number.sam_desired_temperature` — human comfort target

Set by `DaytimeCheapHeat.yaml` based on occupancy, time, **and a 90-minute manual-override lock** so a user-driven change actually sticks:

| Condition (evaluated in order) | Desired |
|---|---|
| **Holiday mode** on | **10°C** (frost protection - always wins) |
| **Manual override active** (current_desired ≠ what the automation last wrote, OR `input_datetime.sam_desired_lock_until` is in the future) | **Preserved as-is** for at least 90 minutes |
| **Evening** (19:00–23:00) or **TV on** | **20°C** |
| Otherwise | **16°C** |

#### How the manual-override lock works

The automation tracks two things in HA helpers:

- `input_number.sam_automation_set_value` - **the value the automation last wrote** to `sam_desired_temperature`. Updated unconditionally at the end of every automation run, BEFORE the desired write, so the automation's own state-change-trigger never looks like a manual override.
- `input_datetime.sam_desired_lock_until` - **when the current lock expires**. Default is in the past (no lock).

On every trigger (state change OR the every-15-min time pattern):

1. Read `current_desired` (whatever's in `sam_desired_temperature` now) and `auto_set` (the helper).
2. If `|current_desired - auto_set| > 0.05`, conclude it was a manual change (someone other than us wrote a different value). Set `sam_desired_lock_until = now + 90 min` and log "Manual override detected".
3. Compute `desired`. While the lock is active OR a manual override was just detected, `desired = current_desired` (preserved as-is). Otherwise use the time/TV/holiday logic.
4. Compute `control`. While the lock is active, `control = desired` directly - **the price logic is bypassed entirely** so the user's "I want 23 now, electricity be damned" intent wins. Outside the lock, the normal cheap-now/expensive-now/pre-evening adjustments apply.
5. Write `auto_set = desired` FIRST, then `desired` to `sam_desired_temperature`, then `control` to `sam_control_temperature`.

The "auto_set BEFORE desired" ordering is critical: the `set_value` on `sam_desired_temperature` fires a fresh trigger, and we don't want the follow-on run to see `current_desired != auto_set` and spuriously re-trigger the override.

#### What this gives the user

- **HA UI / voice / scripts / MiniDisplay temperature dial / KitchenDetectorer Button 6** all just write `input_number.sam_desired_temperature` directly - any of them setting a value different from what the automation just wrote sticks for 90 minutes.
- After 90 min, the auto logic resumes (drops to 16 °C in the daytime, 20 °C in the evening, etc.).
- **Holiday mode still wins** over a manual lock: enabling holiday mode forces desired and control both to 10 °C even if the user has just set 23. (Disable holiday mode and reset the desired manually to get out of this.)
- **Cheap pre-warming still happens** outside the lock - if the lock has expired and electricity is cheap, control jumps back up to 25 °C as before.

### `input_number.sam_control_temperature` — price-adjusted target

Computed from the desired temperature and electricity price ranking. The first two rules below are new (introduced alongside the 90-minute manual-override lock):

| Condition (evaluated in order) | Control temp |
|---|---|
| Holiday mode | **10°C** |
| **Manual override active (lock in effect)** | **= desired** (price logic bypassed) |
| Cheap now + outside < 10°C | **25°C** (max overheat) |
| Cheap now + approaching evening (15:00–19:00) | **Variable** pre-warm (`prewarm_control_target`, capped at 25°C) only to hold **≥ 19°C** — not a flat 25°C |
| **19:00–23:00 (evening)** | **control = desired** (20°C); if living **≥ 19°C**, no boost even if electricity is relatively cheap |
| Cheap now | **desired + 3°C** (capped at 25) — **skipped** if living room is already within 0.5°C of the boosted target |
| Expensive + TV off + not evening | **16°C** (coast) |
| Otherwise | **desired** |

"Cheap now" means the current hourly price rank (`input_number.electricity_price_rank`) is lower than the 4-hour window rank (`input_number.electricity_price_rank_4h`).

### Evening pre-warming strategy

The system ensures comfort during evening hours (19:00–23:00) without expensive peak-time heating:

1. **15:00–19:00** — if electricity is cheap, control is boosted to 25°C to build thermal mass
2. **19:00–23:00** — desired is 20°C regardless of TV state; control won't drop below desired even if electricity is expensive
3. **Result** — the home is warm by evening from pre-heating, and Sam only needs to maintain (not ramp) during peak hours

`DaytimeCheapHeat.yaml` reads the thermal model (**k**, **h**, **τ**, `hours_to_evening_target`, `forecast_outside_4h`) plus **`sensor.forecast_tonight_min`** and **`sensor.forecast_outside_at_23`**. It skips the 25°C evening boost when:

- living room is already **≥ 19°C**, or
- **mild night** (forecast low ≥ 14°C at 23:00 / tonight) **and** (living ≥ 19.5°C **or** `hours_to_evening_target` ≤ hours until 19:00 + 1 h), or
- **`hours_to_evening_target`** says you will reach 20°C before 19:00 with living already ≥ 17.5°C.

Full working is in **`input_text.sam_preheat_calc`** (k, h, Teq, skips, `pre25=true/false`). See `README_HouseThermalModel.md` for the maths.

### Holiday mode

When `input_boolean.holiday_mode` is on:
- `DaytimeCheapHeat.yaml` sets desired and control both to **10°C** (frost protection)
- All price optimisation logic is bypassed
- `sam.yaml` activates the `heat_8_15` preset on `climate.sam`, which unlocks the unit's low-temperature range (`min_temp` is otherwise 16°C, so the HVAC refuses any setpoint below that without this preset)
- Sam is set to `heat` mode at 10°C

When holiday mode is turned **off**, `sam.yaml` automatically clears the preset back to `none` on its next evaluation, restoring normal operation.

### How sam.yaml uses these numbers

`sam.yaml` reads `input_number.sam_control_temperature` as its `desired_base`. The **effective desired** temperature is:

```
desired_effective = max(sam_control_temperature, bedroom_thermostat_target)
```

So the bedroom thermostat can still override the control temperature if it's asking for more heat.

## Remote temperature used for control

Sam uses different "remote" temperatures for cooling vs heating:

- **Cooling logic** uses the living-room sensor only:
  - `sensor.t_h_sensor_temperature`

- **Heating logic** uses:
  - **Fan OFF** → living-room sensor (`sensor.t_h_sensor_temperature`)
  - **Fan ON** → `min(sensor.bedroomlights_bedroomlights_temperature, sensor.t_h_sensor_temperature)`

The "min" rule encourages Sam to keep heating until the bedroom catches up whenever the circulation fan is actively pushing warm air, unless the living-room overheat guard is triggered.

## Overheat guard (living room cap)

To prevent unnecessary overheating in the living room, `sam.yaml` enforces:

- if `sensor.t_h_sensor_temperature > desired_effective`, Sam does not actively heat
- practical behaviour: heating mode switches to `fan_only`, and the computed setpoint is nudged down

This still allows strategic overheating to help the bedroom, but only up to the highest of:

- `input_number.sam_control_temperature`
- `climate.mama_bedroom_thermostat.temperature`

## "Work harder when far off target" (dynamic heat boost)

Sam's internal sensor can read a bit differently to the room sensors, and a fixed `+1°C` request isn't enough when you're **many degrees** below target.

When heating is needed (`remote_heat < desired_effective - temp_tolerance`), `sam.yaml` sets Sam's target to:

- `sam_setpoint ≈ internal + max(heat_offset, desired_effective - remote_heat)`

So if the remote temperature is **6°C** below desired, Sam's target will be set to roughly **internal + 6°C**, which encourages the heat pump to ramp harder.

The final setpoint is clamped to Sam's `min_temp` / `max_temp` attributes (or fallbacks if the integration doesn't expose them), and also to **`sam_setpoint_cap` (27°C)** in `sam.yaml` so `internal + boost` cannot command a sauna under the unit.

If `sensor.sam_inside_temperature` is already **≥ 27°C**, Sam switches to **fan_only** (`Unit hot, fan only` in the headline) even when room remotes are still below the control target.

### Headline / reason helpers

If `input_text.sam_hvac_reason` is missing or still `unknown` (helpers not reloaded yet), `sam.yaml` derives **`plan_reason`** from control vs desired and back-fills the helper. DaytimeCheapHeat still writes the fuller reason when it runs.

## DaytimeCheapHeat triggers

The `DaytimeCheapHeat.yaml` automation re-evaluates on:

- `media_player.lgnano_55` state change (TV on/off)
- `input_number.electricity_price_rank` change
- `input_number.electricity_price_rank_4h` change
- `input_boolean.daytime_cheap_7_21` change
- `input_number.sam_desired_temperature` change (manual override)
- `input_boolean.holiday_mode` change
- Every 15 minutes (time pattern safety net)

## Dependencies

### DaytimeCheapHeat.yaml
- `media_player.lgnano_55` (TV — occupancy signal)
- `sensor.sam_outside_temperature`
- `sensor.t_h_sensor_temperature` (living room — pre-warm cap)
- `input_number.electricity_price_rank`
- `input_number.electricity_price_rank_4h`
- `input_boolean.daytime_cheap_7_21`
- `input_boolean.holiday_mode`
- `input_number.sam_desired_temperature` (reads and writes)
- `input_number.sam_control_temperature` (writes)
- `input_number.sam_automation_set_value` (reads and writes — manual-override detection)
- `input_datetime.sam_desired_lock_until` (reads and writes — 90-minute manual lock)

### sam.yaml
- `climate.sam` (including `preset_mode` attribute)
- `sensor.sam_inside_temperature`
- `sensor.sam_outside_temperature`
- `input_number.sam_control_temperature`
- `input_boolean.holiday_mode`
- `sensor.t_h_sensor_temperature` (living room)
- `sensor.bedroomlights_bedroomlights_temperature` (bedroom)
- `climate.mama_bedroom_thermostat` (target temperature attribute)
- `climate.circulation_fan` (on/off state)

## Helper entities to create in Home Assistant

### `input_number.sam_control_temperature`
- **Name:** Sam Control Temperature
- **Min:** 10 | **Max:** 30 | **Step:** 1 | **Unit:** °C

### `input_boolean.holiday_mode`
- **Name:** Holiday Mode

### `input_number.sam_automation_set_value`
- **Name:** Sam Automation Set Value
- **Min:** 10 | **Max:** 30 | **Step:** 0.1 | **Unit:** °C
- **Initial:** 16
- **Purpose:** Always equals the value `DaytimeCheapHeat.yaml` last wrote to `sam_desired_temperature`. Used to detect manual overrides (current desired ≠ auto_set ⇒ someone other than the automation changed the desired). Not user-facing; you can hide it from dashboards.

### `input_datetime.sam_desired_lock_until`
- **Name:** Sam Desired Lock Until
- **has_date:** true | **has_time:** true
- **Purpose:** Timestamp when the current manual-override lock expires. Written to `now() + 90 min` whenever a manual change is detected. Default value is in the past (no lock active). You can also write this manually from HA to extend or clear a lock - e.g. set it to `1970-01-01 00:00:00` to clear, or to "now + 4 hours" to lock a value all afternoon.

## Logging

Both automations write `logbook.log` entries.

### `input_text.sam_preheat_calc`
- **Set by:** `DaytimeCheapHeat.yaml`
- **Purpose:** One-line audit of the pre-warm decision: temperatures, **k** / **h** / **τ**, equilibrium **Teq**, hours to 20°C, forecast at 23:00, price rank, and `pre25=true/false`.

### `input_text.sam_hvac_reason`
- **Set by:** `DaytimeCheapHeat.yaml` only
- **Purpose:** Short plan reason — why `sam_desired_temperature` / `sam_control_temperature` are set (e.g. `Pre-warm before evening`, `Electricity expensive`, `You set 23°C (45m)`).

### `input_text.sam_hvac_headline`
- **Set by:** `DaytimeCheapHeat.yaml` (reason alone until Sam runs), then `sam.yaml` (reason · action, e.g. `Pre-warm before evening · Heating`).
- **Purpose:** One-line summary for the MiniDisplay screensaver and dashboards.

### `input_text.sam_hvac_status`
- **Set by:** `sam.yaml` each evaluation
- **Format:** `{{ headline }} | Heating: mode=…` plus full sensor detail.

`sam.yaml` also updates `input_text.sam_hvac_status` each time it evaluates, including:

- effective desired temperature (base + bedroom target)
- which remote temperature is used (and its source)
- fan state
- indoor/outdoor/internal readings

## Quick test (Home Assistant)

Use **Developer Tools → Template** and paste this to verify the effective desired, heating remote selection, dynamic heat boost, and living-room overheat guard:

```jinja2
{# Inputs (edit these) #}
{% set sam_control = 25 %}
{% set bedroom_target = 18 %}
{% set living = 17.5 %}
{% set bedroom = 16.9 %}
{% set fan_running = true %}
{% set internal = 16.0 %}
{% set heat_offset = 1 %}
{% set base_stop_heat_offset = -2 %}
{% set max_stop_heat_offset = -5 %}
{% set temp_tolerance = 0.5 %}

{% set desired_effective = [sam_control, bedroom_target] | max %}

{% if fan_running %}
  {% set remote_heat = [living, bedroom] | min %}
{% else %}
  {% set remote_heat = living %}
{% endif %}

{% set living_above_all_targets = living > desired_effective %}
{% set living_overheat_diff = living - desired_effective %}
{% set diff = remote_heat - desired_effective %}
{% set need = desired_effective - remote_heat %}
{% set boost = [heat_offset, need] | max %}
{% if living_above_all_targets %}
  {% set unclamped = internal + [base_stop_heat_offset - living_overheat_diff, max_stop_heat_offset] | max %}
{% elif remote_heat < desired_effective - temp_tolerance %}
  {% set unclamped = internal + boost %}
{% elif remote_heat >= desired_effective %}
  {% set unclamped = internal + [base_stop_heat_offset - diff, max_stop_heat_offset] | max %}
{% else %}
  {% set unclamped = internal %}
{% endif %}
{% set sam_setpoint = unclamped %}
{% set hvac_mode = 'fan_only' if living_above_all_targets else 'heat' %}

desired_effective={{ desired_effective }}
remote_heat={{ remote_heat }}
living_above_all_targets={{ living_above_all_targets }}
need={{ need }}
boost={{ boost }}
hvac_mode={{ hvac_mode }}
sam_setpoint={{ sam_setpoint }}
```
