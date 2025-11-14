# Front Path Lights Control

Controls your front porch and path lights based on:
- **Sunset schedule**: Turn on at 30% brightness at sunset
- **Midnight schedule**: Turn off at midnight
- **Position-based brightness**: Brighten as someone approaches the door, dim as they leave
- **Time-based minimum**: After sunset, lights never dim below 30%

## Requirements

- Entities:
  - `sensor.frontpath_path_person_position` (position in metres)
  - `binary_sensor.frontpath_path_person_detected` (person detected)
  - `sun.sun` (sun state - built into HA)
  - `light.front_porch` (your front porch light)
  - `light.zl_1w3h_aw` (your path light)

## Installation Options

### Option 1: Home Assistant Automations (Recommended)

This is the simplest and most reliable approach using native Home Assistant automations.

1. **Create the helper**:
   - Settings → Devices & Services → Helpers → Create Helper → Toggle
   - Name: `Front Path Evening Mode`
   - Entity ID: `frontpath_evening_mode`
   - Icon: `mdi:weather-sunset`
   - Or add to `configuration.yaml` (see `frontpath_helper.yaml`)

2. **Add the automations**:
   - Copy the contents of `frontpath_lights_automations.yaml`
   - Go to Settings → Automations & Scenes → Automations → Create Automation
   - Click the three dots (⋮) → Edit in YAML
   - Paste the automation YAML
   - Or add to your `automations.yaml` file and restart HA

3. **Verify**:
   - Check that automations are enabled
   - Test by walking the path and watching brightness adjust

### Option 2: Node-RED Setup

For users who prefer Node-RED (requires Node-RED add-on):

## Installation

1. **Import the flow**:
   - Open Node-RED (within Home Assistant)
   - Click the menu (☰) → Import
   - Copy and paste the contents of `frontpath_lights_flow.json`
   - Click "Import"

2. **Configure nodes** (if needed):
   - The flow uses Home Assistant's built-in Node-RED nodes:
     - `sun` node for sunset trigger
     - `server-state` nodes for entity monitoring
     - `api-call-service` nodes for controlling lights
   - Most nodes should work automatically, but verify:
     - Check entity IDs match your setup (path position, person detected, lights)
     - The midnight trigger uses a cron schedule (`0 0 * * *`)

3. **Verify entity names**:
   - Check that all entity IDs match your setup:
     - `sensor.frontpath_path_person_position` - Path position sensor
     - `binary_sensor.frontpath_path_person_detected` - Person detected
     - `sun.sun` - Sun state (should exist by default)
     - `light.front_porch` - Your front porch light
     - `light.zl_1w3h_aw` - Your path light

4. **Deploy**:
   - Click the "Deploy" button (top right)
   - The flow should start working immediately
   - Check the debug panel to see position updates

## How It Works

### Schedule-Based Control
- **Sunset**: Lights turn on at 30% brightness automatically
- **Midnight**: Lights turn off automatically

### Position-Based Brightness
When someone is detected on the path:
- **Position 0-8m** (far end): Brightness 30-60%
  - 0m = 30%
  - 8m = 60%
- **Position 8-16m** (near door): Brightness 60-100%
  - 8m = 60%
  - 16m = 100%

### Time-Based Minimums
- **After sunset**: Lights never dim below 30% (even when no one is detected)
- **Before sunset**: Lights turn off (dim to 0%) when no one is detected

### Smooth Transitions
- All brightness changes use a 2-second transition for smooth dimming
- When person leaves, waits 5 seconds before dimming back to baseline

## Customisation

### Adjust Brightness Range
Edit the "Calculate Brightness" function node:
- Change the position-to-brightness mapping
- Adjust minimum brightness (currently 30%)
- Modify the transition time (currently 2 seconds)

### Adjust Delay After Person Leaves
Edit the "Delay 5s" node:
- Change timeout to your preferred delay (currently 5 seconds)

### Change Sunset/Midnight Times
- Edit the "Sunset" node to add an offset (e.g., 30 minutes before sunset)
- Edit the "Midnight" node to change the turn-off time

## Troubleshooting

**Lights not turning on at sunset:**
- Check that `sun.sun` entity exists and is working
- Verify the "Sunset" trigger node is enabled

**Position not affecting brightness:**
- Check that `sensor.frontpath_path_person_position` is updating
- Look at the Node-RED debug panel for position values
- Verify the position sensor is returning numeric values in metres

**Lights dimming to zero after sunset:**
- Check the "Calculate Brightness" function logic
- Verify `sun.sun` state is correctly detected as "below_horizon"

**Both lights not responding:**
- Verify both light entity IDs are correct
- Check that the lights support brightness control
- Test manually: `light.turn_on` with `brightness_pct` in Home Assistant

## Alternative: Home Assistant Automation

If you prefer HA automations over Node-RED, you can create a similar automation. The logic would be:

```yaml
automation:
  - alias: "Front Path Lights Sunset"
    trigger:
      - platform: sun
        event: sunset
    action:
      - service: light.turn_on
        target:
          entity_id:
            - light.front_porch
            - light.zl_1w3h_aw
        data:
          brightness_pct: 30
  
  - alias: "Front Path Lights Midnight"
    trigger:
      - platform: time
        at: "00:00:00"
    action:
      - service: light.turn_off
        target:
          entity_id:
            - light.front_porch
            - light.zl_1w3h_aw
  
  - alias: "Front Path Lights Position Control"
    trigger:
      - platform: state
        entity_id: sensor.frontpath_path_person_position
    condition:
      - condition: sun
        after: sunset
        before: "00:00:00"
    action:
      - service: light.turn_on
        target:
          entity_id:
            - light.front_porch
            - light.zl_1w3h_aw
        data:
          brightness_pct: >
            {% set pos = states('sensor.frontpath_path_person_position') | float(0) %}
            {% if pos == 0 or pos is none %}
              {% if now().hour >= 18 %} 30 {% else %} 0 {% endif %}
            {% elif pos <= 8 %}
              {{ (30 + (pos / 8) * 30) | round }}
            {% else %}
              {{ (60 + ((pos - 8) / 8) * 40) | round }}
            {% endif %}
          transition: 2
```

However, Node-RED is generally easier to visualise and debug for this type of logic!

