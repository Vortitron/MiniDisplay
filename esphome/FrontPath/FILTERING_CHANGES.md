# Filtering System Changes - November 2025

## Problem Identified

The previous filtering approach was causing issues:
- `sliding_window_moving_average` filter was **rounding/clamping** values instead of smoothing them
- "Moving Energy" sensors were stuck at fixed values (15% for S1, 25% for S2) instead of tracking actual readings
- RAW values were updating correctly (0% in calm conditions), but filtered values never dropped below baseline
- The filters appeared to be adding a floor rather than smoothing
- This broke the adaptive baseline logic completely

## Root Cause

The `on_raw_value` trigger fires **before** filters are applied, which is correct. However:
1. The filters (`sliding_window_moving_average` + `throttle_average`) were somehow **malfunctioning**
2. Instead of creating a moving average, they were creating a **minimum value floor**
3. The baseline tracking was trying to adapt to the broken filtered values (15%/25%)
4. Detection logic compared broken filtered values to broken baselines → no useful detection

## New Filtering Architecture

### Three-Stage Processing Pipeline

```
Sensor → RAW Global → Smoothed Global → Baseline Global
         (instant)     (1s average)      (15s average, no person only)
```

### Stage 1: RAW Readings
- **Direct from sensor**, captured via `on_value` trigger
- Stored in `sensor_1_moving_energy_raw` / `sensor_2_moving_energy_raw` globals
- **No processing** - shows actual instant readings
- Visible as "Sensor 1/2 Moving Energy RAW" sensors
- Update rate: As fast as sensor sends data (~100-200ms)

### Stage 2: Fast Smoothing
- **1-second exponential moving average**: `smoothed = 0.7 × old + 0.3 × new`
- Stored in `sensor_1_smoothed` / `sensor_2_smoothed` globals
- Filters momentary spikes (single raindrops, insects, electrical noise)
- Still responsive to sustained changes (person walking)
- Visible as "Sensor 1/2 Moving Energy Smoothed" sensors
- Update rate: Every 1 second

### Stage 3: Baseline Tracking
- **15-second exponential moving average**: `baseline = 0.95 × old + 0.05 × new`
- Uses **smoothed values** as input (not raw)
- **Only updates when no person detected** (prevents person energy from polluting baseline)
- Takes ~5 minutes to fully adapt to weather changes
- Stored in `sensor_1_baseline` / `sensor_2_baseline` globals
- Visible as "Sensor 1/2 Baseline" sensors
- Update rate: Every 15 seconds (when safe)

### Detection Logic
- Uses **RAW values** for instant detection (via "fast" internal sensors that update every 200ms)
- Compares **current energy vs baseline** with adaptive thresholds:
  - `energy - baseline > 40%` → immediate detection
  - `energy - baseline > 25%` + moving target flag → confirmed person
  - `energy - baseline > 15%` + moving target flag → edge case catch
- `delayed_on: 1s` + `delayed_off: 5s` filters brief spikes at the binary sensor level

## Key Improvements

### Responsiveness
- Detection uses **RAW readings** → instant response when person appears
- No filter delays between sensor and detection logic
- "Fast" internal sensors update every 200ms for quick position tracking

### Spike Filtering
- **Momentary spikes** (single reading): Filtered by 1s smoothing, doesn't affect baseline
- **Brief events** (2-5 second gust of wind): Smoothed value rises but baseline doesn't shift
- **Sustained changes** (rain starting): Baseline adapts over 5+ minutes

### Adaptive Sensitivity
- **Calm/dry conditions**: Baseline ~2-8% → very sensitive to person
- **Light rain/wind**: Baseline ~10-25% → moderate sensitivity
- **Heavy weather**: Baseline ~25-40% → only triggers on clear person-sized targets

### Diagnostics
Users can now see all processing stages:
1. **RAW** - actual sensor output
2. **Smoothed** - after spike filtering
3. **Baseline** - long-term environmental average
4. **Path Person Detected** - final detection result

If enclosure is blocking signal, RAW will show it immediately (low values even when close).

## Migration Notes

### What Changed in YAML
1. **Removed** all filters from `moving_energy` sensors
2. **Changed** `on_raw_value` to `on_value` (captures actual published value)
3. **Added** two new globals: `sensor_1_smoothed`, `sensor_2_smoothed`
4. **Split** baseline update interval into two:
   - 1s interval for fast smoothing
   - 15s interval for baseline tracking (was 10s)
5. **Added** two new diagnostic sensors: "Moving Energy Smoothed"
6. **Updated** "fast" energy sensors to read from RAW globals instead of filtered sensors
7. **Lowered** initial baseline values from 10.0 to 5.0 (more appropriate starting point)

### What Didn't Change
- LD2410 sensor configuration (UART, pins, etc.)
- Binary sensor filters (`delayed_on`, `delayed_off`)
- Position tracking logic
- Light control automations
- Button controls (restart, factory reset)

### Expected Behaviour After Update
1. **First 5 minutes**: Baselines will adapt from initial 5% to actual environment
2. **RAW sensors should track actual conditions**: 0-5% calm, 10-30% light rain, 30-60% heavy rain/person
3. **Smoothed sensors lag RAW by 1-2 seconds** (expected)
4. **Baselines adapt very slowly** (5+ minutes to shift significantly)
5. **Detection should trigger on person** but not on brief rain spikes

### Troubleshooting
- If **RAW is low** (<10% even when walking close) → enclosure too thick
- If **Smoothed is stuck** → check logs for lambda errors
- If **Baseline is stuck** → person detection may always be ON (baseline only updates when clear)
- If **Too many false triggers** → increase detection deltas (currently 15/25/40%)
- If **Not detecting people** → decrease detection deltas or check enclosure

## Technical Reasoning

### Why Not Use ESPHome Filters?
The built-in filters (`sliding_window_moving_average`, `throttle_average`) were causing unexpected behaviour:
- Values were being clamped/rounded incorrectly
- No clear way to debug what the filter was outputting
- Couldn't separate "spike filtering" from "baseline tracking"
- Couldn't conditionally skip updates (baseline should freeze when person present)

### Why Lambda-based Smoothing?
Exponential moving averages in lambdas give us:
- **Full visibility** - can log intermediate values
- **Conditional logic** - baseline only updates when safe
- **Flexible timing** - different update rates for different purposes
- **Predictable behaviour** - no hidden rounding/clamping

### Why Three Stages?
- **RAW**: Essential for diagnosing hardware issues (enclosure blocking signal)
- **Smoothed**: Filters sensor noise without slowing detection
- **Baseline**: Long-term environmental average for adaptive thresholds

## Performance Impact
- **Memory**: Added 2 float globals (~8 bytes) - negligible
- **CPU**: Two additional interval callbacks - negligible on ESP32-C3
- **Network**: Two additional diagnostic sensors - minimal (~100 bytes every 1-5 seconds)
- **Logs**: No additional logging unless person detected

## Future Enhancements (Not Implemented Yet)
- **Auto-tuning detection thresholds** based on false positive rate
- **Different baselines for day/night** (nighttime might be quieter)
- **Sensor health monitoring** (detect if one sensor is malfunctioning)
- **Historical baseline tracking** (compare current baseline to yesterday's)

