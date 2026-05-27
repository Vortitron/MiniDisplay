# Kitchen Detectorer - Pin & Front-Panel Configuration

## Front-panel labels (for printing)

The TM1638 front panel has 8 buttons (S1..S8) and 8 LEDs (LED1..LED8) running left-to-right above the buttons. The labels below match what the firmware actually does — print these directly onto the housing.

### Button labels (left to right)

| # | Short label (~6 chars) | Full description |
|---|------------------------|------------------|
| 1 | `Living`   | **Living Room lights**: short press = show state, repeat within 8 s = `light.toggle area_id: living_room`; long press (>=0.8 s) = full white at 4000 K |
| 2 | `Bio`      | **Bio lights**: short press = show state, repeat within 8 s = `light.toggle area_id: bio`; long press = full white at 4000 K |
| 3 | `Bedroom`  | **Bedroom lights**: short press = show state, repeat within 8 s = `light.toggle area_id: bedroom`; long press = full white at 4000 K |
| 4 | `Parents`  | **Parents' Bedroom lights**: short press = show state, repeat within 8 s = `light.toggle area_id: parent_s_bedroom`; long press = full white at 4000 K |
| 5 | `Cal`      | **Calendar cycle** - short press jumps to the calendar screen and steps to the next active event; long press (>=0.8 s) opens a 5 s "select duration" window during which buttons 1..8 each start an N-minute snake-egg cooking timer (top LED row are N "eggs", one is eaten per minute) |
| 6 | `Set Tmp`  | **Sam target temperature cycle** (short) - press 1 shows inside temp, then sets `input_number.sam_desired_temperature` to 23 / 20 / 17 °C; **long press** starts **hot water boost** (2 h) |
| 7 | `Lily`     | **Lily feed counter** - short press **+0.5 pouch** (time-since on left, count on right); long press **−1** (floor 0). Resets at **midnight** |
| 8 | `Notify`   | **Notifications** - short press cycles through active notifications; long press dismisses the current one |

### LED labels (left to right)

LEDs 1-3 are the three "current screen" indicators (kept on the left so the row reads as **[screens] [ambient] [alerts]**), LED 4-7 reflect ambient state, and LED 8 is the only flashing alert in normal operation.

| # | Short label (~6 chars) | Meaning when lit |
|---|------------------------|------------------|
| 1 | `Mfld`     | The **Manifold** screen (9) is currently being shown |
| 2 | `BioOff`   | The **Bio Office** climate screen (0) is currently being shown |
| 3 | `Price`    | The **Power Price** screen (5) is currently being shown |
| 4 | `Notif`    | One or more **active HA notifications** are queued (steady) |
| 5 | `HotWtr`   | `switch.smart_plug_2_socket_1` is **on** - hot water is heating (steady) |
| 6 | `Boiler`   | A **boiler / heater relay** is energised (steady) |
| 7 | `Cheap`    | Current Nordpool price is in the **cheap** band (steady) |
| 8 | `Beans`    | Coffee **bean level is low** - flashes at 1 Hz once the ultrasonic distance has stayed in the 5..12 cm "reliable low" band continuously for 10 s (filters out transient bean shifts during a refill) |

When the alarm level is non-OK the firmware additionally **flashes all 8 LEDs in unison** using the same pattern as MiniDisplay (Notify / Take Action / Emergency). Between flashes the labelled meanings above are visible again.

---

## Hardware

### TM1638 Display Module
The TM1638 provides an 8-digit 7-segment display, 8 LEDs, and 8 buttons.

- **STB (Strobe / Chip Select)**: GPIO5
- **CLK (Clock)**: GPIO18
- **DIO (Data I/O)**: GPIO17
- **VCC**: 3.3V or 5V
- **GND**: Ground

### Ultrasonic Sensor (Coffee Bean Level)
HC-SR04 or similar ultrasonic distance sensor for measuring coffee bean level.

- **Trigger Pin**: GPIO12
- **Echo Pin**: GPIO13
- **VCC**: 5V
- **GND**: Ground

### I2S Microphone (Air Fryer Beep Detection)
INMP441 or similar I2S MEMS microphone for detecting air fryer beeps.

- **L/R Clock (LRCLK / WS)**: GPIO15
- **Bit Clock (BCLK / SCK)**: GPIO14
- **Data In (DIN / SD)**: GPIO32
- **VCC**: GPIO4 (powered by GPIO pin, always on)
- **GND**: Ground

The microphone is powered directly from GPIO4, which provides sufficient current (~1-2 mA) for I2S MEMS microphones. This frees up the 3.3 V rail for other components.

A boot-time lambda installs a data callback on `id(mic).add_data_callback(...)` so every captured chunk feeds the running globals `mic_peak_value`, `mic_rms_value`, `mic_peak_window`, `mic_peak_session` and `mic_samples_total`. The `microphone:` is started automatically 2 s after boot and can be re-started/stopped from Home Assistant via `switch.microphone_capture`.

**I2S slot configuration**: the mic is configured `bits_per_sample: 32bit, channel: left` because the INMP441 outputs 24-bit signed PCM **MSB-aligned in a 32-bit slot** and only drives one slot of the I2S frame (selected by the chip's L/R pin - GND = left, 3V3 = right). With the previous 16-bit / `channel: right` defaults the device received chunks of pure zero bytes and `max peak=0` even though the DMA was working at full rate (~32 kB/s). The data callback reads `int32_t` samples and shifts right 16 bits to get an `int16_t`-equivalent peak so the existing threshold tuning stays valid. If your L/R pin is wired to 3V3 instead of GND, change `channel: left` -> `channel: right` in `KitchenDetectorer.yaml`.

**Self-diagnostic**: the first 5 received chunks are dumped as a 16-byte hex sample to the `[I][mic_raw]` log so a wiring failure (all `00` bytes - no signal at all) is visually distinct from a slot-format mismatch (non-zero pattern but tiny values).

### Available GPIO pins
The following pins are available for future expansion:
- GPIO16, GPIO19, GPIO21 (formerly used by Nokia 5110 and the calibration button)
- GPIO22, GPIO23, GPIO25, GPIO26, GPIO27, GPIO33, GPIO34, GPIO35, GPIO36, GPIO39

GPIO4 is now used to power the I2S microphone.

---

## Display Screens

The device cycles through 13 screens (0..12) every 3.5 s. Some are conditionally skipped when their data is unavailable. Numbers without a unit are right-aligned (no trailing blank); numbers with a unit (e.g. `°C`, `h`) keep the unit anchored at the right edge.

(The previous *Air Fryer Power* and *Hours-to-Target* screens have been removed - the device sits next to the air fryer so its power use is already obvious, and the hours-to-target value was rarely useful in practice.)

| Screen | Description | Left (digits 0-3) | Right (digits 4-7) | LED Indicator | Skip condition |
|--------|-------------|-------------------|--------------------|---------------|----------------|
| 0  | Bio Office Climate | ` on `/` off`/` ---` | `%4.1fC` current temp | LED2 | - |
| 1  | Hot Water | `hot ` | ` on `/` off` (overridden by `%4.1fC` boiler temp when present) | - | - |
| 2  | Outside Temp | `out ` | `%4.1fC` | - | - |
| 3  | Inside Temp | `in  ` | `%4.1fC` | - | - |
| 4  | Inside Humidity | `in h` | `%5.1f` (no unit) | - | - |
| 5  | Power Price | `%5.2f` SEK/kWh | `  Lo` / `High` | LED3 + LED7 (if low) | - |
| 6  | Coffee Beans | `Bean Lo ` (only shown while bean_warning_active) | (uses both halves) | LED8 | **Skipped entirely when not low** - the auto-cycle jumps straight to SCREEN_DATETIME, so the device only nags about beans when there really is something to refill. The cm reading is still published to HA as `sensor.kitchen_detectorer_espresso_bean_level` for diagnostics. |
| 7  | Date & Time | `dd.mm` | `hh.mm` | - | - |
| 8  | Calendar Events | `HHMM` static (slots 0..3) - the event's local start time, no colon (the TM1638 has no dedicated colon segment so a literal `:` looks like a stray dot) | event title scrolls leftward over the static `HHMM` over 3 s, eventually obscuring the time entirely as the last 8 chars of the title settle across the whole display. 8am-exact events skip the static `HHMM` and just scroll the title across all 8 slots. | - | No active event in window AND `force_calendar_until` expired |
| 9  | Manifold Temps | `%4.1fC` loop temp | `%4.1fC` air temp | LED1 | Both manifold sensors unavailable |
| 10 | Outside Forecast | scrolled `"Day max XX.XC RAIN 4hr XX.XC"` before 14:00, `"Ngt min XX.XC SUN 4hr XX.XC"` from 14:00 onwards (3 s left-scroll; condition word comes from `sensor.openweathermap_condition` mapped to a 5/6-char abbreviation; missing temperatures render as ` --C`; condition is omitted when its sensor is unknown) | (uses both halves) | - | All three forecast helpers unavailable |
| 11 | Sam Desired Temp | `Set ` | `%4.1fC` | - | `input_number.sam_desired_temperature` unavailable |
| 12 | Notifications | `HHMM` static (slots 0..3) - the local time the notification first appeared on the device, captured via `id(homeassistant_time).now()` | sanitised title scrolls leftward over the static `HHMM`, fully obscuring it by the end of the scroll. Scroll RATE is fixed per cell (`NOTIFY_SCROLL_MS_PER_CELL = 200 ms`) so long titles take longer; a manual B8 short press extends the screen hold to "scroll length + 3 s tail" so the entire title gets seen. Multi-notification cases prepend `"N of M "` to the title before scrolling. | LED4 (steady) + alarm flash | No notes and alarm = OK |

Notes on formatting:
- The decimal point on the TM1638 is absorbed into the previous digit, so `"%.1f"` only fills 3 display positions for a value like `23.5`. We therefore use `"%5.1f"` (5-char field, leading space) for unit-less floats and `"%4.1fC"` for `°C` values, so the right-most position is always the digit or unit and never a blank.
- Integers without a unit use `"%4d"` for the same reason.
- The whole 8-digit display is overwritten each frame (`it.print("        ")` clear), so nothing leaks from the previous screen.

---

## Button behaviour in detail

### Buttons 1, 2, 3, 4 (Living / Bio / Bedroom / Parents lights)
All four follow the same "press to see, press to toggle" pattern modelled on MiniDisplay's back-button on light entities. Idle timeout is 8 s, and the per-button last-press time is tracked in `last_lights_button` / `last_lights_button_press` so each button has its own toggle window (pressing Living then Bio resets the cycle for Bio).

| Situation | Action | On-display feedback |
|-----------|--------|---------------------|
| Short press (held < 0.8 s) from idle, **or** a different button was the last one pressed | Show the area's current light state. **No HA call.** | `Liv  on` / `Liv  off` (or the matching `Bio  ` / `Bedr ` / `Par  ` prefix). Reads `Liv  -- ` if the binary_sensor helper hasn't published yet. ~8 s overlay. |
| Short press again within 8 s (same button) | `light.toggle` with `area_id: living_room` (or `bio` / `bedroom` / `parent_s_bedroom`) | `Liv togL` / `Bio togL` / `BedrtogL` / `Par togL` shown immediately as press feedback; once HA reports the new state back (~0.5-1 s later) the overlay **automatically refreshes** to the actual `Liv  on ` / `Liv  off` etc. for another 4 s. |
| Long press (held >= 0.8 s) | `light.turn_on` with `area_id`, `brightness_pct: 100`, `color_temp_kelvin: 4000` | `Liv FuLL` / `Bio FuLL` / `BedrFuLL` / `Par FuLL` for ~3 s |

**Toggle-confirmation implementation:** each `*_lights_any_on` binary_sensor has an `on_state` callback that fires whenever Home Assistant publishes a new value for the area. The callback inspects `last_lights_button` and `last_lights_button_press` and only rewrites the feedback overlay when the state change happened within 6 s of one of *our* recent toggles - random background updates (motion sensor, automation, etc.) can't redraw the screen. This is what gives the user the "first I see `togL`, then I see the new state" feel without needing any explicit polling.

**Long-press implementation:** the long press fires from the dedicated scripts `long_press_b1`...`long_press_b4` (each `mode: restart`), which are kicked off by `on_press` and run a `delay: 800ms` followed by a `binary_sensor.is_on` check. If the button is still held when the delay expires, the long-press action runs and resets `press_start_bX = 0` ("long-press handled" sentinel). `on_release` then sees the sentinel and skips the short-press path, so a long press never doubles as a short press. This avoids the previous problem where the TM1638's polling rate could land the release event in a way that made `on_release` measure too short a hold.

The "current state" lookup uses four Home Assistant binary_sensor helpers - see *Required HA helpers* below.

### Button 5 (Calendar Cycle / Snake Timer)

#### Short press (held < 0.8 s)
- Jumps the display to screen 8 (calendar) on every press, even when there are zero active events.
- Advances `cal_event_index` to the next active event when there are events.
- Sets `force_calendar_until = millis() + 5000` so the screen-skip rule and the auto-cycle leave the calendar screen visible for 5 s. With no events the user sees `noEvent` instead of the press feeling like a no-op.
- The auto-cycle still progresses through events on its own (one event per 3.5 s) once the override expires.
- A short press while the snake timer is active **dismisses the on-device animation** (the cooking notification is just visual, so this only stops the digits / LEDs - it doesn't actually un-cook anything).

#### Long press (held >= 0.8 s) - snake-egg cooking timer (1..8 minutes)
The snake timer is now a two-step interaction: hold to open the menu, then tap a number to commit a duration.

1. **Long press B5** opens a **5 s "select duration" window**. While it's open the display shows `btn 1-8N` (N = seconds remaining) and all 8 top LEDs come on as a "menu open" indicator. **Every other button on the panel is repurposed** to mean a minute count:

   | Button pressed inside the window | Snake duration |
   |----------------------------------|----------------|
   | 1 (Living) | 1 minute |
   | 2 (Bio) | 2 minutes |
   | 3 (Bedroom) | 3 minutes |
   | 4 (Parents) | 4 minutes |
   | 5 (Cal, short) | 5 minutes |
   | 6 (Set Tmp) | 6 minutes |
   | 7 (Lily) | 7 minutes |
   | 8 (Notify) | 8 minutes |

   None of the buttons run their normal action while the window is open (no lights, no temperature change, no calendar jump, no notification cycling). The window closes the moment a number is picked or after 5 s, whichever comes first.

2. **Snake animation** - the snake walks back and forth on the bottom two rows (middle row `-` + bottom row `_`), going round and round. Each minute, **once a minute has passed**, it climbs **up** at the egg's column to grab the LED above. Each grab makes the snake **one segment longer** (length 2 in minute 0 for visibility, then +1 per egg eaten - so a `total_minutes`-minute timer ends at length `total_minutes + 2`). The body trail is implemented as an N-deep history of the last cells the head occupied - the body follows whichever path the head took, including the climb.

   The animation is driven by an explicit **state machine** (LOOP <-> GRAB) rather than a per-minute time formula. The formula version teleported the head from "wherever the loop happened to be at 56 s" to the egg's column, which the user described as "jumps from where it is rather than travelling to it naturally". The state machine never resets the loop position at minute boundaries; instead the head walks the loop continuously and the GRAB phase only kicks in when the head naturally arrives at the next egg's column AND that egg has become "ready" (snake elapsed >= `(N+1)*60 s`). This means each grab is preceded by up to 2.7 s of natural travel along the loop until the head reaches the egg's digit - exactly what the user asked for. After the climb the loop resumes from the same `(digit egg, '-')` cell, so the snake "carries on going round" with no teleport.

   - **Bottom-and-middle loop (continuous, ~17 laps before first egg)** - 18 cells:
     - Cells 0..7  - bottom edge L->R: segment d of digits 0..7 (`_` = 0x08), **200 ms per cell**.
     - Cell 8      - **right corner pivot**: `j` of digit 7 (c+d = 0x0C, lower-right vertical + bottom), **500 ms**. This is the user's "mirror of i" - the lower-right vertical visibly sticks up as the snake rounds the bottom-right corner.
     - Cells 9..16 - middle edge R->L: segment g of digits 7..0 (`-` = 0x40), **200 ms per cell**.
     - Cell 17     - **left corner pivot**: `i` of digit 0 (e = 0x10, lower-left vertical), **500 ms**. As the head arrives the body still has `-` on digit 0, so the rendered OR is `i | -` = 0x50 = `r` - the lower-left vertical *grows out of* the middle bar instead of jumping to a standalone segment.
   - **Egg grab (5 cells, 800 ms per cell, all on the egg's digit)**. LED N (above digit N) is grabbed in minute N. The grab starts the moment the head naturally arrives at `(digit N, '-')` AND the minute boundary has rolled over (`snake_elapsed >= (N+1) * 60 s`). Every adjacent pair shares at least one segment, so the head visibly *travels* from the middle row up to the top row and back rather than teleporting:
     - Cell 0  - middle row of digit N (`-` = g = 0x40). Loop's last step before the climb.
     - Cell 1  - `>` of digit N (a+b+g = 0x43). g stays lit while a + b come on -> head moving up the right side.
     - Cell 2  - `~` of digit N (a = 0x01). **LED N goes out here** - the egg is eaten and the snake gains a body segment on the next push.
     - Cell 3  - `>` of digit N (a+b+g = 0x43). a stays lit while b + g come back on -> head moving back down.
     - Cell 4  - middle row of digit N (`-` = g = 0x40). g stays lit while a + b go off -> back to loop. Loop resumes from this cell for the next minute.
   - **Top LEDs are eggs**: at start, the N positions matching the chosen duration are lit (LED 0..total_minutes-1). The egg above digit N goes out at the moment the snake reaches the top of its climb in minute N - so a 5-minute timer eats LEDs 0..4 in order, and LEDs 5..7 stay off the entire time. With "climb when the head arrives" the user gets a full minute of round-and-round loop motion *first*, matching the spec "until a minute has passed and then it will go up", AND the climb starts from wherever the head actually is.

   *Body rendering note*: the TM1638 component lets us set one ASCII char per digit, not arbitrary segment bytes (the `set_7seg_` method is protected and there's no raw-byte API in the public component). When several body cells share a digit (e.g. at a corner the head is on `j`/`i` while the body cell is still on the previous straight-run char, or during the grab climb where the head visits middle/up/top all on the same digit) the renderer ORs the segments and looks the result up in the font. Known mappings:

   - **Head digit is never OR'd with the body** — the renderer always paints `history[0]` (the head) as `head_char` on its digit; only `history[1..]` contribute to body OR on other digits. This stops corner transitions from collapsing into wrong glyphs (the earlier `c+d+g` OR was mapping to `3`, which looked nothing like a corner).
   - Corner pivots are **`j`** (right, c+d) and **`i`** (left, e). When the body trail on the digit before the left corner still has `-`, the body-only OR on that *other* digit can show **`r`** (e+g) as a soft bridge.

3. **Ending animation** (single pattern, 15 s long):
   - **Fireworks** - alternating `88888888` / `. . . . ` strobe with all LEDs flashing in unison. Same pattern is used for any duration (it was previously chosen by `total_minutes % 3`; the user picked fireworks as the only one worth keeping).
   - At the START of the ending the device **also fires `script.trigger_airfryer_beep_action`** - so finishing a snake timer feels exactly like a real airfryer beep: the floodlight flashes green for 5 s, a mobile-app notification fires, and the on-display `AFry tSt` overlay briefly covers the first ~2.5 s of fireworks before clearing. This is what makes the snake timer a useful "your bake is done" cue: the floodlight is visible from the lounge, the notification reaches you upstairs, and the fireworks confirm on-device.

4. **Cancel**: a second long press of B5 while the timer is running clears it immediately (overlay reads `snakeoff` for 2 s). A short tap of B5 also dismisses the animation (without an explicit confirmation message). Dismissing during the ending animation does NOT cancel the floodlight/notify action that's already been fired.

5. **Implementation notes**:
   - Per-segment access uses ESPHome's TM1638 ASCII map directly via `it.print(pos, "X")`, where the single chosen char's seven-seg byte has only the desired segments set. The snake's vocabulary uses `_` (d), `-` (g), `=` (d+g), `j` (c+d, right corner), `i` (e, left corner), `r` (e+g, left-corner OR result), `` ` `` (b), `~` (a), `>` (a+b+g, climb in/out cells).
   - The state machine (`snake_loop_idx`, `snake_in_grab`, `snake_grab_idx`, `snake_loop_last_step_ms`, `snake_grab_last_step_ms`, `snake_next_egg`, `snake_done_at_ms`) is the SOLE source of truth for where the head is at any moment - there is no time-based "what should the head be at t=now" formula left. The render lambda only advances the relevant cursor when its respective step time has elapsed since the last step (`SNAKE_LOOP_STEP_MS` for straight-run cells, `SNAKE_LOOP_PIVOT_MS` for the two corner cells, `SNAKE_GRAB_STEP_MS` for the climb), pushes the new cell to history, and re-renders.
   - The body is a `std::vector<uint16_t>` history of `(digit << 8) | char` packed cells with the head at `[0]` and the tail at `[N-1]`. After every state-machine advance the history is trimmed to `snake_next_egg + 2` (capped at `total_minutes + 2`) so older cells drop off the tail.
   - Each of buttons 1..8 has a top-level `if (millis() < snake_select_until_ms)` wrapper in its `on_press` chain. The `then:` branch calls a shared `arm_snake_timer` script with the per-button minute count; the `else:` branch runs the original action. `arm_snake_timer` clears `snake_history`, sets `snake_last_head_packed` to `0xFFFF`, and resets the state-machine cursors (`snake_loop_idx = -1`, `snake_in_grab = false`, `snake_grab_idx = 0`, `snake_next_egg = 0`, `snake_done_at_ms = 0`) so the new snake starts fresh.
   - The "fire airfryer action at ending" hook is a single `id(trigger_airfryer_beep_action).execute()` call placed inside the `if (snake_done_at_ms == 0)` guard - so it fires exactly once at the moment the ending begins, not every render frame.

### Button 6 (Set Temp + hot water long-press)

Short press: 4-step temp cycle (idle >8 s resets to step 0). Long press: hot-water boost.

| Situation | Action | Display / feedback |
|-----------|--------|---------------------|
| Short step 0 | Show inside temp | `in  XX.XC` |
| Short step 1 | Set desired to **23** °C | `Set  23C` |
| Short step 2 | Set desired to **20** °C | `Set  20C` |
| Short step 3 | Set desired to **17** °C | `Set  17C` |
| Long press (>= 0.8 s) | `input_button.hot_water_boost_2h` | `hot ON ` for 3 s; hot-water screen |

LED5 still mirrors `switch.smart_plug_2_socket_1` on all screens.

### Button 7 (Lily feed counter)

| Situation | Action | On-display feedback |
|-----------|--------|---------------------|
| First short press | Show count and time since last feed only | Left: `hh:mm` since feed (`02:15`). Right: pouches (`2.5`). **4 s**. |
| Second short press within **5 s** | Add **0.5** pouch, update feed time, sync HA | Same layout |
| Long press (held >= 0.8 s) | Subtract **1** (floor **0**), sync HA | Same layout for 4 s |

Counter **resets at midnight**. HA helpers in `ElectricAutomations/helpers.yaml`: `input_number.lily_pouch_count`, `input_datetime.lily_last_feed`, template `sensor.lily_time_since_feed`.

### Button 8 (Notifications)

| Situation | Action | Effect |
|-----------|--------|--------|
| Short press (held < 0.8 s) | Cycle notifications on screen 12 | Extended hold so long titles scroll fully |
| Long press (held >= 0.8 s) | `persistent_notification.dismiss` | `noteDIS ` / `noteNONE` overlay |

## Home Assistant Buttons

The firmware exposes the following ESPHome `button:` entities. They show up as buttons in Home Assistant and don't take any TM1638 button slots. The previous bean-calibration trio is gone now that the bean-warning logic uses fixed cm thresholds.

| HA entity (button.) | Action | On-display feedback |
|---------------------|--------|---------------------|
| `test_airfryer_beep`| Run the same script as a real beep detection (snapshot flood light, flash green for **5 s**, restore to previous state, send mobile-app notify). Also fired by the snake timer's ending animation so the "your bake is done" cue is identical to a real beep. | `AFry tSt` overlay shown for ~2.5 s while the floodlight is green - so you can see the device acknowledged your press even from across the kitchen. |
| `sample_airfryer_beep` | Run a 10 s **microphone listen session**. Counts beep edges (peak >50) in real time and logs the peak each second. | Live overlay `LISt8 2` (8 s left, 2 beeps so far). After 10 s shows `AF<n>b<peak>` for 10 s - e.g. `AF3b  77` = "3 beeps, peak amplitude 77". `AF NONE ` if no samples were received (mic wiring/power problem). |
| `mic_self_test_button` | Same as `sample_airfryer_beep` (just a different name for the panel). Use it to verify the microphone hears anything at all - clap or whistle during the countdown. | Same as above. |

Reading the `AF<n>b<peak>` result (also check the `Sample finished:` log line which adds `zc_max` and the current threshold values):

| Result example | Meaning | What to do |
|----------------|---------|------------|
| `AF0b  12` | Heard nothing distinct, peak was just ambient (12). | Mic is alive but no sound made it through. Move the device closer or play the beep louder. |
| `AF3b  77` | Heard 3 beeps in 10 s, but each only peaked at 77. | The rhythm was detected but `airfryer_beep_threshold` is too high. Lower `input_number.airfryer_beep_threshold` to ~`peak * 0.7` (e.g. ~50). |
| `AF3b 200` | Heard 3 beeps, peak 200. | Already above default threshold (50). Provided the log shows `zc_max` >= `airfryer_zc_threshold` (default 0.30 - real 4 kHz beeps measure ~0.50 in practice), detection will fire if `switch.airfryer_detection` is on. |
| `AF NONE ` | No mic samples received in 10 s. | Mic wiring / power / I2S config problem - check `[I][mic_raw]` log lines on the next reboot. |
| log shows `zc_max=0.04` despite 3 beeps | Mic heard a low-frequency rhythm, not the air fryer | Either the noise was something else (voice, fridge hum), or the air fryer's beep is being attenuated by distance/walls into a duller sound. If you confirm it really is the fryer, lower `input_number.airfryer_zc_threshold` to ~`zc_max * 0.8`. |

Notes:
- The shared `script.trigger_airfryer_beep_action` is invoked both by the auto-detect `binary_sensor.airfryer_beep` and by `button.test_airfryer_beep`, so any improvements to the action (extra notifications, sound, etc.) only need to be made in one place. The test button bypasses the binary sensor entirely - it works regardless of the master `switch.airfryer_detection` state.
- Auto-detection uses **peak + (ZC OR 4 kHz tone metric) + length + 2-beep cadence**. Master switch defaults **ON** (`switch.airfryer_detection`). A candidate must be loud (`peak > 35` default) and pass **either** `zc >= 0.22` **or** `tone4k >= 0.06` (lag-4 correlation tuned for the user's ~4000 Hz measurement). After **2** valid beeps ~1.5–5.5 s apart within 16 s, the alert fires. See *Air Fryer Beep Detection* below.
- The independent **`binary_sensor.mic_low_beep`** uses a fixed lower threshold (50) to count beep edges into `mic_low_thresh_edges`, which is what the sample button reports. This means you can see "mic heard 3 beeps" even when the main airfryer detector is set so high it wouldn't react - useful for tuning.
- Bean detection is now fully automatic: see *Coffee bean detection* below. There is nothing to calibrate.

---

## Home Assistant Integration
The device subscribes to the following Home Assistant entities. Anything missing simply causes its corresponding screen / LED to be skipped or stay dark - the firmware is tolerant of missing helpers.

### Sensors
- `sensor.bioofficec3_room_temperature` - Bio office temperature
- `sensor.sam_outside_temperature` - Outside temperature
- `sensor.t_h_sensor_temperature` - Inside temperature
- `sensor.t_h_sensor_humidity` - Inside humidity
- `sensor.nordpool_kwh_se4_sek_3_10_025` - Electricity price (state and `low_price` attribute)
- `sensor.manifoldtemperature_hot_water_boiler_temp` - Hot-water boiler temperature
- `sensor.manifoldtemperature_lowest_loop_return_temp` - Lowest heating-loop return temperature
- `sensor.manifoldtemperature_air_temp` - Manifold air temperature
- `sensor.forecast_today_max` - today's day-max (`D` value on forecast screen, 03:00-15:00)
- `sensor.forecast_tonight_min` - tonight's min (`N` value, 15:00-03:00)
- `sensor.sam_outside_temperature` - live outside temp shown as `Out XX.X` in forecast scroll
- `input_number.forecast_outside_4h` - 4 h average from HouseThermalModel (subscribed but not shown on forecast screen)

> **Forecast sensors:** include `ElectricAutomations/forecast_sensors.yaml` in HA packages. Do **not** subscribe to `input_number.*` for daily max/min — use the template sensors above.
- `sensor.openweathermap_condition` - text condition (`rainy`, `sunny`, `partlycloudy` ...); mapped to a short word in the forecast scroll string
- `input_number.sam_desired_temperature` - User-facing Sam desired temperature (changed by Button 6)
- `input_number.airfryer_beep_threshold` *(optional helper)* - Peak amplitude above which `binary_sensor.airfryer_beep` will trip on loudness. Default 50 if the helper is absent. Recommended HA helper config: min 1, max 32000, step 10.
- `input_number.airfryer_zc_threshold` *(optional helper)* - Zero-crossing rate (frequency proxy) above which `binary_sensor.airfryer_beep` will trip on pitch. **Default 0.30 if the helper is absent** (was 0.20 - the user's measured-with-an-app beep is 4000 Hz, so ZC at 16 kHz sample rate is ~0.50; 0.30 leaves a comfortable margin above ALL non-tonal household noise (voice/hum/thuds top out at ~0.10) while still passing real beeps). Recommended HA helper config: min 0.05, max 0.50, step 0.01. Lower to 0.20 if the mic is far away from the fryer and reflections are dulling the beep's measured ZC; raise to 0.40 if a particularly tonal noise source (e.g. a kettle) keeps getting through.
- `switch.kitchen_detectorer_airfryer_detection` *(local switch)* - Master enable for the whole detection pipeline. **Defaults OFF.** With this off, the binary sensor is dormant regardless of acoustic conditions - this is the single biggest false-positive killer. Flip ON manually when you start the fryer or wire to an HA automation that follows the fryer's smart-plug power draw. The `Test Airfryer Beep` button bypasses the binary sensor entirely so the test workflow still works regardless of switch state.

#### Suggested daily-forecast helper (HA template, **modern action-based**)

`weather` entities no longer expose a `forecast` attribute as of HA 2024.4.
Use the ready-made package in the repo instead of copying YAML by hand:

```yaml
# configuration.yaml
homeassistant:
  packages:
    minidisplay_forecast: !include MiniDisplay/ElectricAutomations/forecast_sensors.yaml
```

This produces `sensor.forecast_today_max` and `sensor.forecast_tonight_min`.
The 4-hour average forecast is `input_number.forecast_outside_4h` (written by
`HouseThermalModel.yaml`) — KitchenDetectorer no longer displays it on the
forecast screen; both devices now show live outside temp via
`sensor.sam_outside_temperature` instead.

To verify on the HA side: in **Developer Tools → States** you should see
`sensor.forecast_today_max` with a numeric state (e.g. `8.4`) and a fresh
`last_changed` after a HA restart. If the state is `unknown` or `unavailable`
the device will display `D --` / `N --` for the forecast value.

### Sensors published by this device
- `sensor.kitchen_detectorer_espresso_bean_level` - Current ultrasonic distance to the top of the bean pile, **in cm** (the metres->cm conversion happens in a single `lambda` filter on the sensor itself, so everything downstream just reads centimetres).
- The microphone peak/RMS sensors are kept as ESPHome `template` sensors (used by the airfryer self-test scripts) but are `internal: true`, so they no longer create entities or "Changed to" log spam in Home Assistant. To restore them as HA entities, remove `internal: true` from the two `sensor: - platform: template` blocks named `mic_peak_sensor` / `mic_rms_sensor` in `KitchenDetectorer.yaml`.

### Switches & Climate
- `climate.bio_office_heat` - Bio office heating climate control (state + `current_temperature`)
- `switch.smart_plug_2_socket_1` - Hot water switch (state shown by LED5; boost via Button 6 long-press)
- `switch.boilercontrol_boiler_relay_1`, `switch.boilercontrol_boiler_relay_2` - LED6
- `switch.kitchen_detectorer_microphone_capture` *(local)* - Starts/stops the I2S microphone capture loop. The user's last preference is persisted across reboots in the `mic_capture_enabled` global (`restore_value: yes`); the actual `id(mic).start()` is deferred until `on_boot priority -100` so it runs *after* the I2S task has been built. Earlier versions auto-fired the switch's `turn_on_action` from inside the switch's own setup, which crashed in `xQueueSemaphoreTake` because the mic component wasn't ready yet.

### Notifications & Alarms
- `input_select.alarm_level` - Drives the all-LED alarm flash overlay
- `input_text.minidisplay_notification_ids` - Comma-separated active notification IDs (drives LED4 + the Notifications screen + Button 8 dismiss)
- `input_text.minidisplay_notification_titles` - Pipe-separated titles in the same order as the IDs
- `input_text.minidisplay_notification_messages` - Pipe-separated message bodies in the same order. SCREEN_NOTIFY prefers `message` over `title` (most HA `persistent_notification.create` calls leave `title` empty and put the actual content in `message`)

### Required HA helpers (Buttons 1-4 state)
For Buttons 1-4 to show real state in their overlay (`Liv  on` / `Liv  off` etc.) and for the "togL → new state" auto-refresh to work, you need a `binary_sensor` per area that reports whether **any** light in that area is currently on. The toggle and long-press still work without these helpers, but the overlay will read `Liv  -- ` and stay on `togL` until something else changes the screen.

Add the following to a file in the custom/templates directory:

```yaml
template:
  - binary_sensor:
      - name: "Living Room Any Light On"
        unique_id: living_room_any_light_on
        state: >
          {{ expand(area_entities('living_room')) | selectattr('domain','eq','light')
             | selectattr('state','eq','on') | list | count > 0 }}
      - name: "Bio Any Light On"
        unique_id: bio_any_light_on
        state: >
          {{ expand(area_entities('bio')) | selectattr('domain','eq','light')
             | selectattr('state','eq','on') | list | count > 0 }}
      - name: "Bedroom Any Light On"
        unique_id: bedroom_any_light_on
        state: >
          {{ expand(area_entities('bedroom')) | selectattr('domain','eq','light')
             | selectattr('state','eq','on') | list | count > 0 }}
      - name: "Parents Bedroom Any Light On"
        unique_id: parents_bedroom_any_light_on
        state: >
          {{ expand(area_entities('parent_s_bedroom')) | selectattr('domain','eq','light')
             | selectattr('state','eq','on') | list | count > 0 }}
```

Each of these binary_sensors has an `on_state` callback in `KitchenDetectorer.yaml` that overwrites the on-device feedback overlay with the *new* `Liv  on ` / `Liv  off` whenever HA reports a state change within 6 s of one of *our* recent toggles - that's how the user gets a "first I see togL, then I see the new state" experience without the device polling HA.

If you'd rather not add four template helpers, edit the `entity_id:` lines on the `living_lights_any_on` / `bio_lights_any_on` / `bedroom_lights_any_on` / `parents_lights_any_on` subscriptions in `KitchenDetectorer.yaml` to point at a single representative light per area (e.g. the main ceiling fitting).

### Calendars (3 sources, time-windowed, owner-tagged)
- `calendar.webcal_im2_api_infomentor_se_v1_calendarv2_icalsubscription_subscription_f0d28bc2_1243_4b0e_962c_02243eeea583` - kids' school calendar 1 → **Felix**, prefix `F.`
- `calendar.http_im2_api_infomentor_se_v1_calendarv2_icalsubscription_subscription_8cd9caaa_3f4e_4ee4_b8e8_662e4aa39f09` - kids' school calendar 2 → **Isolde**, prefix `I.`
- `calendar.handl_f` - family calendar (no prefix)

For each calendar the device subscribes to the `message`, `start_time` and `end_time` attributes. The active-events list is rebuilt every 30 s by an `interval:` lambda; an event is shown only while:

```
18:00 the day before start_time  <=  now  <  end_time
```

(If `end_time` is unavailable, a default 1 h duration is assumed.)

This implements the user-facing rule: *"after 6 pm, unless there are evening events tonight, start showing the next day"* - tomorrow's events become visible at 18:00 today. If there are still active events tonight (whose `end_time` hasn't passed) they remain in the list alongside tomorrow's, and the cycler walks through both - so the user only sees tomorrow when tonight is empty.

#### Owner prefix and time-slot rules

Each event is classified by its local start time before the renderer decides what goes in the static slot:

| Start time          | Static slot (left, 4 chars) | Scrolling title (right, can scroll over the static slot)        |
|---------------------|------------------------------|------------------------------------------------------------------|
| Anything other than 00:00 / 08:00 | `HHMM` (e.g. `0830`) | `F. <body>` / `I. <body>` / `<body>` (calendar prefix inlined)  |
| 08:00 exactly       | (none - title scrolls across all 8 chars) | `F. <body>` / `I. <body>` / `<body>` |
| 00:00 (all-day events from HA) | `F.  ` / `I.  ` / (none) | `<body>` (no inline prefix - it's already in the static slot) |

Common school-calendar bodies are abbreviated by `shorten_title` so the scroll stays short:

| Original title | Body shown |
|----------------|------------|
| `Felix Idrott` / `Idrott …` | `Gym` |
| `Felix Simning` / `Simning …` / `Felix Swim` / `Swim …` | `Swim` |
| `Ridlekis …` | `Riding` |

A leading `Felix `/`Isolde ` is stripped from the body even when no abbreviation matches, so `"Felix Mathematics"` becomes `Mathematics` (the `F.` prefix keeps the owner clear).

#### Timezone handling

`parse_dt` explicitly inspects the timestamp for `Z` (UTC) or a `+HH:MM` / `-HH:MM` offset and computes a UTC `time_t` directly (using Howard Hinnant's `days_from_civil`). Only `localtime_r` in the rendering path applies the device's local TZ, so events can no longer be off by the local UTC offset.

If the timestamp has no offset at all (HA's calendar entities serialise their times this way: `"2026-05-06 00:00:00"`), the firmware **does not trust `mktime`** because the underlying `TZ` env var doesn't get applied on this platform - the device log proved the bug by showing `parse_dt: raw='2026-05-05 19:30:00' ... -> utc_ts=1778009400` (`mktime` returned a UTC interpretation, then `localtime_r` added Stockholm DST again, so events appeared 2 h late). Instead, the calendar interval lambda probes `id(homeassistant_time).now()` once per refresh, computes the live local UTC offset by comparing its `hour:minute` fields against `gmtime_r()` of the same `timestamp`, and `parse_dt` uses that offset for any naive timestamp. This makes correctness independent of how (or whether) `setenv("TZ", ...)` was applied at boot.

The same `mktime`-avoidance applies to `show_from_ts` (the "show this event from 18:00 the previous local day" point). It used to be computed with `mktime(struct tm{tm_mday-=1; tm_hour=19; ...})`, which silently shifted the show window by the local UTC offset and made early-morning events fail to appear in the auto-cycle. It's now computed as `start_ts - local_secs_into_day - 6*3600` so the window opens at exactly local 18:00 of the day before the event, regardless of TZ env. A `[D][calendar]` log line is emitted on every parse so any future drift can be diagnosed from the raw input.

#### Scrolling layout

There are two scrolling helpers in the display lambda:

1. **`scroll_text`** - the original "left-shift the whole string across N slots over D ms" subtitle scroll. Used by the **Outside Forecast** screen, which builds `"Day max XX.XC RAIN 4hr XX.XC"` (or `"Ngt min ..."` from 14:00 onwards) and scrolls it once per dwell across the full 8 slots. Missing values appear as ` --C` in the matching slot, and the condition word (mapped from `sensor.openweathermap_condition` to one of `CLEAR / CLOUD / FOG / HAIL / STORM / pCLOUd / RAIN / SNOW / SLEEt / SUN / WIND / EXCEPt`) is omitted entirely when the sensor has no state. Also used as the fallback for **Calendar** events whose `cal_event_show_time` is false (8am-exact events without a time prefix).

2. **`scroll_with_static_prefix(prefix, title, elapsed, duration, out)`** - the "static prefix that gets walked over by the scrolling title" helper added for the calendar / notification rework. The prefix is up to 4 chars and is rendered at slots 0..3; the title scrolls leftward starting at slot `prefix_len` and ending with its last 8 chars across the whole display. As the title's start position decreases past 0, **it overwrites the prefix in place** - implemented by computing each output slot from the title's index when valid and only falling back to the prefix where the title isn't currently covering that slot. No string splitting, no manual character juggling, just a single index calculation per slot. Used by:
   - the **Calendar** screen (prefix = `HHMM`, title = event message). 8am-exact events skip the static `HHMM` and use `scroll_text` instead.
   - the **Notifications** screen (prefix = `HHMM` captured the first time the notification ID appears in `notification_ids_csv`, preserved on subsequent refreshes via a parallel `notification_times` vector). Notifications use a per-cell scroll rate (`NOTIFY_SCROLL_MS_PER_CELL = 200 ms`) instead of a fixed total duration so a 30-char title takes ~5 s and a 4-char title takes ~0 s. A manual B8 short press also sets `notify_hold_until_ms = now + scroll_cells * 200 ms + 3000 ms` so the auto-cycle defers advancing until the entire title has scrolled past plus a tail dwell - long messages no longer get cut off mid-scroll.

Short titles that already fit in 8 chars are space-padded and shown stationary in either helper.

### Time
- `homeassistant_time` - Date and time synchronisation. `timezone: Europe/Stockholm` is set so that `localtime_r` produces correct local-time conversions for the calendar event window. The calendar lambda derives the live UTC offset from `id(homeassistant_time).now()` rather than depending on `mktime` to honour `TZ` (see the *Timezone handling* note above).

---

## Coffee bean detection

The HC-SR04 ultrasonic sensor sits directly above the espresso hopper and measures the distance to the top of the bean pile. The raw `ultrasonic` platform reports distance in **metres**; a `lambda: 'return x * 100.0f;'` filter on the sensor converts that to **cm** at the source so every other piece of firmware can just read `id(espresso_bean_level).state` and assume centimetres.

Bean state is then derived directly from that cm value:

| Reading (cm) | State | Meaning |
|--------------|-------|---------|
| < 5          | full / sensor-touched | Beans are full enough that they're physically touching the sensor face. The reading is unreliable, so we treat it as "no warning". |
| 5 .. 8       | low | Pile is dropping but there's still some left. |
| 8 .. 12      | empty / nearly-empty | Real reliable signal that the hopper needs refilling. |
| > 12         | full | The IR cone overshot the bean pile entirely - read as "nothing in the way", which during normal operation only happens when the hopper has just been topped up. |

Rather than reacting instantly the firmware requires the reading to stay in the **5..12 cm "reliable low" band continuously for 10 s** (`BEAN_RELIABLE_MS`) before it raises `bean_warning_active = true`. 10 s is roughly one grind cycle, so a brief bean shift while pouring or while a grind is in progress doesn't trigger a false alarm. The state machine lives in the `on_value` handler of `sensor.espresso_bean_level`:

- `bean_in_range_since_ms` records when the current "in range" run started (0 = not currently in range).
- Once that run is 10 s old, `bean_warning_active` flips to `true` and stays that way until the reading leaves the band.
- Out-of-range readings reset both globals immediately, so a transient false reading can't sustain the warning.

When `bean_warning_active` is true:
- LED8 flashes at 1 Hz.
- The Beans screen left side reads `bnLo` (instead of `bnEm` / `bnFu` / `bn..`).
- The right side keeps showing the live cm value with `%4.1f`.

There are no calibration buttons; the thresholds are baked into the sensor's `on_value` lambda. Adjust them there if your hopper geometry is different.

---

## Air Fryer Beep Detection
When the air fryer's "shake" pattern is detected (or when the snake-egg timer's ending fires this same script):
1. The current state of `light.led_flood_light` is **snapshotted** into a temporary HA scene `scene.airfryer_floodlight_snapshot`, AND `floodlight_was_on` is recorded from the live `light.led_flood_light` text_sensor (HA's scene snapshot is unreliable about restoring an OFF state for some lights).
2. The flood light turns **green** at full brightness for **5 s**, set via `color_name: green` + `brightness_pct: '100'` (the `rgb_color: '[0,255,0]'` format that worked on some lights left this floodlight at full brightness without ever turning green; `color_name: green` is the format the existing `mdold.yaml` colour palette uses on the same hardware family and is known to apply). 5 s (up from 2 s) is long enough that the green is visible whether the user is at the kitchen, the lounge or upstairs, and also long enough to overlap the snake-timer's "fireworks" ending animation.
3. After the flash:
   - If `floodlight_was_on == true` -> `scene.turn_on` to restore the previous brightness / colour.
   - If `floodlight_was_on == false` -> `light.turn_off` is called explicitly so the light goes back off (instead of being left on at the previous-on brightness, which is what `scene.turn_on` does for some HA versions).
4. A notification is sent to the mobile app.

The snake-timer ending also fires this exact same script - the "your bake is done" cue is therefore identical to a real beep (floodlight + notification + on-display overlay), no separate alert path to maintain.

The detection itself is a **four-gate pipeline**: master switch + amplitude + frequency + cadence. The earlier "amplitude + length + cadence" version still tripped a few times per minute on incidental loud noise (drawer slams, voice, fridge compressor), so the rebuilt pipeline adds (a) an explicit master enable that defaults OFF and (b) a frequency proxy via zero-crossing rate. Both are intended to make false positives nearly impossible without reducing real-beep sensitivity.

```
Master gate ------------------------------------------------------
  switch.airfryer_detection (HA-controllable, default OFF)
    -> sets global airfryer_detect_enabled
    -> binary_sensor.airfryer_beep returns false unconditionally when off

Stage 1 - amplitude + frequency gate -----------------------------
  binary_sensor.airfryer_beep =
        mic.is_running()
     && airfryer_detect_enabled                       (master switch)
     && mic_peak_value > airfryer_beep_threshold      (loudness gate, default 50)
     && mic_zc_value   > airfryer_zc_threshold        (frequency gate, default 0.20)
     with delayed_on: 100ms / delayed_off: 50ms

Stage 2 - length filter (on_release) -----------------------------
  duration_ms = millis() - beep_rise_ms
  if duration_ms outside AIRFRYER_MIN_BEEP_MS..AIRFRYER_MAX_BEEP_MS
                             (= 50..450 ms): REJECT (not airfryer-shaped)

Stage 3 - frequency re-check (on_release) ------------------------
  zc_peak = max(mic_zc_value) seen during the beep
  if zc_peak < airfryer_zc_threshold: REJECT (too low-pitched)

Stage 4 - cadence (gap) matcher ----------------------------------
  gap_ms = beep_rise_ms - last_valid_beep_ms
  if gap_ms inside AIRFRYER_MIN_GAP_MS..AIRFRYER_MAX_GAP_MS
                             (= 2.0..4.0 s): bump beep_pattern_count
  else                                       : reset to 1

  trigger fires when beep_pattern_count >= AIRFRYER_REQUIRED_BEEPS (= 3)
  inside AIRFRYER_PATTERN_WINDOW_MS (= 14 s).
```

### Why the "big rethink"

The user reported that even with length+cadence filtering the detector still fired several times per minute on its own. There are three independent root causes; the new pipeline addresses each:

1. **Most of the time the air fryer isn't even running**, but the detector was always armed - so any low-probability random match (any 3 loud-enough sounds happening to fall in 2..4 s spacing in a 14 s window) eventually fires. The new `switch.airfryer_detection` defaults OFF and is intended to be flipped ON only when the user actually starts a fryer cycle (manually or via an automation tied to the fryer's smart-plug power draw). With the switch OFF the binary sensor refuses to go true at all - a complete dormant state.
2. **Voice / drawer slams / fridge compressor are LOW-frequency**, all around 100..1000 Hz. The air fryer beep, **measured by the user with a sound-frequency app, is ~4000 Hz** - which at 16 kHz sample rate produces ~0.50 zero-crossings per sample. Voice / hum / thuds all sit at 0..0.10. Adding a per-chunk **zero-crossing rate** to the mic data callback gives us a cheap frequency proxy with huge headroom: the threshold is `airfryer_zc_threshold` (default **0.30**, tunable via `input_number.airfryer_zc_threshold` from HA) which is comfortably below a real beep's 0.50 but well above any non-tonal household noise. The ZC is checked both live (gate the binary_sensor) and as a peak-during-beep re-check on the falling edge.
3. **Length alone wasn't sufficient** - many household sounds happen to sit in the 50..450 ms band (knife clicks, plate clinks, cupboard creaks) and three of them within 14 s isn't actually unusual in a busy kitchen. With the frequency gate AND length AND cadence ALL having to match, a non-fryer source has to (a) be loud, (b) be high-pitched, (c) last 50..450 ms, AND (d) repeat at ~3 s spacing three times in a row - which is essentially the air fryer's signature.

### Tuning workflow

1. **Decide whether to leave detection on**. The default is OFF. Either flip `switch.airfryer_detection` ON in HA when you start cooking and OFF when you finish, or wire it to an HA automation that follows the fryer's smart plug:
   ```yaml
   automation:
     - trigger: { platform: state, entity_id: switch.airfryer_plug, to: 'on' }
       action: { service: switch.turn_on, target: { entity_id: switch.airfryer_detection } }
     - trigger: { platform: state, entity_id: switch.airfryer_plug, to: 'off', for: '00:01:00' }
       action: { service: switch.turn_off, target: { entity_id: switch.airfryer_detection } }
   ```
2. **Use `Sample Airfryer Beep`** to confirm the mic actually hears the beep:
   - Press the button. The display shows a live count `LISt8 2` (8 s left, 2 beeps so far) for ten seconds.
   - While it's counting, make the air fryer actually beep (or play a recording).
   - When the countdown ends the device shows `AF<n>b<peak>` for ~10 s (e.g. `AF3b  77` = 3 beeps, peak amplitude 77). The detailed log line includes `zc_max=0.42` so you can confirm the beep was high-pitched.
3. **Tune thresholds** based on the sample log:
   - If `peak >= airfryer_beep_threshold` AND `zc_max >= airfryer_zc_threshold` AND `n >= 3` -> nothing to do, real beeps will pass all four gates.
   - If `peak < airfryer_beep_threshold` -> lower `input_number.airfryer_beep_threshold` to roughly `peak * 0.7`.
   - If `zc_max < airfryer_zc_threshold` -> lower `input_number.airfryer_zc_threshold` to roughly `zc_max * 0.8`. **But check first that the high-frequency content is genuinely the beep** - if a sustained low-pitched noise was the loudest thing in the window, you don't want to drop the gate.
   - If `n == 0` -> the mic isn't hearing the beep at all. Move the device closer.
   - `AF NONE ` -> no samples received in 10 s. Mic wiring / I2S problem.

### Diagnosing a still-stuck detector

Look in the device log for per-beep detail lines:

```
[airfryer] Beep rejected: length 12 ms outside [50..450] band (zc_peak=0.36) - not airfryer-shaped
[airfryer] Beep rejected: zc_peak 0.04 below threshold 0.30 - too low-pitched (length=210 ms)
[airfryer] Beep candidate: len=210 ms, zc_peak=0.43, count=1/3 (gap=120 ms, gap too short - probably echo or rapid noise)
[airfryer] Beep candidate: len=180 ms, zc_peak=0.41, count=2/3 (gap=2950 ms, valid airfryer cadence)
```

Each candidate's measured length, ZC peak, and gap are logged so you can see which stage rejected what. If the airfryer's own beeps are getting rejected as "length out of range" widen `AIRFRYER_MAX_BEEP_MS`; if they're rejected as "too low-pitched" lower `airfryer_zc_threshold` (or move the mic closer, since ZC drops with distance through reflections); if "gap too long" the cadence is faster than 4 s - widen `AIRFRYER_MAX_GAP_MS`.

The `Test Airfryer Beep` HA button bypasses the binary sensor entirely (calls `script.trigger_airfryer_beep_action` directly), so it works regardless of the master detection switch state - useful for confirming the floodlight + notification action chain still works without having to actually fry.

---

## Notes
- TM1638 display intensity is set to 7 (max).
- Outer screen auto-cycle is 3.5 s; the calendar slot (screen 8) sub-cycles through each active event for the same 3.5 s before letting the outer loop move on.
- TM1638 `update_interval` is **100 ms** (10 Hz). This rate also dictates how often the chip's keys are polled, so a normal ~200 ms tap is reliably detected. The previous 500 ms setting routinely missed quick presses, especially on the lights buttons - hence the move from `on_multi_click` (which depends on seeing both ON and OFF transitions) to dedicated long-press scripts.
- Buttons 1-3 + Button 8 record the press start in `press_start_b1`...`press_start_b8` on `on_press` and immediately kick a `long_press_bX` script (`mode: restart`). The script waits 800 ms and then re-checks the binary sensor with `binary_sensor.is_on`; if the button is still down, the long-press action runs and `press_start_bX` is reset to `0` as a "long-press handled" sentinel. `on_release` only runs the short-press path when the sentinel is non-zero. This removes the polling-rate sensitivity of measuring the held duration after the fact and means a long press fires *while* the button is still held, which is also better UX.
- Buttons 1-4 (lights) show their state / `togL` overlay for ~8 s, but the overlay is **automatically refreshed** when HA reports the new area state (within ~1 s) so the user effectively sees `togL` for half a second and then the actual `on`/`off` for ~4 s. Button 6 shows its action for 3 s.
- All sensors have fallback displays (`--`, `--C`, `---`) when data is unavailable.
- The firmware uses `wifi.reboot_timeout: 10min` and `api.reboot_timeout: 15min` so a prolonged WiFi or HA-API outage triggers a self-recovery reboot rather than leaving the display stuck on stale data. A 60 s `interval:` heartbeat (`ESP_LOGI("hb", ...)`) is also emitted to confirm the main loop is alive.
- Coffee-bean detection is **fixed-threshold and fully automatic** (5..12 cm reliable-low band, 10 s sustain to trigger). No calibration knobs, no HA buttons. See *Coffee bean detection* below.
- The mic peak/RMS sensors are still computed on the device (the airfryer detector reads them) but they're now `internal: true` so they no longer publish 1 Hz "Changed to" updates to Home Assistant. The mic globals (`mic_peak_value`, `mic_peak_session`, `mic_samples_total`) are still readable on-device and via the airfryer self-test scripts.
- The previously-required HA template binary sensors `binary_sensor.felix_morning_alert` / `binary_sensor.isolde_morning_alert` are no longer used: the time-window logic is now done in the on-device lambda directly from the calendars' `message` / `start_time` / `end_time` attributes.
