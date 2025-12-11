# Front Path BLE Processing Mode

## Overview

This ESPHome config moves **all detection logic and rolling averages** to the ESP32, drastically reducing WiFi traffic and eliminating the need for 18 statistics entities in Home Assistant.

## Network Traffic Reduction

### Before (BLE Proxy Mode)
- **36+ entities** updating every 200ms:
  - 2 × moving target energy
  - 2 × 9 gate energies (18 sensors)
  - 2 × has_moving_target
  - 2 × moving target distance
  - Plus statistics sensors recalculating in HA
- **WiFi load**: BLE → ESP32 → WiFi → HA (constant stream)
- **HA CPU**: Template sensors recalculating on every update

### After (BLE Processing Mode)
- **4 entities** updating only on state change:
  - `binary_sensor.frontpath_path_person_detected` (ON/OFF)
  - `sensor.frontpath_path_person_position` (0.00-16.00m)
  - `text_sensor.frontpath_active_gate` (door_3, street_5, none)
  - `sensor.frontpath_light_level` (0-100%)
- **WiFi load**: ~90% reduction (only meaningful changes sent)
- **HA CPU**: Minimal (simple automation triggers)

## How It Works

### On the ESP32
1. **Direct BLE connection** to both LD2410 sensors (based on [dgrnbrg's work](https://github.com/dgrnbrg/appdaemon-configs/blob/main/ld2410ble.yaml))
2. **Authenticates** with sensors and enables engineering mode (gate data)
3. **Parses BLE packets** in C++ lambdas
4. **Calculates rolling averages** using exponential moving average (EMA):
   - Overall moving target energy baseline (per sensor)
   - Per-gate energy baselines (18 baselines, 9 gates × 2 sensors)
   - Stored in `globals` (RAM only, no database writes)
5. **Runs detection logic**:
   - Overall energy spike vs baseline
   - Gate spike with moving flag
   - Sequential gate activation (person walking through)
6. **Calculates position** from strongest gate
7. **Publishes only final results** to HA

### In Home Assistant
- Simple automation that reads ESP32 outputs
- No template sensors with complex math
- No statistics integration entities
- Just light control based on person presence/position

## Installation

### 1. Flash New ESP32 Config

```bash
cd esphome
esphome run FrontPath/FrontPath_BLE_Processing.yaml
```

**First boot**: ESP32 will connect to both sensors via BLE (takes 30-60s). Watch logs:

```bash
esphome logs FrontPath/FrontPath_BLE_Processing.yaml
```

You should see:
```
[I][ble_sensor1] Sensor 1 (7144) configured, waiting for data...
[I][ble_sensor2] Sensor 2 (6602) configured, waiting for data...
[I][sensor1_parse] Sensor 1 (7144) data flowing
[I][sensor2_parse] Sensor 2 (6602) data flowing
```

### 2. Replace HA Automation

Replace your current automation package with:

```yaml
# In packages/frontpath.yaml or automations.yaml
packages:
  frontpath_lights: !include esphome/FrontPath/frontpath_lights_automations_simple.yaml
```

**Delete the old package** that has 18 statistics sensors.

### 3. Restart HA

```bash
# In HA Developer Tools → YAML
# Check configuration
# Restart Home Assistant
```

### 4. Verify Entities

In HA, check these entities exist and update when you walk the path:
- `binary_sensor.frontpath_path_person_detected` (should turn ON)
- `sensor.frontpath_path_person_position` (should change 0→16m)
- `text_sensor.frontpath_active_gate` (should show door_3, street_5, etc.)

### 5. Tune Detection Parameters

Adjust via HA (stored in ESP32 globals):
- **number.frontpath_energy_margin** (default 22%) - Overall energy spike threshold
- **number.frontpath_gate_trigger_floor** (default 18%) - Minimum gate energy
- **number.frontpath_gate_delta_margin** (default 8%) - Per-gate delta threshold
- **number.frontpath_path_length** (default 16m) - Your actual path length

## Tuning Guide

### Too Many False Positives (Wind)
1. Raise `Energy Margin` to 30-35%
2. Raise `Gate Trigger Floor` to 25-30%
3. Raise `Gate Delta Margin` to 12-15%

### Missing People Walking
1. Lower `Energy Margin` to 18-20%
2. Lower `Gate Delta Margin` to 5-6%
3. Check logs - are sensors seeing them?

### Check Sensor Health
```bash
esphome logs FrontPath/FrontPath_BLE_Processing.yaml
```

Watch for:
- `Detection: energy=X gate=X seq=X => 1` (person detected)
- `delta1=XX.X delta2=XX.X gate_peak=XX.X` (raw values)
- If you see `Sensor X disconnected`, BLE connection dropped (will auto-reconnect)

## Adaptive Baseline Behavior

- **EMA alpha = 0.0083** ≈ 240-sample window @ 200ms ≈ 48 seconds
- Baseline adapts slowly to changing conditions (rain, wind, temperature)
- Detection looks for **spikes above the adaptive baseline**
- On windy days: baseline rises slowly, reducing false triggers

To adjust adaptation speed, change `avg_alpha` in the YAML:
- **Faster adaptation** (30s): `0.0167` 
- **Slower adaptation** (90s): `0.0044`

## Troubleshooting

### Sensors Won't Connect
1. Check MAC addresses match: `B8:BE:51:7D:71:44` and `14:AA:8C:58:66:02`
2. Ensure sensors are powered (via ESP32 or separate 5V)
3. Check logs for `Failed to connect` - may need to power cycle sensors
4. BLE can be flaky - wait 2-3 minutes for retries

### Position Always Shows 0.00
- Gate energies not parsing correctly
- Packet format may differ from engineering mode spec
- Check logs: add `ESP_LOGD("sensor1_parse", "Packet size: %d", x.size());`
- May need to adjust gate parsing offset (line 424 in YAML)

### Lights Not Responding
1. Check automation is active in HA
2. Verify entity names match (`light.front_porch_local`, `light.fairy_lights`)
3. Test manually: turn on `binary_sensor.frontpath_path_person_detected` via Developer Tools

## Technical Notes

### Why EMA Instead of Statistics?
- **EMA (Exponential Moving Average)**: Lightweight, constant memory, adapts continuously
- **Statistics Sensor**: Needs array of samples, more memory, periodic recalculation
- For ESP32 with limited RAM, EMA is ideal

### Gate Energy Parsing
The LD2410 engineering mode packet format isn't fully documented. The code assumes:
- Byte 17+ contains gate data
- Format: `[motion_gate_0, static_gate_0, ...]`

If gate energies aren't working, you may need to:
1. Capture raw BLE packets with Wireshark + nRF Sniffer
2. Reverse-engineer the exact format
3. Update parsing logic in lambdas

**Fallback**: If packet is too small, code estimates gate from distance (distance / 75cm).

### Memory Usage
- **Globals**: ~400 bytes (2 × 9 gates × 2 floats + misc)
- **BLE buffers**: ~2KB per sensor
- **Total**: Well under ESP32-C3 available RAM

## Comparison: BLE Proxy vs BLE Processing

| Feature | BLE Proxy | BLE Processing |
|---------|-----------|----------------|
| **WiFi Traffic** | High (36+ entities @ 5 Hz) | Low (4 entities @ 0.1 Hz) |
| **HA Entities** | 56+ (raw + statistics) | 10 (outputs + controls) |
| **Detection Logic** | HA Templates | ESP32 C++ |
| **Baseline Adaptation** | Statistics integration | On-device EMA |
| **Network Resilience** | Breaks if WiFi drops | Detection continues locally |
| **Setup Complexity** | Simple (native HA integration) | Moderate (custom ESPHome) |
| **Debugging** | Easy (HA logs/templates) | Requires ESPHome logs |

## Credits

Based on [dgrnbrg's LD2410 BLE ESPHome config](https://github.com/dgrnbrg/appdaemon-configs/blob/main/ld2410ble.yaml), extended to support:
- Dual-sensor setups
- Per-gate energy tracking
- On-device adaptive baseline
- Position calculation
- Sequential detection logic

