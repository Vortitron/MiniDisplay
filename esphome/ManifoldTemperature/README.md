# ManifoldTemperature ESPHome Device

## Overview
The ManifoldTemperature is an ESP32-based monitoring and display system designed to track temperatures across a multi-loop heating manifold system. It provides real-time temperature monitoring for up to 8 heating loops, manifold input, hot water boiler, and ambient air temperature, while also monitoring gas safety through an MQ2 sensor.

## Purpose
This device serves as a central monitoring station for:
- **Hydronic Heating System**: Monitors supply and return temperatures across 8 independent heating loops
- **Hot Water Boiler**: Tracks boiler temperature
- **Safety Monitoring**: Gas detection via MQ2 sensor
- **System Status**: Displays boiler relay states and connectivity status
- **User Interface**: 8-digit 7-segment display with 8 programmable buttons and LEDs for interactive viewing

## Hardware Components

### Main Controller
- **ESP32-DevKit** (ESP32-WROOM-32)
  - Framework: ESP-IDF
  - Ethernet connectivity (no WiFi required for reliable operation)

### Network
- **WIZ820io (W5500)** Ethernet Module
  - Provides stable, wired network connection
  - Custom patched driver for ESP-IDF compatibility

### Display & Input
- **TM1638** Display Module
  - 8-digit 7-segment LED display
  - 8 push buttons (S1-S8)
  - 8 individual LEDs
  - Used for temperature display and system status indication

### Temperature Sensors
- **10x DS18B20** Digital Temperature Sensors (1-Wire)
  - Manifold Input Temperature
  - 8x Loop Return Temperatures (Loop 1-8)
  - Air Temperature
  - Hot Water Boiler Temperature

### Gas Detection
- **MQ2 Gas Sensor**
  - Detects LPG, propane, methane, hydrogen, alcohol, smoke
  - Analog output for concentration levels
  - Digital output for threshold-based alarm

## Pin Assignments

### Ethernet (W5500)
| Function | ESP32 Pin |
|----------|-----------|
| MOSI | GPIO13 |
| MISO | GPIO12 |
| CLK | GPIO14 |
| CS | GPIO15 |
| RESET | GPIO26 |
| INTERRUPT | GPIO27 |

### TM1638 Display Module
| Function | ESP32 Pin |
|----------|-----------|
| STB (Strobe) | GPIO19 |
| CLK (Clock) | GPIO5 |
| DIO (Data) | GPIO18 |

### Temperature Sensors (1-Wire)
| Function | ESP32 Pin |
|----------|-----------|
| DATA | GPIO4 |

**Note**: All DS18B20 sensors share the same 1-Wire bus. Each sensor is identified by its unique 64-bit address.

### MQ2 Gas Sensor
| Function | ESP32 Pin | Notes |
|----------|-----------|-------|
| Analog Output (AO) | GPIO34 | ADC1_CH6, 0-3.3V input |
| Digital Output (DO) | GPIO35 | ADC1_CH7, threshold alarm |

**MQ2 Power**: 5V (VCC), GND

### Power
- **ESP32**: 5V via USB or Vin pin
- **MQ2 Sensor**: 5V (has onboard regulator)
- **W5500**: 3.3V (powered from ESP32)
- **TM1638**: 5V
- **DS18B20**: 3.3V or 5V (parasitic power or external)

## DS18B20 Sensor Mapping

Each temperature sensor has a unique 64-bit ROM address. To identify which physical sensor corresponds to which address:

1. Flash the ESPHome firmware
2. Check the logs - all detected sensors will be listed
3. Heat each sensor individually (warm water, finger, etc.)
4. Watch the logs to see which address changes
5. Update the YAML configuration with the correct addresses

### Current Sensor Assignments
| Sensor ID | Name | Address | Location |
|-----------|------|---------|----------|
| manifold_input_temp | Manifold Input Temp | 0x170000007bc02828 | Supply manifold |
| loop_1_return_temp | Loop 1 Return Temp | 0x7b0000007a769928 | Loop 1 return |
| loop_2_return_temp | Loop 2 Return Temp | 0x780000007a859c28 | Loop 2 return |
| loop_3_return_temp | Loop 3 Return Temp | 0x8300000077cf3e28 | Loop 3 return |
| loop_4_return_temp | Loop 4 Return Temp | 0x0e000000788c2b28 | Loop 4 return |
| loop_5_return_temp | Loop 5 Return Temp | 0x430000007852bb28 | Loop 5 return |
| loop_6_return_temp | Loop 6 Return Temp | 0xaa000000788bcf28 | Loop 6 return |
| loop_7_return_temp | Loop 7 Return Temp | 0xb30000007bfe9f28 | Loop 7 return |
| loop_8_return_temp | Loop 8 Return Temp | 0x060000007cf13f28 | Loop 8 return |
| air_temp | Air Temp | 0xde0000007c3ac428 | Ambient air |
| boiler_temp | Hot Water Boiler Temp | 0x0000000000000000 | Hot water boiler |

**Note**: The boiler_temp address needs to be discovered and updated after installation.

## Display Operation

### Normal Mode (Default)
- **Left 4 digits**: Manifold Input Temperature (°C)
- **Right 4 digits**: Air Temperature (°C)
- **LED Status Indicators**:
  - LED 1: Boiler Control Device Available/Connected
  - LED 2: Boiler Relay 1 State (ON when active)
  - LED 3: Boiler Relay 2 State (ON when active)
  - LED 4: Gas Sensor OK (ON = safe, OFF = gas detected)
  - LED 5-8: Reserved for future use

### Button Selection Mode
- **Press S1-S8**: Display corresponding loop temperature
- **Left 4 digits**: Selected loop return temperature (°C)
- **Right 4 digits**: Air Temperature (°C)
- **LED Behavior**: INVERTED - All LEDs ON except the selected loop
- **Timeout**: Returns to Normal Mode after 10 seconds of inactivity

### Example
- Press **S3** → Display shows Loop 3 temperature + Air temp
- **LEDs**: 1, 2, 4, 5, 6, 7, 8 are ON; LED 3 is OFF (indicating Loop 3 selected)

## Home Assistant Integration

This device imports the following entities from Home Assistant:
- `switch.boilercontrol_boiler_relay_1` - Boiler relay 1 state
- `switch.boilercontrol_boiler_relay_2` - Boiler relay 2 state

These states are used to:
1. Determine if the boiler control device is available (LED 1)
2. Display relay states on LEDs 2 and 3

## Network Configuration

The device uses **Ethernet only** (no WiFi) for reliability in a critical heating system application.

- Uses custom W5500 driver patch from: `https://github.com/Vortitron/WIZ820io_w5500_esphome_patch2`
- Clock speed: 12MHz
- Static IP can be configured via Home Assistant or DHCP

## Safety Features

### Gas Detection
- Continuous analog monitoring of gas concentration
- Digital threshold alarm for immediate notification
- LED indicator on display module
- Exposed to Home Assistant for automation/notifications

### Temperature Monitoring
- Regular 10-second updates for all heating loops
- 2-second updates for gas sensor (faster response)
- Sliding window average filter on gas sensor to prevent false alarms

## Installation Notes

1. **1-Wire Pull-up**: Install a 4.7kΩ pull-up resistor between DATA (GPIO4) and 3.3V
2. **MQ2 Warm-up**: The MQ2 sensor requires 24-48 hours of initial burn-in for accurate readings
3. **Power Supply**: Ensure adequate 5V power supply (>2A recommended) for all components
4. **Ethernet Cable**: Use quality Cat5e or better ethernet cable for reliable connectivity
5. **Sensor Placement**: Keep DS18B20 sensors away from direct heat sources for accurate readings

## Troubleshooting

### No Ethernet Connection
- Check W5500 wiring and reset pin
- Verify clock speed (12MHz)
- Check for proper power to W5500 module

### Temperature Sensors Not Detected
- Verify 4.7kΩ pull-up resistor on GPIO4
- Check 1-Wire bus wiring
- Ensure sensors are powered correctly
- Check ESPHome logs for detected addresses

### Display Not Working
- Verify TM1638 connections (STB, CLK, DIO)
- Check power supply to TM1638 (5V)
- Verify correct pin assignments

### MQ2 False Alarms
- Allow 24-48 hour burn-in period
- Adjust threshold potentiometer on MQ2 module
- Check placement away from cooking fumes/steam
- Verify power supply stability

## Firmware Updates

Update via:
1. **OTA** (Over The Air) through Home Assistant
2. **USB** connection to ESP32

OTA password is configured in the YAML file.

## License & Credits

- ESPHome: https://esphome.io
- W5500 ESP-IDF Patch: https://github.com/Vortitron/WIZ820io_w5500_esphome_patch2

