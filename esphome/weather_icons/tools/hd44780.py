"""Hand-drawn HD44780 (5x8 CGRAM) weather glyphs.

Every icon is 2 characters wide and 2 rows tall, sent as four 5x8 glyphs
(top-left, top-right, bottom-left, bottom-right).

On the glass there is a gap of roughly one dot between characters (a little
less between rows). The art is therefore drawn on an 11x17 "physical" grid
in which column 5 ('|') and row 8 ('-') are that gap: they are never lit and
are dropped when the glyphs are cut out. Drawing it this way keeps the
proportions right, instead of a shape that looks stretched by a dot where
it crosses from one character into the next.

'#' is a lit dot. Precipitation is a hand-drawn tile that scrolls down a
step per frame under a cloud that stays put, so only the bottom two glyphs
change from frame to frame.
"""

import json
import os

PW, PH = 11, 17     # physical grid including the gaps
GAP_X, GAP_Y = 5, 8


def parse(s):
    """Rows of a physical-grid drawing (any width up to 11) as lists of 0/1."""
    rows = []
    for r in s.strip("\n").split("\n"):
        r = r.strip()
        if " " in r:
            r = r.split(" ", 1)[1].strip()
        rows.append([1 if c == "#" else 0 for c in r])
    return rows


def blank():
    return [[0] * PW for _ in range(PH)]


def put(g, rows, x0=0, y0=0):
    """OR a drawing onto the physical grid g at (x0, y0)."""
    out = [r[:] for r in g]
    for j, r in enumerate(rows):
        for i, v in enumerate(r):
            if v and 0 <= x0 + i < PW and 0 <= y0 + j < PH:
                out[y0 + j][x0 + i] = 1
    return out


def full(s):
    rows = parse(s)
    assert len(rows) == PH, (len(rows), s)
    for r in rows:
        assert len(r) == PW, r
    return put(blank(), rows)


def strip(g):
    """Physical 11x17 -> logical 10x16 (drop the gap column and row)."""
    return [[g[y][x] for x in range(PW) if x != GAP_X] for y in range(PH) if y != GAP_Y]


def scroll(tile, step, f, y0=9, h=8):
    """A vertically repeating tile in rows y0..y0+h-1, moved down f*step."""
    g = blank()
    n = len(tile)
    for j in range(h):
        g[y0 + j] = (tile[(j - f * step) % n] + [0] * PW)[:PW]
    return g


def shift(g, dx):
    out = blank()
    for y in range(PH):
        for x in range(PW):
            if g[y][x] and 0 <= x + dx < PW:
                out[y][x + dx] = 1
    return out


# ---- parts -----------------------------------------------------------------

# Cloud filling the top two characters, sitting on the row gap so whatever
# falls from it appears straight underneath.
CLOUD_TOP = parse("""
.....|.....
....#|##...
.##.#|###..
.####|####.
#####|#####
#####|#####
.####|####.
""")   # rows 1-7

# Cloud for the bottom half of the partly cloudy icons (rows 6-13).
CLOUD_LOW = parse("""
.....|.##..
...##|####.
-----------
.####|#####
#####|#####
#####|#####
.####|####.
""")   # rows 6-12 (third row is the gap)


SUNNY = [full("""
00 ....#|#....
01 ....#|#....
02 ....#|#....
03 .....|.....
04 .....|.....
05 ...##|##...
06 ..###|###..
07 #.###|###.#
08 -----------
09 #.###|###.#
10 ..###|###..
11 ...##|##...
12 .....|.....
13 .....|.....
14 ....#|#....
15 ....#|#....
16 ....#|#....
"""), full("""
00 .....|.....
01 .....|.....
02 #....|....#
03 .#...|...#.
04 .....|.....
05 ...##|##...
06 ..###|###..
07 ..###|###..
08 -----------
09 ..###|###..
10 ..###|###..
11 ...##|##...
12 .....|.....
13 .#...|...#.
14 #....|....#
15 .....|.....
16 .....|.....
""")]

MOON = parse("""
..###|#....
.###.|.....
###..|.....
###..|.....
###..|.....
###..|.....
-----------
###..|.....
###..|.....
###..|.....
###..|.....
.###.|.....
..###|#....
""")   # rows 2-14

PLUS = parse("""
.#.
###
.#.
""")


def clear_night():
    f0 = put(put(put(blank(), MOON, 0, 2), PLUS, 7, 2), [[1]], 8, 12)
    f1 = put(put(put(blank(), MOON, 0, 2), [[1]], 8, 3), PLUS, 7, 11)
    return [f0, f1]


def partly():
    sun = parse("""
.###
.###
.###
""")
    frames = []
    for rays in ([(2, 1), (0, 3), (6, 3)], [(0, 0), (6, 0), (0, 6)]):
        g = put(blank(), sun, 1, 2)
        for x, y in rays:
            g[y][x] = 1
        g = put(g, CLOUD_LOW, 0, 6)
        frames.append(g)
    return frames


def partly_night():
    moon = parse("""
.##..
##...
##...
##...
.##..
""")
    frames = []
    for f in range(2):
        g = put(blank(), moon, 0, 0)
        g = put(g, PLUS, 7, 0) if f == 0 else put(g, [[1]], 8, 1)
        g = put(g, CLOUD_LOW, 0, 6)
        frames.append(g)
    return frames


def cloudy():
    back = parse("""
.....|.##..
....#|####.
...##|#####
....#|####.
""")
    front = parse("""
.##..|.....
####.|#....
####.|##...
-----------
#####|###..
#####|####.
#####|####.
.####|###..
""")
    frames = []
    for f in range(2):
        b = shift(put(blank(), back, 0, 1), -f)
        fr = shift(put(blank(), front, 0, 5), f)
        g = blank()
        for y in range(PH):
            for x in range(PW):
                near = any(fr[yy][xx] for yy in range(max(0, y - 1), min(PH, y + 2))
                           for xx in range(max(0, x - 1), min(PW, x + 2)))
                if fr[y][x] or (b[y][x] and not near):
                    g[y][x] = 1
        frames.append(g)
    return frames


def fog():
    lines = (("####.|####.", "####.|.####"), (".####|.####", "####.|####."), ("..###|###..", "###..|..###"))
    frames = []
    for f in range(2):
        g = put(blank(), CLOUD_TOP, 0, 1)
        for y, pair in zip((10, 13, 16), lines):
            g = put(g, parse(pair[f]), 0, y)
        frames.append(g)
    return frames


RAIN_TILE = parse("""
.#...|.....
.#...|...#.
.....|...#.
...#.|.....
...#.|.#...
.....|.#...
""")
POUR_TILE = parse("""
#.#..|#.#.#
#.#..|#.#.#
#.#.#|..#..
..#.#|..#..
""")
SNOW_TILE = parse("""
.#...|.....
###..|..#..
.#...|.###.
.....|..#..
...#.|.....
..###|...#.
...#.|..###
.....|...#.
""")
SLEET_TILE = parse("""
.#...|..#..
###..|..#..
.#...|.....
.....|.....
...#.|..#..
...#.|.###.
.....|..#..
.....|.....
""")
HAIL_TILE = parse("""
.##..|.....
.##..|.##..
.....|.##..
...##|.....
...##|...##
.....|...##
""")


def precip(tile, step, n):
    return [put(scroll(tile, step, f), CLOUD_TOP, 0, 1) for f in range(n)]


BOLT = parse("""
.....|..##.
.....|.##..
.....|##...
...##|###..
.....|##...
....#|#....
...#.|.....
..#..|.....
""")   # rows 9-16


def lightning(rainy):
    side = parse("""
#....|....#
#....|....#
.#...|...#.
.#...|...#.
""")
    frames = []
    for f, bolt in enumerate((True, True, False)):
        g = scroll(side, 2, f) if rainy else blank()
        g = put(g, CLOUD_TOP, 0, 1)
        if bolt:
            g = put(g, BOLT, 0, 9)
        frames.append(g)
    return frames


def windy():
    frames = []
    for f in range(2):
        top = "#####|###.." if f == 0 else "##.##|###.."
        mid = "###.#|####." if f == 0 else "#####|#.##."
        low = "..###|###.." if f == 0 else "..#.#|###.."
        g = full(f"""
00 .....|.##..
01 .....|#..#.
02 .....|...#.
03 {top}
04 .....|.....
05 .....|.....
06 .....|.....
07 {mid}
08 -----------
09 .....|.....
10 .....|.....
11 {low}
12 .....|...#.
13 .....|#..#.
14 .....|.##..
15 .....|.....
16 .....|.....
""")
        frames.append(g)
    return frames


TRI = full("""
00 ....#|#....
01 ....#|#....
02 ....#|#....
03 ...#.|.#...
04 ...#.|.#...
05 ...#.|.#...
06 ..#.#|#.#..
07 ..#.#|#.#..
08 -----------
09 .#..#|#..#.
10 .#..#|#..#.
11 .#..#|#..#.
12 #....|....#
13 #...#|#...#
14 #...#|#...#
15 #####|#####
16 .....|.....
""")
BANG = [(y, x) for y in (6, 7, 9, 10, 11, 13, 14) for x in (4, 6)]


def exceptional():
    inv = blank()
    for y in range(PH):
        xs = [x for x in range(PW) if TRI[y][x]]
        if xs:
            for x in range(min(xs), max(xs) + 1):
                inv[y][x] = 1
    for y, x in BANG:
        inv[y][x] = 0
    return [TRI, inv]


def build():
    """icon -> (frames, interval_ms); each frame is the logical 16x10 grid."""
    phys = {
        "sunny": (SUNNY, 600),
        "clear-night": (clear_night(), 700),
        "partlycloudy": (partly(), 700),
        "partlycloudy-night": (partly_night(), 700),
        "cloudy": (cloudy(), 800),
        "fog": (fog(), 700),
        "rainy": (precip(RAIN_TILE, 2, 3), 350),
        "pouring": (precip(POUR_TILE, 2, 2), 300),
        "snowy": (precip(SNOW_TILE, 2, 4), 500),
        "snowy-rainy": (precip(SLEET_TILE, 2, 4), 450),
        "hail": (precip(HAIL_TILE, 2, 3), 300),
        "lightning": (lightning(False), 350),
        "lightning-rainy": (lightning(True), 350),
        "windy": (windy(), 500),
        "exceptional": (exceptional(), 700),
    }
    return {k: ([strip(g) for g in frames], ms) for k, (frames, ms) in phys.items()}


def cells(g):
    """Split a 16x10 design into four 5x8 cells (TL, TR, BL, BR) as 5-bit rows."""
    out = []
    for cy in (0, 8):
        for cx in (0, 5):
            rows = []
            for y in range(cy, cy + 8):
                v = 0
                for x in range(cx, cx + 5):
                    v = (v << 1) | g[y][x]
                rows.append(v)
            out.append(rows)
    return out


def cname(icon):
    return icon.upper().replace("-", "_")


def write(d, glyphs, ha_map, order):
    os.makedirs(d, exist_ok=True)
    js = {
        "format": "HD44780 5x8 CGRAM. Each icon is 2 cells wide by 2 rows tall. "
                  "Each frame lists four characters in the order top-left, top-right, "
                  "bottom-left, bottom-right; each character is 8 rows, top first, "
                  "as 5-bit integers with bit 4 the leftmost dot.",
        "layout": [["TL", "TR"], ["BL", "BR"]],
        "icons": {},
        "ha_conditions": {k: {"day": v[0], "night": v[1]} for k, v in ha_map.items()},
    }
    for name in order:
        frames, ms = glyphs[name]
        js["icons"][name] = {"interval_ms": ms, "frames": [cells(g) for g in frames]}
    # One icon per line keeps the file readable and the diffs small.
    with open(os.path.join(d, "glyphs.json"), "w") as fh:
        head = {k: v for k, v in js.items() if k != "icons"}
        fh.write("{\n")
        for k, v in head.items():
            fh.write(f" {json.dumps(k)}: {json.dumps(v)},\n")
        fh.write(' "icons": {\n')
        names = list(js["icons"])
        for i, name in enumerate(names):
            sep = "," if i < len(names) - 1 else ""
            fh.write(f"  {json.dumps(name)}: {json.dumps(js['icons'][name], separators=(',', ':'))}{sep}\n")
        fh.write(" }\n}\n")
    json.load(open(os.path.join(d, "glyphs.json")))

    h = []
    h.append("// Generated by weather_icons/tools/generate.py. Do not edit by hand.")
    h.append("// HD44780 5x8 CGRAM weather glyphs, 2 cells wide by 2 rows tall.")
    h.append("// Icon art derived from Meteocons by Bas Milius (MIT licence).")
    h.append("//")
    h.append("// Use from an ESPHome lcd_pcf8574 / lcd_gpio lambda:")
    h.append("//   esphome: includes: [weather_icons/hd44780/weather_glyphs.h]")
    h.append("//   auto icon = weather_glyphs::from_condition(id(wx).state, !id(sun_up).state);")
    h.append("//   weather_glyphs::load(&it, icon, id(wx_frame));   // CGRAM slots 4-7")
    h.append("//   it.print(0, 0, \"\\x04\" \"\\x05\");  it.print(0, 1, \"\\x06\" \"\\x07\");")
    h.append("// Slots 4-7 are used so that slot 0 (which cannot sit in a C string) stays free.")
    h.append("#pragma once")
    h.append("#include <cstdint>")
    h.append("#include <cstring>")
    h.append("#include <string>")
    h.append("")
    h.append("namespace weather_glyphs {")
    h.append("")
    h.append("enum Icon : uint8_t {")
    for name in order:
        h.append(f"  {cname(name)},")
    h.append("  ICON_COUNT")
    h.append("};")
    h.append("")
    for name in order:
        frames, ms = glyphs[name]
        h.append(f"static const uint8_t {cname(name)}_FRAMES[{len(frames)}][4][8] = {{")
        for g in frames:
            cs = cells(g)
            inner = ", ".join("{" + ",".join(f"0x{v:02X}" for v in c) + "}" for c in cs)
            h.append(f"  {{{inner}}},")
        h.append("};")
    h.append("")
    h.append("struct IconGlyphs {")
    h.append("  uint8_t frames;")
    h.append("  uint16_t interval_ms;")
    h.append("  const uint8_t (*data)[4][8];")
    h.append("};")
    h.append("")
    h.append("static const IconGlyphs ICONS[ICON_COUNT] = {")
    for name in order:
        frames, ms = glyphs[name]
        h.append(f"  {{{len(frames)}, {ms}, {cname(name)}_FRAMES}},  // {name}")
    h.append("};")
    h.append("")
    h.append("// Home Assistant weather condition to icon; night picks the moon variants.")
    h.append("inline Icon from_condition(const std::string &c, bool night) {")
    for cond, (day, nt) in ha_map.items():
        if day == nt:
            h.append(f"  if (c == \"{cond}\") return {cname(day)};")
        else:
            h.append(f"  if (c == \"{cond}\") return night ? {cname(nt)} : {cname(day)};")
    h.append("  return CLOUDY;")
    h.append("}")
    h.append("")
    h.append("// Write frame `frame` (taken modulo the icon's frame count) into CGRAM")
    h.append("// slots first..first+3 as top-left, top-right, bottom-left, bottom-right.")
    h.append("template<typename LCD> inline void load(LCD *lcd, Icon icon, uint32_t frame, uint8_t first = 4) {")
    h.append("  const IconGlyphs &g = ICONS[icon < ICON_COUNT ? icon : CLOUDY];")
    h.append("  const uint8_t (*f)[8] = g.data[frame % g.frames];")
    h.append("  for (uint8_t c = 0; c < 4; c++) {")
    h.append("    uint8_t buf[8];")
    h.append("    memcpy(buf, f[c], 8);")
    h.append("    lcd->loadchar((first + c) & 7, buf);")
    h.append("  }")
    h.append("}")
    h.append("")
    h.append("}  // namespace weather_glyphs")
    with open(os.path.join(d, "weather_glyphs.h"), "w") as fh:
        fh.write("\n".join(h) + "\n")

    # YAML-ready static user_characters (first frame of each icon) for a quick
    # test without the header.
    y = ["# Generated by weather_icons/tools/generate.py.",
         "# First frame of each icon as lcd_pcf8574 / lcd_gpio user_characters,",
         "# for a static test. Animation needs weather_glyphs.h (see README).",
         ""]
    for name in order:
        frames, ms = glyphs[name]
        y.append(f"{name}:")
        for slot, c in zip(range(4, 8), cells(frames[0])):
            y.append(f"  - position: {slot}")
            y.append("    data:")
            for v in c:
                y.append(f"      - 0b{v:05b}")
    with open(os.path.join(d, "user_characters.yaml"), "w") as fh:
        fh.write("\n".join(y) + "\n")
