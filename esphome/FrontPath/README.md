# FrontPath - ESP32-C3 SuperMini with Dual LD2410C Sensors

## Which files are actually in use

Home Assistant device **FrontPath BLE Processing** (GamlaBio, Front Walkway, MAC `58:8C:81:AD:39:EC`, `frontpath.local`; DHCP, last seen at `192.168.1.161`) is the live box. The ESPHome dashboard should show **one** FrontPath config. Every top-level `.yaml` in `/config/esphome` appears there as a device, and these files all share `name: frontpath`, so stray copies show up as duplicates that go live and dark together. The building blocks live in `frontpath/`, which the dashboard does not scan.

| Role | File | Notes |
|------|------|--------|
| **Flash this** | `frontpath-display.yaml` | Screen and a passive Bluetooth proxy. Includes the colour overlay. |
| **Colour + radar** | `frontpath/frontpath-rgb.yaml` | Rollback without the panel. This is what the box was running before the screen. Copy it to the top level to flash it. |
| **Radar base** | `frontpath/frontpath.yaml` | BLE processing v3. Included by the overlay; keep this as the TEMT6000 rollback. |
| **Live lighting package** | `frontpath_lights_automations_simple.yaml` | Loaded on HA as `packages/frontpath_automations.yaml`. Also caches hours-until-rain and the next-hour temperature. |

`FrontPath_BLE_Processing_v3.yaml` is an alias of `frontpath-display.yaml` so old flash commands still hit the current stack.

Flash:

```bash
esphome run esphome/FrontPath/frontpath-display.yaml
```

**Do not flash:** `frontpath/frontpath-sweep.yaml` (I²C register diagnostic, finished — not on the dashboard), `FrontPath.yaml` (capital F — old BLE proxy), UART / v1 / v2, `frontpath_lights_automations.yaml`.

The overlay does not duplicate radar logic. It `!include`s `frontpath/frontpath.yaml`, removes the TEMT6000 ADC sensors, and adds the VEML6040. Colour is read with `write_readv` (repeated START); a split write-then-read silently returns the same value for every register.

---

## Hardware Configuration

This configuration uses an ESP32-C3 SuperMini board with two LD2410C millimetre-wave radar sensors in a single enclosure positioned at the middle of an outdoor path:
- **Sensor 1**: `B8:BE:51:7D:71:44` - Points towards the **street end** (`street_1..street_8`)
- **Sensor 2**: `14:AA:8C:58:66:02` - Points towards the **door end** (`door_1..door_8`)

Both sensors are mounted in the same box at the path's midpoint, pointing in opposite directions to provide full coverage of the 12m path length and enable direction/position tracking.

### Windy-day noise hardening (on-device, v3)

- Detection can only be triggered/held by **motion-backed conditions**; a raw “gate delta” noise spike is no longer allowed to latch `person_detected` on its own (prevents wind from getting it “stuck detected”).
- **Near-gate wind guard**: if activity is **only** in the near gates (defaults: gates 1–3) the firmware requires a short **streak** of consecutive hits before it will trigger `Path Person Detected`. This is aimed at wind/LED-string flutter close to the radars, while keeping far-end/door detection responsive. Tune in YAML (`near_gate_*` globals) and reflash.
- **Static confirmation only for near gates**: `static_confirmation_max_gate` controls up to which gate index we require static confirmation for motion to be considered valid. Far gates often do not produce strong stationary energy for walking people, so allowing moving-only there improves detection at the ends without reintroducing near-gate wind chatter.

## Wiring

ESP32-C3 SuperMini, USB at the top. Left side top-to-bottom is 5V, GND, 3.3V, GPIO4, GPIO3, GPIO2, GPIO1, GPIO0. Right side is GPIO5, GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, GPIO20, GPIO21.

```
        USB
         |
    +---------+
5V  |  5V     | GPIO5
GND |  GND    | GPIO6
3V3 |  3.3V   | GPIO7
 4  |  GPIO4  | GPIO8
 3  |  GPIO3  | GPIO9
 2  |  GPIO2  | GPIO10
 1  |  GPIO1  | GPIO20
 0  |  GPIO0  | GPIO21
    +---------+
```

| Function | Connection |
|----------|------------|
| VEML6040 SDA / SCL / VCC | GPIO4 / GPIO5 / **3.3 V** (address `0x10`, not 5 V) |
| VEML6040 GND / INT | GND / leave INT off |
| Street radar (sensor 1) TX → ESP RX | GPIO21 |
| Street radar RX ← ESP TX | GPIO20 |
| Door radar (sensor 2) TX → ESP RX | GPIO7 |
| Door radar RX ← ESP TX | GPIO6 |
| Both radars VCC / GND | 5 V / GND. UART logic is 3.3 V; do not level-shift up |
| LCD SCL / SDA / D/C | GPIO1 / GPIO3 / GPIO2 |
| LCD CS | **Tied to GND** on the module (keeps the panel selected) |
| Software CS | **GPIO9** (BOOT), ESPHome only — nothing attached. Was GPIO21, which the street radar's TX drives |
| LCD RES | **GPIO10.** ESPHome pulses it low at boot. Tied straight to 3.3 V the panel stayed blank, even with all pixels on |
| LCD BL | **GPIO0.** High = on. PWM, so it can dim |
| LCD VCC / GND | 3.3 V / GND |
| Onboard LED | GPIO8, blue only, active-low. Blinks while a journey is off its usual road |
| GPIO9 | BOOT. Used only as the software CS above; do not wire anything to it |

The cable order on the module is BL, RES, D/C, CS, SCL, SDA, GND, VCC. That matches the WeAct 1.37" board.

BL does not need the LED current from the ESP. The module has a SI2302 that switches the backlight LED through 47 Ω, with a 33 kΩ pulldown so the lamp stays off until GPIO0 is driven. Leave the **Backlight ON** solder bridge open. If that bridge is closed, BL is tied to 3.3 V and the lamp cannot be turned off.

SDA is on GPIO3, not GPIO2. The module pulls SDA down with 33 kΩ, and GPIO2 is a strapping pin that should not be held low while the chip boots. D/C is only a 100 Ω series resistor into the controller, so that wire is the one on GPIO2. GPIO0 is not a boot pin on the C3 (GPIO9 is).

The panel is transflective, so the backlight stays off in daylight. It comes on at about 40% when the VEML reads under 15 lx, and goes off again above 40 lx. The light is named **Path Display Backlight** if you want to set it by hand; the next time the light level crosses a threshold it follows the sensor again. Refresh of the pixels is every 30 seconds, not in the radar path.

**Do not plug in radar TX/RX yet.** `frontpath-display.yaml` still speaks to the LD2410s as BLE clients. Connecting UART makes the modules stop advertising, and this firmware will lose them. The pins above are the wiring to build to. Logger baud is 0 so GPIO20/21 stay quiet.

### What the screen and LED do

Four lines. Place names are ASCII, so Örkelljunga is written Orkelljunga:

1. `Markaryd 11m Gamla` — from `sensor.journey_markaryd` attributes `minutes` and `road`
2. `Orkelljunga 16m Gamla` — from `sensor.journey_orkelljunga`, the pool. It stands in for the drive to SiS Ljungaskog, which goes by Gamla E4; Google would route Ljungaskog itself down the E4
3. `Rain 4h`, `Rain now`, or `No rain`
4. Next-hour temperature, with `ice` appended when frost is expected

`road` is compared exactly. `Gamla E4` is the old road. `E4` means that journey has diverted.

Rain and the predicted temperature come from the OpenWeatherMap hourly forecast (`weather.openweathermap`), the same feed as the other forecasts. AccuWeather charges, so it is not used. `input_number.frontpath_hours_until_rain` is 48 when nothing wet is in the window (precipitation under 0.2 mm is ignored). `input_number.frontpath_forecast_temp_next` is the next hour's temperature. Both are filled by `frontpath_update_frost_forecast` every 30 minutes. They appear after a Home Assistant configuration reload.

Bluetooth proxy is on, advertisements only (`active: false`), so phone presence can see the box without taking the two radar connection slots.

## Important Notes

1. **Power**: Both LD2410C modules want 5 V on VCC. The VEML6040 and the LCD want 3.3 V.

2. **Logging**: UART logging is off (`baud_rate: 0`) so GPIO20/21 stay free for the street radar. Logs still come over the Home Assistant API, and over USB-JTAG on the C3.

3. **Onboard LED**: GPIO8 blinks at 1 Hz while either journey is off its usual road: both are normally Gamla E4, so it blinks when Google moves one to the E4. The `diverted` attribute on each journey sensor decides it (`ElectricAutomations/JourneyTime.yaml`). Ice is shown on the screen only (`ice` after the temperature).

4. **BLE**: This firmware is still a client of the two radars, plus a passive proxy. It is not the old `FrontPathUART.yaml` detection stack — do not flash that file.

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

### Light sensing & darkness trigger

- **VEML6040** on I²C reports illuminance (lux), **Twilight Index** (smoothed B/R), RGBW counts, sky greyness (%), `Sky Condition`, and a **Dusk** binary sensor (dim *and* blue, delayed 2 min on / 5 min off).
- Twilight index, not Kelvin: overcast is dim but colour-neutral (~1.0–1.3); civil twilight is the blue hour (~1.8–3.0). A cloud at 14:00 therefore does not look like sunset.
- `Light Level` is still 0–100 % so `frontpath_darkness_threshold_pct` (default 32 % ≈ 64 lx) keeps working. Drive path lights from **Dusk** once it has been watched for a few evenings.
- Path lamps will pull B/R toward red once they are on; read twilight before switching, or gate on lights-off.
- Integration time auto-ranges (80 ms bright … 1280 ms dim). The old TEMT6000 on GPIO0 is removed by the overlay.

### Automatic gate calibration

- **Purpose:** keeps all nine motion-gate thresholds per sensor just above the current background energy so you can run maximum sensitivity without babysitting the sliders.
- **How it runs now:** the scheduler checks every 20 minutes. It only proceeds if no live targets are detected, the rolling **Detection Activity Score** exceeds the **Gate Activity Threshold** (defaults: score ≥ 6 events), or it has been at least four hours since the last successful run. This means windy/rainy bursts trigger quick recalibration, while quiet nights leave the gates untouched.
- **Step limiting:** every gate change is clamped by **Gate Max Step** (default 5 pp) so even if calibration runs while someone is on the path, the firmware only nudges the LD2410 thresholds a few percent and converges gradually.
- **Adjustments:** the **Gate Sensitivity Margin**, **Gate Activity Threshold**, and **Gate Max Step** numbers in Home Assistant expose all the tuning knobs. Set a lower activity threshold if you want recalibrations to happen with fewer spurious detections, or lower the step limit for ultra-conservative adjustments.
- **Visibility:** `sensor.frontpath_detection_activity_score` mirrors the internal score (increments per detection, decays every 30 s) so you can see why a calibration did or didn’t fire. Logs announce whether a run was skipped (movement/quiet) or capped by the step limiter.
- **Scope:** only the *Motion Energy Gate 0–8* numbers are auto-tuned so you still retain manual control of static thresholds if you need them extra conservative outdoors. The existing **Recalibrate Gate Thresholds** button still forces an immediate run irrespective of the activity score.

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

