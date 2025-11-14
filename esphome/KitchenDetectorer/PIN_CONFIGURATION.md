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
The device cycles through up to 11 screens every 3.5 seconds (some are conditionally skipped):

| Screen | Description | Left Display | Right Display | LED Indicator | Condition |
|--------|-------------|--------------|---------------|---------------|-----------|
| 0 | Air Fryer Power | "AirW" | Power (whole watts) | - | Only shown when power > 0 |
| 1 | Bio Office Climate | on/off | Current Temp °C | LED2 (always on) | Always shown |
| 2 | Hot Water | "hot" | Boiler Temp °C | - | Always shown |
| 3 | Outside Temp | "out" | Temperature °C | - | Always shown |
| 4 | Inside Temp | "in" | Temperature °C | - | Always shown |
| 5 | Inside Humidity | "in h" | Humidity (with decimal) | - | Always shown |
| 6 | Power Price | Price (SEK) | Lo/High indicator | LED5 (always on) | Always shown |
| 7 | Coffee Beans | beanLo/beanok | Distance (cm) | - | Always shown |
| 8 | Date & Time | dd.mm | hh.mm | - | Always shown |
| 9 | Calendar Alerts | Event name | Time (if applicable) | - | Felix 8am events or Ridlekis Isolde (Saturdays) |
| 10 | Manifold Temps | Loop temp | Air temp °C | LED1 (always on) | Only shown when sensor data available |

## Button Functions
Buttons 1-4 turn off all lights in their respective areas and Button 2 also controls climate. Button 8 is used for calibration.

**Button 2 (Bio/Bio Office)** has special logic:
- **Always** turns off all lights in the **bio** area
- If **bio_office climate is heating** → turns climate **OFF**
- If **bio_office climate is OFF** → turns climate to **HEAT** mode
- Climate state controls heating in bio_office (separate from bio lights)
- Matches LED2 which indicates Bio Office climate data on screen 1

| Button | TM1638 Key | Function | Area / Entity |
|--------|------------|----------|---------------|
| 1 | Key 0 | Turn off Living Room lights | area: living_room |
| 2 | Key 1 | Turn off Bio lights + toggle Bio Office climate | area: bio + climate.bio_office_heat |
| 3 | Key 2 | Turn off Bedroom lights | area: bedroom |
| 4 | Key 3 | Turn off Parent's Bedroom lights | area: parent_s_bedroom |
| 5-7 | Keys 4-6 | Reserved for future use | - |
| 8 | Key 7 | Calibration Mode | - |

## LED Indicators

| LED | Purpose | Condition |
|-----|---------|-----------|
| LED1 | Manifold Screen | Lights during manifold temperature screen display (screen 10) |
| LED2 | Bio Office Screen | Lights during Bio Office climate screen display (screen 1) |
| LED3 | Reserved | Available for future use |
| LED4 | Reserved | Available for future use |
| LED5 | Power Price Screen | Lights during power price screen display (screen 6) |
| LED6 | Boiler/Heater Status | Lights when any boiler relay is active |
| LED7 | Alarm Level | Flashes based on Home Assistant alarm level (see below) |
| LED8 | Low Beans Alert | **Flashes continuously** when beans are low (any screen) |

### Alarm Level LED Patterns (LED7)
LED7 syncs with the Home Assistant `input_select.alarm_level` entity and uses the same flashing pattern as MiniDisplay:

| Alarm Level | LED Pattern |
|-------------|-------------|
| OK | LED off |
| Notify | Single 300ms flash every 60 seconds |
| Take Action | Double flash every 20 seconds |
| Emergency | Rapid constant flash (200ms on/off) |

## Home Assistant Integration
The device subscribes to the following Home Assistant entities:

### Sensors
- `sensor.energy_monitoring_smartplug_power` - Air fryer power consumption (Tuya Local, faster updates)
- `sensor.bioofficec3_room_temperature` - Bio office temperature
- `sensor.sam_outside_temperature` - Outside temperature
- `sensor.t_h_sensor_temperature` - Inside temperature
- `sensor.t_h_sensor_humidity` - Inside humidity
- `sensor.nordpool_kwh_se4_sek_3_10_025` - Electricity price
- `sensor.manifoldtemperature_hot_water_boiler_temp` - Hot water boiler temperature
- `sensor.manifoldtemperature_lowest_loop_return_temp` - Lowest heating loop return temperature
- `sensor.manifoldtemperature_air_temp` - Manifold air temperature

### Switches & Climate
- `climate.bio_office_heat` - Bio office heating climate control
- `switch.smart_plug_2_socket_1` - Hot water switch status
- `switch.boilercontrol_boiler_relay_1` - Boiler relay 1 status (for LED6)
- `switch.boilercontrol_boiler_relay_2` - Boiler relay 2 status (for LED6)

### Binary Sensors
- `binary_sensor.felix_morning_alert` - Indicates when Felix has a morning activity (custom template helper)
- `binary_sensor.isolde_morning_alert` - Indicates when Isolde has riding lesson (custom template helper)

### Calendar & Text Sensors
- `calendar.handl_f` - Family calendar entity (provides event names for display)
- `input_select.alarm_level` - Home Assistant alarm level for LED7 flashing pattern

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
The device uses **Home Assistant binary sensors** to reliably track family events, even when multiple events exist on the same day.

### Required Home Assistant Binary Sensors
The device monitors these binary sensors (create via Settings → Devices & Services → Helpers → Template):

**`binary_sensor.felix_morning_alert`** - Felix morning activity alert
```yaml
{# Check if there's a Felix 8am event today or tomorrow #}
{% set ns = namespace(found=false) %}
{% set cal_state = states('calendar.handl_f') %}
{% if cal_state != 'unavailable' and 'Felix' in state_attr('calendar.handl_f', 'message') | default('') %}
  {% set event_start = state_attr('calendar.handl_f', 'start_time') %}
  {# Show alert from 6pm day before until 8am event day #}
  {% set ns.found = true %}
{% endif %}
{{ ns.found }}
```

**`binary_sensor.isolde_morning_alert`** - Isolde riding lesson alert
```yaml
{# Check for Ridlekis Isolde on Saturdays #}
{% set ns = namespace(found=false) %}
{% set cal_state = states('calendar.handl_f') %}
{% if cal_state != 'unavailable' and 'Ridlekis Isolde' in state_attr('calendar.handl_f', 'message') | default('') %}
  {% set ns.found = true %}
{% endif %}
{{ ns.found }}
```

### Felix Activities Display
- Calendar screen appears when `binary_sensor.felix_morning_alert` is ON
- Events starting with "Felix" are automatically shortened:
  - **"Felix Swim"** → displays as **"F. Swim"**
  - **"Felix Idrott"** → displays as **"F.   PE"**
  - Other Felix events → displays as **"F."** + first 4 chars after "Felix"
- LED5 lights up during display

### Isolde Riding Lessons Display
- Calendar screen appears when `binary_sensor.isolde_morning_alert` is ON
- Shows **"Riding 930"** on display
- LED5 lights up during display

**✅ Benefit**: This approach works even when multiple events exist on the same day! The binary sensors can analyze the full calendar while ESPHome displays the relevant event name.

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
- Screen 1 (Bio Office) now displays climate.bio_office_heat state and current temperature
- Screen 2 (Hot Water) displays boiler temperature on the right side
- Screen 9 (Calendar) is automatically skipped unless there's a relevant Felix or Isolde event
- Screen 10 (Manifold) combines both loop and air temperatures on one screen with LED1 indicator
- Screen 10 is automatically skipped unless manifold temperature sensors are available
- Calibration order has been reversed: start with empty container and fill up (easier than removing beans)
- Button 2 turns off all bio area lights and toggles bio_office climate between heat and off
- All button presses use area-based light.turn_off for better control across multiple devices
- LED1 indicates manifold temperature screen (screen 10)
- LED2 indicates Bio Office screen (screen 1) to match Button 2
- LED5 indicates power price screen (screen 6)
- LED6 lights up when any boiler heating relay is active
- LED7 flashes based on Home Assistant alarm level with the same pattern as MiniDisplay
- LED8 flashes continuously (500ms interval) whenever beans are low
