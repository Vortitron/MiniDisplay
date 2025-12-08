# Setting Up BLE + Adaptive Lighting Automation

## Quick Start

This guide shows you how to install the new adaptive + seasonal lighting automation that uses BLE sensors.

## Prerequisites

✅ FrontPath device running `FrontPath.yaml` (BLE proxy mode)  
✅ Both LD2410 sensors paired in Home Assistant  
✅ Sensors show as `sensor.hlk_ld2410_7144_*` and `sensor.hlk_ld2410_6602_*`  
✅ Light entities: `light.front_porch_local` and `light.fairy_lights`

## Installation Methods

### Method 1: As a Package (Recommended)

1. **Enable packages** in your `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

2. **Create packages directory**:
   - Go to your HA config directory (where `configuration.yaml` lives)
   - Create a folder called `packages` if it doesn't exist

3. **Copy the automation file**:
   - Copy `frontpath_lights_automations.yaml` to `config/packages/`
   - Rename it if you like (e.g., `frontpath_adaptive_lights.yaml`)

4. **Restart Home Assistant**:
   - Settings → System → Restart Home Assistant
   - Or Developer Tools → YAML → Restart Home Assistant

5. **Verify entities created**:
   - Settings → Devices & Services → Entities
   - Search for "frontpath" - you should see:
     - 5 input numbers (helpers)
     - 1 input boolean (Christmas mode)
     - 2 statistics sensors (baseline averages)
     - 1 position sensor
     - 1 person detected binary sensor
     - 1 automation

### Method 2: Split Into Separate Files

If you prefer to keep your config organized in separate files:

#### A. Add Helpers

Add to `configuration.yaml` or create `input_boolean.yaml` and `input_number.yaml`:

```yaml
# In configuration.yaml
input_boolean: !include input_boolean.yaml
input_number: !include input_number.yaml
```

Then copy the `input_boolean` and `input_number` sections from `frontpath_lights_automations.yaml`.

#### B. Add Statistics Sensors

Add to `configuration.yaml` or your existing `sensor:` section:

```yaml
sensor:
  - platform: statistics
    name: "FrontPath 7144 Motion Energy Avg"
    entity_id: sensor.hlk_ld2410_7144_motion_energy
    state_characteristic: mean
    sampling_size: 120
    max_age:
      minutes: 10
  - platform: statistics
    name: "FrontPath 6602 Motion Energy Avg"
    entity_id: sensor.hlk_ld2410_6602_motion_energy
    state_characteristic: mean
    sampling_size: 120
    max_age:
      minutes: 10
```

#### C. Add Template Sensors

Create or edit `templates.yaml`:

```yaml
# In configuration.yaml
template: !include templates.yaml
```

Then copy the entire `template:` section from `frontpath_lights_automations.yaml`.

#### D. Add Automation

Go to Settings → Automations & Scenes → Create Automation → Edit in YAML.

Paste the `automation:` section from `frontpath_lights_automations.yaml`.

## Configuration

### 1. Update Entity IDs (If Needed)

If your sensors have different names:

1. Check your sensor names:
   - Developer Tools → States
   - Search for `hlk_ld2410`
   - Note the MAC addresses in the entity IDs

2. Find and replace in `frontpath_lights_automations.yaml`:
   - Replace `7144` with your door-end sensor MAC suffix
   - Replace `6602` with your street-end sensor MAC suffix
   - Replace `light.front_porch_local` with your porch light entity
   - Replace `light.fairy_lights` with your path/fairy light entity

### 2. Set Initial Values

The automation includes sensible defaults, but you can adjust via the UI:

**Settings → Devices & Services → Helpers:**

- **Front Path Christmas Mode**: ON (toggle for seasonal patterns)
- **Front Path Path Length**: 16m (adjust to your actual path length)
- **Front Path Idle Brightness**: 12% (dim glow when no one present)
- **Front Path Energy Margin**: 22% (increase if too sensitive to weather)
- **Front Path Gate Trigger Floor**: 18% (minimum gate spike for detection)
- **Front Path Darkness Threshold**: 32% (light level % threshold)

### 3. Wait for Baseline to Stabilize

The statistics sensors need **5-10 minutes** of data before they work properly:

1. After restart, wait 10 minutes
2. Check Developer Tools → States:
   - `sensor.frontpath_7144_motion_energy_avg` should show a number (not "unknown")
   - `sensor.frontpath_6602_motion_energy_avg` should show a number

3. If still "unknown" after 10 minutes:
   - Check that base sensors exist and are updating:
     - `sensor.hlk_ld2410_7144_motion_energy`
     - `sensor.hlk_ld2410_6602_motion_energy`
   - Check Configuration → Logs for statistics errors

## Testing

### 1. Test Darkness Detection

```
Developer Tools → States → sensor.frontpath_light_level
```

- Should be <32% when dark (triggering lights)
- Should be >32% in daylight (lights off)

Or check:
```
Developer Tools → States → binary_sensor.frontpath_path_is_dark
```
- Should be ON when genuinely dark

### 2. Test Person Detection

Walk the path after dark:

1. Check `binary_sensor.frontpath_path_person_detected` turns ON
2. Check `sensor.frontpath_path_person_position` shows distance (0-16m)
3. Lights should brighten as you approach the door

### 3. Test Christmas Mode

1. Walk to different zones:
   - **Far end** (0-5m): Green "Evergreen Fade" effect
   - **Middle** (5-12m): Red "Candy Cane" effect  
   - **Door** (12-16m): Warm white "Sparkle" effect

2. Toggle Christmas mode OFF:
   - Should switch to warm white with no effects

### 4. Monitor Baseline Adaptation

Create a dashboard card to watch the adaptive baseline:

```yaml
type: entities
title: FrontPath Adaptive Monitoring
entities:
  - entity: sensor.hlk_ld2410_7144_motion_energy
    name: "Door Sensor Current"
  - entity: sensor.frontpath_7144_motion_energy_avg
    name: "Door Sensor Baseline (10min avg)"
  - entity: sensor.hlk_ld2410_6602_motion_energy
    name: "Street Sensor Current"
  - entity: sensor.frontpath_6602_motion_energy_avg
    name: "Street Sensor Baseline (10min avg)"
  - entity: binary_sensor.frontpath_path_person_detected
  - entity: sensor.frontpath_path_person_position
  - entity: input_number.frontpath_energy_margin
  - entity: input_number.frontpath_gate_trigger_floor
```

Watch this card while it's windy/rainy:
- Current energy will spike and vary
- Baseline will slowly rise over 5-10 minutes
- Detection should still work (current - baseline > margin)

## Troubleshooting

### Lights Don't Turn On

**Check darkness detection:**
```
Developer Tools → States → sensor.frontpath_light_level
```
Should be <32%. If higher, increase `frontpath_darkness_threshold_pct`.

**Check person detection:**
```
Developer Tools → States → binary_sensor.frontpath_path_person_detected
```
Should turn ON when you walk. If not, decrease `frontpath_energy_margin`.

**Check automation is active:**
```
Settings → Automations → Front Path - Adaptive + Seasonal Lighting
```
Should show "active" (not disabled or error state).

### False Triggers (Wind/Rain)

**Increase sensitivity thresholds:**
- `frontpath_energy_margin`: 22% → 30-40%
- `frontpath_gate_trigger_floor`: 18% → 25-35%

**Watch the baseline adapt:**
The statistics sensors should show the baseline rising over 5-10 minutes in bad weather.

### Lights Stay On Even When Bright Outside

**Check light sensor:**
```
Developer Tools → States → sensor.frontpath_light_level
```
Should be >32% in daylight. If stuck low, the TEMT6000 sensor may be covered or faulty.

**Manually test:**
```
Developer Tools → Developer Tools → Actions
Action: automation.trigger
Target: automation.front_path_adaptive_seasonal_lighting
```
Should turn lights off if it's bright.

### Position Not Updating

**Check gate sensors exist and update:**
```
Developer Tools → States → sensor.hlk_ld2410_7144_motion_energy_gate_0
```
(through gate_6)

Walk the path and watch which gates spike. If none spike, the sensors may not be paired or gates may be disabled.

**Enable gates in LD2410 config:**
Each sensor must have gates 0-6 enabled. Use the HLKRadarTool app or HA device page.

### Statistics Sensors Show "Unknown"

**Wait 10 minutes** after restart - they need data to calculate mean.

**Check base sensor exists:**
```
Developer Tools → States → sensor.hlk_ld2410_7144_motion_energy
```
Should show a number and update regularly.

**Check recorder is enabled** (statistics requires it):
```yaml
# In configuration.yaml
recorder:
```

### Christmas Effects Don't Work

Your `light.fairy_lights` entity must support:
- `effect` attribute (for pattern names)
- `rgb_color` attribute (for color control)

If your lights don't support effects, remove the `effect:` lines and keep just brightness + color.

## Customization

### Change Christmas Color Palette

Edit the automation's `rgb_color` values:

```yaml
rgb_color: >
  {% if zone == 'door' %}
    [255, 180, 120]  # Warm white - change to [255, 215, 0] for gold
  {% elif zone == 'mid' %}
    [255, 0, 0]      # Red - change to [255, 255, 255] for white
  {% else %}
    [0, 200, 90]     # Green - change to [0, 0, 255] for blue
  {% endif %}
```

### Change Effect Names

Replace effect names with ones your lights support:

```yaml
effect: >
  {% if zone == 'door' %}
    Sparkle      # Replace with your light's effect name
  {% elif zone == 'mid' %}
    Candy Cane
  {% else %}
    Evergreen Fade
  {% endif %}
```

Check Developer Tools → States → `light.fairy_lights` attributes to see available effects.

### Add More Zones

Edit the zone logic:

```yaml
zone: >
  {% if position == '' %}
    none
  {% else %}
    {% set pos = position | float(0) %}
    {% if pos < path_length * 0.25 %}
      far
    {% elif pos < path_length * 0.50 %}
      mid_far
    {% elif pos < path_length * 0.75 %}
      mid_near
    {% else %}
      door
    {% endif %}
  {% endif %}
```

Then add corresponding colors/effects for each new zone.

## Next Steps

1. ✅ Install automation using Method 1 or 2
2. ✅ Verify all entities created (helpers, sensors, automation)
3. ✅ Wait 10 minutes for statistics baseline to stabilize
4. ✅ Test during daytime (lights should stay off)
5. ✅ Test after dark with no one present (dim baseline glow)
6. ✅ Walk the path (brightness should ramp with position)
7. ✅ Toggle Christmas mode (effects should change by zone)
8. ✅ Monitor for 24 hours to verify baseline adapts to weather
9. ✅ Tune helpers based on false positive/negative rate

See `BLE_ADAPTIVE_BASELINE.md` for detailed tuning guidance and troubleshooting.

