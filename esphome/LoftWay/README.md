# LoftWay (`NewLoftWayC3.yaml`)

ESP32-C3 (SuperMini / devkitm-1) configuration for:

- Bluetooth proxy extension
- Local AHT20 temperature/humidity sensing
- Local MQ2 gas/smoke sensing
- 16x2 I2C LCD dashboard (`lcd_pcf8574`)
- PIR-driven LCD backlight timeout
- PWM LCD backlight dimming (external transistor on `GPIO4`)
- Push button for LCD backlight, then Loft LEDs (hold = all off)
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
6. **Indoor bins** — shown from **18:00 the evening before** a BEDA
   collection until the end of collection day (same window as the
   calendar). Skipped the rest of the week. Reminder to empty indoor
   bins, not to take the outdoor containers out.
   - Top: `Empty tomorrow` / `Empty today`
   - Bottom: `RecylBin` (C1 packaging), `OtherBin` (C2 food/residual/
     newspapers/coloured glass), or `BothBins` if both are due.

Top row is used for compact numeric/status info, bottom row for descriptive/scrolling text.

All text coming from Home Assistant (calendar titles, notification
bodies) is transliterated to 7-bit ASCII before being printed so the
HD44780 A00 character ROM doesn't render Swedish/European diacritics
as garbage. `Å Ä Ö ö ä å` etc. become their nearest ASCII letters.

## Backlight Behaviour

Two brightness levels, both PWM on `GPIO4` (linear, gamma 1.0):

- **Any motion** (PIR rising edge): dim glow immediately.
  `dim_brightness_day` (default 16%) or `dim_brightness_night`
  (default 4%, very dim). Holds for `dim_hold_seconds` (8 s) after
  the last pulse.
- **Lingering** (PIR ON continuously for `pir_continuous_on_seconds`,
  default 5 s): full brightness from the HA sliders. Holds for
  `backlight_hold_seconds` (20 s) after that window. If the night
  slider is 0, lingering uses the day slider so the LCD still comes
  up bright when you stand there.
- At boot the backlight is forced full for 30 s. A short press of
  the lights button forces full for 60 s.
- **23:00–07:00:** PWM is capped at `dim_brightness_night` (4%).
  Linger, button and boot cannot go brighter. The tap sequence still
  runs; only the LCD stays dim.
- **Bedtime:** while the Pixel 8 is on charge
  (`binary_sensor.pixel_8_is_charging`) between `pir_quiet_from_hour`
  (21) and `pir_quiet_until_hour` (07), motion does not light the LCD
  at all — no dim glow, no linger. A button tap still does, and
  `LoftC3 Motion` still reports to HA.

Day vs night dim level is decided by the clock + `sun.sun`:

- **Day** = 07:00 onwards until **min(sunset, 23:00)**.
- **Night** = otherwise (incl. forced after 23:00 even if sun
  technically up at high latitudes in summer). PIR dim uses 4% in
  this window; the hard “never bright” cap is clock-only 23:00–07:00.

Between dashboard pages the backlight does a **fade-through-black**
(`fade_thru_black_out_ms` 450 ms down, `fade_black_hold_ms` 50 ms black,
`fade_thru_black_in_ms` 120 ms up). Set `fade_thru_black_out_ms` to
`0` to disable the effect. Calendar event-to-event on the same page
does not fade.

## Wiring / Pin Assignments

ESP32-C3 SuperMini GPIOs already taken by the original sensors are
`GPIO0`–`GPIO3`. Remaining clean pins are `GPIO4`–`GPIO7`, `GPIO10`,
`GPIO20`, `GPIO21`. Avoid `GPIO8` (onboard LED on many SuperMini
boards) and `GPIO9` (BOOT button).

| Component | ESP32-C3 pin | Notes |
|---|---|---|
| LCD1602 + PCF8574 `SDA` | `GPIO1` | Shared I2C bus |
| LCD1602 + PCF8574 `SCL` | `GPIO2` | Shared I2C bus |
| AHT20 `SDA` | `GPIO1` | Same bus as LCD |
| AHT20 `SCL` | `GPIO2` | Same bus as LCD |
| MQ2 analog output (`AO`) | `GPIO0` | ADC input |
| PIR AM312 output (`OUT`) | `GPIO3` | Motion input |
| LCD backlight PWM (transistor base/gate) | `GPIO4` | Via `1 kΩ`. LEDC PWM, not a strapping pin, next to the existing GPIO0–3 wiring |
| Loft lights push button | `GPIO10` | Momentary N.O. to `GND`, internal pull-up. GPIO5 pad is damaged; do not use GPIO9 (BOOT) or GPIO8 (onboard LED) |
| LCD1602 + PCF8574 `VCC` | `5V` (or `3.3V` if stable) | 5V gives brighter backlight; use level-safe I2C wiring |
| MQ2 `VCC` | `5V` | Typical MQ2 boards expect 5V heater supply |
| PIR AM312 `VCC` | `5V` | See note below - 3.3V is *technically* in spec but unreliable on most AM312 clones |
| Ground | `GND` | Common ground for all modules |

Pins still free: `GPIO6`, `GPIO7`, `GPIO20`, `GPIO21`. Avoid `GPIO6`
if the GPIO5 corner of the board is damaged — it is the next pad
along that edge.

## LCD Backpack Notes

- Default I2C address is configured as `0x27` via `lcd_i2c_address`.
- Some boards use `0x3F`; if the display is not found, change that substitution.
- The backpack has a 2-pin jumper labelled `LED`, not `BLA`/`BLK`.
  That jumper is **5V to the LED anode**. Do not put an NPN across it
  to GND — that shorts USB. Dimming is on the cathode (LCD pin 16);
  see below.
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
- `input_number.loftc3_lcd_brightness_day` - full brightness when lingering (day)
- `input_number.loftc3_lcd_brightness_night` - full brightness when lingering after sunset until 23:00; 0 falls back to the day slider. Ignored 23:00–07:00 (capped at 4%).
- `input_text.minidisplay_notification_ids`
- `input_text.minidisplay_notification_titles`
- `input_text.minidisplay_notification_messages`
- `calendar.webcal_im2_api_infomentor_se_v1_calendarv2_icalsubscription_subscription_f0d28bc2_1243_4b0e_962c_02243eeea583`
- `calendar.http_im2_api_infomentor_se_v1_calendarv2_icalsubscription_subscription_8cd9caaa_3f4e_4ee4_b8e8_662e4aa39f09`
- `calendar.handl_f`
- `sensor.handl_f_loft_calendar_slots` — multi-event feed for the family calendar (see `ElectricAutomations/loft_calendar_sensors.yaml`)
- `sensor.waste_collection_schedule_beda_container_1_packaging_of_paper_plastic_metal_and_clear_glass` — BEDA C1 (packaging)
- `sensor.waste_collection_schedule_beda_container_2_food_waste_residual_waste_newspapers_and_colored_glass` — BEDA C2 (food/residual)
- `light.loft_lights`, `light.isp_1a3c38_3c38`, `light.isp_0db21e_b21e` — tap-2 LED sets (Loft area)

Family calendar events use the same visibility window as KitchenDetectorer: each event is shown from **18:00 the day before** its start until its end time, so from 6pm you see **tomorrow’s** entries (and any still-active events tonight). The indoor-bin reminder uses that same 18:00-evening-before window against the two BEDA waste-collection sensors.

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

## LCD backlight dimming (`GPIO4`)

The PCF8574 backpack can only switch the backlight on or off over I2C.
Firmware therefore holds that backpack pin **off** (`it.no_backlight()`)
and PWMs `GPIO4` instead.

These clones have a 2-pin jumper labelled **`LED`**, not `BLA`/`BLK`.
The jumper sits in the **anode** path:

```
5V (VCC pad) --[LED jumper]-- LCD pin 15 (LED+) --[backlight LEDs]-- LCD pin 16 (LED-) -- resistor -- backpack transistor -- GND
```

With the jumper off, a meter from each pad to GND shows:

- **~5 V** = VCC. Never connect the NPN collector here.
- **~0 V** (or a couple of volts of leakage) = LED+. The ~−3 V reading
  across the two pads is just 5 V minus that LED+ voltage with the
  probes swapped. It is not a cathode.

Putting an NPN from either jumper pad to GND, with the jumper on (or
from the 5 V pad with the jumper off), saturates 5 V straight to GND
when GPIO4 goes high at boot. USB then current-limits / drops out.
That is a short, not a firmware bug. **Unplug the collector wire
before plugging USB in again.**

### Transistor pinout (TO-92, flat towards you)

A real 2N2222A / PN2222A is **E B C** left to right. Confirm with the
diode range: base (middle) to each outer pin should read ~0.6 V one
way only. Cheap “2N2222” parts are sometimes **C B E** (BC547 style);
if C–E reads as a diode, the pinout is swapped.

### Correct NPN wiring (low-side on the cathode)

1. **Put the LED jumper back on** so pin 15 stays fed from 5 V.
2. Find **LCD pin 16** (LED−). It is the last pin of the 16-pin LCD
   header, at the same end as the LED jumper — the pin *next to*
   pin 15, not either jumper pad. On the solder side it is often a
   thin track to a small resistor beside a SOT/TO transistor.
3. Wire:
   - **E** → ESP `GND`
   - **C** → LCD **pin 16** (LED− / that resistor’s LCD-side pad)
   - **B** → `1 kΩ` → **`GPIO4`**
4. Firmware holds the backpack transistor off, so only this NPN
   conducts and the day/night sliders are real 0–100 PWM.

The backpack is already soldered through those header pins. A wire on
the **top** of pin 16 is the intended connection — leave the backpack
on pin 16. Firmware holds the backpack backlight transistor **off**,
so pin 16 floats until the external NPN pulls it to GND.

A continuity beep pin 16 → GND that comes and goes is that backpack
transistor, not a hard short. First beep then open is normal (last
I2C state, or the meter biasing P3). A **permanent** beep with power
off and the NPN disconnected would mean pin 16 is tied to GND; this
board is not that. Do not unsolder pin 16.

Continuity **will not** show the USB-killing fault. A meter’s
continuity beep is for a near-0 Ω wire. The NPN **B–E junction is a
diode** (~0.6 V), so GPIO4 (or 5 V / 3.3 V) to GND through E and B
reads “open” and still crowbars the rail the instant power is applied.
On the SuperMini, **GPIO4 sits immediately below 5 V / GND / 3.3 V**.
If the “GPIO4” wire is actually on **5 V** or **3.3 V**, Emitter on
GND, and there is no 1 kΩ (or the 1 kΩ is bypassed), USB current-limits
with pin 16 **disconnected**. That is this diode, not a pin-16 short.

Prove it:

1. Remove the transistor entirely (all three leads). Plug USB in. If
   the port is still unhappy, the 3.3 V regulator may already be
   wounded from the earlier crowbar — the transistor is no longer the
   live fault.
2. If USB is happy with the transistor off, the wiring is wrong. Confirm
   the PWM wire is on the pad labelled **4**, not `5V` or `3.3V`.
3. **1 kΩ must be in series with the base.** Without it, B–E is a diode
   straight onto the rail.
4. Diode-range on the meter: base (middle) to emitter should be ~0.6 V
   one way only. Continuity mode will often stay silent.

Watch for a solder blob to **pin 15** (adjacent, 5 V). That is a USB
crowbar even with the transistor unplugged.

Do not solder the collector to the LED jumper. That jumper is 5 V.

Without the transistor on pin 16 the LCD stays dark (the backpack pin
is no longer used). Desolder any jumper-pad wiring first, then fit
the NPN on pin 16 and plug in.

## Loft lights push button (`GPIO10`)

Momentary **normally-open** push button between **`GPIO10` and GND**
(switches to earth). Internal pull-up, inverted, debounced. The GPIO5
corner pad is damaged, so the button lives on GPIO10 (further along
the same header, not BOOT / onboard LED).

Gestures while the 1-minute full backlight window is active. The
sequence resets when that window expires. Successful light overlays
last about 2 seconds. Tap 1 does not overlay the dashboard.

- **Tap 1:** LCD backlight full for 60 s (night-dim only 23:00–07:00).
  No room lights. No overlay.
- **Tap 2** (backlight still on): turn on only
  `light.loft_lights`, `light.isp_1a3c38_3c38`,
  `light.isp_0db21e_b21e`. Overlay `LEDs on` then `n/3 on`. A miss is
  retried after 1.5 s. Backlight refreshed another 60 s.
- **Tap 3:** all lights in HA area `loft`. Overlay `All loft on`.
- **Tap 4** (all loft already on): back to the three LED sets
  only (desk/spots off). Overlay `LEDs on`. Another tap goes to
  all loft again.
- **Hold (~600 ms):** turn off loft lights **except the stairs**.
  Overlay `Lights off` / `stairs stay`.
- **Keep holding (~1 s more), night only:** also turn off the stairs
  light and turn on `light.gu10_b505z2_2` (loft spot south) for 30 s
  as a path light. Overlay `Stairs off` / `path 30s`. The GU10 may be
  unavailable; that call is allowed to fail. Daytime extra hold does
  nothing — stairs stay on.

The button publishes `sensor.loft_loftc3_light_command`. Automation
`loftc3_light_command` actually switches the lights. BLE LED sets are
staggered so the proxy is not flooded.

Plugging in the Pixel 8 after 21:00 / before 06:45 runs
`Loft lights off Pixel charge`: loft floor off, then the stairs
strip (`light.isp_0db21e_b21e`) to red at 3%. The Pixel wall
charger reports `ac`, so that value is a trigger as well as `usb`.
The red command is last, because the floor turn-off includes the
stairs and would otherwise leave them off. The other iDeal strips
are only switched off. HA cannot see DIY patterns
([idealLED](https://github.com/8none1/idealLED) has no state
discovery and does not expose DIY); the stairs red write replaces
that strip's DIY, the others can resume on a bare LoftC3
`light.turn_on`. Hold still only turns the room lights off (stairs
stay, including the dim red). Extra hold at night still kills the
stairs.

The ESPHome dashboard “`homeassistant.service` → `homeassistant.action`”
banner is **not** LoftC3 (this device no longer calls HA actions). It
appears on BedroomLights, Kitchen Detectorer, MiniDisplay and
Downstairs Allrum. Click **Update config** on those devices if you
want the rename applied there.

## Build/Bring-up Checklist

1. Wire modules according to the pin table. The `GPIO4` transistor
   collector goes to LCD **pin 16**, not the `LED` jumper. Leave the
   jumper on. Button on **`GPIO10` to GND** (not GPIO5).
2. Flash `NewLoftWayC3.yaml`.
3. Check boot logs for detected I2C devices (`0x27` or `0x3F`).
4. Confirm the LCD backlight PWM: boot should light it for 30 s
   (dim only if the clock is 23:00–07:00); the day slider should
   dim it. If USB current-limits, the collector is on the 5 V jumper
   pad — unplug and move it to pin 16. If the LCD stays dark with USB
   happy, the transistor is on the anode or the LED jumper is off.
5. Trigger PIR movement and verify backlight timeout behaviour.
6. Press the GPIO10 button once: LCD should go full for 1 minute
   (stays at night-dim if the clock is 23:00–07:00).
   Press again while it is on: the three loft LED sets should come on
   (staggered; a miss is retried). Press a third time: all Loft-area
   lights. Press a fourth time: back to the three LED sets only.
   Hold ~600 ms: loft lights off, stairs stay. Keep holding
   at night: stairs off and south spot on for 30 s. If nothing
   happens, confirm the button wire is on GPIO10 not GPIO5.
7. Confirm weather/calendar/notification entities exist in Home Assistant.

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
3. **Try a different GPIO.** Set `pir_pin: "GPIO7"` (or `GPIO6`,
     `GPIO20`) and reflash. Do not steal `GPIO4` (backlight PWM) or
     `GPIO10` (lights button). This rules out a damaged or
     repurposed input pin.
4. **Try with `pir_pulldown: "true"`.** Some AM312 boards float `OUT`
   when idle; this nails idle LOW so transitions to HIGH are clean.
5. **Try with `pir_pullup: "true"` and `pir_inverted: "true"`.** Some
   open-collector clones pull LOW on motion instead of HIGH.
6. **Replace with an HC-SR501.** AM312 modules are extremely
   hit-and-miss on no-name suppliers; HC-SR501 has on-board
   sensitivity / time pots and is far more forgiving.
