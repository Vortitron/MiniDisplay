# Adaptive Sensitivity System

## Overview
The LD2410 sensors now automatically adjust their hardware sensitivity based on learned environmental baselines. On windy/noisy days, sensitivity is reduced. On calm days, it's increased for better detection.

## How It Works

### Baseline Learning
- The ESP32 continuously tracks gate energy baselines using EMA (Exponential Moving Average)
- High baseline = noisy environment (wind, trees moving, etc.)
- Low baseline = calm environment

### Adaptive Adjustment
Every **5 minutes** (configurable), the system:
1. Checks each gate's current baseline (gates 4-8 only)
2. Calculates target device sensitivity: `30 + (baseline × 0.5)`
3. Clamps to range 20-80 (20 = very sensitive, 80 = less sensitive)
4. Sends updated sensitivity to LD2410 via BLE command protocol
5. Saves to device flash

### Example
- **Calm day**: Gate 5 baseline = 15 → Device sensitivity = 37 (moderate)
- **Windy day**: Gate 5 baseline = 50 → Device sensitivity = 55 (less sensitive)
- **Very noisy**: Gate 5 baseline = 100 → Device sensitivity = 80 (maximum threshold)

## Home Assistant Controls

### Switches
- **`switch.frontpath_adaptive_sensitivity`** - Enable/disable auto-adjustment (default: ON)

### Buttons
- **`button.frontpath_auto_calibrate_sensor_1`** - Manual calibration for door sensor (keep area clear 10s)
- **`button.frontpath_auto_calibrate_sensor_2`** - Manual calibration for street sensor

### Numbers
- **`number.frontpath_sensitivity_update_interval`** - How often to adjust (1-60 minutes, default: 5)

## Manual Calibration

To manually calibrate the sensors:
1. Clear the path completely (no people, pets, or moving objects)
2. Press `Auto Calibrate Sensor 1` button
3. Wait 10 seconds (stay clear!)
4. Press `Auto Calibrate Sensor 2` button
5. Wait 10 seconds

This resets the LD2410's internal noise floor. Best done on a calm day.

## LD2410 BLE Command Protocol

The system uses the official LD2410 BLE protocol:
- **0xFF 00 01 00** - Enter configuration mode
- **0x64 00 + data** - Set gate sensitivities (18 bytes: 9 motion + 9 static)
- **0xA3 00** - Auto-calibrate
- **0xFE 00** - Exit configuration mode

Commands are sent via characteristic `0000fff2-0000-1000-8000-00805f9b34fb`.

## Logs

Watch for adaptive updates:
```
[adaptive] Updating device sensitivity based on learned baselines
[adaptive] S1 Gate 4: baseline=22.3 → sensitivity=41
[adaptive] S1 Gate 5: baseline=35.1 → sensitivity=47
[adaptive] S1: Sent sensitivity update
[adaptive] S2: Sent sensitivity update
[adaptive] Queued sensitivity write to devices
```

## Tuning

If you need to adjust the adaptive formula:
- **More aggressive**: Change `30 + (baseline × 0.5)` to `30 + (baseline × 0.7)`
- **Less aggressive**: Change to `30 + (baseline × 0.3)`
- Edit the `update_adaptive_sensitivity` script in the YAML

## Compatibility

Requires:
- LD2410 firmware with BLE command support (most recent firmware)
- BLE connection from ESP32 to both sensors
- Write characteristic support (0000fff2)

## Future Enhancements

Possible additions:
- Per-gate manual sensitivity sliders in HA UI
- Save/restore sensitivity profiles
- Time-based profiles (day vs. night sensitivity)
- Historical baseline tracking graph



