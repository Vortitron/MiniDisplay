# Mama Bedroom Smart Heating Automation

Home Assistant automation for `climate.mama_bedroom_thermostat` that balances comfort, occupancy, and electricity costs.

## Temperature Schedule

### Night Period (22:00–04:00)
- **Base**: 16°C
- Maintains comfortable sleeping temperature regardless of electricity price

### Morning Preheat (04:00–09:00)
- **Base**: 22°C (rank 0, cheapest electricity)
- Drops with electricity price rank:
  - Rank 0: 22°C
  - Rank 1: 21°C
  - Rank 2: 20°C
  - Rank 3: 19°C
  - Rank 4+: 18°C
- Takes advantage of cheap overnight electricity to warm the room before waking

### Daytime (09:00–22:00)
- **Empty room**: 14°C (energy saving)
- **Occupied** (media player on): Minimum 17°C, boosted if electricity is cheap:
  - Rank 0: 20°C
  - Rank 1: 19°C
  - Rank 2: 18°C
  - Rank 3+: 17°C

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

Adjust temperature targets in the `target_temp` template if the room needs different comfort levels. The current logic prioritises:
1. Comfortable sleeping temperature at night (16°C)
2. Cheap electricity utilisation for morning warmth (04:00–09:00)
3. Energy savings when unoccupied during the day (14°C)
4. Occupancy comfort boost when media player is active (17–20°C)

