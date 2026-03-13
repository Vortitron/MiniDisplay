# BedroomLights - Smart Button Controller

ESP32-C3 SuperMini button controller for bedroom lights with smart LED feedback.

## Hardware

- **Board**: ESP32-C3 SuperMini
- **Button**: GPIO8 (switch connects GPIO8 to GND)
- **LED**: GPIO9 → LED (with resistor) → GND
- **Environmental sensor (optional)**: AHT20 + BMP280 combo board wired to the I²C bus  
  - Pin order on sensor (flipped): VDD, SDA, GND, SCL  
  - `VDD` → 3V3 on the SuperMini (right-hand side)
  - `SDA` → GPIO21 (right-hand "5-21" side)  
  - `GND` → jumper wire to any GND pad  
  - `SCL` → GPIO20 (right-hand "5-21" side)  
  - **Note**: GPIO0/GPIO1 cannot be used - they're strapping pins that prevent WiFi from initialising

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

### Per-Light Colour Memory

- `bedroom_light` and `bedroom_light_stand` now persist their most recent colour index (stored in `bedroom_colour_index` / `stand_colour_index` with `restore_value: true`), so toggling a light off/on via the latching switches restores the last hue or kelvin without resetting to 2700K.
- When both lights are on, the stand automatically holds **Warm White** whilst the RGB light cycles through colour indices 4-9, keeping the room lighting balanced.
- Cycling colours whilst a light is off leaves its stored index untouched, so you can park `bedroom_light` on pink, turn it off, adjust the stand, and when you next enable the RGB light it will still come back on in pink.

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

### Preconnect Pulse (Disabled)

- The earlier boot/reconnect LED pulsing routine has been removed because it occasionally latched “on” when Home Assistant lagged, leading to distracting flashes.
- On boot we now simply wait for the usual HA state callbacks; the switches, LEDs and momentary button remain immediately usable.

### Dusk-Friendly Brightness Cap

- `switch_led_day_on_level` sets the maximum indicator brightness (default `1.0` → 100% PWM).
- Between 18:00 and 06:00 the cap automatically halves to `switch_led_night_on_level` (default `0.5`) so the hallway isn’t flooded with light overnight.
- Update the substitutions at the top of `BedroomLights.yaml` if you’d like a different day cap or deeper night dimming.

### Pending Command Pulse

- Whenever a latching switch is pressed or released, the firmware compares the requested light state with the latest Home Assistant state.
- There are now three feedback patterns so you can distinguish where the command stalled:
  - **Waiting for acknowledgement**: normal pulse between `switch_led_pending_low_ratio` and full cap.
  - **Cannot send to Home Assistant**: rapid double blink (HA API disconnected).
  - **No acknowledgement timeout**: slow-low + short-high pattern after `switch_command_ack_timeout_ms` (default 8000 ms), usually meaning HA accepted the call but the light state did not converge.
- The pulse stops automatically once HA confirms the requested state, and it also suspends manual LED overrides so feedback stays truthful.
- Timing knobs are exposed in `BedroomLights.yaml` substitutions: `switch_led_pending_step`, `switch_led_ha_error_on_step`, `switch_led_ha_error_off_step`, `switch_led_ha_error_pause_step`, `switch_led_bulb_timeout_low_ratio`, `switch_led_bulb_timeout_low_step`, `switch_led_bulb_timeout_high_step`, and `switch_command_ack_timeout_ms`.

## Network Configuration

- **Static IP**: 192.168.1.38
- **Gateway**: 192.168.1.1
- **WiFi Power**: 8.5dBm
- **Bluetooth Proxy**: Enabled (extends Home Assistant BLE range)

## Home Assistant Integration

The device exposes:
- `binary_sensor.light_control_button` - Button state
- `light.button_led` - Manual LED control (can override smart behaviour)
- `sensor.bedroomlights_temperature` (AHT20)
- `sensor.bedroomlights_humidity` (AHT20)
- `sensor.bedroomlights_barometric_temperature` (BMP280)
- `sensor.bedroomlights_pressure` (BMP280)

It subscribes to:
- `binary_sensor.mama_s_mobile_is_charging` - For bedtime detection
- `sensor.mama_s_mobile_active_notification_count` - For notification pulsing
- Home Assistant time - For time-based logic

## Notes

- All state tracking resets on device reboot
- LED can be manually controlled via Home Assistant if needed
- Logging enabled for debugging button behaviour
- Uses ESP-IDF framework for C3 compatibility

## Switch Reliability Guard

- Both latching switches route through `command_stand_light` / `command_bedroom_light` scripts (`mode: single`) which inline the `homeassistant.service` call directly so it cannot be killed mid-flight.
- Each switch interaction launches a `guard_*_switch_alignment` script which, for 8 x 500 ms (currently 4 s), re-checks the Home Assistant light state and re-sends the command **only if no command is already pending** -- this prevents the guard from interrupting an in-flight service call.
- Guard activity is logged under the `switch_guard` tag, making it easy to correlate with any observed bounce in the ESPHome logs.
- Adjust the guard timing via the `substitutions` block at the top of `BedroomLights.yaml` if the hardware ever needs a longer or shorter stabilisation window.

### Previous Bug (Fixed)

The command scripts were previously `mode: restart` and delegated to `set_stand_light_colour` / `set_bedroom_light_colour` (also `mode: restart`) via `.execute()`.  The guard would re-call the command script every 500 ms, which restarted the entire chain -- killing the `homeassistant.service` action before it could complete.  This caused the lights to appear unresponsive even though HA was connected and reachable.

