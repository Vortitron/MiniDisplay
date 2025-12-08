# Adaptive Baseline with BLE Mode

## Overview

The BLE mode uses **Home Assistant's Statistics integration** to replicate the adaptive baseline behavior that was previously handled on the ESP32 in UART mode.

## How It Works

### 1. Statistics Sensors (The Baseline)

```yaml
sensor:
  - platform: statistics
    name: "FrontPath 7144 Motion Energy Avg"
    entity_id: sensor.hlk_ld2410_7144_motion_energy
    state_characteristic: mean
    sampling_size: 120
    max_age:
      minutes: 10
```

These sensors continuously track the **10-minute rolling average** of the motion energy from each LD2410 sensor. This creates an adaptive baseline that:

- **Adapts to weather**: If rain/wind picks up, the baseline slowly rises over 5-10 minutes
- **Ignores brief spikes**: A single gust won't shift the baseline significantly
- **Tracks daily patterns**: Gradual changes in environmental conditions are absorbed
- **Resets naturally**: When conditions calm down, the baseline drifts back down

### 2. Person Detection Logic

The template binary sensor compares **current energy vs. baseline**:

```yaml
{% set s1 = states('sensor.hlk_ld2410_7144_motion_energy') | float(0) %}
{% set base1 = states('sensor.frontpath_7144_motion_energy_avg') | float(s1) %}
{% set delta1 = s1 - base1 %}
```

A person is detected when:
- `delta >= margin` (default 22%) - current energy is significantly above the rolling average
- OR any gate shows `>= gate_floor` (default 18%) - strong localized spike

### 3. Key Differences from UART Mode

| Feature | UART Mode | BLE Mode |
|---------|-----------|----------|
| **Baseline calculation** | On ESP32 (lambda) | In Home Assistant (statistics) |
| **Update frequency** | Every 15s | Every sensor update (~1s) |
| **Sampling window** | Exponential moving avg | 120 samples, 10 min window |
| **Gate auto-calibration** | Yes (adjusts thresholds) | No (uses fixed margin) |
| **Person-aware updates** | Yes (freezes during detection) | No (always tracks mean) |

## Tuning for Your Environment

### If You Get False Triggers (Wind/Rain)

1. **Increase Energy Margin**: 
   - Settings → Helpers → `Front Path Energy Margin`
   - Increase from 22% to 30-40%
   - This requires a bigger spike above baseline to trigger

2. **Increase Gate Trigger Floor**:
   - Settings → Helpers → `Front Path Gate Trigger Floor`
   - Increase from 18% to 25-35%
   - This ignores weaker localized spikes

3. **Increase Statistics Window**:
   - Edit `frontpath_lights_automations.yaml`
   - Change `sampling_size: 120` to `240` (20 min baseline)
   - Slower adaptation, more stable

### If You Miss People Walking

1. **Decrease Energy Margin**:
   - Settings → Helpers → `Front Path Energy Margin`
   - Decrease from 22% to 15-18%

2. **Decrease Gate Trigger Floor**:
   - Settings → Helpers → `Front Path Gate Trigger Floor`
   - Decrease from 18% to 12-15%

3. **Check Sensor Positioning**:
   - Look at Developer Tools → States
   - Search for `sensor.hlk_ld2410_*_motion_energy_gate_*`
   - Walk the path and see which gates light up
   - If gates stay low (<15%), you may have a sensor angle/enclosure issue

## Monitoring the Adaptive Baseline

### Key Entities to Watch

1. **Current Energy** (instant reading):
   - `sensor.hlk_ld2410_7144_motion_energy`
   - `sensor.hlk_ld2410_6602_motion_energy`
   - Should spike when you walk by (30-60%)

2. **Baseline** (10-minute average):
   - `sensor.frontpath_7144_motion_energy_avg`
   - `sensor.frontpath_6602_motion_energy_avg`
   - Should be low in calm conditions (5-15%), higher in wind/rain (15-35%)

3. **Detection Status**:
   - `binary_sensor.frontpath_path_person_detected`
   - Should turn ON when you walk, stay OFF in calm conditions

4. **Per-Gate Energy**:
   - `sensor.hlk_ld2410_7144_motion_energy_gate_0` through `gate_6`
   - Shows which distance zones are active

### Creating Debug Cards

Add to your dashboard to monitor the system:

```yaml
type: entities
title: FrontPath Adaptive Baseline
entities:
  - entity: sensor.hlk_ld2410_7144_motion_energy
    name: "Sensor 1 Current"
  - entity: sensor.frontpath_7144_motion_energy_avg
    name: "Sensor 1 Baseline"
  - entity: sensor.hlk_ld2410_6602_motion_energy
    name: "Sensor 2 Current"
  - entity: sensor.frontpath_6602_motion_energy_avg
    name: "Sensor 2 Baseline"
  - entity: binary_sensor.frontpath_path_person_detected
  - entity: sensor.frontpath_path_person_position
  - entity: input_number.frontpath_energy_margin
  - entity: input_number.frontpath_gate_trigger_floor
```

### Understanding the Numbers

**Calm, clear day:**
- Current: 3-8%
- Baseline: 5-10%
- Delta: -2% to +3% (no detection)

**Light breeze:**
- Current: 8-15%
- Baseline: 10-18%
- Delta: -2% to +5% (occasional false triggers possible)

**Person walking:**
- Current: 30-70%
- Baseline: 10-18% (unchanged during walk)
- Delta: +20% to +60% (clear detection)

**Windy/rainy:**
- Current: 15-40% (spikes to 60%)
- Baseline: 20-35% (adapts over 10 mins)
- Delta: -5% to +25% (reduces false triggers as baseline rises)

## Advanced: Improving Baseline Tracking

If you want the baseline to **freeze when a person is detected** (like UART mode), you can create a more sophisticated template:

```yaml
template:
  - trigger:
      - platform: state
        entity_id: sensor.hlk_ld2410_7144_motion_energy
      - platform: time_pattern
        seconds: "/15"
    sensor:
      - name: "FrontPath 7144 Adaptive Baseline"
        unique_id: frontpath_7144_adaptive_baseline
        unit_of_measurement: "%"
        state: >
          {% set current = states('sensor.hlk_ld2410_7144_motion_energy') | float(5) %}
          {% set old_baseline = states('sensor.frontpath_7144_adaptive_baseline') | float(5) %}
          {% set person = is_state('binary_sensor.frontpath_path_person_detected', 'on') %}
          
          {# Only update baseline when no person detected #}
          {% if person %}
            {{ old_baseline }}
          {% else %}
            {# Exponential moving average: 95% old + 5% new #}
            {{ (0.95 * old_baseline + 0.05 * current) | round(1) }}
          {% endif %}
```

Then update the detection template to use `sensor.frontpath_7144_adaptive_baseline` instead of the statistics sensor.

## Comparison: UART vs BLE Adaptive Baseline

### UART Mode Advantages
- ✅ Gate auto-calibration (adjusts per-gate thresholds automatically)
- ✅ Freezes baseline during person detection
- ✅ All logic on ESP32 (no HA dependency for detection)
- ✅ Per-gate threshold tuning built-in

### BLE Mode Advantages
- ✅ All BLE sensors available (can see individual gate energies in HA)
- ✅ Full control over detection logic in HA (no reflashing needed)
- ✅ Easier to debug (see all values in real-time in HA UI)
- ✅ Can create multiple detection zones/automations with same data
- ✅ No UART conflicts (can use BLE config tool anytime)

### Recommended Approach

For most users, the **statistics-based baseline** (current implementation) works well:
- Automatically adapts to weather over 5-10 minutes
- Simple to tune via HA helpers
- Minimal template complexity

If you experience frequent false triggers in challenging weather:
1. First try increasing the margin/floor helpers
2. If that doesn't help, implement the "freeze on person" template above
3. As a last resort, consider switching back to UART mode if you need aggressive auto-calibration

## Troubleshooting

### "Statistics sensor shows 'unknown'"
- **Cause**: Not enough data yet (needs 2-5 minutes after restart)
- **Fix**: Wait 5 minutes, or adjust `sampling_size` to a lower value (e.g., 30)

### "Baseline doesn't seem to adapt"
- **Cause**: `max_age` might be too short, or statistics integration not enabled
- **Fix**: Check Configuration → Logs for statistics errors, increase `max_age` to 30 minutes

### "Person detection is too slow to trigger"
- **Cause**: Statistics sensor updates slowly
- **Fix**: Detection uses raw energy (instant), not baseline, so this shouldn't happen. Check gate energies.

### "Lights don't turn on when dark"
- **Cause**: Darkness detection may be too strict
- **Fix**: 
  - Check `sensor.frontpath_light_level` (should be <32% when dark)
  - Adjust `input_number.frontpath_darkness_threshold_pct`
  - Verify `binary_sensor.frontpath_path_is_dark` is ON when you expect lights

## Next Steps

1. **Monitor for 24 hours**: Watch how the baseline adapts through day/night and weather changes
2. **Tune margins**: Adjust `energy_margin` and `gate_trigger_floor` based on false positive rate
3. **Test edge cases**: Walk the path in rain, at different times, to verify detection
4. **Consider seasonal adjustments**: You might want different margins in winter (windy) vs summer (calm)

