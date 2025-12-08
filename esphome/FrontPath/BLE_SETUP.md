# FrontPath BLE Setup Guide

## Overview

This configuration uses the ESP32-C3 as a **Bluetooth Proxy** to extend Home Assistant's BLE range. The LD2410 sensors communicate directly with Home Assistant via Bluetooth, and all detection logic runs in HA automations.

## Hardware Configuration

**ESP32-C3 SuperMini:**
- Acts as BLE proxy (extends HA's Bluetooth range)
- TEMT6000 light sensor on GPIO0
- Onboard LED on GPIO8 (controllable from HA)
- WiFi connectivity to Home Assistant

**LD2410 Sensors:**
- **Sensor 1**: `B8:BE:51:7D:71:44` (points towards house/door)
- **Sensor 2**: `14:AA:8C:58:66:02` (points away from house)
- Both powered by ESP32 (5V) but communicate via BLE
- No UART connections needed

## Wiring

### TEMT6000 Light Sensor
| TEMT6000 Pin | ESP32-C3 Pin | Function |
|--------------|--------------|----------|
| VCC          | 5V           | Power    |
| GND          | GND          | Ground   |
| OUT (SIG)    | GPIO0        | Analog output |

### LD2410 Sensors (Power Only)
| LD2410 Pin | ESP32-C3 Pin | Function |
|------------|--------------|----------|
| VCC        | 5V           | Power    |
| GND        | GND          | Ground   |
| TX         | Not connected | BLE mode |
| RX         | Not connected | BLE mode |

**Important:** Do NOT connect the TX/RX pins. The sensors will automatically broadcast BLE when UART is not connected.

## Setup Steps

### 1. Flash the Configuration

```bash
cd esphome/FrontPath
esphome run FrontPath.yaml
```

### 2. Verify BLE Advertisements

After flashing, check the ESPHome logs:
- You should see "Sensor 1/2 advertisements resumed" messages
- The sensors will show as "Connected" in HA

### 3. Add LD2410 Integration in Home Assistant

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for "LD2410 BLE"
4. Home Assistant should auto-discover both sensors
5. Add each sensor (they'll appear with their MAC addresses)

### 4. Configure Sensors (Optional)

You can configure the LD2410 sensors using:
- **Home Assistant UI**: Once integrated, sensor settings appear in the device page
- **HLKRadarTool Android App**: Connect directly to sensors via BLE

**Recommended Settings for 12m Outdoor Path:**
- Max Move Distance Gate: **6-8** (covers ~4.5-6m per sensor)
- Max Still Distance Gate: **3-4** (still detection unreliable outdoors)
- Timeout: **3-5 seconds**

## Available Entities in Home Assistant

### From ESP32 (FrontPath device)

**Binary Sensors:**
- `binary_sensor.frontpath_ld2410_sensor_1_ble_connected` - Sensor 1 connectivity
- `binary_sensor.frontpath_ld2410_sensor_2_ble_connected` - Sensor 2 connectivity
- `binary_sensor.frontpath_path_is_dark` - Darkness detection (based on light sensor)

**Sensors:**
- `sensor.frontpath_light_level` - Light level (0-100%)
- `sensor.frontpath_light_level_voltage` - Raw voltage from TEMT6000
- `sensor.frontpath_wifi_signal_db` - WiFi signal strength

**Text Sensors:**
- `text_sensor.frontpath_ld2410_sensor_1_ble_status` - Sensor 1 status message
- `text_sensor.frontpath_ld2410_sensor_2_ble_status` - Sensor 2 status message
- `text_sensor.frontpath_frontpath_mode` - Shows "BLE Proxy Mode"

**Number Controls:**
- `number.frontpath_darkness_threshold` - Adjust darkness threshold (0-100%)

**Output:**
- `output.frontpath_person_indicator_led` - Onboard LED (controllable from automations)

### From LD2410 Sensors (via BLE)

Each sensor provides (names will include MAC address):

**Binary Sensors:**
- `has_target` - Any presence detected
- `has_moving_target` - Moving target detected
- `has_still_target` - Still target detected

**Sensors:**
- `moving_distance` - Distance to moving target (cm)
- `still_distance` - Distance to still target (cm)
- `moving_energy` - Moving target signal strength (0-100%)
- `still_energy` - Still target signal strength (0-100%)
- `detection_distance` - Overall detection distance

**Number Controls:**
- `max_move_distance_gate` - Maximum detection range for movement (0-8 gates)
- `max_still_distance_gate` - Maximum detection range for still targets (0-8 gates)
- `timeout` - How long to keep detection active after target lost (seconds)
- Per-gate thresholds (g0-g8) for fine-tuning sensitivity

## Troubleshooting

### Sensors Not Appearing in HA

1. **Check BLE advertisements:**
   - View ESPHome logs: `esphome logs FrontPath.yaml`
   - Look for "Sensor 1/2 advertisements resumed" messages
   - If not appearing, sensors may still be in UART mode

2. **Force BLE mode:**
   - Disconnect TX/RX pins completely
   - Power cycle the sensors (disconnect 5V for 10 seconds)
   - Sensors should start broadcasting BLE automatically

3. **Check Bluetooth Proxy:**
   - Verify `binary_sensor.frontpath_ld2410_sensor_1_ble_connected` shows "Connected"
   - If "Never seen", the sensor isn't broadcasting BLE

### Poor BLE Range

- The ESP32 acts as a range extender for HA
- Ensure ESP32 is within ~5-10m of the sensors
- Check WiFi signal strength (`sensor.frontpath_wifi_signal_db`)
- Consider adding more Bluetooth proxies if needed

### Sensors Keep Disconnecting

- Check the status sensors: they show time since last advertisement
- "Missing X min" = temporary loss (may reconnect)
- "Stale X min" = likely needs intervention
- Try power cycling the sensors

### Light Sensor Not Working

- Check `sensor.frontpath_light_level_voltage`:
  - Should vary between ~0V (dark) and ~3.3V (bright)
  - If stuck at 3.3V: sensor saturated or wiring issue
  - If stuck at 0V: no power or bad connection
- Adjust `number.frontpath_darkness_threshold` to tune darkness detection

## Advantages of BLE Mode

✅ **No UART conflicts** - All GPIO pins available for other uses  
✅ **Direct HA integration** - Sensors appear as native HA devices  
✅ **Better diagnostics** - Full sensor data visible in HA  
✅ **Easier configuration** - Adjust settings via HA UI  
✅ **Range extension** - ESP32 acts as BLE proxy  
✅ **Simpler code** - No complex on-device logic needed  

## Reverting to UART Mode

If BLE mode doesn't work well, you can revert:

1. Flash `FrontPathUART.yaml` (backup of original UART config)
2. Reconnect TX/RX pins to sensors
3. Sensors will automatically switch back to UART mode

The UART configuration includes all the adaptive baseline logic and on-device person detection.

## Next Steps

See `HA_AUTOMATIONS.md` for example Home Assistant automations using the BLE sensors.

