# Sam HVAC (Living Room) – Bedroom Support

`sam.yaml` controls the living-room heat pump (`climate.sam`) using a “fooling” approach: it adjusts Sam’s target relative to Sam’s internal sensor so that Sam effectively turns heat on/off based on a remote temperature.

This document explains how Sam now supports the bedroom by working together with `CirculationFan.yaml` and the bedroom thermostat schedule.

## Key idea

- **Effective desired temperature** for Sam is now:
  - `max(input_number.sam_desired_temperature, climate.mama_bedroom_thermostat.temperature)`

Meaning: if the bedroom is asking for more heat than the living room, Sam can overheat the living room above its own desired temperature to help the bedroom.

Guard: once the living room is already above the **effective desired** temperature (the max target), Sam stops active heating (`fan_only`), so the living room is not overheated above **both** desired targets.

## Remote temperature used for control

Sam uses different “remote” temperatures for cooling vs heating:

- **Cooling logic** uses the living-room sensor only:
  - `sensor.t_h_sensor_temperature`

- **Heating logic** uses:
  - **Fan OFF** → living-room sensor (`sensor.t_h_sensor_temperature`)
  - **Fan ON** → `min(sensor.bedroomlights_bedroomlights_temperature, sensor.t_h_sensor_temperature)`

The “min” rule encourages Sam to keep heating until the bedroom catches up whenever the circulation fan is actively pushing warm air, unless the living-room overheat guard is triggered.

## Overheat guard (living room cap)

To prevent unnecessary overheating in the living room, `sam.yaml` enforces:

- if `sensor.t_h_sensor_temperature > desired_effective`, Sam does not actively heat
- practical behaviour: heating mode switches to `fan_only`, and the computed setpoint is nudged down

This still allows strategic overheating to help the bedroom, but only up to the highest of:

- `input_number.sam_desired_temperature`
- `climate.mama_bedroom_thermostat.temperature`

## “Work harder when far off target” (dynamic heat boost)

Sam’s internal sensor can read a bit differently to the room sensors, and a fixed `+1°C` request isn’t enough when you’re **many degrees** below target.

When heating is needed (`remote_heat < desired_effective - temp_tolerance`), `sam.yaml` now sets Sam’s target to:

- `sam_setpoint ≈ internal + max(heat_offset, desired_effective - remote_heat)`

So if the remote temperature is **6°C** below desired, Sam’s target will be set to roughly **internal + 6°C**, which encourages the heat pump to ramp harder.

The final setpoint is clamped to Sam’s `min_temp` / `max_temp` attributes (or fallbacks if the integration doesn’t expose them).

## Dependencies

- `climate.sam`
- `sensor.sam_inside_temperature`
- `sensor.sam_outside_temperature`
- `input_number.sam_desired_temperature`
- `sensor.t_h_sensor_temperature` (living room)
- `sensor.bedroomlights_bedroomlights_temperature` (bedroom)
- `climate.mama_bedroom_thermostat` (target temperature attribute)
- `climate.circulation_fan` (on/off state)

## Logging

`sam.yaml` writes a `logbook.log` entry (“Sam HVAC …”) and updates `input_text.sam_hvac_status` each time it evaluates, including:

- effective desired temperature (base + bedroom target)
- which remote temperature is used (and its source)
- fan state
- indoor/outdoor/internal readings

## Quick test (Home Assistant)

Use **Developer Tools → Template** and paste this to verify the effective desired, heating remote selection, dynamic heat boost, and living-room overheat guard:

```jinja2
{# Inputs (edit these) #}
{% set sam_desired = 16 %}
{% set bedroom_target = 18 %}
{% set living = 17.5 %}
{% set bedroom = 16.9 %}
{% set fan_running = true %}
{% set internal = 16.0 %}
{% set heat_offset = 1 %}
{% set base_stop_heat_offset = -2 %}
{% set max_stop_heat_offset = -5 %}
{% set temp_tolerance = 0.5 %}

{% set desired_effective = [sam_desired, bedroom_target] | max %}

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

