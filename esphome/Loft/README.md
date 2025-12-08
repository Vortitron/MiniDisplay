# Loft TFT Display Controller

A comprehensive home automation display controller with rotary encoder, 240x320 colour TFT display (portrait), and MQ2 gas sensor running on ESP32-WROOM. The UI now uses full-screen cards, live graphs, and contextual headers so the content finally looks as rich as the data feeding it.

**Note:** Bluetooth Proxy is disabled to save memory for the display and sensors.

## Quick Reference - Pin Connections

**TFT Display (240x320 ST7789V, portrait):**
- SCL (CLK) → GPIO18
- SDA (MOSI) → GPIO23  
- CS → GPIO5
- DC → GPIO16
- RES (RST) → GPIO17
- BLK (Backlight) → GPIO4


**Rotary Encoder:**
- A → GPIO25
- B → GPIO26
- PUSH → GPIO27

**KEYO Button:**
- PUSH → GPIO14

## Pin Assignments (ESP32-WROOM)

### TFT Display Module Connections (240x320 ST7789V, portrait)

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
```

**Important Notes:**
- **SCL** on display = SPI Clock (NOT I2C!)
- **SDA** on display = SPI Data/MOSI (NOT I2C!)
- All modules run on **3.3V** (NOT 5V!)

## Features

### 🎨 **Colour TFT Display (ST7789)**
- 320×240 pixel colour display in landscape orientation (rotary/button underneath)
- Four main screens with summary and detail views
- Smooth rotation control via rotary encoder
- Auto-dimming backlight (30s timeout)
- On-screen clock, mode indicator, and status footer
- Wide format optimised for charts and data visualization

### 📺 **Five Display Screens**

1. **Notifications** (Screen 0)
   - Summary: Hero card with alert indicator, title, and trimmed body
   - Detail: Paginated list (up to 8 per page) with readable spacing
   - Auto wake + highlight whenever HA pushes a new notification

2. **Weather** (Screen 1) ✨ **ANIMATED**
   - Summary: Large temperature with **animated weather icon**, condition text, humidity progress bar, wind speed
   - Detail: Expanded weather stats (temperature, condition, humidity, wind)
   - **Animated icons**: Sun rays rotate, rain drops fall, clouds drift, snowflakes tumble
   - Icons update every second for smooth animation

3. **Power** (Screen 2) 📊 **ENHANCED CHARTS**
   - Summary: Price info (left) + **wide 24-hour chart with markers** (right), Bio/HEM L1 power at bottom
   - Detail: **Large 4-hour zoom chart** (16 bars at 15-min resolution) + all Bio/HEM phases in 3 columns
   - **Chart enhancements**:
     - Min/Max price markers (green dot = cheapest, red dot = most expensive)
     - Average price line (dotted white)
     - Trend arrows (↗️ rising prices, ↘️ falling prices)
     - Current hour/slot highlighted with white border
     - Colour-coded: green=cheap, yellow=normal, red=expensive

4. **Calendar** (Screen 3)
   - Summary: Next upcoming event with start time and location card
   - Detail: Expanded event card fed by `message`, `start_time`, and `location` attributes

5. **Energy** (Screen 4) ⚡ **NEW**
   - Summary: Total power consumption (kW), Bio/HEM breakdown bars, current cost rate (SEK/h)
   - Detail: Per-phase power visualization with horizontal bars for all 6 phases (Bio L1/L2/L3, HEM L1/L2/L3)
   - Visual power flow representation
   - Real-time cost calculation based on Nordpool prices

### 🎛️ **Controls**

**Rotary Encoder (Dial):**
- **Rotate in summary view**: Switch between screens (Notifications → Weather → Power → Calendar → Energy)
- **Rotate in detail view**: Scroll through detail items (notifications, power sensors, etc.)
- **Push**: Toggle between summary ↔ detail view
- Automatically turns on backlight when used

**KEYO Button (Big Button):**
- **Short press**: Back/Home button
  - If in detail view: Exit to summary view
  - If in summary view: Return to home screen (Weather)
- **Long press (3s)**: Quick lights control
  - Turn OFF all downstairs lights: gold_light, bio_floodlight, led_flood_light, living_office_stand, isp_ba4bb8_4bb8
  - Turn ON loft lights: isp_1a3c38_3c38, loft_lights


### 🎨 **Graphics & Visualization**
- **Animated weather icons**: Real-time vector graphics with smooth animations
  - Sun rays rotate slowly
  - Rain drops fall frame-by-frame
  - Clouds drift across
  - Snowflakes tumble down
- **Enhanced price charts**:
  - 24-hour overview with min/max markers and average line
  - 4-hour zoom with trend arrows
  - Push encoder to toggle between views
  - Current time highlighted
- **Energy dashboard**: Visual power flow with horizontal bar graphs
- **Progress bars**: Humidity and power visualization
- **Memory-efficient**: All graphics drawn using basic shapes (circles, lines, rectangles) - no bitmap images

### 🔋 **Power Monitoring**
- Real-time readouts for Bio + HEM phases (L1/L2/L3)
- Inline tariff classifier (cheap/normal/high thresholds)
- **Two-level price chart**:
  - Summary: 24-hour day overview (hourly averages)
  - Detail: 4-hour zoom with 15-minute resolution
- Colour-coded price visualization (green/yellow/red)
- Current time/slot highlighted with white border

### 📅 **Calendar Integration**
- Reads from `calendar.handl_f` (state + `message`, `location`, `start_time` attributes)
- Shows next upcoming event
- Detail view highlights the next event in a dedicated card

### 💡 **Smart Backlight**
- Turns on automatically when encoder is rotated
- Turns on when notification arrives
- Auto-dims after 30 seconds of inactivity
- Manual control available via Home Assistant

## Display Model Configuration

The configuration uses `model: Custom` with 320×240 dimensions in landscape orientation (`rotation: 90`). This provides optimal horizontal space for charts while staying within ESP32-WROOM memory limits (~153KB framebuffer).

```yaml
display:
  - platform: st7789v
    model: Custom
    height: 320
    width: 240
    rotation: 90  # Landscape orientation
```

Rotate via the `rotation:` parameter (`0`, `90`, `180`, `270`) if you mount the screen differently.

## Home Assistant Integration

The device exposes these entities:
- **Display Backlight** (light) - Manual backlight control
- **Encoder Push** (binary_sensor) - Dial push button state
- **KEYO Button** (binary_sensor) - Big button state

Required Home Assistant entities:
- `input_text.minidisplay_notification_ids`
- `input_text.minidisplay_notification_titles`
- `input_text.minidisplay_notification_messages`
- `sensor.nordpool_kwh_se4_sek_3_10_025`
- `weather.openweathermap`
- `calendar.handl_f`
- `sensor.bio_p1ib_active_power_l1/l2/l3`
- `sensor.hem_p1ib_active_power_l1/l2/l3`
- Attributes consumed from `weather.openweathermap`: `temperature`, `humidity`, `wind_speed`
- Attributes consumed from `calendar.handl_f`: `message`, `location`, `start_time`
- Attributes consumed from `sensor.nordpool_kwh_se4_sek_3_10_025`: `raw_today` (for price chart)

## Wiring Notes

1. **TFT Display** runs at 3.3V
   - **SCL** and **SDA** labels are for SPI, not I2C!
   - **RES** = Reset pin
   - **BLK** = Backlight
2. **Rotary Encoder** uses internal pullups on both phases
3. **Buttons** use internal pullups (connect button to pin and GND)
4. **Backlight** is PWM-controlled for smooth dimming on GPIO4
5. **Use VSPI pins** for best SPI performance (GPIO18/23 are hardware SPI)

## Why ESP32-WROOM Instead of ESP32-C3?

The ESP32-WROOM has:
- **More RAM** (~520KB vs ~400KB on C3)
- **Better support** for colour TFT displays
- **More stable** with complex lambdas and multiple fonts
- **Same price** as C3

The 320×240 colour TFT requires ~153KB for the framebuffer at 16-bit colour. This is at the memory limit for ESP32-WROOM (~520KB total RAM, ~200KB used by WiFi/system). The landscape orientation provides better horizontal space for charts without requiring more memory than portrait 240×320.

## Network Configuration

Static IP: **192.168.1.31**
- Gateway: 192.168.1.1
- Subnet: 255.255.255.0

## TODO / Future Enhancements

- [x] Animated weather icons
- [x] Enhanced price charts with markers and trends
- [x] Energy dashboard screen
- [ ] Parse actual raw_today data for real 15-minute price charts
- [ ] Add hourly weather forecast in detail view (if memory allows)
- [ ] Add calendar event scrolling in detail view
- [ ] Add more colour themes
- [ ] Add screen saver mode
- [ ] Consider upgrading to ESP32-S3 with PSRAM for:
  - Live camera feeds (5-10 FPS possible)
  - Larger display support
  - More complex graphics

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


## Notes

- Screens are manually controlled via rotary encoder (no auto-rotation)
- Detail view allows deeper inspection of each screen's data
- All screens support both summary and detail modes
- The ESP32-WROOM easily handles this configuration with room to spare

