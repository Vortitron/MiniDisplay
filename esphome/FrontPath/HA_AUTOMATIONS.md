# Home Assistant Automation Examples for FrontPath BLE

This document provides example automations for the FrontPath BLE setup. All detection logic runs in Home Assistant, giving you full flexibility to customise behaviour.

## Basic Path Lighting Automation

Turn on path lights when person detected and it's dark:

```yaml
automation:
  - id: frontpath_lights_on
    alias: "FrontPath - Lights On When Person Detected"
    trigger:
      - platform: state
        entity_id:
          - binary_sensor.ld2410_b8be517d7144_has_moving_target  # Sensor 1
          - binary_sensor.ld2410_14aa8c586602_has_moving_target  # Sensor 2
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.front_path_lights
        data:
          brightness_pct: 100
      # Optional: Turn on ESP32 LED for visual feedback
      - service: esphome.frontpath_person_indicator_led_turn_on

  - id: frontpath_lights_off
    alias: "FrontPath - Lights Off After Timeout"
    trigger:
      - platform: state
        entity_id:
          - binary_sensor.ld2410_b8be517d7144_has_moving_target
          - binary_sensor.ld2410_14aa8c586602_has_moving_target
        to: "off"
        for:
          seconds: 30  # Keep lights on for 30s after last movement
    action:
      - service: light.turn_off
        target:
          entity_id: light.front_path_lights
      - service: esphome.frontpath_person_indicator_led_turn_off
```

## Direction-Based Lighting

Light up different sections based on which sensor detects movement:

```yaml
automation:
  - id: frontpath_sensor1_detected
    alias: "FrontPath - Sensor 1 Side (Towards House)"
    trigger:
      - platform: state
        entity_id: binary_sensor.ld2410_b8be517d7144_has_moving_target
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
    action:
      # Light up house-side of path first
      - service: light.turn_on
        target:
          entity_id: light.path_section_house
        data:
          brightness_pct: 100
      - delay:
          seconds: 1
      # Then light up middle section
      - service: light.turn_on
        target:
          entity_id: light.path_section_middle
        data:
          brightness_pct: 80

  - id: frontpath_sensor2_detected
    alias: "FrontPath - Sensor 2 Side (Away from House)"
    trigger:
      - platform: state
        entity_id: binary_sensor.ld2410_14aa8c586602_has_moving_target
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
    action:
      # Light up far end first
      - service: light.turn_on
        target:
          entity_id: light.path_section_far
        data:
          brightness_pct: 100
      - delay:
          seconds: 1
      # Then light up middle section
      - service: light.turn_on
        target:
          entity_id: light.path_section_middle
        data:
          brightness_pct: 80
```

## Energy-Based Detection (Adaptive Threshold)

Use energy levels for more sophisticated detection:

```yaml
automation:
  - id: frontpath_person_detected_energy
    alias: "FrontPath - Person Detected (Energy-Based)"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ld2410_b8be517d7144_moving_energy
        above: 40  # Adjust based on your environment
      - platform: numeric_state
        entity_id: sensor.ld2410_14aa8c586602_moving_energy
        above: 40
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
      # Optional: Require moving target confirmation
      - condition: or
        conditions:
          - condition: state
            entity_id: binary_sensor.ld2410_b8be517d7144_has_moving_target
            state: "on"
          - condition: state
            entity_id: binary_sensor.ld2410_14aa8c586602_has_moving_target
            state: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.front_path_lights
        data:
          brightness_pct: 100
```

## Template Sensor for Combined Detection

Create a helper sensor that combines both sensors with logic:

```yaml
template:
  - binary_sensor:
      - name: "FrontPath Person Detected"
        unique_id: frontpath_person_detected
        device_class: occupancy
        state: >
          {% set s1_moving = is_state('binary_sensor.ld2410_b8be517d7144_has_moving_target', 'on') %}
          {% set s2_moving = is_state('binary_sensor.ld2410_14aa8c586602_has_moving_target', 'on') %}
          {% set s1_energy = states('sensor.ld2410_b8be517d7144_moving_energy') | float(0) %}
          {% set s2_energy = states('sensor.ld2410_14aa8c586602_moving_energy') | float(0) %}
          
          {# Person detected if: #}
          {# - Moving target AND energy > 30% #}
          {# - OR energy > 50% (strong signal even without movement flag) #}
          {{ (s1_moving and s1_energy > 30) or 
             (s2_moving and s2_energy > 30) or 
             s1_energy > 50 or 
             s2_energy > 50 }}
        delay_on: "00:00:01.5"  # 1.5 second delay to filter false triggers
        delay_off: "00:00:05"    # 5 second delay to keep detection active
```

Then use this combined sensor in automations:

```yaml
automation:
  - id: frontpath_combined_detection
    alias: "FrontPath - Combined Person Detection"
    trigger:
      - platform: state
        entity_id: binary_sensor.frontpath_person_detected
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.front_path_lights
```

## Notification on Sensor Disconnection

Get notified if sensors stop working:

```yaml
automation:
  - id: frontpath_sensor_offline_alert
    alias: "FrontPath - Sensor Offline Alert"
    trigger:
      - platform: state
        entity_id:
          - binary_sensor.frontpath_ld2410_sensor_1_ble_connected
          - binary_sensor.frontpath_ld2410_sensor_2_ble_connected
        to: "off"
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "FrontPath Sensor Offline"
          message: >
            {{ trigger.to_state.attributes.friendly_name }} has been offline for 5 minutes.
            Status: {{ states('text_sensor.frontpath_ld2410_sensor_1_ble_status') }}
```

## Adaptive Baseline Tracking (Advanced)

Replicate the UART config's adaptive baseline logic in HA:

```yaml
template:
  - sensor:
      - name: "FrontPath Sensor 1 Baseline"
        unique_id: frontpath_sensor1_baseline
        unit_of_measurement: "%"
        state_class: measurement
        state: >
          {% set current = states('sensor.ld2410_b8be517d7144_moving_energy') | float(5) %}
          {% set baseline = states('sensor.frontpath_sensor1_baseline') | float(5) %}
          {% set person = is_state('binary_sensor.frontpath_person_detected', 'on') %}
          
          {# Only update baseline when no person detected #}
          {% if not person %}
            {# Very slow adaptation: 95% old + 5% new #}
            {{ (0.95 * baseline + 0.05 * current) | round(1) }}
          {% else %}
            {{ baseline }}
          {% endif %}
        availability: >
          {{ has_value('sensor.ld2410_b8be517d7144_moving_energy') }}

      - name: "FrontPath Sensor 1 Above Baseline"
        unique_id: frontpath_sensor1_above_baseline
        unit_of_measurement: "%"
        state: >
          {% set current = states('sensor.ld2410_b8be517d7144_moving_energy') | float(0) %}
          {% set baseline = states('sensor.frontpath_sensor1_baseline') | float(5) %}
          {{ (current - baseline) | round(1) }}
```

Then use the "above baseline" sensor for detection:

```yaml
automation:
  - id: frontpath_adaptive_detection
    alias: "FrontPath - Adaptive Baseline Detection"
    trigger:
      - platform: numeric_state
        entity_id: sensor.frontpath_sensor1_above_baseline
        above: 25  # 25% above baseline = person
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.front_path_lights
```

## Distance-Based Actions

Use distance sensors for progressive lighting:

```yaml
automation:
  - id: frontpath_distance_progressive
    alias: "FrontPath - Progressive Lighting by Distance"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ld2410_b8be517d7144_moving_distance
        below: 600  # 6 metres
    condition:
      - condition: state
        entity_id: binary_sensor.frontpath_path_is_dark
        state: "on"
    action:
      - choose:
          # Very close (0-2m) - full brightness
          - conditions:
              - condition: numeric_state
                entity_id: sensor.ld2410_b8be517d7144_moving_distance
                below: 200
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.front_path_lights
                data:
                  brightness_pct: 100
          
          # Medium distance (2-4m) - 70% brightness
          - conditions:
              - condition: numeric_state
                entity_id: sensor.ld2410_b8be517d7144_moving_distance
                below: 400
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.front_path_lights
                data:
                  brightness_pct: 70
          
          # Far distance (4-6m) - 40% brightness
          - conditions:
              - condition: numeric_state
                entity_id: sensor.ld2410_b8be517d7144_moving_distance
                below: 600
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.front_path_lights
                data:
                  brightness_pct: 40
```

## Tips for Tuning

### Reducing False Triggers

1. **Increase energy threshold**: Change `above: 40` to `above: 50` or higher
2. **Add delay_on**: Use `delay_on: "00:00:02"` in template sensors
3. **Require moving target**: Add condition checking `has_moving_target` is on
4. **Combine multiple conditions**: Require both energy AND movement

### Improving Sensitivity

1. **Lower energy threshold**: Change `above: 40` to `above: 30`
2. **Reduce delay_on**: Use shorter delays like `delay_on: "00:00:01"`
3. **Use OR logic**: Trigger on either sensor detecting movement
4. **Monitor energy levels**: Watch the energy sensors to find good thresholds

### Weather Adaptation

Create input numbers in HA to adjust thresholds dynamically:

```yaml
input_number:
  frontpath_energy_threshold:
    name: FrontPath Energy Threshold
    min: 20
    max: 80
    step: 5
    initial: 40
    unit_of_measurement: "%"
```

Then reference in automations:

```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.ld2410_b8be517d7144_moving_energy
    above: input_number.frontpath_energy_threshold
```

Adjust the threshold higher during windy/rainy weather, lower during calm conditions.

## Entity ID Reference

**Note:** The LD2410 sensor entity IDs will include their MAC addresses. Replace these examples with your actual entity IDs:

- Sensor 1 (B8:BE:51:7D:71:44): `ld2410_b8be517d7144_*`
- Sensor 2 (14:AA:8C:58:66:02): `ld2410_14aa8c586602_*`

Check **Settings → Devices & Services → LD2410 BLE** to find your exact entity IDs.

