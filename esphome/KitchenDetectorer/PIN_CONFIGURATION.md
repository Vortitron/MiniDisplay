# Kitchen Detectorer - Pin Configuration

## TM1638 Display Module
The TM1638 provides an 8-digit 7-segment display, 8 LEDs, and 8 buttons.

### TM1638 Wiring
- **STB (Strobe/Chip Select)**: GPIO5
- **CLK (Clock)**: GPIO18
- **DIO (Data I/O)**: GPIO17
- **VCC**: 3.3V or 5V
- **GND**: Ground

## Ultrasonic Sensor (Coffee Bean Level)
HC-SR04 or similar ultrasonic distance sensor for measuring coffee bean level.

### Ultrasonic Wiring
- **Trigger Pin**: GPIO12
- **Echo Pin**: GPIO13
- **VCC**: 5V
- **GND**: Ground

## I2S Microphone (Air Fryer Beep Detection)
INMP441 or similar I2S MEMS microphone for detecting air fryer beeps.

### I2S Microphone Wiring
- **L/R Clock (LRCLK/WS)**: GPIO15
- **Bit Clock (BCLK/SCK)**: GPIO14
- **Data In (DIN/SD)**: GPIO32
- **VCC**: GPIO4 (powered by GPIO pin, always on)
- **GND**: Ground

**Note**: The microphone is powered directly from GPIO4, which provides sufficient current (~1-2mA) for I2S MEMS microphones. This frees up your 3.3V rail for other components.

## Available GPIO Pins
The following pins are available for future expansion:
- GPIO16, GPIO19, GPIO21 (formerly used by Nokia 5110 and calibration button)
- GPIO22, GPIO23, GPIO25, GPIO26, GPIO27, GPIO33, GPIO34, GPIO35, GPIO36, GPIO39

**Note**: GPIO4 is now used to power the I2S microphone.

## Display Screens
The device cycles through up to 10 screens every 3.5 seconds (some are conditionally skipped):

| Screen | Description | Left Display | Right Display | LED Indicator | Condition |
|--------|-------------|--------------|---------------|---------------|-----------|
| 0 | Air Fryer Power | "AirW" | Power (whole watts) | LED1 (on when >0W) | Only shown when power > 0 |
| 1 | Bio Heaters & Temp | on/off | Temperature °C | LED2 (always on) | Always shown |
| 2 | Hot Water | "hot" | on/off status | - | Always shown |
| 3 | Outside Temp | "out" | Temperature °C | - | Always shown |
| 4 | Inside Temp | "in" | Temperature °C | - | Always shown |
| 5 | Inside Humidity | "in h" | Humidity (with decimal) | - | Always shown |
| 6 | Power Price | Price (SEK) | Lo/High indicator | LED3 (always on) | Always shown |
| 7 | Coffee Beans | beanLo/beanok | Distance (cm) | LED4 (warning when low) | Always shown |
| 8 | Date & Time | dd.mm | hh.mm | - | Always shown |
| 9 | Calendar Alerts | Event name | Time (if applicable) | LED5 | Felix 8am events (from 6pm prior day) or Ridlekis Isolde (Saturdays) |

## Button Functions
Buttons 1-4 are configured as toggles. When pressed, they toggle Home Assistant entities and briefly display status. Button 8 is used for calibration.

| Button | TM1638 Key | Function | Home Assistant Entity |
|--------|------------|----------|----------------------|
| 1 | Key 0 | Toggle Bio Office Lights | light.bio_office |
| 2 | Key 1 | Toggle Living Room Lights | light.living_room |
| 3 | Key 2 | Toggle Bedroom Lights | light.bedroom |
| 4 | Key 3 | Toggle Hot Water | switch.smart_plug_2_socket_1 |
| 5-7 | Keys 4-6 | Reserved for future use | - |
| 8 | Key 7 | Calibration Mode | - |

## LED Indicators

| LED | Purpose | Condition |
|-----|---------|-----------|
| LED1 | Air Fryer Active | Lights when air fryer power > 0W |
| LED2 | Bio Office Screen | Lights during Bio Office screen display |
| LED3 | Power Price Screen | Lights during power price screen display |
| LED4 | Coffee Bean Warning | Lights when coffee beans are low |
| LED5 | Calendar Alerts | Lights during calendar event screen display |
| LED6-7 | Reserved | Available for future features |
| LED8 | Calibration Mode | Lights when in calibration mode |

## Home Assistant Integration
The device subscribes to the following Home Assistant entities:

### Sensors
- `sensor.energy_monitoring_smartplug_power` - Air fryer power consumption (Tuya Local, faster updates)
- `sensor.bioofficec3_room_temperature` - Bio office temperature
- `sensor.sam_outside_temperature` - Outside temperature
- `sensor.t_h_sensor_temperature` - Inside temperature
- `sensor.t_h_sensor_humidity` - Inside humidity
- `sensor.nordpool_kwh_se4_sek_3_10_025` - Electricity price

### Switches
- `switch.bio_office_heaters_socket_1` - Bio office heaters status
- `switch.smart_plug_2_socket_1` - Hot water switch status

### Calendar
- `calendar.handl_f` - Family calendar for Felix activities and Isolde riding lessons

### Time
- `homeassistant_time` - Date and time synchronisation

## Calibration Procedure
To calibrate the coffee bean level sensor using Button 8 on the TM1638 (reversed order - start empty and fill up):

1. **Press Button 8** to enter calibration mode - Display shows "CAL Empty", LED8 lights up
2. With the coffee bean container **empty**, **press Button 8** again - Display shows "CAL 50g"
3. Add beans to approximately 50g level, **press Button 8** again - Display shows "CAL FULL"
4. Fill the container to maximum level, **press Button 8** again - Display shows "CAL beep"
5. Trigger the air fryer beep (for future beep detection), **press Button 8** again - Display shows "done"
6. Calibration complete - device returns to normal screen cycling

During calibration, LED8 (index 7) remains lit to indicate calibration mode is active.

## Calendar Event Alerts
The device monitors `calendar.handl_f` for specific family events:

### Felix Activities (8am events)
- Displays from **6pm the day before** until **8am on event day**
- Events starting with "Felix" are automatically shortened:
  - **"Felix Swim"** → displays as **"F. Swim"**
  - **"Felix Idrott"** → displays as **"F.   PE"**
  - Other Felix events → displays as **"F."** + first 4 chars after "Felix"
- LED5 lights up during display

### Isolde Riding Lessons (Saturdays 9:30am)
- Displays when **"Ridlekis Isolde"** event found on Saturdays
- Shows **"Riding 930"** on display
- LED5 lights up during display

These alerts help ensure morning activities aren't forgotten!

## Air Fryer Beep Detection
When the air fryer beep is detected:
1. The flood light turns green (RGB: 0, 255, 0) at full brightness
2. After 2 seconds, the flood light turns off
3. A notification is sent to your mobile app

This provides a clear visual alert that the air fryer needs attention.

## Notes
- The TM1638 display uses the same GPIO pins previously allocated to the Nokia 5110 screen
- Display intensity is set to 7 (maximum brightness range: 0-7)
- Screens auto-cycle every 3.5 seconds
- Button press feedback is displayed for 1 second
- All sensors have fallback displays if data is unavailable
- Calibration mode takes priority over normal display cycling
- GPIO21 is now available for other uses (no longer needed for calibration)
- LED indicators (LED2, LED3) now show actual data instead of "LED" labels
- Screen 1 combines Bio heater status and temperature on one screen with LED2 indicator
- Screen 6 shows power price (left) and "Lo" or "High" indicator (right) based on the `low_price` attribute with LED3 indicator
- Display is cleared between screen updates to prevent character hangover
- Humidity displays with one decimal place (e.g., "65.5")
- Screen 0 (Air Fryer) is automatically skipped when power is 0 or unavailable - only displays when air fryer is active
- Air fryer power displays as whole watts (e.g., "1500" not "1500.5")
- Screen 9 (Calendar) is automatically skipped unless there's a relevant Felix or Isolde event
- Calibration order has been reversed: start with empty container and fill up (easier than removing beans)
- Bio temperature now displays with °C suffix on screen 1
