# BedroomLights - Smart Button Controller

ESP32-C3 SuperMini button controller for bedroom lights with smart LED feedback.

## Hardware

- **Board**: ESP32-C3 SuperMini
- **Button**: GPIO8 (switch connects GPIO8 to GND)
- **LED**: GPIO9 → LED (with resistor) → GND

## Controlled Lights

- `light.bedroom_light` - RGB light with colour temperature control
- `light.bedroom_light_stand` - White bulb with adjustable colour temperature (2700K-5000K)

## Button Functions

The button operates in two distinct phases:

### Phase 1: Selection Phase (LED Full Bright)

During selection phase, single presses cycle through light states:
1. **Press 1**: Turn on `bedroom_light` only
2. **Press 2**: Turn on `bedroom_light_stand` (both lights now on)
3. **Press 3**: Turn off `bedroom_light` (stand remains on)
4. **Press 4**: Turn off `bedroom_light_stand` (both lights off)

**LED Behaviour**: Full brightness (100%) during selection
**Timer**: Each press restarts a 3-second timer

### Phase 2: Control Phase (LED Returns to Normal)

After 3 seconds of no activity, automatically enters Control Phase where:

**Single Tap**: Turn off all lights and return to selection phase
**Double Tap (within 1.2s)**: Cycle colours with smart syncing:
  - When only `bedroom_light` is on (state 1): Cycles through all 8 colours
  - When only `bedroom_light_stand` is on (state 3): Toggles between Warm/Daylight
  - When both lights are on (state 2): Syncs colours where possible

**Hold Button (600ms+)**: Cycle brightness through three levels (33%, 66%, 100%)
  - Continues cycling whilst held (every 1 second)

### Colour Modes

1. **Warm White** (2700K) - both lights
2. **Daylight** (5000K) - both lights
3. **Soft Red** - bedroom_light only, stand stays warm white
4. **Amber/Orange** - bedroom_light only, stand stays warm white
5. **Warm Purple** - bedroom_light only, stand stays warm white
6. **Soft Blue** - bedroom_light only, stand stays warm white
7. **Soft Green** - bedroom_light only, stand stays warm white
8. **Pink** - bedroom_light only, stand stays warm white

## Smart LED Feedback

### Phase-Based Brightness

**Selection Phase**:
- LED at **100%** brightness to indicate you're selecting lights

**Control Phase** (normal operation):
- **10%**: Both lights off
- **30%**: One light on  
- **60%**: Both lights on

### Bedtime Mode

When `binary_sensor.mama_s_mobile_is_charging` is `on` AND time is between 8pm-5am:
- LED brightness reduced to 30% of normal
- Provides gentle indicator without disturbing sleep

### Notification Pulse

When `sensor.mama_s_mobile_active_notification_count` > 0 AND time is after 5am:
- LED pulses gently (fade up 800ms, fade down 800ms, pause 400ms)
- Respects bedtime dimming if active
- Stops automatically when notification count returns to 0

## Network Configuration

- **Static IP**: 192.168.1.38
- **Gateway**: 192.168.1.1
- **WiFi Power**: 8.5dBm
- **Bluetooth Proxy**: Enabled (extends Home Assistant BLE range)

## Home Assistant Integration

The device exposes:
- `binary_sensor.light_control_button` - Button state
- `light.button_led` - Manual LED control (can override smart behaviour)

It subscribes to:
- `binary_sensor.mama_s_mobile_is_charging` - For bedtime detection
- `sensor.mama_s_mobile_active_notification_count` - For notification pulsing
- Home Assistant time - For time-based logic

## Notes

- All state tracking resets on device reboot
- LED can be manually controlled via Home Assistant if needed
- Logging enabled for debugging button behaviour
- Uses ESP-IDF framework for C3 compatibility

