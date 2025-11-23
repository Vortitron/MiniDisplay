# LoftWay - Bluetooth Proxy with Alarm LED

A simple Bluetooth proxy device based on ESP32-C3 SuperMini with visual alarm status indication.

## Features

### 🔵 **Bluetooth Proxy**
- Extends Home Assistant's Bluetooth range
- Allows HA to communicate with BLE devices through this proxy
- Low power consumption in LIGHT mode

### 💡 **Status LED (On-board LED GPIO8)**
The on-board LED provides visual feedback for:
- **Steady ON**: Device connected to Home Assistant
- **OFF**: Device disconnected from Home Assistant
- **Flashing**: Alarm status indication (see below)

### 🚨 **Alarm Status LED Patterns**

The LED flashes according to the `input_select.alarm_level` entity in Home Assistant:

| Alarm Level | LED Pattern | Description |
|-------------|-------------|-------------|
| **OK** | OFF (when connected) | Normal operation |
| **Notify** | Single 300ms flash every 60 seconds | Minor alert |
| **Take Action** | Double flash every 20 seconds | Requires attention |
| **Emergency** | Rapid flash (200ms on/off) | Critical alert |

## Hardware

**ESP32-C3 SuperMini**
- Board: `esp32-c3-devkitm-1`
- Framework: ESP-IDF
- On-board LED: GPIO8 (inverted logic)

## Pin Assignments

| Component | Pin | Notes |
|-----------|-----|-------|
| **Status LED** | GPIO8 | On-board LED (inverted) |

## Home Assistant Integration

### Required Entity
- `input_select.alarm_level` - Must have options: "OK", "Notify", "Take Action", "Emergency"

### Setup in Home Assistant

Create the input_select in your `configuration.yaml`:

```yaml
input_select:
  alarm_level:
    name: Alarm Level
    options:
      - "OK"
      - "Notify"
      - "Take Action"
      - "Emergency"
    initial: "OK"
```

## Configuration Notes

- **Power Save Mode**: Set to LIGHT for balance between power and responsiveness
- **Reboot Timeout**: Disabled (`0s`) to prevent unnecessary reboots
- **API Reboot Timeout**: Disabled to keep device stable
- **LED Update**: Checks alarm status every 100ms for responsive flashing

## Usage

1. Upload the configuration to your ESP32-C3 SuperMini
2. Device will appear in Home Assistant as a Bluetooth Proxy
3. LED will turn on steady when connected to HA
4. Change `input_select.alarm_level` in HA to see different LED patterns
5. Use the device to extend Bluetooth range for BLE devices

## Troubleshooting

**LED not working:**
- Check GPIO8 is not being used by other components
- Verify `inverted: true` is set for the LED output
- Check Home Assistant connection (LED should be ON when connected)

**Alarm patterns not working:**
- Ensure `input_select.alarm_level` entity exists in Home Assistant
- Check ESPHome logs for "Alarm level updated" messages
- Verify the entity_id matches exactly: `input_select.alarm_level`

**Bluetooth not working:**
- Ensure `bluetooth_proxy: active: true` is set
- Check device is within range of Bluetooth devices
- Verify ESP32-C3 Bluetooth is not disabled in Home Assistant

## Previous Configuration

This device was previously configured as a TFT display controller. That functionality has been removed in favour of a simpler, more stable Bluetooth proxy with alarm LED functionality.
