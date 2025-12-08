# FrontPath BLE Mode - Quick Start Guide

Get your FrontPath sensors running in BLE mode in 10 minutes!

## Prerequisites

- ✅ ESP32-C3 SuperMini board
- ✅ Two LD2410C sensors (MAC addresses: `B8:BE:51:7D:71:44` and `14:AA:8C:58:66:02`)
- ✅ TEMT6000 light sensor
- ✅ Home Assistant with ESPHome integration
- ✅ USB cable for flashing

## Step 1: Wire Everything (5 minutes)

### Light Sensor (TEMT6000)
```
TEMT6000 VCC  →  ESP32 5V
TEMT6000 GND  →  ESP32 GND
TEMT6000 OUT  →  ESP32 GPIO0
```

### LD2410 Sensors (Power Only!)
```
Sensor 1 VCC  →  ESP32 5V
Sensor 1 GND  →  ESP32 GND
Sensor 1 TX   →  NOT CONNECTED
Sensor 1 RX   →  NOT CONNECTED

Sensor 2 VCC  →  ESP32 5V
Sensor 2 GND  →  ESP32 GND
Sensor 2 TX   →  NOT CONNECTED
Sensor 2 RX   →  NOT CONNECTED
```

**⚠️ Important:** Do NOT connect TX/RX pins! Sensors will automatically broadcast BLE when UART is disconnected.

## Step 2: Flash ESP32 (2 minutes)

```bash
cd esphome/FrontPath
esphome run FrontPath.yaml
```

Select your USB port and wait for the flash to complete.

## Step 3: Verify BLE Advertisements (1 minute)

Check ESPHome logs:
```bash
esphome logs FrontPath.yaml
```

Look for these messages:
```
[INFO] [ld2410_ble] Sensor 1 (B8:BE:51:7D:71:44) advertisements resumed
[INFO] [ld2410_ble] Sensor 2 (14:AA:8C:58:66:02) advertisements resumed
```

If you don't see these:
1. Power cycle the sensors (disconnect 5V for 10 seconds)
2. Ensure TX/RX pins are NOT connected
3. Check sensors are powered (should have LED indicators)

## Step 4: Add Sensors to Home Assistant (2 minutes)

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for "LD2410 BLE"
4. Home Assistant should auto-discover both sensors
5. Click **Configure** for each sensor
6. Give them friendly names:
   - `B8:BE:51:7D:71:44` → "FrontPath Sensor 1 (House Side)"
   - `14:AA:8C:58:66:02` → "FrontPath Sensor 2 (Far Side)"

## Step 5: Create Basic Automation (5 minutes)

Go to **Settings → Automations & Scenes → + Create Automation**

### Simple Motion-Activated Lights

```yaml
alias: FrontPath - Lights On When Motion Detected
description: Turn on path lights when either sensor detects movement in the dark
trigger:
  - platform: state
    entity_id:
      - binary_sensor.ld2410_b8be517d7144_has_moving_target
      - binary_sensor.ld2410_14aa8c586602_has_moving_target
    to: "on"
condition:
  - condition: state
    entity_id: binary_sensor.frontpath_path_is_dark
    state: "on"
action:
  - service: light.turn_on
    target:
      entity_id: light.your_path_lights  # Change this to your light entity
    data:
      brightness_pct: 100
  - delay:
      seconds: 30
  - service: light.turn_off
    target:
      entity_id: light.your_path_lights
mode: restart
```

**Replace `light.your_path_lights` with your actual light entity ID!**

## Step 6: Test It! (2 minutes)

1. Wait for it to get dark (or cover the light sensor)
2. Walk past the sensors
3. Lights should turn on!
4. Check the HA logs if it doesn't work

## Troubleshooting

### Sensors Not Appearing in HA

**Check BLE advertisements:**
```bash
esphome logs FrontPath.yaml
```

Look for "advertisements resumed" messages. If missing:
- Power cycle sensors
- Verify TX/RX pins are disconnected
- Check 5V power is connected

### Lights Not Turning On

**Check entity states in HA:**
- Go to **Developer Tools → States**
- Search for `ld2410_b8be517d7144_has_moving_target`
- Walk past sensor and watch it change to "on"

If it doesn't change:
- Sensors may need configuration (see below)
- Check HA logs for errors

### False Triggers (Lights Turn On Randomly)

**Increase sensitivity thresholds:**
1. Go to sensor device page in HA
2. Find "Max Move Distance Gate" 
3. Reduce from 8 to 6 (shorter range)
4. Or increase gate thresholds (higher = less sensitive)

### Sensors Keep Disconnecting

**Check connection status:**
- `binary_sensor.frontpath_ld2410_sensor_1_ble_connected`
- `text_sensor.frontpath_ld2410_sensor_1_ble_status`

If showing "Missing" or "Stale":
- Check ESP32 WiFi signal strength
- Ensure ESP32 is within 5-10m of sensors
- Power cycle sensors

## Next Steps

### Tune Detection
See `HA_AUTOMATIONS.md` for advanced automation examples:
- Energy-based detection (more reliable)
- Direction-based lighting
- Progressive brightness by distance
- Adaptive baseline tracking

### Configure Sensors
Adjust sensor settings in HA:
- **Max Move Distance Gate**: 6-8 for outdoor path
- **Timeout**: 3-5 seconds
- **Gate Thresholds**: Increase for less sensitivity

### Monitor Performance
Watch these entities:
- `sensor.frontpath_light_level` - Light sensor reading
- `binary_sensor.frontpath_path_is_dark` - Darkness detection
- `sensor.ld2410_*_moving_energy` - Signal strength
- `binary_sensor.frontpath_ld2410_sensor_*_ble_connected` - Connection status

## Quick Reference

**Entity IDs to use in automations:**
```yaml
# Motion detection
binary_sensor.ld2410_b8be517d7144_has_moving_target  # Sensor 1
binary_sensor.ld2410_14aa8c586602_has_moving_target  # Sensor 2

# Darkness detection
binary_sensor.frontpath_path_is_dark

# Signal strength (for tuning)
sensor.ld2410_b8be517d7144_moving_energy  # Sensor 1
sensor.ld2410_14aa8c586602_moving_energy  # Sensor 2

# Distance (for progressive lighting)
sensor.ld2410_b8be517d7144_moving_distance  # Sensor 1 (cm)
sensor.ld2410_14aa8c586602_moving_distance  # Sensor 2 (cm)
```

## Success Checklist

- ✅ ESP32 flashed and connected to WiFi
- ✅ Both sensors showing "Connected" in HA
- ✅ Light sensor reading changes when covered
- ✅ Moving target sensors change when walking past
- ✅ Automation triggers lights when dark
- ✅ No false triggers during calm weather

**You're done! 🎉**

For more advanced setups, see:
- `BLE_SETUP.md` - Detailed setup guide
- `HA_AUTOMATIONS.md` - Advanced automation examples
- `MODE_COMPARISON.md` - BLE vs UART comparison

