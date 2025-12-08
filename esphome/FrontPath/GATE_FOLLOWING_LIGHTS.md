# Gate-Following Christmas Lights

## Overview

The fairy lights now **follow you as you walk**, with each gate (0-8) triggering a different color/effect combination. This creates a smooth "wave" of light that tracks your movement down the path.

## How It Works

### 1. Active Gate Detection

A new sensor `binary_sensor.frontpath_active_gate` continuously tracks which gate has the highest motion energy:

- Returns `door_0` through `door_8` for the door-end sensor (Sensor 1)
- Returns `street_0` through `street_8` for the street-end sensor (Sensor 2)
- Returns `none` when no gate is active

### 2. Gate-to-Color Mapping

Each gate maps to a specific color in Christmas mode:

**Door Sensor (walking towards door):**
- **Gate 7-8** (closest to door): Warm white `[255, 200, 150]` - "Sparkle" effect
- **Gate 5-6**: Golden `[255, 180, 100]` - "Twinkle" effect
- **Gate 3-4**: Red `[255, 100, 100]` - "Candy Cane" effect
- **Gate 0-2**: Deep red `[255, 50, 50]` - "Chase" effect

**Street Sensor (walking from street):**
- **Gate 6-8** (far end): Bright green `[0, 255, 150]` - "Fade" effect
- **Gate 4-5**: Green `[0, 200, 100]` - "Pulse" effect
- **Gate 2-3**: Light green `[50, 255, 100]` - "Wave" effect
- **Gate 0-1** (furthest): Yellow-green `[100, 200, 50]` - "Evergreen Fade" effect

### 3. Visual Effect

As you walk:
1. **Street → Door**: Colors shift from green → yellow-green → red → golden → warm white
2. **Door → Street**: Colors shift from warm white → golden → red → yellow-green → green
3. Each gate change updates in **0.8 seconds** (fast tracking)
4. Brightness increases as you approach the door (position-based)

## Porch Light Control

The porch light now requires **moving target confirmation**:

```yaml
{{ (delta1 >= margin or delta2 >= margin) or (gate_peak >= gate_floor and (moving1 or moving2)) }}
```

This means:
- ✅ **Large energy spike** above baseline triggers immediately
- ✅ **Gate spike + moving target flag** triggers with confirmation
- ❌ Gate spike without moving target flag = ignored (reduces false positives)

## Customization

### Change Gate Colors

Edit the `rgb_color` template in `frontpath_lights_automations.yaml`:

```yaml
rgb_color: >
  {% set gate = active_gate %}
  {% if gate.startswith('door_') %}
    {% set idx = gate.split('_')[1] | int %}
    {% if idx >= 7 %}
      [255, 200, 150]  # Change this for door gates 7-8
    {% elif idx >= 5 %}
      [255, 180, 100]  # Change this for door gates 5-6
    # ... etc
```

**Color format**: `[R, G, B]` where each value is 0-255

**Christmas color suggestions:**
- **Red**: `[255, 0, 0]`
- **Green**: `[0, 255, 0]`
- **Blue**: `[0, 0, 255]`
- **Gold**: `[255, 215, 0]`
- **White**: `[255, 255, 255]`
- **Purple**: `[128, 0, 128]`
- **Orange**: `[255, 165, 0]`

### Change Gate Effects

Edit the `effect` template:

```yaml
effect: >
  {% set gate = active_gate %}
  {% if gate.startswith('door_') %}
    {% set idx = gate.split('_')[1] | int %}
    {% if idx >= 7 %}
      Sparkle  # Change effect name here
```

**Available effects** (depends on your light):
- `Sparkle`, `Twinkle`, `Fade`, `Pulse`, `Wave`, `Chase`
- `Candy Cane`, `Evergreen Fade`, `Rainbow`, `Strobe`
- Check your light's entity attributes in Developer Tools → States

### Adjust Gate Zones

Change the gate groupings to create more or fewer zones:

```yaml
{% if idx >= 7 %}
  # Gates 7-8: Change to >= 6 to include gate 6
{% elif idx >= 5 %}
  # Gates 5-6: Change to >= 4 to include gate 4
```

### Disable Gate Following

If you prefer simpler zone-based lighting, change back to the original logic:

```yaml
effect: >
  {% if zone == 'door' %}
    Sparkle
  {% elif zone == 'mid' %}
    Candy Cane
  {% else %}
    Evergreen Fade
  {% endif %}
```

## Testing

### 1. Enable Christmas Mode

Settings → Devices & Services → Helpers → Toggle `Front Path Christmas Mode` ON

### 2. Check Active Gate Sensor

```
Developer Tools → States → binary_sensor.frontpath_active_gate
```

Should show `none` when calm, then `door_3`, `street_5`, etc. as you walk

### 3. Walk the Path

Walk slowly from street to door and watch:
- Colors shift from green → yellow → red → gold → white
- Effects change per gate
- Brightness increases as you approach door

### 4. Debug Gate Energies

Create a dashboard card to see all gates:

```yaml
type: entities
title: FrontPath Gate Energies
entities:
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_0
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_1
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_2
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_3
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_4
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_5
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_6
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_0
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_1
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_2
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_3
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_4
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_5
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_6
  - entity: binary_sensor.frontpath_active_gate
```

Walk the path and watch which gates spike (should be sequential as you move).

## Troubleshooting

### Colors Don't Change As I Walk

**Check active gate updates:**
```
Developer Tools → States → binary_sensor.frontpath_active_gate
```
Should change as you move (e.g., `street_2` → `street_4` → `door_5`)

**Check gate energies:**
Walk the path and verify individual gate sensors show spikes in Developer Tools.

**Check light supports effects:**
Your `light.fairy_lights` entity must support `effect` attribute. Check:
```
Developer Tools → States → light.fairy_lights
```
Look for `effect_list` in attributes.

### Lights Stay One Color

**Transition might be too fast:**
Edit `transition: 0.8` to `transition: 0.3` for instant updates, or `1.5` for smoother fades.

**Check Christmas mode is ON:**
Settings → Helpers → `Front Path Christmas Mode` should be ON.

### Wrong Gate Triggers

**Gate calibration needed:**
Use HLKRadarTool app to auto-calibrate each sensor. Some gates may be oversensitive.

**Adjust gate floor:**
Settings → Helpers → `Front Path Gate Trigger Floor`
- Increase to ignore weak gates
- Decrease for more sensitive gate tracking

### Porch Light Too Sensitive

**Increase energy margin:**
Settings → Helpers → `Front Path Energy Margin` → 30-40%

**The moving target flag now helps filter false positives.**

### Porch Light Not Triggering

**Check moving target sensors exist:**
```
Developer Tools → States → binary_sensor.hlk_ld2410_7144_has_moving_target
Developer Tools → States → binary_sensor.hlk_ld2410_6602_has_moving_target
```

If they don't exist, your LD2410 BLE entities may use different naming. Check Settings → Devices & Services → LD2410 BLE to find the correct entity IDs.

**Decrease gate floor temporarily:**
Settings → Helpers → `Front Path Gate Trigger Floor` → 12-15%

## Advanced: Addressable LED Support

If your fairy lights support **addressable LED control** (WLED, ESPHome addressable light, etc.), you can map individual gates to individual bulbs/segments:

```yaml
# Example for WLED
- service: light.turn_on
  target:
    entity_id: light.fairy_lights
  data:
    brightness_pct: 100
    segment_id: "{{ active_gate.split('_')[1] | int }}"
    rgb_color: [255, 0, 0]
```

This would light up only the segment corresponding to the active gate, creating a true "chasing" effect where a single bulb/section lights up as you walk.

## Gate Distance Reference

Each gate represents approximately **0.75 meters**:

| Gate | Distance from Sensor | Path Position |
|------|---------------------|---------------|
| 0 | 0-0.75m | Far end |
| 1 | 0.75-1.5m | |
| 2 | 1.5-2.25m | |
| 3 | 2.25-3m | |
| 4 | 3-3.75m | Middle |
| 5 | 3.75-4.5m | |
| 6 | 4.5-5.25m | |
| 7 | 5.25-6m | |
| 8 | 6-6.75m | Near end |

For a 16m path with sensors at each end:
- **Door sensor gate 8** = 0-0.75m from door
- **Street sensor gate 8** = 0-0.75m from street
- **Middle of path** = Gates 4-5 on both sensors

## Summary

✅ **Moving target flag** reduces false triggers on porch light  
✅ **Gate-specific colors** create smooth gradient as you walk  
✅ **Fast transitions** (0.8s) track your movement in real-time  
✅ **Customizable** - change colors, effects, and zones easily  
✅ **Works with BLE mode** - no firmware changes needed  

Enjoy your personalized Christmas light show that follows you down the path! 🎄✨

