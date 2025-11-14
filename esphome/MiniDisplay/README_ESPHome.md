# MiniDisplay ESPHome Migration

This document describes how to migrate your MiniDisplay controller from Arduino to ESPHome.

## What Has Changed

### Color Temperature Support ✅
- Added proper color temperature control for lights (153-500 mireds / 6500K-2000K)
- Updated color definitions to include Warm White, Cool White, and Daylight options
- Added color temperature adjustment controls via rotary encoder and buttons

### ESPHome Migration ✅
- Complete ESPHome configuration with all original features
- **Direct Home Assistant API Integration** - No more MQTT or Node-RED needed!
- Bluetooth proxy functionality for BTLE devices
- Improved entity management with state tracking
- Enhanced display logic with weather information

### Key Advantage: No More Node-RED! 🎉
- **Direct API Control**: ESPHome communicates directly with Home Assistant
- **Simplified Setup**: No complex MQTT automation flows required
- **Better Reliability**: Direct API calls are more reliable than MQTT parsing
- **Real-time State**: Entity states are read directly from Home Assistant

## Files Modified

### `controller.ino` - Color Temperature Support
- Updated color definitions to include color temperature values
- Added color temperature MQTT topics (`color_temp`)
- Enhanced knob and button controls for color temperature adjustment
- Updated display to show color temperature information

### `minidisplay.yaml` - New ESPHome Configuration
- Complete ESPHome configuration with all features
- Bluetooth proxy for BTLE devices
- Weather display functionality
- Entity management and state tracking
- GPIO pin definitions for all controls

## Setup Instructions

### 1. Install ESPHome
```bash
pip install esphome
```

### 2. Configure Secrets
Create a `secrets.yaml` file in your ESPHome directory:

```yaml
wifi_ssid: "YourWiFiSSID"
wifi_password: "YourWiFiPassword"
```

### 3. Update Entity Names
Update the entity names in `minidisplay.yaml` to match your Home Assistant entities:

- **Home Assistant Sensors**: Update the `entity_id` fields in the `homeassistant` sensors (lines ~274-423)
- **Service Calls**: Update the entity IDs in the control scripts (lines ~511-628)

Example changes needed:
- `light.gold_light` → Your actual light entity ID
- `media_player.lgnano_55` → Your actual media player entity ID
- `climate.sam` → Your actual climate entity ID
- `input_number.sam_desired_temperature` → Your actual climate setpoint entity ID
- `switch.smart_plug_2_socket_1` → Your actual hot water switch entity ID

### 4. Flash the Device
```bash
esphome run minidisplay.yaml
```

## Major Improvement: Direct Home Assistant API

### What Changed
- **Removed all MQTT-based entities** (light, media_player, climate platforms)
- **Added Home Assistant sensors** to read entity states directly
- **Created API control scripts** that call Home Assistant services directly
- **Eliminated Node-RED dependency** - no more complex automation flows!

### Benefits
1. **Simpler Setup**: No MQTT broker configuration needed
2. **Better Reliability**: Direct API calls are more reliable than MQTT parsing
3. **Real-time Updates**: Entity states are read directly from Home Assistant
4. **No Node-RED Required**: ESPHome handles all the logic internally
5. **Native Integration**: Uses Home Assistant's built-in service calls

## New Features

### Color Temperature Control
- **White Mode**: Pure white (no color temperature)
- **Warm White**: 3700K (cozy lighting)
- **Cool White**: 5000K (bright white)
- **Daylight**: 6500K (natural daylight)

### Weather Display
- Alternates between entity control and weather information
- Shows indoor/outdoor temperature and humidity
- Updates every 10 seconds when idle

### Bluetooth Proxy
- Acts as a Bluetooth proxy for Home Assistant
- Supports up to 2 simultaneous connections
- Enables control of BTLE devices through Home Assistant

### Alarm Notifications and LED Alerts
- Active Home Assistant persistent notifications appear as individual screens after the standard entity list.
- Each notification is queried directly from Home Assistant, so title and message are always current.
- Rotate to choose a notification; push the encoder to dismiss it immediately.
- `input_select.alarm_level` drives the onboard LED behaviour: steady on (OK), single 300 ms flash every minute (Notify), double flash every 15 seconds (Take Action), and continuous quick flashing (Emergency).
- Notification IDs flow through `input_text.minidisplay_notification_ids` (comma-separated list, 255 char limit).

## Control Mapping

| Control | Function |
|---------|----------|
| **Rotary Encoder** | Adjust brightness (lights) / volume (media) / temperature (climate) |
| **Encoder Push** | Toggle entity on/off or dismiss the selected notification |
| **Button** | Adjust values in larger increments |
| **Back Button** | Cycle colors (lights) / cycle TV sources (media) / toggle (hot water) |
| **Left Button** | Switch between entities |

## Entity Structure (7 Entities)

The controller cycles through 7 different entities:

1. **Gold Light** - Light control with brightness and full color cycling
2. **Living Room Flood** - Light control with brightness and full color cycling
3. **Bio Floodlight** - Light control with brightness and full color cycling
4. **LG Nano 55** - Media player volume control and TV source cycling
5. **LG Nano 55** - Media player volume control and TV source cycling (same entity)
6. **Sam HVAC** - Climate temperature setpoint control
7. **Hot Water** - Smart plug on/off toggle control

## Light Color Options

The back button cycles through all available color options for lights:

1. **Red** - HS color (hue: 0°, saturation: 100%)
2. **Green** - HS color (hue: 120°, saturation: 100%)
3. **Blue** - HS color (hue: 240°, saturation: 100%)
4. **Yellow** - HS color (hue: 60°, saturation: 100%)
5. **Magenta** - HS color (hue: 300°, saturation: 100%)
6. **Cyan** - HS color (hue: 180°, saturation: 100%)
7. **White** - HS color (hue: 0°, saturation: 0%)
8. **Warm White** - Color temperature (3700K)
9. **Cool White** - Color temperature (5000K)
10. **Daylight** - Color temperature (6500K)

## TV Sources Available

The media player can cycle through these 11 TV sources:

1. **Disney+**
2. **Jellyfin**
3. **Max**
4. **Netflix**
5. **Prime Video**
6. **Roku**
7. **SVT Play**
8. **TV4 Play**
9. **Telia Play**
10. **YouTube**
11. **HDMI 3**

## How Direct API Control Works

### Before (Arduino + Node-RED)
1. ESP32 sends MQTT messages to broker
2. Node-RED parses MQTT messages
3. Node-RED calls Home Assistant services
4. Home Assistant updates entities
5. Complex automation flows required

### After (ESPHome Direct API)
1. ESP32 calls Home Assistant services directly
2. Home Assistant updates entities immediately
3. ESP32 reads entity states directly from Home Assistant
4. No intermediate steps or parsing needed

### Example API Calls
- **Light Control**: `light.gold_light.turn_on({"brightness": 128, "color_temp": 270})`
- **Media Volume**: `media_player.lgnano_55.volume_set({"volume_level": 0.5})`
- **Climate Setpoint**: `input_number.set_value({"entity_id": "input_number.sam_desired_temperature", "value": 22.0})`
- **Hot Water Control**: `switch.turn_on({"entity_id": "switch.smart_plug_2_socket_1"})`

## Migration Benefits

1. **Native Home Assistant Integration** - No more MQTT message parsing
2. **Bluetooth Proxy** - Control BTLE devices
3. **Better State Management** - Persistent state across reboots
4. **Improved Reliability** - ESPHome's proven stability
5. **Easier Updates** - OTA updates through ESPHome
6. **Weather Display** - Built-in weather information display

## Limitations

- Weather animations are simplified (text-based instead of graphical)
- Some advanced computer control features may need adjustment
- Display logic is more basic than the original WeatherAnimations library

## Troubleshooting

### Display Not Showing
1. Check I2C pin connections (SDA: GPIO21, SCL: GPIO22)
2. Verify OLED address (0x3C)
3. Check display power connections

### Controls Not Working
1. Verify GPIO pin assignments
2. Check pull-up resistors on button inputs
3. Ensure rotary encoder pins are correctly connected

### Weather Data Not Showing
1. Verify Home Assistant sensor entity IDs
2. Check Home Assistant API connectivity
3. Ensure proper permissions for the ESPHome device

## Original Arduino Code

The original `controller.ino` has been enhanced with color temperature support and can still be used if you prefer to stay with the Arduino implementation. The ESPHome version provides the same functionality with additional features.
