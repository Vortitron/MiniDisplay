# Sam HVAC (Living Room) – Two-Number Temperature Control

`sam.yaml` controls the living-room heat pump (`climate.sam`) using a "fooling" approach: it adjusts Sam's target relative to Sam's internal sensor so that Sam effectively turns heat on/off based on a remote temperature.

`DaytimeCheapHeat.yaml` manages electricity price optimisation by setting two temperature numbers that feed into `sam.yaml`.

## Two-number architecture

### `input_number.sam_desired_temperature` — human comfort target

Set by `DaytimeCheapHeat.yaml` based on occupancy and time:

| Condition (evaluated in order) | Desired |
|---|---|
| **Holiday mode** on | **10°C** (frost protection) |
| Manual change (triggered by desired) | Preserved as-is |
| **Evening** (19:00–23:00) or **TV on** | **20°C** |
| Otherwise | **16°C** |

This number can be changed manually in the HA UI. Manual changes are preserved — the automation only overwrites it when a non-desired trigger fires.

### `input_number.sam_control_temperature` — price-adjusted target

Computed from the desired temperature and electricity price ranking:

| Condition (evaluated in order) | Control temp |
|---|---|
| Holiday mode | **10°C** |
| Cheap now + outside < 10°C | **25°C** (max overheat) |
| Cheap now + approaching evening (15:00–19:00) | **25°C** (pre-warm for evening) |
| Cheap now | **desired + 3°C** (capped at 25) |
| Expensive + TV off + not evening | **16°C** (coast) |
| Otherwise | **desired** |

"Cheap now" means the current hourly price rank (`input_number.electricity_price_rank`) is lower than the 4-hour window rank (`input_number.electricity_price_rank_4h`).

### Evening pre-warming strategy

The system ensures comfort during evening hours (19:00–23:00) without expensive peak-time heating:

1. **15:00–19:00** — if electricity is cheap, control is boosted to 25°C to build thermal mass
2. **19:00–23:00** — desired is 20°C regardless of TV state; control won't drop below desired even if electricity is expensive
3. **Result** — the home is warm by evening from pre-heating, and Sam only needs to maintain (not ramp) during peak hours

The `HouseThermalModel.yaml` automation continuously learns how fast the house cools/heats (see `README_HouseThermalModel.md`). Once converged, `DaytimeCheapHeat.yaml` can use `input_number.hours_to_evening_target` to data-drive the pre-warm start time instead of the fixed 15:00 window.

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

The final setpoint is clamped to Sam's `min_temp` / `max_temp` attributes (or fallbacks if the integration doesn't expose them).

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
- `input_number.electricity_price_rank`
- `input_number.electricity_price_rank_4h`
- `input_boolean.daytime_cheap_7_21`
- `input_boolean.holiday_mode`
- `input_number.sam_desired_temperature` (reads and writes)
- `input_number.sam_control_temperature` (writes)

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

## Logging

Both automations write `logbook.log` entries. `sam.yaml` also updates `input_text.sam_hvac_status` each time it evaluates, including:

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
