# Circulation Fan Automations

Home Assistant automations for `climate.circulation_fan`, used to push warm air into the bedroom **only when it’s actually beneficial** (the other room is warmer and the bedroom is below its target).

## What’s in `CirculationFan.yaml`

`CirculationFan.yaml` contains **two automations** separated by a YAML document marker (`---`). In Home Assistant, create/import them as **two separate automations**.

### 1) Temperature Sync

- Keeps the circulation fan’s target temperature at **`climate.mama_bedroom_thermostat` + 1°C**.
- Triggered whenever the bedroom thermostat target changes.

### 2) Temperature Control (early start)

- Turns the circulation fan **on earlier than before** to reduce bedroom heater cycling.
- Uses these entities:
  - Bedroom temperature: `sensor.bedroomlights_bedroomlights_temperature`
  - Other room temperature: `sensor.t_h_sensor_temperature`
  - Bedroom target temperature: `state_attr('climate.mama_bedroom_thermostat', 'temperature')`

#### Current thresholds (tune in the YAML)

- **Turn on** when:
  - Other room is warmer by at least **0.5°C**
  - AND bedroom is below its target by at least **0.1°C**
- **Turn off** when:
  - Other room is warmer by **0.2°C or less**
  - OR bedroom has reached its target (at/above)

The automation also triggers on bedroom target temperature changes so it reacts immediately at schedule boundaries (e.g. 04:00/09:00/22:00), not just when sensors next update.

#### Logging

When the fan is switched **on/off**, the automation writes a `logbook.log` entry (“Circulation Fan …”) including the temperature difference and how far below target the bedroom is.

## Using Sam HVAC to support the bedroom

If the living-room heat pump (`climate.sam`) should “follow” the bedroom demand when the fan is moving air, see `README_SamHVAC.md`.

## Quick testing (Home Assistant)

Use **Developer Tools → Template** and paste this to sanity-check the decision logic:

```jinja2
{# Inputs (edit these) #}
{% set bedroom_temp = 17.0 %}
{% set other_room_temp = 17.7 %}
{% set bedroom_target = 18.0 %}

{# Thresholds (should match CirculationFan.yaml) #}
{% set other_room_turn_on_diff_c = 0.5 %}
{% set other_room_turn_off_diff_c = 0.2 %}
{% set bedroom_below_target_on_c = 0.1 %}
{% set bedroom_below_target_off_c = 0.0 %}

{% set diff = other_room_temp - bedroom_temp %}
{% set below_target = bedroom_target - bedroom_temp %}

diff={{ diff | round(2) }}°C
below_target={{ below_target | round(2) }}°C

should_turn_on={{ diff >= other_room_turn_on_diff_c and below_target >= bedroom_below_target_on_c }}
should_turn_off={{ diff <= other_room_turn_off_diff_c or below_target <= bedroom_below_target_off_c }}
```

