# Weather icons for the small house displays

1-bit animated weather icons for three kinds of display, made on the PC and
embedded by ESPHome at compile time (no image decoding on the ESP32):

| Folder | For | Size | Frames |
|---|---|---|---|
| `oled32/` | 128x64 OLED (MiniDisplay) | 32x32 GIF | 4-8 |
| `lcd20/` | 128x64 STN LCD, 42x20 cell (FrontPath) | 24x20 GIF | 2 |
| `hd44780/` | 16x2 character LCD (CGRAM) | 2x2 characters | 2-4 |

On Home Assistant this folder lives at `/config/esphome/weather_icons/`,
next to the flat device YAMLs, so YAMLs refer to it as `weather_icons/...`
(for example `file: weather_icons/oled32/rainy.gif`).

## What is here

```
weather_icons/
  oled32/<icon>.gif          32x32, white = lit pixel
  oled32/images.yaml         ESPHome package: one image (platform: animation) per icon, ids wx32_<icon>
  lcd20/<icon>.gif           24x20, white = dark pixel on the STN glass
  lcd20/images.yaml          the same, ids wx20_<icon>
  hd44780/glyphs.json        5x8 CGRAM frames, rows as 5-bit ints
  hd44780/weather_glyphs.h   the same as a C++ header with a loader and the HA mapping
  hd44780/user_characters.yaml  first frame of each icon as static user_characters
  manifest.json              icons, frame counts, suggested step intervals, file sizes, HA mapping
  tools/                     generator (see "Regenerating")
  LICENSE-Meteocons          licence of the icon set these are drawn from
```

In every GIF a white pixel is "ink": with `type: BINARY` ESPHome turns it
into a set bit, drawn in `COLOR_ON`. That is a lit pixel on the OLED and a
dark pixel on the STN LCD, so the same files suit both kinds of panel.

Sizes as stored on disk (GIF) and as embedded in flash (ESPHome keeps the raw
bits: 4 bytes x 32 rows per 32 px frame, 3 bytes x 20 rows per 24x20 frame):

| Icon | oled32 frames | oled32 GIF bytes | lcd20 frames | lcd20 GIF bytes | hd44780 frames |
|---|---|---|---|---|---|
| sunny | 4 | 427 | 2 | 178 | 2 |
| clear-night | 6 | 309 | 2 | 147 | 2 |
| partlycloudy | 4 | 352 | 2 | 169 | 2 |
| partlycloudy-night | 6 | 428 | 2 | 140 | 2 |
| cloudy | 8 | 597 | 2 | 179 | 2 |
| fog | 4 | 272 | 2 | 144 | 2 |
| rainy | 6 | 368 | 2 | 146 | 3 |
| pouring | 6 | 414 | 2 | 160 | 2 |
| snowy | 6 | 443 | 2 | 152 | 4 |
| snowy-rainy | 6 | 414 | 2 | 151 | 4 |
| hail | 6 | 415 | 2 | 146 | 3 |
| lightning | 4 | 279 | 2 | 135 | 3 |
| lightning-rainy | 6 | 461 | 2 | 158 | 3 |
| windy | 4 | 264 | 2 | 139 | 2 |
| exceptional | 4 | 382 | 2 | 177 | 2 |

All 15 in flash: about 10.2 kB for oled32 and 1.8 kB for lcd20. A device
only pays for the ids it declares, so a YAML can copy just the entries it
needs out of `images.yaml` instead of including the whole package.

## Home Assistant condition to icon

`sun.sun` decides day or night: use the night icon when it is
`below_horizon`.

| HA condition | Day icon | Night icon |
|---|---|---|
| clear-night | clear-night | clear-night |
| sunny | sunny | clear-night |
| partlycloudy | partlycloudy | partlycloudy-night |
| cloudy | cloudy | cloudy |
| fog | fog | fog |
| rainy | rainy | rainy |
| pouring | pouring | pouring |
| snowy | snowy | snowy |
| snowy-rainy | snowy-rainy | snowy-rainy |
| hail | hail | hail |
| lightning | lightning | lightning |
| lightning-rainy | lightning-rainy | lightning-rainy |
| windy | windy | windy |
| windy-variant | windy | windy |
| exceptional | exceptional | exceptional |

`windy-variant` (wind with cloud) shares the wind icon: a cloud squeezed in
beside the wind lines did not read at these sizes. `sunny` at night maps to
the moon because some integrations keep reporting `sunny` after dark.
Anything unknown (or `unavailable`) is best shown as `cloudy`; that is what
`weather_glyphs::from_condition()` returns.

## Using them in ESPHome

The `image:` component with `platform: animation` is the current form
(ESPHome 2026.x). The older top-level `animation:` block takes the same
keys and still works until ESPHome 2027.1.0, but prints a deprecation
warning.

### OLED or STN LCD (GIFs)

```yaml
packages:
  wx32: !include weather_icons/oled32/images.yaml   # or lcd20 / wx20

text_sensor:
  - platform: homeassistant
    id: wx_condition
    entity_id: weather.forecast_home
  - platform: homeassistant
    id: sun_state
    entity_id: sun.sun

globals:
  - id: wx_tick
    type: uint32_t
    initial_value: '0'

interval:
  - interval: 150ms          # oled32; about 450 ms suits lcd20 (STN pixels are slow)
    then:
      - lambda: 'id(wx_tick)++;'

display:
  - platform: ssd1306_i2c
    # ...
    lambda: |-
      const std::string &c = id(wx_condition).state;
      bool night = id(sun_state).state == "below_horizon";
      animation::Animation *a = id(wx32_cloudy);
      if (c == "sunny") a = night ? id(wx32_clear_night) : id(wx32_sunny);
      else if (c == "clear-night") a = id(wx32_clear_night);
      else if (c == "partlycloudy") a = night ? id(wx32_partlycloudy_night) : id(wx32_partlycloudy);
      else if (c == "fog") a = id(wx32_fog);
      else if (c == "rainy") a = id(wx32_rainy);
      else if (c == "pouring") a = id(wx32_pouring);
      else if (c == "snowy") a = id(wx32_snowy);
      else if (c == "snowy-rainy") a = id(wx32_snowy_rainy);
      else if (c == "hail") a = id(wx32_hail);
      else if (c == "lightning") a = id(wx32_lightning);
      else if (c == "lightning-rainy") a = id(wx32_lightning_rainy);
      else if (c == "windy" || c == "windy-variant") a = id(wx32_windy);
      else if (c == "exceptional") a = id(wx32_exceptional);
      a->set_frame(id(wx_tick) % a->get_animation_frame_count());
      it.image(0, 16, a, COLOR_ON, COLOR_OFF);
```

Driving every icon from one shared tick keeps the code short; the per-icon
intervals in `manifest.json` (and in the GIF frame delays) are what the art
was tuned for, if a display wants to match them exactly. Pass only
`COLOR_ON` to `it.image()` to draw the icon over something else without
clearing behind it.

This exact package and lambda pass `esphome config` and code generation
(`esphome compile --only-generate`) with ESPHome 2026.9.1.

### 16x2 character LCD (HD44780)

Each icon is 2 characters wide and 2 rows tall, using CGRAM slots 4-7 so
that slot 0 (which cannot appear in a C string) and slots 1-3 stay free for
other symbols. Animation means rewriting those four slots each step; the
header does that through the `lcd_base` `loadchar()` call.

```yaml
esphome:
  includes:
    - weather_icons/hd44780/weather_glyphs.h

display:
  - platform: lcd_pcf8574
    dimensions: 16x2
    update_interval: 500ms
    lambda: |-
      auto icon = weather_glyphs::from_condition(id(wx_condition).state,
                                                 id(sun_state).state == "below_horizon");
      weather_glyphs::load(&it, icon, id(wx_tick));
      it.print(0, 0, "\x04" "\x05");
      it.print(0, 1, "\x06" "\x07");
      it.printf(3, 0, "%.1f C", id(outdoor_temp).state);
```

Keep the escapes in separate string literals (`"\x04" "\x05"`), otherwise
C reads `"\x05A"` as one character. `user_characters.yaml` has each icon's
first frame as `user_characters:` entries, to test the look without the
header.

`glyphs.json` holds the same data for other uses: each frame is four
characters in the order top-left, top-right, bottom-left, bottom-right,
each character eight rows from the top, bit 4 being the leftmost dot.

## How good are they?

Checked frame by frame on the contact sheets (8x, every frame, with the
Meteocons original alongside). Honest notes:

- oled32: all read at a glance. Sun, moon, rain, pouring (solid cloud,
  dense rain), snow, hail, fog, wind and the warning triangle are strong.
  The weaker ones: `cloudy` (two outlined clouds overlapping is a little
  busy at 32 px) and the rotating sun rays, which look slightly jagged in
  the in-between frames, as straight lines do at shallow angles.
- lcd20: sun, moon, rain, pouring, snow, hail, fog, wind and the triangle
  read well. The lightning bolt is only 5 px wide and reads as a bolt rather
  than crisply. `snowy-rainy` versus `snowy` relies on spotting the drops.
- hd44780: the weakest set, as expected with 10x16 dots split by the gaps
  between characters. The art is drawn with the gaps included (an 11x17
  grid) so nothing looks stretched. Clouds with rain, snow or hail, the
  sun, the moon and the wind are recognisable; `exceptional` is the
  weakest, because the "!" has to sit either side of the centre gap.
  `partlycloudy` and `cloudy` are recognisable but small.

## Regenerating

The icons are pixel art drawn by `tools/generate.py`, guided by the
Meteocons shapes (cloud proportions, the crescent, the wind hooks, the
bolt, the triangle). Downscaling the vectors to 32 or 20 px and
thresholding gave mush, so shapes are placed on the pixel grid directly.
The HD44780 glyphs are hand-drawn in `tools/hd44780.py`.

```sh
cd esphome/weather_icons/tools
python generate.py                         # rewrites everything in weather_icons/
python generate.py --sheets /tmp/wx-sheets \
    --meteocons /path/to/meteocons/production/fill/png/128   # plus contact sheets
```

It needs Python 3 with Pillow. Every GIF is decoded again the way ESPHome's
image component does it and compared with what was drawn, and two identical
frames in a row stop the run.

## Licence

The icons are derived from **Meteocons** by Bas Milius,
<https://github.com/basmilius/weather-icons>, MIT licence, Copyright (c)
2020-2024 Bas Milius. The full licence text is in `LICENSE-Meteocons`.
