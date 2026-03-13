# Mama Bedroom Smart Heating Automation

Home Assistant automation for `climate.mama_bedroom_thermostat` that balances comfort, occupancy, and electricity costs.

## Temperature Schedule

### Night Period (22:00–04:00)
- **Base**: 15°C
- Maintains comfortable sleeping temperature regardless of electricity price

### Morning Preheat (04:00–09:00)
- **Base**: 21°C (rank 0, cheapest electricity)
- Drops with electricity price rank:
  - Rank 0: 21°C
  - Rank 1: 20°C
  - Rank 2: 19°C
  - Rank 3: 18°C
  - Rank 4+: 17°C
- Takes advantage of cheap overnight electricity to warm the room before waking

### Daytime (09:00–22:00)
- **Empty room**: 13°C (energy saving)
- **Occupied** (media player on): Minimum 16°C, boosted if electricity is cheap:
  - Rank 0: 19°C
  - Rank 1: 18°C
  - Rank 2: 17°C
  - Rank 3+: 16°C

## Occupancy Detection

Uses `media_player.ceol_piccolo` state to detect room occupancy:
- States `playing`, `on`, or `idle` indicate someone is present
- Automatically boosts temperature when media player is active during daytime hours

## Triggers

- **Electricity price rank changes** → Recalculate target temperature
- **Media player state changes** → Adjust for occupancy
- **04:00** → Start morning preheat window
- **09:00** → Switch to daytime schedule
- **22:00** → Begin night period
- **Home Assistant restart** → Re-establish automation

## Dependencies

- `input_number.electricity_price_rank` (0–4, where 0 is cheapest)
- `media_player.ceol_piccolo`
- `climate.mama_bedroom_thermostat`

## Installation

1. Copy `BedroomHeatingAutomation.yaml` to your Home Assistant automations directory
2. Reload automations or restart Home Assistant
3. Verify the automation appears in **Settings → Automations & Scenes**

## Tuning

Adjust temperature targets in the `target_temp` template if the room needs different comfort levels. The current logic applies a global `comfort_offset_c` (currently **-1°C**) and prioritises:
1. Comfortable sleeping temperature at night (15°C)
2. Cheap electricity utilisation for morning warmth (04:00–09:00)
3. Energy savings when unoccupied during the day (13°C)
4. Occupancy comfort boost when media player is active (16–19°C)

Additional controls in the automation:

- **`set_temp_epsilon_c`**: prevents re-sending the same setpoint (some thermostats can “twitch” if they receive repeats).
- **`min_target_c`**: clamps the minimum setpoint in case the schedule is edited later.

## Quick testing (Home Assistant)

Use **Developer Tools → Template** and paste this to validate the schedule logic for a few scenarios:

```jinja2
{# Inputs (edit these) #}
{% set hour = 6 %}
{% set rank = 0 %}
{% set media_on = false %}

{# Tuning (should match BedroomHeatingAutomation.yaml) #}
{% set comfort_offset_c = -1 %}
{% set min_target_c = 13 %}

{% set ns = namespace(base=14) %}

{% if hour >= 22 or hour < 4 %}
  {% set ns.base = 16 %}
{% elif hour >= 4 and hour < 9 %}
  {% if rank == 0 %}
    {% set ns.base = 22 %}
  {% elif rank == 1 %}
    {% set ns.base = 21 %}
  {% elif rank == 2 %}
    {% set ns.base = 20 %}
  {% elif rank == 3 %}
    {% set ns.base = 19 %}
  {% else %}
    {% set ns.base = 18 %}
  {% endif %}
{% else %}
  {% if media_on %}
    {% if rank == 0 %}
      {% set ns.base = 20 %}
    {% elif rank == 1 %}
      {% set ns.base = 19 %}
    {% elif rank == 2 %}
      {% set ns.base = 18 %}
    {% else %}
      {% set ns.base = 17 %}
    {% endif %}
  {% else %}
    {% set ns.base = 14 %}
  {% endif %}
{% endif %}

{% set adjusted = ns.base + comfort_offset_c %}
target={{ [adjusted, min_target_c] | max | int }}
```

If you’re also using the circulation fan, see `README_CirculationFan.md`.

