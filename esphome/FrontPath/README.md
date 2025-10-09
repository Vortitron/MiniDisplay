# FrontPath - ESP32-C3 SuperMini with Dual LD2410C Sensors

## Hardware Configuration

This configuration uses an ESP32-C3 SuperMini board with two LD2410C millimetre-wave radar sensors.

## Wiring Connections

### ESP32-C3 SuperMini Pinout Reference
```
        USB
         |
    +---------+
5U  |  5V     | 5
 G  |  GND    | 6
3.3 |  3.3V   | 7
 4  |  GPIO4  | 8
 3  |  GPIO3  | 9
 2  |  GPIO2  | 10
 1  |  GPIO1  | 20
 0  |  GPIO0  | 21
    +---------+
```

### LD2410C Sensor 1 Connections
| LD2410C Pin | ESP32-C3 Pin | Function |
|-------------|--------------|----------|
| VCC         | 5V           | Power (5V) |
| GND         | GND          | Ground |
| TX          | GPIO21       | Data from sensor to ESP32 |
| RX          | GPIO20       | Data from ESP32 to sensor |

### LD2410C Sensor 2 Connections
| LD2410C Pin | ESP32-C3 Pin | Function |
|-------------|--------------|----------|
| VCC         | 5V           | Power (5V) |
| GND         | GND          | Ground |
| TX          | GPIO9        | Data from sensor to ESP32 |
| RX          | GPIO8        | Data from ESP32 to sensor |

## Important Notes

1. **Power Supply**: The LD2410C sensors require 5V power. Connect both VCC pins to the 5V pin on the ESP32-C3 SuperMini.

2. **Logging**: UART logging has been disabled (set to 0) to free up GPIO20/21 for the first sensor. You can still view logs over WiFi using the Home Assistant API.

3. **Pin Usage**: 
   - GPIO20/21: Sensor 1 (UART0)
   - GPIO8/9: Sensor 2 (UART1)
   - These pins are now dedicated to the sensors and cannot be used for other purposes.

4. **Bluetooth Proxy**: The Bluetooth proxy feature is still active and will work alongside the sensors.

## Features

Each LD2410C sensor provides:
- **Binary Sensors**:
  - Presence detection (has_target)
  - Moving target detection
  - Still target detection

- **Distance & Energy Sensors**:
  - Moving distance (cm)
  - Still distance (cm)
  - Moving energy level
  - Still energy level
  - Detection distance

## Home Assistant Integration

Once flashed and connected to Home Assistant, you'll see 16 entities per sensor (32 total):
- 3 binary sensors (presence, moving, still)
- 5 numeric sensors (distances and energy levels)

All entities will be prefixed with "Sensor 1" or "Sensor 2" for easy identification.

