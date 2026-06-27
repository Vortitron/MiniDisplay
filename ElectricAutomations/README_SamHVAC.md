# Sam HVAC (Living Room) – Two-Number Temperature Control

`sam.yaml` controls the living-room heat pump (`climate.sam`) using a "fooling" approach: it adjusts Sam's target relative to Sam's internal sensor so that Sam effectively turns heat on/off based on a remote temperature.

`DaytimeCheapHeat.yaml` manages electricity price optimisation by setting two temperature numbers that feed into `sam.yaml`.

> **Fixed-price feed:** when `input_boolean.on_fixed_price_feed` is on, all
> 15-min spot-price behaviour is suppressed — no cheap-hour boost, no
> expensive-hour cut and no price-driven pre-cool. Normal occupancy/comfort
> heating and cooling are unaffected. See `README_FixedPriceSwap.md`.

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
| **Hot day ahead** (`forecast_today_max` > 25°C) + morning (< 12:00) + not really cold | **No cheap-power boost** — the two "cheap now" rows below are disabled, so control = **desired** |
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

### Summer: skip morning heating on a hot day

If the day is forecast to be warm there's no point heating (or cheap-boosting) the house in the morning — it'll warm up by itself. When **`sensor.forecast_today_max` > 25 °C** and it's **before 12:00**, `DaytimeCheapHeat.yaml` disables the cheap-power morning boost (`cheap_for_boost` is forced false), so `control` falls through to `desired` (16 °C) and Sam doesn't actively heat.

Exception — **"unless really cold"**: if the living room is below 16 °C, or it's below 5 °C outside, the morning warm-up is still allowed. Tunables in `DaytimeCheapHeat.yaml`: `hot_day_max_threshold` (25), `morning_end_hour` (12), `really_cold_living` (16), `really_cold_outside` (5). The reason helper shows **"Hot day — no morning heat"** when this is active. Regression test: `tests/test_daytime_cheap_heat_templates.py::test_hot_day_morning_skip`.

### Holiday mode

When `input_boolean.holiday_mode` is on:
- `DaytimeCheapHeat.yaml` sets desired and control both to **10°C** (frost protection)
- All price optimisation logic is bypassed
- `sam.yaml` activates the `heat_8_15` preset on `climate.sam`, which unlocks the unit's low-temperature range (`min_temp` is otherwise 16°C, so the HVAC refuses any setpoint below that without this preset)
- Sam is set to `heat` mode at 10°C

When holiday mode is turned **off**, `sam.yaml` automatically clears the preset back to `none` on its next evaluation, restoring normal operation.

### Super-expensive mode

When `input_boolean.super_expensive_active` is on (set by `SuperExpensive.yaml`
once the base electricity price exceeds the threshold), `sam.yaml` turns
`climate.sam` **off** — but **only when it is just idling**, i.e. the living room
is above `super_expensive_off_above` (19 °C). At/below 19 °C (or if the
temperature is unknown) Sam keeps running, because it may be actively heating.
Holiday mode still wins over super-expensive. See **README_SuperExpensive.md**.

### How sam.yaml uses these numbers

`sam.yaml` reads `input_number.sam_control_temperature` as its `desired_base`, and the **effective target** is simply that:

```
desired_effective = sam_control_temperature
```

(The old `max(sam_control_temperature, bedroom_thermostat_target)` blend was retired in summer 2026 when the bedroom heater + thermostat were removed.)

## Remote temperature used for control

Sam uses different "remote" temperatures for cooling vs heating:

- **Cooling logic** uses the living-room sensor only:
  - `sensor.t_h_sensor_temperature`

- **Heating logic** uses:
  - **Fan OFF** → living-room sensor (`sensor.t_h_sensor_temperature`)
  - **Fan ON** → `min(sensor.bedroomlights_bedroomlights_temperature, sensor.t_h_sensor_temperature)`

The "min" rule encourages Sam to keep heating until the bedroom catches up whenever the circulation fan is actively pushing warm air, unless the living-room overheat guard is triggered.

## Cooling behaviour (summer)

Sam is primarily a heating optimiser; cooling is deliberately conservative so the compressor never runs on a merely warm day.

| Situation | What Sam does |
|---|---|
| Living **< 25 °C**, or it's **< 22 °C** outside | No active cooling — the heating branch idles it in `fan_only` |
| Living **≥ 25 °C** and **≥ 22 °C** outside, but not 27/27 | **Fan only** — circulate air, no compressor |
| Living **≥ 27 °C** *and* outside **≥ 27 °C** | **Compressor `cool`** (setpoint ≈ internal − 1 °C) |
| **Scorcher override**: outside **> 30 °C** *and* **either** room (living *or* bedroom) **> 27 °C** *and* **power cheap** | **Compressor `cool`** outright — no trend / cheaper-later guessing. Falls back to **fan only** when power is expensive |
| **Power cheap now** + hot day (`forecast_today_max` ≥ 27 °C) + not about to cool outside + room > 23 °C | **Pre-cool** — run the compressor early down to ~23 °C, before the expensive afternoon peak |
| Forecast to get **cooler outside** (next-4h avg ≥ 1 °C below the baseline) | Pre-cool suppressed; Sam coasts on the fan. Baseline is capped at `forecast_today_max` so a **sun-baked outdoor sensor can't fake a cooling trend** |
| **Sam is cooling** (compressor *or* fan-only) | **Circulation fan ON** — the Tuya plug `switch.smart_plug_5_socket_1` is switched on to spread the cool air; switched off when cooling stops in warm weather |

**"Power cheap now"** (for pre-cool) = `input_boolean.cheap_leccy` on (price ≤ 50 % of the daily average — catches a cheap morning even when it's cheaper still later) **or** the current price rank is below the 4-hour-ahead rank. Suppressed on the fixed-price feed.

Constants in `sam.yaml`: `cool_compressor_in`/`cool_compressor_out` (27/27), `cool_fan_target` (25), `cool_outdoor_gate` (22), `cool_precool_day_max` (27), `cool_precool_floor` (23), `cool_trend_margin` (1.0), `cool_hot_outdoor` (30), `cool_hot_room` (27). Inputs: `input_boolean.cheap_leccy` / `input_number.electricity_price_rank` vs `…_4h` (cheap-now), `sensor.forecast_today_max` (hot day **and** the cooling-trend baseline cap), `input_number.forecast_outside_4h` (cooling trend), living + bedroom temperature sensors (scorcher override).

The circulation fan is a Tuya smart plug fed by the `climate.circulation_fan` generic_thermostat. Sam drives the underlying `switch.smart_plug_5_socket_1` directly (the thermostat stays `off`) — verified ~45 W, so it is a fan, not a heater. It is only managed while it's warm out (`outdoor ≥ cool_outdoor_gate`); in winter it's left alone.

Outside the scorcher override the compressor needs **27 °C outside** and pre-cool excludes a cooling trend, so "it's getting cooler outside anyway" never starts the compressor — Sam just runs the fan. The scorcher override deliberately bypasses the trend (it requires > 30 °C out, so it can't be "cooling"), but still demands cheap power.

### Jun 2026 — cooling was running far too eagerly (and the fix)

The old rule cooled whenever `living > 26 °C` **or** (`outdoor ≥ 25 °C` **and** `living > 20 °C`). With the fan idling the room at ~20 °C while it was 25 °C outside, the second clause was permanently true, so Sam sat in **compressor `cool`** (made worse by a stray `powerful` preset) actively chilling a 20 °C living room. Rewritten so the compressor only runs at a genuine **27 °C inside *and* 27 °C outside**, fan-only below that, plus the cheap-power pre-cool and "don't cool if it's cooling outside anyway" smarts above. Regression tests: `tests/test_sam_hvac_templates.py` (9 cooling scenarios). If a stray `powerful`/`quiet` preset is ever left on `climate.sam`, clear it to `none` — `sam.yaml` does not manage comfort presets (only `heat_8_15` for holiday frost).

### Jun 2026 (hot-day update) — pre-cool fires on a cheap morning + circulation fan

On a rare 34 °C day the room was only ~24 °C during the cheap morning, so the
rank-vs-4h "cheap now" test said "wait" (it was cheaper still later) and the
compressor never started. **"Cheap now" for pre-cool now also accepts
`input_boolean.cheap_leccy`** (price ≤ 50 % of the daily average), so a cheap
morning pre-cools ahead of the hot afternoon. Sam also now switches the
**circulation fan** (`switch.smart_plug_5_socket_1`) on whenever it is cooling
and off when cooling stops in warm weather; `SuperExpensive.yaml` sheds the same
switch. Regression: `tests/test_sam_hvac_templates.py` (`today_hot_day_precool_live`
+ the `cheap_now` derivation cases).

### Jun 2026 (scorcher override + sun-baked sensor trend fix)

On a 38 °C-sensor afternoon Sam dropped out of `cool` after under a minute. Two
problems:

1. **False cooling trend.** The outdoor *sensor* read 38 °C (sun-baked) while the
   *forecast* was a flat 32–33 °C all afternoon. The trend test compared the
   sensor against the forecast (`32.5 < 38 − 1`), so it wrongly concluded "it's
   cooling" and suppressed pre-cool. Fix: the trend baseline is now
   `min(outdoor, forecast_today_max)` — capping at the day's forecast max stops a
   sun-baked reading inventing a downward trend. With the cap the trend is
   correctly `False` (`32.5 < 33 − 1` is false).
2. **No reliable "just cool" rule.** Added the **scorcher override** — when it's
   **> 30 °C outside** *and* **either** the living room **or bedroom is > 27 °C**
   *and* power is **cheap**, run the compressor outright (bypassing the trend /
   cheaper-later logic). When power is expensive it falls back to fan-only, matching
   "by the time it's expensive it'll be cooling outside, so just fan is fine".
   `super_expensive` still idles Sam off normally if the living room is warm enough.

New constants `cool_hot_outdoor` (30) and `cool_hot_room` (27). The cooling status
line now also reports `hot_cheap`, the trend `base` and the bedroom temperature.
Regression: `tests/test_sam_hvac_templates.py` (`scorcher_bedroom_hot_live`,
`scorcher_but_expensive_fan`, `sunbaked_sensor_still_precools`).

## Overheat guard (living room cap)

To prevent unnecessary overheating in the living room, `sam.yaml` enforces:

- if `sensor.t_h_sensor_temperature > desired_effective`, Sam does not actively heat
- practical behaviour: heating mode switches to `fan_only`, and the computed setpoint is nudged down

This still allows strategic overheating (e.g. the evening pre-warm) up to `input_number.sam_control_temperature`; above that the living-room overheat guard pulls the setpoint down.

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

- `media_player.lgnano_55` / `media_player.telia_tv` state change (either TV playing → comfort)
- `input_number.electricity_price_rank` change
- `input_number.electricity_price_rank_4h` change
- `input_boolean.daytime_cheap_7_21` change
- `input_number.sam_desired_temperature` change (manual override)
- `input_boolean.holiday_mode` change
- `sensor.forecast_tonight_min` / `sensor.forecast_outside_at_23` change
- `sensor.t_h_sensor_temperature` change (debounced 30 s)
- Every 15 minutes (time pattern safety net)
- 19:00 / 19:05 / 23:00 (evening boundary times)

Thermal-model outputs (`house_heat_loss_k`, `house_heat_rate`,
`forecast_outside_4h`, `hours_to_evening_target`) are **deliberately not**
state triggers — they update every 10 minutes and caused a trigger storm
(the automation fired several times per 10 minutes). The /15 time pattern
picks up fresh model values often enough.

### Jun 2026 template bug fixes (DaytimeCheapHeat)

Three template bugs meant **every run before 19:00 died at the variables
step** (and with the living room below 19°C, evening runs died too). The
visible symptom: `desired`/`control`/`sam_hvac_reason` frozen at stale
values (e.g. control stuck at 16°C all morning while the user wanted ~20°C).

1. `hours_until_19` used `(19 - hour) | max(0)` — on this HA the `min`/`max`
   filters accept a **list only**, so the varargs form raises
   `TypeError: 'int' object is not iterable`. Fixed to `[19 - hour, 0] | max`.
2. `prewarm_control_target` used `[a, b, c] | min | max` — the trailing
   `| max` on a scalar raises the same TypeError whenever living < 19.
   Fixed to `[[needed, prewarm_max] | min, evening_comfort_target] | max`.
3. The `control` and `reason` templates referenced `use_prewarm_evening`,
   but the variable is `use_prewarm_25_evening`. Undefined names are silently
   falsy, so the variable pre-warm branch was dead code.

Regression tests: `tests/test_daytime_cheap_heat_templates.py` (mirrors the
live HA list-only `min`/`max` filter semantics).

### Legacy Sam automations (UI-created, pre-date the two-number system)

- **Sam TV Comfort** (`automation.sam_tv_comfort`) — TV on → writes 19.9°C
  to `sam_desired_temperature`, which the lock system treats as a manual
  override (90-min lock at 19.9, price logic bypassed). Left **enabled**
  because `media_player.lgnano_55` is often `unavailable`. As of Jun 2026
  DaytimeCheapHeat's `tv_on` also covers both `media_player.lgnano_55` and
  `media_player.telia_tv` (either playing ⇒ desired 20°C via the normal
  price-aware path), so this legacy automation can be disabled once the TV
  signals prove reliable.
- **Sam TV Off** (`automation.sam_tv_off`) — **disabled Jun 2026**: TV off →
  forced desired to 16.5°C with a fake 90-min manual lock, even during the
  19:00–23:00 evening-comfort window, directly fighting DaytimeCheapHeat.
- **Sam over average El** (`automation.sam_over_average_el`) — **disabled
  Jun 2026**: duplicated the expensive-electricity reduction that
  DaytimeCheapHeat already does (control → 16), again via fake manual locks.

## Dependencies

### DaytimeCheapHeat.yaml
- `media_player.lgnano_55` and `media_player.telia_tv` (TVs — occupancy/comfort signal; either playing ⇒ desired 20°C)
- `sensor.sam_outside_temperature`
- `sensor.t_h_sensor_temperature` (living room — pre-warm cap)
- `input_number.electricity_price_rank`
- `input_number.electricity_price_rank_4h`
- `sensor.forecast_today_max` (hot-day morning heat skip)
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
- `input_boolean.super_expensive_active` (super-expensive guard — Sam off above the price threshold)
- `sensor.t_h_sensor_temperature` (living room)
- `sensor.bedroomlights_bedroomlights_temperature` (bedroom)
- `climate.circulation_fan` (on/off state, read) and `switch.smart_plug_5_socket_1` (the fan's Tuya plug — driven on/off during cooling)
- `input_boolean.cheap_leccy` and `input_number.electricity_price_rank` / `…_4h` (smart cooling: cheap-now pre-cool)
- `input_boolean.on_fixed_price_feed` (suppresses price-driven pre-cool)
- `sensor.forecast_today_max` (smart cooling: hot-day pre-cool)
- `input_number.forecast_outside_4h` (smart cooling: "cooler outside soon" trend)

> **Bedroom thermostat retired (summer 2026).** `climate.mama_bedroom_thermostat`
> was removed when the bedroom heater was taken out for the summer and its smart
> socket repurposed. `sam.yaml` no longer references it — `desired_effective` is
> now simply the price-adjusted control temperature (the old
> `max(control, bedroom_target)` blend is gone). The dependent automations are
> turned **off**: `BedroomHeatingAutomation.yaml` (`Mama Bedroom Smart Heating`)
> and both `CirculationFan.yaml` automations (which compared room temps against
> the bedroom thermostat target). The circulation fan device itself still runs
> on its own built-in thermostat. If the bedroom heater returns, re-add a
> `climate` target and re-enable those automations.

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
- **Format:** pure diagnostic detail, e.g. `Heating: mode=… control=… effective=… need=… boost=… setpoint=… remote=… living=… bedroom=… guard=… fan=… outdoor=… internal=…` (the short reason·action summary lives in `sam_hvac_headline`, so it is no longer duplicated here).
- **Length cap:** the value is `truncate`d to **255 chars** before writing. The `input_text` helper has `max: 255`; the old status string rendered ~291 chars, so `input_text.set_value` was silently **rejected every run** and the helper stuck at `Initializing...`. The truncate guard means the write can never be rejected again, regardless of future content.

`sam.yaml` also updates `input_text.sam_hvac_status` each time it evaluates, including:

- effective desired temperature (base + bedroom target)
- which remote temperature is used (and its source)
- fan state
- indoor/outdoor/internal readings

### Single source of truth for the heat/cool maths

The heating/cooling **mode** and **setpoint** maths are computed once in the
automation `variables:` block (`cool_active`, `cool_room_warm`, `cool_fan_only`,
`cool_mode`, `cool_setpoint`, `heat_diff`, `heat_need`, `heat_boost`,
`heat_fan_only`, `heat_mode`, `heat_setpoint`, `heat_action_label`) and then
referenced by every action (set_hvac_mode, set_temperature, logbook, headline,
status). Previously the same expressions were copied up to four times and had to
be kept in sync by hand. `ElectricAutomations/tests/test_sam_hvac_templates.py`
pins the maths down and proves the extracted variables are behaviour-identical to
the original inline copies (run with `python3 ElectricAutomations/tests/test_sam_hvac_templates.py`).

> **Subtle point preserved by the tests:** the cool **mode** uses
> `room warm AND outdoor cooler than target`, but the cool **setpoint** `-1°C`
> nudge uses only `room warm`. These are deliberately different conditions
> (`cool_fan_only` vs `cool_room_warm`).

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
