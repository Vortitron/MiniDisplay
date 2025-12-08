# Tuya Custom Pattern Mode

## Overview

This mode creates an **8-bulb custom pattern** on Tuya-compatible string lights that responds in real-time to gate motion detection. Each of the first 8 bulbs in the string corresponds to one detection gate (0-7), lighting up as someone walks past.

## How It Works

### Gate-to-Bulb Mapping

The string lights are positioned at the **street end** of the path, so:

| Bulb Position | Gate | Distance from Street | Color When Active |
|---------------|------|---------------------|-------------------|
| Bulb 1 | Gate 0 | 0-0.75m | 🟢 Green (120° hue) |
| Bulb 2 | Gate 1 | 0.75-1.5m | 🟢 Green (120° hue) |
| Bulb 3 | Gate 2 | 1.5-2.25m | 🟡 Yellow (60° hue) |
| Bulb 4 | Gate 3 | 2.25-3m | 🟡 Yellow (60° hue) |
| Bulb 5 | Gate 4 | 3-3.75m | 🔴 Red (0° hue) |
| Bulb 6 | Gate 5 | 3.75-4.5m | 🔴 Red (0° hue) |
| Bulb 7 | Gate 6 | 4.5-5.25m | 🟠 Orange (30° hue) |
| Bulb 8 | Gate 7 | 5.25-6m | 🟠 Orange (30° hue) |

### Combined Energy Detection

For each gate, the system **sums the motion energy from both LD2410 sensors**:

```yaml
combined_energy[gate_0] = sensor_7144_gate_0 + sensor_6602_gate_0
```

This means:
- Someone near the street triggers gates 0-2 (mostly from sensor 6602)
- Someone in the middle triggers gates 3-5 (both sensors detect)
- Someone near the door triggers gates 6-7 (mostly from sensor 7144)

### Dynamic Brightness

Each bulb's brightness is determined by the combined gate energy:

- **Active gate** (energy ≥ floor threshold): Brightness = `energy × 2.5` (capped at 255)
- **Inactive gate** (energy < floor): Dim warm white (HSV: 30°, 50%, 30%)

### Visual Effect

As you walk from street to door:
1. **Bulbs 1-2 light up green** (you're at the street end)
2. **Bulbs 3-4 light up yellow** (approaching middle)
3. **Bulbs 5-6 light up red** (past middle)
4. **Bulbs 7-8 light up orange** (near door)
5. Behind you, bulbs fade back to dim warm white

The effect creates a **"wave"** that follows you down the path!

## Setup

### Prerequisites

✅ Tuya Local integration installed  
✅ String lights entity: `light.fairy_lights` using Tuya Local  
✅ String lights support custom scenes (check device capabilities)  
✅ At least 8 individually controllable bulbs/LEDs  

### Enable Tuya Pattern Mode

1. **Reload templates** (to get the new sensor):
   - Developer Tools → YAML → Reload Template Entities

2. **Check the pattern sensor exists**:
   - Developer Tools → States → `sensor.frontpath_tuya_scene_pattern`
   - Should show a JSON string like `{"scene_num":1,"scene_units":{...}}`

3. **Enable Tuya Pattern Mode**:
   - Settings → Devices & Services → Helpers
   - Toggle `Front Path Tuya Pattern Mode` **ON**

4. **Optional: Enable daytime motion override**:
   - Settings → Devices & Services → Helpers
   - Toggle `Front Path Fairy Lights Daytime Motion` **ON**
   - Allows fairy lights to activate during day when motion detected

### Verify Scene Text Entity

Check the scene text entity exists:

```
Developer Tools → States → text.fairy_lights_scene
```

This entity accepts JSON strings to control the custom 8-bulb pattern.

If it doesn't exist:
- Verify Tuya Local integration is installed and configured
- Check your light entity exposes scene control as a text entity
- Look for entities like `text.*_scene` or `text.*_control_data`

## Testing

### 1. Test Pattern Sensor

```
Developer Tools → States → sensor.frontpath_tuya_scene_pattern
```

Should show a base64-encoded string (e.g., `ARgCZGTgAABkALI5AQpkAS1kAT9k`).

This is the JSON scene data encoded to base64 (Tuya requirement). Walk the path and watch it update as gate energies change.

### 2. Test Manual Scene

Try manually setting a test rainbow pattern (8 colors):

```yaml
service: text.set_value
target:
  entity_id: text.fairy_lights_scene
data:
  value: 'eyJzY2VuZV9udW0iOjEsInNjZW5lX3VuaXRzIjp7InVuaXRfMSI6eyJoIjowLCJzIjoyNTUsInYiOjI1NX0sInVuaXRfMiI6eyJoIjo2MCwicyI6MjU1LCJ2IjoyNTV9LCJ1bml0XzMiOnsiZCI6MTIwLCJzIjoyNTUsInYiOjI1NX0sInVuaXRfNCI6eyJoIjoxODAsInMiOjI1NSwidCI6MjU1fSwidW5pdF81Ijp7ImgiOjI0MCwicyI6MjU1LCJ2IjoyNTV9LCJ1bml0XzYiOnsiZCI6MzAwLCJzIjoyNTUsInYiOjI1NX0sInVuaXRfNyI6eyJoIjowLCJzIjoyNTUsInYiOjI1NX0sInVuaXRfOCI6eyJoIjo2MCwicyI6MjU1LCJ2IjoyNTV9fX0='
```

**Note:** The value is base64-encoded. The decoded JSON is:
```json
{"scene_num":1,"scene_units":{"unit_1":{"h":0,"s":255,"v":255},"unit_2":{"h":60,"s":255,"v":255},"unit_3":{"h":120,"s":255,"v":255},"unit_4":{"h":180,"s":255,"v":255},"unit_5":{"h":240,"s":255,"v":255},"unit_6":{"h":300,"s":255,"v":255},"unit_7":{"h":0,"s":255,"v":255},"unit_8":{"h":60,"s":255,"v":255}}}
```

This should display a rainbow pattern on the first 8 bulbs (red → yellow → green → cyan → blue → magenta → red → yellow).

### 3. Walk the Path

With Tuya Pattern Mode enabled:
1. Walk from street toward door
2. Watch bulbs light up sequentially (green → yellow → red → orange)
3. As you move away from a bulb, it should fade to dim white

### 4. Debug Gate Energies

Create a dashboard card:

```yaml
type: entities
title: FrontPath Gate Combined Energies
entities:
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_0
    name: "Door Sensor Gate 0"
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_0
    name: "Street Sensor Gate 0"
  - entity: sensor.hlk_ld2410_7144_motion_energy_gate_1
    name: "Door Sensor Gate 1"
  - entity: sensor.hlk_ld2410_6602_motion_energy_gate_1
    name: "Street Sensor Gate 1"
  # ... repeat for gates 2-7
  - entity: sensor.frontpath_tuya_scene_pattern
```

Walk and verify gate energies spike as you pass each zone.

## Customization

### Change Gate Colors

Edit the `h` (hue) values in the pattern sensor template:

```yaml
{% if i < 2 %}
  {% set h = 120 %}  # Green - change to 240 for blue, 0 for red, etc.
{% elif i < 4 %}
  {% set h = 60 %}   # Yellow - change to 180 for cyan
```

**Hue reference** (0-360°):
- **0°** = Red
- **30°** = Orange
- **60°** = Yellow
- **120°** = Green
- **180°** = Cyan
- **240°** = Blue
- **300°** = Magenta

### Adjust Brightness Multiplier

Change the `energy * 2.5` multiplier to make bulbs brighter or dimmer:

```yaml
{% set v = (energy * 2.5) | int %}
```

- Increase to `* 3.0` for brighter response
- Decrease to `* 2.0` for dimmer response

### Change Inactive Bulb Color

Modify the inactive bulb HSV values:

```yaml
{% else %}
  {# Inactive gate: dim warm white #}
  {% set h = 30 %}   # Hue: change color
  {% set s = 50 %}   # Saturation: 0=white, 255=full color
  {% set v = 30 %}   # Value: brightness (0-255)
{% endif %}
```

### Use More/Fewer Zones

Currently maps gates 0-7 to 4 color zones (2 gates per color). To create 8 distinct colors:

```yaml
{% for i in range(8) %}
  {% set h = i * 45 %}  # Creates 8 evenly spaced hues (rainbow)
  {% set s = 255 %}
  {% set v = (energy * 2.5) | int %}
```

## Switching Between Modes

You can have **three distinct modes** by toggling helpers:

| Christmas Mode | Tuya Pattern Mode | Result |
|----------------|-------------------|--------|
| OFF | OFF | Warm white, brightness follows position |
| ON | OFF | **Effect-based** (gate-following effects) |
| OFF/ON | ON | **Tuya pattern** (8-bulb custom scene) |

**Tuya Pattern Mode takes priority** - if enabled, it overrides Christmas mode.

## Daytime Motion Override

When `Front Path Fairy Lights Daytime Motion` is **ON**:
- ✅ Porch light stays off during day (unless dark)
- ✅ Fairy lights activate when motion detected during day
- ✅ Fairy lights turn off after 5s delay (no motion)

When **OFF** (default behavior):
- ❌ All lights off during day regardless of motion

## Troubleshooting

### Pattern Doesn't Update

**Check sensor updates:**
```
Developer Tools → States → sensor.frontpath_tuya_scene_pattern
```
Walk the path - the base64 string should change. If it doesn't, gate sensors may not be updating.

**Note:** The sensor outputs base64-encoded JSON. This is required by Tuya's scene protocol.

**Check Tuya Pattern Mode is ON:**
```
Developer Tools → States → input_boolean.frontpath_tuya_pattern_mode
```
Should be `on`.

### Wrong Bulbs Light Up

**Your string might be numbered differently** - some Tuya strings count from the plug end, others from the far end.

Try reversing the mapping:

```yaml
{% for i in range(8) %}
  {% set gate_idx = 7 - i %}  # Reverse order
  {% set door_energy = states('sensor.hlk_ld2410_7144_motion_energy_gate_' ~ gate_idx) | float(0) %}
```

### Lights Don't Respond to Scene Changes

**Check text entity exists:**
```
Developer Tools → States → text.fairy_lights_scene
```

**Manually test the entity:**
```yaml
service: text.set_value
target:
  entity_id: text.fairy_lights_scene
data:
  value: 'eyJzY2VuZV9udW0iOjEsInNjZW5lX3VuaXRzIjp7InVuaXRfMSI6eyJoIjowLCJzIjoyNTUsInYiOjI1NX0sInVuaXRfMiI6eyJoIjoxMjAsInMiOjI1NSwidCI6MjU1fSwidW5pdF8zIjp7ImgiOjI0MCwicyI6MjU1LCJ2IjoyNTV9LCJ1bml0XzQiOnsiZCI6MCwicyI6MjU1LCJ2IjoyNTV9LCJ1bml0XzUiOnsiZCI6MTIwLCJzIjoyNTUsInYiOjI1NX0sInVuaXRfNiI6eyJoIjoyNDAsInMiOjI1NSwidCI6MjU1fSwidW5pdF83Ijp7ImgiOjAsInMiOjI1NSwidCI6MjU1fSwidW5pdF84Ijp7ImgiOjEyMCwicyI6MjU1LCJ2IjoyNTV9fX0='
```
(Base64-encoded RGB/Green/Blue pattern)

**Check device capabilities:**
Some Tuya devices expose scenes through different entities - check for `text.*_control_data` or similar.

### Bulbs Stay Dim/Don't Get Bright

**Increase brightness multiplier:**
```yaml
{% set v = (energy * 3.5) | int %}  # Was 2.5
```

**Check gate energies are spiking:**
Use the debug card above - gate energies should reach 40-80% when you walk by.

### All Bulbs Light Up at Once

**Increase gate floor threshold:**
Settings → Helpers → `Front Path Gate Trigger Floor` → 25-35%

This requires stronger signals to activate bulbs.

### Pattern Looks Wrong

**Test with manual rainbow pattern** (from Testing section above) to verify your lights support custom scenes correctly.

**Check sensor output** in Developer Tools - should be a base64 string like:
```
eyJzY2VuZV9udW0iOjEsInNjZW5lX3VuaXRzIjp7InVuaXRfMSI6eyJoIjoxMjAsInMiOjI1NSwidCI6MjAwfSwuLi59fQ==
```

If you see raw JSON instead of base64, the template needs the `| b64encode` filter.

## Technical Details

### Why Sum Both Sensors?

Summing energies from both sensors provides:
- **Better coverage**: Middle gates detect from both directions
- **Smoother transitions**: As you walk, multiple gates activate/deactivate gradually
- **Direction agnostic**: Works whether walking street→door or door→street

### Update Rate

The pattern updates whenever:
- Any gate energy changes (typically 1-5 times per second)
- The automation triggers (on state change or every 5 minutes)

Tuya scene commands are sent with **no transition time** for instant response.

### Performance

Each automation run:
- Reads 16 gate sensors (8 per LD2410)
- Calculates 8 combined values
- Generates JSON string (~200 characters)
- Calls Tuya service once

This is lightweight and shouldn't cause performance issues.

## Comparison: Effect Mode vs Tuya Pattern Mode

| Feature | Effect Mode | Tuya Pattern Mode |
|---------|-------------|-------------------|
| **Color change** | Entire string changes color | Individual bulbs per gate |
| **Effects** | Built-in effects (Sparkle, etc.) | Custom scene only |
| **Responsiveness** | Moderate (0.8s transition) | Instant (no transition) |
| **Visual style** | Smooth gradients | Discrete "chasing" bulbs |
| **Setup complexity** | Works with any light | Requires Tuya scene support |
| **Daytime override** | No | Yes (optional) |

## Summary

✅ **8 bulbs map to 8 gates** (gate 0 → bulb 1, gate 7 → bulb 8)  
✅ **Combined energy** from both sensors for each gate  
✅ **Color gradient**: Green (street) → Yellow → Red → Orange (door)  
✅ **Dynamic brightness** based on motion intensity  
✅ **Instant updates** via Tuya scene API  
✅ **Optional daytime override** for fairy lights only  
✅ **Keeps effect-based mode** as alternative (toggle to switch)  

Perfect for creating a true "following" effect where individual bulbs light up as you walk! 🎄✨

