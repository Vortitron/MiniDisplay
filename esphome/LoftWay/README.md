# LoftWay (`NewLoftWayC3.yaml`)

ESP32-C3 (SuperMini / devkitm-1) configuration for:

- Bluetooth proxy extension
- Local AHT20 temperature/humidity sensing
- Local MQ2 gas/smoke sensing
- 16x2 I2C LCD dashboard (`lcd_pcf8574`)
- PIR-driven LCD backlight timeout
- Home Assistant calendar + notification display

## Display Pages (auto-cycle)

The LCD rotates every 8 seconds:

1. **Time/Date**
2. **Weather**
   - Top row: live outside (from HA) + inside (AHT20) temperatures.
   - Bottom row: `D 12.3C pcloudy` (day max + condition) or
     `N  8.2C rain` (night min + condition). Uses 15:00–03:00 for night min.
3. **Local sensors** (AHT20 + MQ2 status)
4. **Calendar events** — each active event shown for 4 seconds before
   advancing to the next; all events are shown before moving on.
5. **Notifications** (from HA `input_text` helpers)

Top row is used for compact numeric/status info, bottom row for descriptive/scrolling text.

All text coming from Home Assistant (calendar titles, notification
bodies) is transliterated to 7-bit ASCII before being printed so the
HD44780 A00 character ROM doesn't render Swedish/European diacritics
as garbage. `Å Ä Ö ö ä å` etc. become their nearest ASCII letters.

## Backlight Behaviour

- Backlight only turns on when the PIR sees motion **continuously for
  `pir_continuous_on_seconds`** (default 5 s). Brief blips
  (settling shadows, a moth) never light the display.
- After the last continuous-motion window the backlight stays on for
  `backlight_hold_seconds` (default 20 s).
- At boot the backlight is forced on for 30 s for setup visibility.
- Day vs night is decided by the clock + `sun.sun`:
  - **Day** = 07:00 onwards until **min(sunset, 23:00)**.
  - **Night** = otherwise (incl. forced after 23:00 even if sun
    technically up at high latitudes in summer).
- Brightness during day and night is controlled by two HA helpers
  (`input_number.loftc3_lcd_brightness_day` and `_night`). The
  PCF8574 backpack **cannot dim by I2C**, so the firmware currently
  treats `> 0` as "backlight on" and `0` as "backlight off". The
  slider values are read from HA anyway so a future hardware-PWM mod
  can be wired in without touching HA. See "Real dimming requires a
  hardware mod" below.

## Wiring / Pin Assignments

| Component | ESP32-C3 pin | Notes |
|---|---|---|
| LCD1602 + PCF8574 `SDA` | `GPIO1` | Shared I2C bus |
| LCD1602 + PCF8574 `SCL` | `GPIO2` | Shared I2C bus |
| AHT20 `SDA` | `GPIO1` | Same bus as LCD |
| AHT20 `SCL` | `GPIO2` | Same bus as LCD |
| MQ2 analog output (`AO`) | `GPIO0` | ADC input |
| PIR AM312 output (`OUT`) | `GPIO3` | Motion input, pulldown enabled |
| LCD1602 + PCF8574 `VCC` | `5V` (or `3.3V` if stable) | 5V gives brighter backlight; use level-safe I2C wiring |
| MQ2 `VCC` | `5V` | Typical MQ2 boards expect 5V heater supply |
| PIR AM312 `VCC` | `5V` | See note below - 3.3V is *technically* in spec but unreliable on most AM312 clones |
| Ground | `GND` | Common ground for all modules |

## LCD Backpack Notes

- Default I2C address is configured as `0x27` via `lcd_i2c_address`.
- Some boards use `0x3F`; if the display is not found, change that substitution.
- Keep the backpack backlight jumper fitted if software backlight control is required.
- If the LCD backpack is powered at 5V, ensure SDA/SCL are not pulled beyond 3.3V at the ESP32-C3 (level shifter or compatible board).

## Safety Notes

- ESP32-C3 ADC pins are **not 5V tolerant**. Ensure MQ2 `AO` never exceeds 3.3V at `GPIO0` (divider/buffer if needed).

## Required Home Assistant Entities

These are set in substitutions at the top of `NewLoftWayC3.yaml` and can be changed there:

- `sensor.sam_outside_temperature`
- `sensor.openweathermap_condition`
- `sensor.forecast_today_max` - HA template sensor (see `ElectricAutomations/forecast_sensors.yaml`)
- `sensor.forecast_tonight_min` - HA template sensor (same file)
- `sun.sun` - HA built-in sun entity
- `input_number.loftc3_lcd_brightness_day` - 0-100 helper
- `input_number.loftc3_lcd_brightness_night` - 0-100 helper
- `input_text.minidisplay_notification_ids`
- `input_text.minidisplay_notification_titles`
- `input_text.minidisplay_notification_messages`
- `calendar.webcal_im2_api_infomentor_se_v1_calendarv2_icalsubscription_subscription_f0d28bc2_1243_4b0e_962c_02243eeea583`
- `calendar.http_im2_api_infomentor_se_v1_calendarv2_icalsubscription_subscription_8cd9caaa_3f4e_4ee4_b8e8_662e4aa39f09`
- `calendar.handl_f`
- `sensor.handl_f_loft_calendar_slots` — multi-event feed for the family calendar (see `ElectricAutomations/loft_calendar_sensors.yaml`)

Family calendar events use the same visibility window as KitchenDetectorer: each event is shown from **18:00 the day before** its start until its end time, so from 6pm you see **tomorrow’s** entries (and any still-active events tonight).

### Suggested HA helper YAML

Add these via `configuration.yaml` or the Helpers UI:

```yaml
input_number:
  loftc3_lcd_brightness_day:
    name: LoftC3 LCD brightness (day)
    min: 0
    max: 100
    step: 5
    initial: 100
    icon: mdi:brightness-6
  loftc3_lcd_brightness_night:
    name: LoftC3 LCD brightness (night)
    min: 0
    max: 100
    step: 5
    initial: 0
    icon: mdi:brightness-3
```

Include the Loft family-calendar package alongside the forecast sensors:

```yaml
homeassistant:
  packages:
    minidisplay_forecast: !include MiniDisplay/ElectricAutomations/forecast_sensors.yaml
    loft_calendar: !include MiniDisplay/ElectricAutomations/loft_calendar_sensors.yaml
```

The forecast template sensors can be derived from any weather
integration via `weather.get_forecasts`. Example using
`weather.openweathermap`:

```yaml
template:
  - trigger:
      - platform: time_pattern
        minutes: "/15"
    action:
      - service: weather.get_forecasts
        data:
          type: daily
        target:
          entity_id: weather.openweathermap
        response_variable: fc
    sensor:
      - name: "Forecast today max"
        unique_id: forecast_today_max
        unit_of_measurement: "°C"
        device_class: temperature
        state: "{{ fc['weather.openweathermap'].forecast[0].temperature }}"
      - name: "Forecast tonight min"
        unique_id: forecast_tonight_min
        unit_of_measurement: "°C"
        device_class: temperature
        state: "{{ fc['weather.openweathermap'].forecast[0].templow }}"
```

## Real dimming requires a hardware mod

The PCF8574 LCD backpack drives the LCD backlight through a single
on/off pin on the PCF8574 chip. There is no way to PWM that from
ESPHome without saturating the I2C bus, so the firmware deliberately
treats brightness as binary (`>0` = on, `0` = off).

To get true dimming:

1. **Cut the backlight jumper** on the back of the PCF8574 board.
2. Wire a small **NPN transistor (e.g. 2N2222)** or N-MOSFET (e.g.
   2N7000):
   - Collector / drain to the backlight `BLA` pad on the LCD side
     of the cut jumper.
   - Emitter / source to GND.
   - Base / gate via a `1 kΩ` resistor to a free **PWM-capable GPIO**
     on the ESP32-C3 (`GPIO4`, `GPIO5`, `GPIO20` are good options).
3. Add an `output: ledc` block and a `monochromatic` light component
   in `NewLoftWayC3.yaml` that drives that GPIO. Replace the current
   `it.backlight()` / `it.no_backlight()` calls in the display lambda
   with `id(lcd_backlight_light).turn_on().set_brightness(brightness / 100.0f).perform();`
   and similar.

When the hardware mod is in place, the existing `lcd_brightness_day`
and `lcd_brightness_night` sliders will already feed the right
values - no HA changes needed.

## Build/Bring-up Checklist

1. Wire modules according to the pin table.
2. Flash `NewLoftWayC3.yaml`.
3. Check boot logs for detected I2C devices (`0x27` or `0x3F`).
4. Trigger PIR movement and verify backlight timeout behaviour.
5. Confirm weather/calendar/notification entities exist in Home Assistant.

## Troubleshooting

### LCD is backlit but shows no text

Almost always the **contrast trim-pot** on the back of the PCF8574 backpack.
The display lambda is verifiably running (the ESPHome scheduler logs
`display took a long time for an operation` when the lambda writes to
the PCF8574). Backlight working confirms I2C is talking to the chip.

Steps:

1. Turn the blue trim-pot on the backpack slowly clockwise until faint
   character cells appear, then back off slightly until clean text shows.
2. If turning the pot has zero effect across its full range:
   - Check the LCD ribbon to the backpack is fully seated.
   - Confirm `VCC` is 5V (3.3V often leaves segments too dim to see).
   - Some PCF8574 clones use a non-standard pin mapping; if a known-good
     5V supply + full pot sweep still shows nothing, that is the cause.

### PIR (AM312) never triggers

The config logs:

- A `[pir]` heartbeat every 60s with the current state.
- A `[pir]` state-change line whenever the sensor flips ON/OFF.

Use those to narrow it down:

- **Heartbeat always `OFF`, no edges, no detection** -> the pin is not
  seeing the AM312 output. Verify wiring, ground, and PIR `VCC` (see
  the "AM312 power gotcha" note immediately below - this is the
  single most common cause).
- **Heartbeat always `ON`** -> set `pir_inverted: "true"` in the
  substitutions block at the top of `NewLoftWayC3.yaml` and reflash.
- AM312 has a **warm-up of ~30-60 s** after power-on during which it
  will not trigger.
- The output pulse is short (~2 s); the YAML already adds
  `delayed_off: 2s` so brief motion still lights the backlight, but if
  the AM312 itself is dead you will never see a single state change.

#### AM312 power gotcha (3.3V vs 5V)

Datasheet says `2.7V-12V`. In practice almost every cheap AM312 module
needs **5V** to operate reliably. A common failure mode at 3.3V is:

- One `OFF -> ON -> OFF` pulse at power-up (the chip's startup
  self-test), and then **nothing ever again**, no matter how much you
  wave at it.

This is because the on-module LDO/comparator front-end only regulates
cleanly above ~4V; at 3.3V the analogue path sits right at its
threshold and the chip cannot re-arm after the first pulse. Plug the
PIR `VCC` into the `5V` (USB / VIN) rail of the ESP32-C3 SuperMini.
The OUT pin is still TTL-safe at 3.3V swing even when the module is
fed 5V, so no level shifter is required.

Other things to check if 5V doesn't fix it:

- Keep the PIR at least ~10 cm away from the ESP module and the LCD;
  PIRs detect IR (heat) changes and a warm neighbour can saturate them.
- The white plastic dome lens **must** be fitted - bare PIR die does
  not have any focusing optics and will not see motion.
- Give it the full 60s warm-up before declaring it dead.

#### Step-by-step diagnostic flow when the heartbeat stays `OFF`

The PIR input pin is set up via these substitutions at the top of
`NewLoftWayC3.yaml`:

| Substitution | Default | Purpose |
|---|---|---|
| `pir_pin` | `GPIO3` | GPIO the AM312 `OUT` is wired to |
| `pir_pullup` | `false` | Enable internal pull-up |
| `pir_pulldown` | `false` | Enable internal pull-down |
| `pir_inverted` | `false` | Flip GPIO logic (active-low PIRs) |

If the 60s `[pir]` heartbeat shows `OFF` forever and waving at the PIR
never produces a state change, work through these in order:

1. **Confirm the wire identity.** AM312 boards label pins (often on
   the back). Make absolutely sure `OUT` is the middle pin and not
   swapped with `GND`. A swapped wire reads a permanent LOW (matches
   your symptom exactly).
2. **Multimeter on AM312 `OUT` vs `GND`.** Wave at the PIR. You should
   see the voltage briefly jump to ~3V for ~2s on each motion event.
   - If yes, the AM312 is fine and the issue is on the ESP side - try
     `pir_pulldown: "true"` or move to a different GPIO via `pir_pin`.
   - If no, the AM312 (or its power supply) is the problem, even with
     5V wired.
3. **Try a different GPIO.** Set `pir_pin: "GPIO10"` (or `GPIO4`,
     `GPIO5`, `GPIO20`) and reflash. This rules out a damaged or
     repurposed input pin.
4. **Try with `pir_pulldown: "true"`.** Some AM312 boards float `OUT`
   when idle; this nails idle LOW so transitions to HIGH are clean.
5. **Try with `pir_pullup: "true"` and `pir_inverted: "true"`.** Some
   open-collector clones pull LOW on motion instead of HIGH.
6. **Replace with an HC-SR501.** AM312 modules are extremely
   hit-and-miss on no-name suppliers; HC-SR501 has on-board
   sensitivity / time pots and is far more forgiving.
