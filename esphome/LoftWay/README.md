# LoftWay - TFT Display Controller

A comprehensive home automation display controller with rotary encoder, colour TFT display, and MQ2 gas sensor.

## Pin Assignments (ESP32-C3 SuperMini)

| Component | Pin | Notes |
|-----------|-----|-------|
| **MQ2 Gas Sensor** | GPIO3 | Analog input (ADC1_CH3) |
| **TFT Display - CLK** | GPIO2 | SPI Clock |
| **TFT Display - MOSI** | GPIO7 | SPI Data |
| **TFT Display - CS** | GPIO10 | Chip Select |
| **TFT Display - DC** | GPIO6 | Data/Command select |
| **TFT Display - RST** | GPIO5 | Reset |
| **TFT Display - Backlight** | GPIO8 | PWM controlled backlight |
| **Rotary Encoder - A** | GPIO20 | Encoder phase A |
| **Rotary Encoder - B** | GPIO21 | Encoder phase B |
| **Rotary Encoder - Push** | GPIO1 | Encoder push button (with internal pullup) |
| **KEYO Button** | GPIO9 | Back button (with internal pullup) |

## Features

### 🎨 **Colour TFT Display (ST7789)**
- 135x240 pixel colour display (or 240x240 depending on model)
- Four main screens with summary and detail views
- Smooth rotation control via rotary encoder
- Auto-dimming backlight (30s timeout)

### 📺 **Four Display Screens**

1. **Notifications** (Screen 0)
   - Summary: Current notification with title and message
   - Detail: List of all active notifications

2. **Weather** (Screen 1)
   - Summary: Current conditions with temperature and AI-generated weather imagery
   - Detail: Hourly forecast predictions

3. **Power** (Screen 2)
   - Summary: Current Nordpool electricity price
   - Detail: All power sensors (Bio P1IB L1/L2/L3, HEM P1IB L1/L2/L3)

4. **Calendar** (Screen 3)
   - Summary: Next upcoming event with AI-generated calendar imagery
   - Detail: List of upcoming calendar events with scrolling

### 🎛️ **Controls**

**Rotary Encoder:**
- **Rotate**: Switch between screens (Notifications → Weather → Power → Calendar)
- **Push**: Toggle between summary and detail view
- Automatically turns on backlight when rotated

**KEYO Button:**
- **Short press**: Exit detail view (go back to summary)
- **Long press (3s)**: Turn off all downstairs lights, turn on loft lights

### 🔥 **MQ2 Gas Sensor**
- Continuous gas/smoke monitoring
- Percentage reading (0-100%)
- Software alarm with hysteresis (triggers at 25%, clears at 20%)
- Integrated into Home Assistant

### 🤖 **AI Integration** (Placeholders Ready)
- OpenAI task integration prepared (`ai_task.openai_ai_task`)
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
- Detail view lists multiple events (implementation ready)

### 💡 **Smart Backlight**
- Turns on automatically when encoder is rotated
- Turns on when notification arrives
- Auto-dims after 30 seconds of inactivity
- Manual control available via Home Assistant

## Wiring Notes

1. **TFT Display** runs at 3.3V - perfect for ESP32-C3
2. **MQ2 Sensor** outputs 0-3.3V analog signal to GPIO3
3. **Rotary Encoder** uses internal pullups on both phases
4. **Buttons** use internal pullups (connect to GND)
5. **Backlight** is PWM-controlled for smooth dimming

## Display Model Configuration

The configuration uses `model: TTGO TDisplay 135x240`. If your display is different, update line 114:

```yaml
display:
  - platform: st7789v
    model: TTGO TDisplay 135x240  # Change this to match your display
```

Common alternatives:
- `TTGO TDisplay 135x240` (135x240 pixels)
- `Custom` (for generic ST7789 displays - specify dimensions)

You may also need to adjust the `rotation:` parameter (line 119) to `0`, `90`, `180`, or `270` degrees.

## Home Assistant Integration

The device exposes these entities:
- **Display Backlight** (light) - Manual backlight control
- **MQ2 Gas/Smoke Level** (sensor) - Percentage reading
- **MQ2 Smoke/Gas Alarm** (binary_sensor) - Alarm status
- **Encoder Push** (binary_sensor) - Push button state
- **KEYO Button** (binary_sensor) - Back button state

## TODO / Future Enhancements

- [ ] Implement AI image generation and display
- [ ] Add hourly weather forecast in detail view
- [ ] Add calendar event scrolling in detail view
- [ ] Add detail view scrolling with rotary encoder
- [ ] Add graph for power consumption trends
- [ ] Add more colour themes
- [ ] Add screen saver mode

## Notes

- Screens are manually controlled via rotary encoder (no auto-rotation)
- Detail view allows deeper inspection of each screen's data
- All screens support both summary and detail modes
- The configuration is optimised for readability and maintainability

