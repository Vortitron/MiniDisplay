# FrontPath - ESP32-C3 SuperMini with Dual LD2410C Sensors

## Hardware Configuration

This configuration uses an ESP32-C3 SuperMini board with two LD2410C millimetre-wave radar sensors in a single enclosure positioned at the middle of a 12m outdoor path:
- **Sensor 1**: Points towards the door/house
- **Sensor 2**: Points away from the door/house (towards the far end)

Both sensors are mounted in the same box at the path's midpoint, pointing in opposite directions to provide full coverage of the 12m path length and enable direction/position tracking.

## Wiring Connections

### ESP32-C3 SuperMini Pinout Reference
```
        USB
         |
    +---------+
5U  |  5V     | 5
 G  |  GND    | 6
3.3 |  3.3V   | 7
 4  |  GPIO4  | 8
 3  |  GPIO3  | 9
 2  |  GPIO2  | 10
 1  |  GPIO1  | 20
 0  |  GPIO0  | 21
    +---------+
```

### LD2410C Sensor 1 Connections
| LD2410C Pin | ESP32-C3 Pin | Function |
|-------------|--------------|----------|
| VCC         | 5V           | Power (5V) |
| GND         | GND          | Ground |
| TX          | GPIO21       | Data from sensor to ESP32 |
| RX          | GPIO20       | Data from ESP32 to sensor |

### LD2410C Sensor 2 Connections
| LD2410C Pin | ESP32-C3 Pin | Function |
|-------------|--------------|----------|
| VCC         | 5V           | Power (5V) |
| GND         | GND          | Ground |
| TX          | GPIO9        | Data from sensor to ESP32 |
| RX          | GPIO8        | Data from ESP32 to sensor |

## Important Notes

1. **Power Supply**: The LD2410C sensors require 5V power. Connect both VCC pins to the 5V pin on the ESP32-C3 SuperMini.

2. **Logging**: UART logging has been disabled (set to 0) to free up GPIO20/21 for the first sensor. You can still view logs over WiFi using the Home Assistant API.

3. **Pin Usage**: 
   - GPIO20/21: Sensor 1 (UART0)
   - GPIO8/9: Sensor 2 (UART1)
   - These pins are now dedicated to the sensors and cannot be used for other purposes.

4. **Bluetooth Proxy**: The Bluetooth proxy feature is still active and will work alongside the sensors.

## Features

### Reliability & Auto-Recovery
- **Auto-restart on connection loss**: Reboots if WiFi or Home Assistant connection lost for 15 minutes
- **Memory optimised**: Calibration tools removed to reduce memory usage and prevent crashes, memory monitoring sensor tracks heap
- **Fast response**: No filters on main sensors - actual real-time readings for instant detection
- **Multi-stage filtering**: 
  - RAW readings → Smoothed (1s average) → Baseline (15s average, only when no person)
  - Filters momentary spikes while maintaining responsive person detection
  - Adaptive baseline automatically adjusts to weather changes over minutes

### Sensor Capabilities

Each LD2410C sensor provides:
- **Binary Sensors**:
  - Presence detection (has_target)
  - Moving target detection
  - Still target detection

- **Distance & Energy Sensors**:
  - Moving distance (cm)
  - Still distance (cm)
  - Moving energy level
  - Still energy level
  - Detection distance

## Home Assistant Integration

Once flashed and connected to Home Assistant, you'll see the following entities:

**Per sensor (x2):**
- **2 binary sensors** (presence, moving target) - still target is hidden
- **14 numeric sensors** (5 general: distances and energy levels, 9 per-gate move energy)
- **21 number controls** (3 basic: max gates + timeout, 18 per-gate sensitivity thresholds)
- **2 button controls** (restart, factory reset)

**Diagnostic sensors:**
- **Sensor 1/2 Moving Energy RAW** - unfiltered readings direct from sensor
- **Sensor 1/2 Moving Energy Smoothed** - 1-second moving average
- **Sensor 1/2 Baseline** - long-term environmental baseline
- **Sensor 1/2 Gate 0-8 Move Energy** - per-gate energy readings (see which distances are detecting)
- **Free Memory** - ESP32 heap memory in bytes

**Smart combined sensors:**
- **Path Person Detected** - binary sensor using adaptive baseline detection (energy - baseline > 25-40%)
- **Path Person Position** - numeric sensor showing position in metres along the path:
  - Sensor box is at the **8m mark** (middle of ~16m total path coverage)
  - Position calculated from sensor with highest energy
  - **Sensor 1 detection**: position = 8 - distance (points towards 0m end)
  - **Sensor 2 detection**: position = 8 + distance (points towards 16m end / door)
  - Example: If sensor 2 detects someone 4m away, position = 12m
  - Example: If sensor 1 detects someone 3m away, position = 5m
  - At the sensor box itself: position ≈ 8m
  - The exact end values depend on your max distance gate settings

All entities will be prefixed with "Sensor 1" or "Sensor 2" for easy identification.

## Calibration Guide

The LD2410C sensors are quite sensitive by default and often need tuning to prevent false detections.

**Current detection: Adaptive Baseline System** (automatically adjusts to weather conditions)

**How it works:**
The system uses a multi-stage filtering approach:

1. **RAW readings** → Direct from sensor, no processing
2. **Smoothed readings** → Fast exponential moving average (1s updates, 70% old + 30% new)
3. **Baseline** → Very slow exponential moving average (15s updates, 95% old + 5% new, only when no person detected)

This means:
- **Dry conditions**: Low baseline (~2-8%) → sensitive detection
- **Rain/wind**: Higher baseline (~10-25%) → automatically less sensitive to prevent false triggers
- **Heavy rain**: Very high baseline (~25-40%) → only triggers on clear person-sized targets

**Why multi-stage filtering?**
- **Momentary spikes** (single raindrops, insects): Filtered out by 1s smoothing
- **Brief weather events** (gust of wind): Smoothed values catch it, but baseline doesn't shift
- **Sustained weather changes** (rain starting): Baseline adapts over 5+ minutes to the new normal

**Baseline tracking:**
- Updates every 15 seconds when no person is detected
- Uses smoothed values (not raw) to avoid chasing spikes
- Visible in Home Assistant as "Sensor 1/2 Baseline" sensors

**Detection logic** (adaptive thresholds above baseline):
- **Energy > baseline + 30%**: Immediate detection (strong spike = definitely person)
- **Energy > baseline + 20% AND moving target detected**: Confirmed person (moderate spike + movement)
- **Energy > baseline + 12% AND moving target detected**: Edge case catch (small spike but movement confirmed)

**Note:** These thresholds are tuned for calibrated gates and tested to balance sensitivity with false trigger prevention. The adaptive baseline automatically adjusts to environmental conditions.

**Final safety net:** Person detection requires 1.5 seconds sustained signal (delayed_on filter) and stays ON for 5 seconds after signal clears (delayed_off filter).

This adaptive approach automatically handles:
- Rain/light wind: Brief spikes filtered by averaging, baseline slowly rises over minutes
- Branches/heavy wind: Requires sustained spike +25-40% above baseline to trigger
- Small animals: Usually filtered unless sustained above baseline
- Person walking: Clear spike above baseline (typically +30-50%) triggers detection
- Weather changes: Baseline adapts gradually over 3-5 minutes (not reactive to brief spikes)

### Important: Outdoor Path Limitations

⚠️ **These sensors are NOT designed for outdoor use.** They detect any movement/presence based on radar reflections and **cannot distinguish between people and other objects**. For outdoor paths, you will get false triggers from:
- Wind moving trees, bushes, or foliage
- Rain, snow, or heavy fog
- Animals (cats, dogs, birds, etc.)
- Vehicles passing nearby
- Even flying insects in some cases

**For outdoor use:** Focus on "Moving Target" detection only, set very short detection distances (2-3m to just cover the path), and use delayed_on filters (already configured).

### Quick Calibration Steps for 12m Path

1. **Set Detection Distance for Path Coverage**:
   - Set **Max Move Distance Gate** to **6-8** (covers ~4.5-6m, half the path from each sensor)
     - Each gate = ~0.75m, so gate 6 = 4.5m, gate 8 = 6m
   - Set **Max Still Distance Gate** to **3-4** (~2-3m - still targets are unreliable outdoors)
   - Each sensor covers roughly half the path length

2. **Adjust Timeout**:
   - Keep **Timeout** at **3-5s** for paths - you want quick clearing
   - Longer timeouts mean lights stay on longer after triggers (including false ones)

3. **Fine-tune Per-Gate Sensitivity** (Advanced - Optional):
   - Each gate (0-8) has **motion threshold** and **static threshold** controls (0-100)
   - **Higher value = less sensitive** (needs stronger signal to trigger)
   - **Lower value = more sensitive** (triggers on weaker signals)
   - **Default is usually 50** - good starting point
   - **Use case**: If gate 3 (2.25-3m range) gets too many false triggers from a bush, increase "Motion Energy Gate 3" to 70-80
   - **Tip**: Only adjust gates that correspond to enabled distance ranges (if max gate = 6, gates 7-8 don't matter)

4. **Use the Smart Sensors**:
   - **"Path Person Detected"** - binary sensor that triggers when either sensor sees strong movement (>50% energy)
   - **"Path Person Position"** - shows where the person is on the path (in metres):
     - Position values are in metres from one end of the path
     - Sensor box is at the **8m mark**
     - Position **0-8m**: Detected by Sensor 1 (8 minus distance)
     - Position **8-16m**: Detected by Sensor 2 (8 plus distance)
     - Example: 12m = 4 metres from sensor box towards door
     - Example: 5m = 3 metres from sensor box towards far end
     - You can use this for:
       - Progressive lighting (light up sections as person approaches)
       - Direction detection (position increasing = approaching door, decreasing = leaving)
       - Door triggers (position > 12m = near door, unlock/turn on porch light)
       - Zone-based actions (0-5m = "far path", 5-11m = "middle", 11-16m = "doorstep")
   - You can still use individual "Moving Target" sensors if needed
   - Ignore "Still Target" (already hidden from HA)

5. **Test and Refine**:
   - **Essential sensors to monitor in Home Assistant**:
     - **"Sensor 1/2 Moving Energy RAW"**: Unfiltered readings straight from the sensor (updates rapidly)
     - **"Sensor 1/2 Moving Energy"**: Same as RAW - actual current values with no processing
     - **"Sensor 1/2 Moving Energy Smoothed"**: 1-second moving average (filters momentary spikes)
     - **"Sensor 1/2 Baseline"**: Long-term environmental baseline (very slow adaptation, updates every 15s only when no person)
     - **"Sensor 1/2 Gate 0-8 Move Energy"**: Per-gate energy readings - shows which distance ranges are detecting movement
     - **"Free Memory"**: Should stay stable above ~100,000 bytes - if it keeps dropping, there's a memory leak
     - **Person detection logic**: energy - baseline > 25-40% triggers detection
   
   - **Using per-gate energy readings**:
     - Each gate represents ~0.75m distance range:
       - Gate 0: 0-0.75m (very close)
       - Gate 1: 0.75-1.5m
       - Gate 2: 1.5-2.25m
       - Gate 3: 2.25-3m
       - Gate 4: 3-3.75m
       - Gate 5: 3.75-4.5m
       - Gate 6: 4.5-5.25m
       - Gate 7: 5.25-6m
       - Gate 8: 6-6.75m
     - **Walk the path** and watch which gates light up - this shows your actual detection coverage
     - **Identify problem zones**: If gate 3 always shows high energy (even when nobody's there), you might have a bush/object at ~2.5m
     - **Fine-tune sensitivity**: Increase the threshold for problem gates, lower it for gates that miss people
   
   - **Diagnosing enclosure problems**:
     - If RAW energy is consistently very low (<10%) even when walking close to sensors, the plastic enclosure may be too thick
     - Typical RAW energy values when walking nearby should be 40-80%
     - If values are much lower, try a thinner plastic or repositioning sensors closer to the plastic
     - The LD2410C works through thin plastic but struggles with thick/dense materials
   
   - **Checking detection logs**:
     - Enable ESPHome logs in Home Assistant
     - When person detected, you'll see: "PERSON DETECTED - S1: X.X% (baseline Y.Y%, delta Z.Z%)"
     - This shows you exactly what triggered detection and helps fine-tune thresholds
   
   - Watch the "Path Person Position" as you walk the path - it should show metres from one end
   
   - **Fine-tuning the adaptive thresholds** (in YAML lambda, lines 161-163):
     - If getting false triggers in wind: increase `moderate_delta` from 25.0 to 30.0
     - If missing detections in calm weather: decrease `weak_delta` from 15.0 to 10.0
     - If getting brief false triggers: increase window_size from 5 to 7 (lines 331 & 363)
     - If detection too slow: reduce `delayed_on` from 1s to 500ms (line 186)
   
   - Baseline adapts gradually over 3-5 minutes to sustained weather changes

### Advanced Calibration

- Use **Restart** button after changing settings (usually automatic)
- Use **Factory Reset** button to return to default settings if needed
- Watch the energy and distance sensors in Home Assistant to tune the detection thresholds

### Typical False Detection Causes

- **Too much detection range**: Sensors picking up movement outside intended area
- **Ceiling fans**: Detected as moving targets
- **Curtains/blinds**: Moving with air currents
- **Radiators/heating**: Causing air movement
- **Electronics**: Some devices emit interference

### Recommended Starting Values

**For 12-16m outdoor path (this configuration):**
- Max Move Distance Gate: **6-8** (each gate ~75cm, so 6-8 = 4.5-6m, covers up to 8m from sensor box)
- Max Still Distance Gate: **3-4** (~2-3m - minimal, not reliable outdoors)
- Timeout: **3-5s** (quick clearing)
- **Adaptive thresholds** (automatically adjust to weather):
  - `strong_delta`: **40%** above baseline (person without movement confirmation)
  - `moderate_delta`: **25%** above baseline (person with movement)
  - `weak_delta`: **15%** above baseline (edge cases with movement)
- **Spike filtering**:
  - 5-reading sliding window average
  - 1 second throttle averaging
  - 1 second delayed_on (ignores momentary spikes)
  - 5 second delayed_off (keeps detection active briefly)
- **Baseline adaptation**: 10 second intervals, 95% old + 5% new (3-5 minute adaptation time)
- Position: **Displayed in metres** (8m = sensor box, 0m = far end, 16m = door end)
- **Use "Path Person Detected" sensor in automations** (already configured with adaptive detection)

**New diagnostic sensors:**
- **"Sensor 1/2 Moving Energy RAW"**: Unfiltered sensor readings - use to diagnose enclosure signal strength
- **"Sensor 1/2 Baseline"**: Current adaptive baseline - should slowly track weather changes
- **"Free Memory"**: Available heap memory in bytes - monitor for memory leaks (should stay stable above ~100KB)

For indoor room (4-6m monitoring):
- Max Move Distance Gate: 5-7 (~4-5m)
- Max Still Distance Gate: 5-7 (~4-5m)
- Timeout: 10-30s

For indoor hallway (2-4m monitoring):
- Max Move Distance Gate: 3-5 (~2-4m)
- Max Still Distance Gate: 3-5 (~2-4m)
- Timeout: 5-10s

### Better Options for Outdoor Paths

Consider using PIR motion sensors with pet-immunity or thermal/ToF sensors instead. These are better suited for outdoor use and can better differentiate between people and environmental factors.

