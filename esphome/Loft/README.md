# Loft TFT Display Controller

A comprehensive home automation display controller with rotary encoder, 160x240 colour TFT display (portrait), and MQ2 gas sensor running on ESP32-WROOM.

**Note:** Bluetooth Proxy is disabled to save memory for the display and sensors.

## Quick Reference - Pin Connections

**TFT Display (160x240 ST7789V, portrait):**
- SCL (CLK) → GPIO18
- SDA (MOSI) → GPIO23  
- CS → GPIO5
- DC → GPIO16
- RES (RST) → GPIO17
- BLK (Backlight) → GPIO4

**MQ2 Sensor:**
- AO → GPIO34

**Rotary Encoder:**
- A → GPIO25
- B → GPIO26
- PUSH → GPIO27

**KEYO Button:**
- PUSH → GPIO14

## Pin Assignments (ESP32-WROOM)

### TFT Display Module Connections (160x240 ST7789V, portrait)

| Display Label | ESP32 Pin | ESP32 Label | Notes |
|---------------|-----------|-------------|-------|   
| **SCL (CLK)** | GPIO18 | GPIO18 | SPI Clock |
| **SDA (MOSI)** | GPIO23 | GPIO23 | SPI Data |
| **CS** | GPIO5 | GPIO5 | Chip Select |
| **DC** | GPIO16 | GPIO16 | Data/Command |
| **RES (RST)** | GPIO17 | GPIO17 | Reset |
| **BLK** | GPIO4 | GPIO4 | Backlight (PWM) |
| **VCC** | 3.3V | 3.3V | Power |
| **GND** | GND | GND | Ground |

### Other Components

| Component | ESP32 Pin | ESP32 Label | Notes |
|-----------|-----------|-------------|-------|
| **MQ2 Gas Sensor** | GPIO34 | GPIO34 | Analog input (ADC1_CH6) |
| **Rotary Encoder - A** | GPIO25 | GPIO25 | Encoder phase A |
| **Rotary Encoder - B** | GPIO26 | GPIO26 | Encoder phase B |
| **Rotary Encoder - Push** | GPIO27 | GPIO27 | Encoder button |
| **KEYO Button** | GPIO14 | GPIO14 | Back button |

## Wiring Diagram Summary

```
OLED Display Module (128x64 I2C) ESP32-WROOM Board
---------------------------------  -----------------
SCL (Clock)                   --> GPIO18
SDA (Data)                    --> GPIO23
BLK (Backlight)               --> GPIO4
VCC                           --> 3.3V
GND                           --> GND

EC11 Rotary Encoder Module      ESP32-WROOM Board
---------------------------      -----------------
A (Phase A)                 --> GPIO25
B (Phase B)                 --> GPIO26
PUSH (Switch)               --> GPIO27
GND                         --> GND

KEYO Button Module              ESP32-WROOM Board
------------------              -----------------
PUSH                        --> GPIO14
GND                         --> GND

MQ2 Gas Sensor                  ESP32-WROOM Board
--------------                  -----------------
AO (Analog Out)             --> SVP (GPIO36)
VCC                         --> 3.3V
GND                         --> GND
```

**Important Notes:**
- **SVP** on the ESP32 board = GPIO36 (Sensor VP pin)
- **SCL** on display = SPI Clock (NOT I2C!)
- **SDA** on display = SPI Data/MOSI (NOT I2C!)
- All modules run on **3.3V** (NOT 5V!)

## Features

### 🎨 **Colour TFT Display (ST7789)**
- 240×240 pixel colour display
- Four main screens with summary and detail views
- Smooth rotation control via rotary encoder
- Auto-dimming backlight (30s timeout)

### 📺 **Four Display Screens**

1. **Notifications** (Screen 0)
   - Summary: Current notification with title and message (red)
   - Detail: List of all active notifications

2. **Weather** (Screen 1)
   - Summary: Current conditions with temperature (blue)
   - Detail: Hourly forecast predictions
   - AI image placeholder ready

3. **Power** (Screen 2)
   - Summary: Current Nordpool electricity price (green)
   - Detail: All power sensors (Bio P1IB L1/L2/L3, HEM P1IB L1/L2/L3)

4. **Calendar** (Screen 3)
   - Summary: Next upcoming event (yellow)
   - Detail: List of upcoming calendar events
   - AI image placeholder ready

### 🎛️ **Controls**

**Rotary Encoder:**
- **Rotate**: Switch between screens (Notifications → Weather → Power → Calendar)
- **Push**: Toggle between summary and detail view
- Automatically turns on backlight when rotated

**KEYO Button:**
- **Short press**: Exit detail view (go back to summary)
- **Long press (3s)**: Turn off all downstairs lights, turn on loft lights
  - Downstairs OFF: gold_light, bio_floodlight, led_flood_light, living_office_stand, isp_ba4bb8_4bb8
  - Loft ON: isp_1a3c38_3c38, loft_lights

### 🔥 **MQ2 Gas Sensor**
- Continuous gas/smoke monitoring
- Percentage reading (0-100%)
- Software alarm with hysteresis (triggers at 25%, clears at 20%)
- Integrated into Home Assistant
- Uses GPIO36 (ADC1_CH0) - one of the best analog pins on ESP32

### 🤖 **AI Integration** (Placeholders Ready)
- OpenAI task integration prepared
- AI-generated images for weather conditions
- AI-generated calendar imagery
- Image placeholders currently shown as grey rectangles with "AI IMG" text

### 🔋 **Power Monitoring**
Displays detailed power consumption from:
- Bio P1IB Active Power L1, L2, L3
- HEM P1IB Active Power L1, L2, L3

### 📅 **Calendar Integration**
- Reads from `calendar.handl_f`
- Shows next upcoming event
- Detail view lists multiple events

### 💡 **Smart Backlight**
- Turns on automatically when encoder is rotated
- Turns on when notification arrives
- Auto-dims after 30 seconds of inactivity
- Manual control available via Home Assistant

## Display Model Configuration

The configuration uses `model: Custom` with 240×240 dimensions. If your display is different, update line 118-122:

```yaml
display:
  - platform: st7789v
    model: Custom
    height: 240
    width: 240
```

You may need to adjust the `rotation:` parameter (line 125) to `0`, `90`, `180`, or `270` degrees.

## Home Assistant Integration

The device exposes these entities:
- **Display Backlight** (light) - Manual backlight control
- **MQ2 Gas/Smoke Level** (sensor) - Percentage reading
- **MQ2 Smoke/Gas Alarm** (binary_sensor) - Alarm status
- **Encoder Push** (binary_sensor) - Push button state
- **KEYO Button** (binary_sensor) - Back button state

Required Home Assistant entities:
- `input_text.minidisplay_notification_ids`
- `input_text.minidisplay_notification_titles`
- `input_text.minidisplay_notification_messages`
- `sensor.nordpool_kwh_se4_sek_3_10_025`
- `weather.openweathermap`
- `calendar.handl_f`
- `sensor.bio_p1ib_active_power_l1/l2/l3`
- `sensor.hem_p1ib_active_power_l1/l2/l3`

## Wiring Notes

1. **TFT Display** runs at 3.3V
   - **SCL** and **SDA** labels are for SPI, not I2C!
   - **RES** = Reset pin
   - **BLK** = Backlight
2. **MQ2 Sensor** outputs 0-3.3V analog signal to **SVP** (GPIO36)
   - SVP stands for "Sensor VP" (VP = Voltage Positive)
   - This is one of the best analog pins on ESP32
3. **Rotary Encoder** uses internal pullups on both phases
4. **Buttons** use internal pullups (connect button to pin and GND)
5. **Backlight** is PWM-controlled for smooth dimming on GPIO4
6. **Use VSPI pins** for best SPI performance (GPIO18/23 are hardware SPI)

## Why ESP32-WROOM Instead of ESP32-C3?

The ESP32-WROOM has:
- **More RAM** (~520KB vs ~400KB on C3)
- **Better support** for colour TFT displays
- **More stable** with complex lambdas and multiple fonts
- **Same price** as C3

The 240×240 colour TFT requires ~170KB just for the framebuffer, which is why the ESP32-C3 couldn't handle it (kernel panic due to out of memory).

## Network Configuration

Static IP: **192.168.1.31**
- Gateway: 192.168.1.1
- Subnet: 255.255.255.0

## TODO / Future Enhancements

- [ ] Implement AI image generation and display
- [ ] Add hourly weather forecast in detail view
- [ ] Add calendar event scrolling in detail view
- [ ] Add detail view scrolling with rotary encoder
- [ ] Add graph for power consumption trends
- [ ] Add more colour themes
- [ ] Add screen saver mode
- [ ] Add gas sensor alert to display

## Troubleshooting

### Display not working:
1. Check all SPI connections (CLK, MOSI, CS, DC, RST)
2. Verify 3.3V power supply is stable
3. Try different rotation values (0°, 90°, 180°, 270°)
4. Check backlight connection to GPIO4

### Rotary encoder not responding:
1. Verify encoder common is connected to GND
2. Check GPIO25 and GPIO26 connections
3. Test encoder push button separately

### Gas sensor always 0% or 100%:
1. MQ2 sensors need 24-48 hours initial burn-in
2. Verify 3.3V power to sensor
3. Check analog output connection to GPIO36
4. Wait for sensor to warm up (takes several minutes)

## Notes

- Screens are manually controlled via rotary encoder (no auto-rotation)
- Detail view allows deeper inspection of each screen's data
- All screens support both summary and detail modes
- The ESP32-WROOM easily handles this configuration with room to spare

