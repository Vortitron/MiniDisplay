#!/usr/bin/env python3
"""Generate the 1-bit animated weather icons in esphome/weather_icons/.

The shapes are pixel art drawn procedurally at the native size, guided by
the Meteocons set by Bas Milius (MIT licence, see ../README.md). Downscaling
the vectors to 32 px or 20 px and thresholding gave mushy results, so every
cloud, sun, moon, drop and flake here is placed on the pixel grid by hand
(or by a small geometric rule) and checked on the contact sheets.

Outputs (relative to the weather_icons folder):
  oled32/<icon>.gif      32x32, 4-8 frames, for the 128x64 OLED
  lcd20/<icon>.gif       24x20, 2-4 frames, for the 128x64 STN LCD
  hd44780/glyphs.json    5x8 CGRAM frames, 2x2 cells per icon
  hd44780/weather_glyphs.h  the same as a C++ header for ESPHome lambdas
  oled32/images.yaml, lcd20/images.yaml  ESPHome packages declaring them
  hd44780/user_characters.yaml  first frames as static user_characters
  manifest.json          icon list, frame counts, intervals, HA mapping

The GIFs are written by gifwrite.py (two-colour palette, 2-bit LZW, frames
cropped to what changed) and then decoded again the way ESPHome's image
component does it, so a file that would not embed correctly stops the run.

In every GIF a white pixel means "ink": a set bit when ESPHome encodes the
frame as type BINARY, drawn in COLOR_ON. That is a lit pixel on the OLED and
a dark pixel on the STN LCD.

Usage:
  python generate.py [--out DIR] [--sheets DIR] [--meteocons DIR]

--sheets writes contact sheets (every frame, 8x) for checking by eye.
--meteocons points at Meteocons production/fill/png/128 to add the
original icon as a reference column on the sheets.
"""

import argparse
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.dirname(HERE)

# --------------------------------------------------------------------------
# Bitmap primitives
# --------------------------------------------------------------------------


class Bm:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.p = [[0] * w for _ in range(h)]

    def copy(self):
        b = Bm(self.w, self.h)
        b.p = [r[:] for r in self.p]
        return b

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.p[y][x]
        return 0

    def set(self, x, y, v=1):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y][x] = v

    def cells(self):
        for y in range(self.h):
            for x in range(self.w):
                if self.p[y][x]:
                    yield x, y

    def paint(self, mask, v=1, dx=0, dy=0):
        for x, y in mask.cells():
            self.set(x + dx, y + dy, v)

    def shifted(self, dx, dy):
        b = Bm(self.w, self.h)
        b.paint(self, 1, dx, dy)
        return b

    def to_image(self):
        im = Image.new("1", (self.w, self.h), 0)
        for x, y in self.cells():
            im.putpixel((x, y), 1)
        return im

    def key(self):
        return tuple(tuple(r) for r in self.p)


def disc(m, cx, cy, r):
    """Fill pixels whose centres lie within r of (cx, cy) (edge coordinates)."""
    for y in range(m.h):
        for x in range(m.w):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                m.set(x, y)


def rect(m, x0, y0, x1, y1, v=1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            m.set(x, y, v)


def pill(m, x0, y0, x1, y1):
    """Horizontal capsule covering the box from (x0, y0) to (x1, y1), edge coords."""
    r = (y1 - y0) / 2.0
    cy = (y0 + y1) / 2.0
    for y in range(m.h):
        for x in range(m.w):
            px, py = x + 0.5, y + 0.5
            if py < y0 or py > y1:
                continue
            if x0 + r <= px <= x1 - r:
                m.set(x, y)
            else:
                cx = x0 + r if px < x0 + r else x1 - r
                if (px - cx) ** 2 + (py - cy) ** 2 <= r * r:
                    m.set(x, y)


def line(m, x0, y0, x1, y1, v=1):
    x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        m.set(x0, y0, v)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def sprite(m, art, x, y, v=1):
    """Blit an ASCII sprite ('#' = ink) with its top-left at (x, y)."""
    for j, row in enumerate(art.strip("\n").split("\n")):
        for i, c in enumerate(row):
            if c == "#":
                m.set(x + i, y + j, v)


def outline(mask, thick=1):
    """Pixels of mask that touch the outside (4-neighbourhood)."""
    out = Bm(mask.w, mask.h)
    inner = mask
    for _ in range(thick):
        nxt = Bm(mask.w, mask.h)
        for x, y in inner.cells():
            if all(inner.get(x + a, y + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                nxt.set(x, y)
        inner = nxt
    for x, y in mask.cells():
        if not inner.get(x, y):
            out.set(x, y)
    return out


def stamp(dst, mask, filled=False, thick=1, halo=0):
    """Draw a shape over dst: clear what it covers (plus an optional halo
    ring so it stands clear of what is behind) then ink it as a filled shape
    or an outline."""
    if halo:
        grown = grow(mask, halo)
        dst.paint(grown, 0)
    else:
        dst.paint(mask, 0)
    dst.paint(mask if filled else outline(mask, thick), 1)


def grow(mask, n=1):
    g = mask
    for _ in range(n):
        nxt = g.copy()
        for x, y in g.cells():
            for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt.set(x + a, y + b)
        g = nxt
    return g


# --------------------------------------------------------------------------
# Shapes (Meteocons-like proportions)
# --------------------------------------------------------------------------


def cloud(W, H, x, y, w, h):
    """Meteocons cloud: a capsule base with a big puff right of centre and
    a smaller one on the left. (x, y, w, h) is the bounding box in edge
    coordinates."""
    m = Bm(W, H)
    hb = h * 0.5
    pill(m, x, y + h - hb, x + w, y + h)
    rb = h * 0.5
    disc(m, x + w * 0.64, y + rb, rb)
    rs = h * 0.32
    disc(m, x + w * 0.30, y + h * 0.22 + rs, rs)
    return despur(m)


def despur(m):
    """Remove one-pixel nubs (pixels with at most one 4-neighbour), which
    the round ends of the capsule leave on the outline."""
    out = m.copy()
    for x, y in m.cells():
        if sum(m.get(x + a, y + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))) <= 1:
            out.set(x, y, 0)
    return out


def crescent(W, H, cx, cy, r, ox, oy, r2=None):
    m = Bm(W, H)
    disc(m, cx, cy, r)
    cut = Bm(W, H)
    disc(cut, cx + ox, cy + oy, r2 if r2 else r * 0.85)
    m.paint(cut, 0)
    return m


def sun_rays(m, cx, cy, r1, r2, rot_deg=0.0, n=8, which=None, avoid=None):
    """Draw n rays. Rays that would touch `avoid` (grown by two pixels) are
    left out whole, so a cloud in front never leaves stray ray stubs."""
    keep_out = grow(avoid, 2) if avoid is not None else None
    for k in range(n):
        if which is not None and k % 2 != which:
            continue
        a = math.radians(rot_deg + k * 360.0 / n)
        x0, y0 = cx + r1 * math.cos(a) - 0.5, cy + r1 * math.sin(a) - 0.5
        x1, y1 = cx + r2 * math.cos(a) - 0.5, cy + r2 * math.sin(a) - 0.5
        ray = Bm(m.w, m.h)
        line(ray, x0, y0, x1, y1)
        if keep_out is not None and any(keep_out.get(x, y) for x, y in ray.cells()):
            continue
        m.paint(ray)


# Small sprites
FLAKE5 = """
..#..
#.#.#
.###.
#.#.#
..#..
"""
FLAKE3 = """
#.#
.#.
#.#
"""
HAIL4 = """
.##.
####
####
.##.
"""
HAIL2 = """
##
##
"""
STAR5 = """
..#..
..#..
##.##
..#..
..#..
"""
STAR3 = """
.#.
#.#
.#.
"""
BOLT32 = """
.....###
....###.
...###..
..###...
.#######
.....##.
....##..
...##...
...#....
..#.....
.#......
"""
BOLT20 = """
...##
..##.
.##..
#####
...#.
..#..
.#...
"""

# --------------------------------------------------------------------------
# Icon builders. Each returns a list of Bm frames.
# --------------------------------------------------------------------------


def falling(W, H, items, f, n, ytop, period, draw):
    """Draw falling things. items: (x, phase, wobble list or None).
    Position loops over `period` pixels in n frames."""
    m = Bm(W, H)
    step = period / n
    for x, phase, wob in items:
        pos = (phase + f * step) % period
        y = int(round(ytop + pos))
        dx = wob[f % len(wob)] if wob else 0
        draw(m, x + dx, y)
    return m


def drop_line(length, slant=0):
    def d(m, x, y):
        for i in range(length):
            m.set(x - (i * slant) // 2, y + i)
    return d


def sprite_at(art):
    def d(m, x, y):
        sprite(m, art, x, y)
    return d


# ---- 32 x 32 (OLED) ------------------------------------------------------

W32 = H32 = 32
TOP32 = (2.5, 2.5, 27, 16)      # cloud with weather under it
FULL32 = (2.5, 8.5, 27, 17)     # cloud on its own


def o_cloud_top(filled=False):
    return cloud(W32, H32, *TOP32)


def o_sunny():
    frames = []
    for f in range(4):
        m = Bm(W32, H32)
        disc(m, 16, 16, 5.6)
        sun_rays(m, 16, 16, 9, 13.5, rot_deg=f * 11.25)
        frames.append(m)
    return frames, 140


def o_clear_night():
    moon = crescent(W32, H32, 14, 17, 10.5, 6, -4.5, 9)
    stars = [(22, 4), (27, 13), (24, 22)]
    frames = []
    for f in range(6):
        m = Bm(W32, H32)
        m.paint(moon)
        for i, (sx, sy) in enumerate(stars):
            ph = (f - i * 2) % 6
            if ph == 0:
                sprite(m, STAR5, sx - 2, sy - 2)
            elif ph in (1, 5):
                sprite(m, STAR3, sx - 1, sy - 1)
            else:
                m.set(sx, sy)
        frames.append(m)
    return frames, 180


def o_partly(night=False):
    frames = []
    n = 4 if not night else 6
    for f in range(n):
        m = Bm(W32, H32)
        c = cloud(W32, H32, 8.5, 13.5, 22, 13)
        if not night:
            disc(m, 11, 11, 4.1)
            sun_rays(m, 11, 11, 6.5, 9.6, rot_deg=f * 11.25, avoid=c)
        else:
            m.paint(crescent(W32, H32, 10, 10, 7.5, 4.5, -3.5, 6.5))
            st = ["dot", "small", "big", "small", "dot", None][f]
            if st == "big":
                sprite(m, STAR5, 24, 1)
            elif st == "small":
                sprite(m, STAR3, 25, 2)
            elif st == "dot":
                m.set(26, 3)
        dx = [0, 1, 1, 0, -1, -1][f % 6] if night else 0
        stamp(m, c.shifted(dx, 0), halo=1)
        frames.append(m)
    return frames, 140 if not night else 180


def o_cloudy():
    frames = []
    offs = [0, 1, 2, 1, 0, -1, -2, -1]
    for f in range(8):
        m = Bm(W32, H32)
        back = cloud(W32, H32, 12.5, 5.5, 18, 11).shifted(-offs[f], 0)
        stamp(m, back)
        front = cloud(W32, H32, 1.5, 13.5, 24, 14).shifted(offs[f] // 2, 0)
        stamp(m, front, halo=1)
        frames.append(m)
    return frames, 200


def o_fog():
    frames = []
    for f in range(4):
        m = Bm(W32, H32)
        stamp(m, cloud(W32, H32, 2.5, 1.5, 27, 15))
        for j, (y, x0, x1, d) in enumerate(((20, 4, 27, 1), (24, 2, 29, -1), (28, 5, 26, 1))):
            for x in range(x0, x1 + 1):
                if (x + d * f * 2) % 12 < 9:
                    m.set(x, y)
        frames.append(m)
    return frames, 200


def scroll(W, H, items, f, step, y0, period):
    """Precipitation as a vertically repeating band from row y0 down,
    `period` rows tall, scrolled down by `step` rows per frame. Each item is
    (x, phase, draw, wobble); a sprite running off the bottom reappears at
    the top of the band, just under the cloud, so the band never empties."""
    m = Bm(W, H)
    for x, phase, draw, wob in items:
        tmp = Bm(W, period + 8)
        dx = wob[f % len(wob)] if wob else 0
        draw(tmp, x + dx, 0)
        off = int(phase + f * step)
        for px, py in tmp.cells():
            m.set(px, y0 + (py + off) % period)
    return m


def o_precip(kind):
    """Cloud with rain, snow, hail, sleet or thunder under it."""
    n = 4 if kind == "lightning" else 6
    cl = cloud(W32, H32, *TOP32)
    y0, period, step = 20, 12, 2
    rain, pour = drop_line(4), drop_line(6)
    flake, hail = sprite_at(FLAKE5), sprite_at(HAIL4)
    wob = [0, 0, 1, 1, 0, 0]
    wob2 = [1, 1, 0, 0, 1, 1]
    items = {
        "rainy": [(8, 0, rain, None), (14, 6, rain, None), (20, 3, rain, None), (26, 9, rain, None)],
        "pouring": [(5, 0, pour, None), (9, 6, pour, None), (13, 3, pour, None), (17, 9, pour, None),
                    (21, 1, pour, None), (25, 7, pour, None)],
        "snowy": [(3, 0, flake, wob), (10, 6, flake, wob2), (17, 3, flake, wob), (24, 9, flake, wob2)],
        "snowy-rainy": [(4, 0, flake, wob), (13, 6, rain, None), (18, 3, flake, wob2), (27, 9, rain, None)],
        "hail": [(5, 0, hail, None), (12, 6, hail, None), (19, 3, hail, None), (26, 9, hail, None)],
        "lightning": [],
        "lightning-rainy": [(5, 0, rain, None), (8, 6, rain, None), (23, 3, rain, None), (27, 9, rain, None)],
    }[kind]
    frames = []
    for f in range(n):
        m = scroll(W32, H32, items, f, step, y0, period)
        st = None
        if kind in ("lightning", "lightning-rainy"):
            # The strike grows out of the cloud, flashes (the cloud lights
            # up), then goes dark.
            st = ["half", "full", "flash", None, None, None][f]
        stamp(m, cl, filled=(kind == "pouring" or st == "flash"), halo=1)
        if st:
            bolt = Bm(W32, H32)
            rows = BOLT32.strip("\n").split("\n")
            sprite(bolt, "\n".join(rows[:4] if st == "half" else rows), 11, 19)
            stamp(m, bolt, filled=True, halo=1)
        frames.append(m)
    return frames, 120


def wind_lines(W, H, specs, f, dash, gap, step):
    """specs: (y, x0, x1, curl) with curl 'up', 'down' or None at the right end.
    The straight parts carry a moving gap so the wind seems to flow."""
    m = Bm(W, H)
    for y, x0, x1, curl, r in specs:
        for x in range(x0, x1 + 1):
            if (x - f * step) % (dash + gap) < dash:
                m.set(x, y)
        if curl:
            # Hook: a circle of radius r tangent to the line end, going round
            # three quarters and pointing back to the left.
            sgn = -1 if curl == "up" else 1
            cy = y + sgn * r
            cx = x1
            pts = []
            for i in range(0, 271, 5):
                a = math.radians(90 - i) if curl == "up" else math.radians(-90 + i)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                line(m, ax, ay, bx, by)
    return m


def o_windy():
    frames = []
    specs = [(11, 2, 21, "up", 3.5), (17, 4, 27, None, 0), (23, 2, 17, "down", 3.5)]
    for f in range(4):
        frames.append(wind_lines(W32, H32, specs, f, 14, 3, 4))
    return frames, 150


TRI32_INV = None


def triangle(W, H, ax, ay, bx, by, cx, cy):
    m = Bm(W, H)
    def side(px, py, x1, y1, x2, y2):
        return (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)
    for y in range(H):
        for x in range(W):
            px, py = x + 0.5, y + 0.5
            d1 = side(px, py, ax, ay, bx, by)
            d2 = side(px, py, bx, by, cx, cy)
            d3 = side(px, py, cx, cy, ax, ay)
            neg = d1 < 0 or d2 < 0 or d3 < 0
            pos = d1 > 0 or d2 > 0 or d3 > 0
            if not (neg and pos):
                m.set(x, y)
    return m


def o_exceptional():
    tri = triangle(W32, H32, 16, 2, 30.5, 29, 1.5, 29)
    bang = Bm(W32, H32)
    rect(bang, 15, 10, 16, 20)
    rect(bang, 15, 23, 16, 24)
    # A slow blink between outline and solid. Four frames rather than two
    # so that, stepped by the same short interval as the other 32 px icons,
    # each state is held for two ticks.
    frames = []
    for f in range(4):
        m = Bm(W32, H32)
        if f % 2 == 0:
            m.paint(outline(tri, 2))
            m.paint(bang)
        else:
            m.paint(tri)
            m.paint(bang, 0)
        frames.append(m)
    return frames, 300


# ---- 24 x 20 (STN LCD cell) ----------------------------------------------

W20, H20 = 24, 20
TOP20 = (1.5, 0.5, 21, 10)


def l_sunny():
    frames = []
    for f in range(2):
        m = Bm(W20, H20)
        disc(m, 12, 10, 4.1)
        # Long rays on one set, short on the other, swapping each frame.
        sun_rays(m, 12, 10, 6.4, 9.6, which=f, rot_deg=0)
        sun_rays(m, 12, 10, 6.4, 7.6, which=1 - f, rot_deg=0)
        frames.append(m)
    return frames, 500


def l_clear_night():
    moon = crescent(W20, H20, 10, 11, 8, 4.5, -3.5, 7)
    frames = []
    for f in range(2):
        m = Bm(W20, H20)
        m.paint(moon)
        if f == 0:
            sprite(m, STAR5, 17, 1)
            m.set(21, 13)
        else:
            m.set(19, 3)
            sprite(m, STAR3, 20, 12)
        frames.append(m)
    return frames, 600


def l_partly(night=False):
    frames = []
    for f in range(2):
        m = Bm(W20, H20)
        c = cloud(W20, H20, 5.5, 9.5, 18, 10)
        if not night:
            disc(m, 8, 7, 3.1)
            sun_rays(m, 8, 7, 4.9, 7.4, which=f, avoid=c)
            sun_rays(m, 8, 7, 4.9, 5.9, which=1 - f, avoid=c)
        else:
            m.paint(crescent(W20, H20, 8, 7, 6, 3.5, -2.5, 5.2))
            if f == 0:
                sprite(m, STAR3, 18, 0)
            else:
                m.set(19, 1)
        stamp(m, c, halo=1)
        frames.append(m)
    return frames, 600


def l_cloudy():
    frames = []
    for f in range(2):
        m = Bm(W20, H20)
        stamp(m, cloud(W20, H20, 8.5, 2.5, 15, 9).shifted(-f, 0))
        stamp(m, cloud(W20, H20, 0.5, 8.5, 18, 11).shifted(f, 0), halo=1)
        frames.append(m)
    return frames, 600


def l_fog():
    frames = []
    for f in range(2):
        m = Bm(W20, H20)
        stamp(m, cloud(W20, H20, 1.5, 0.5, 21, 11))
        for y, x0, x1, d in ((14, 3, 20, 1), (17, 1, 22, -1)):
            for x in range(x0, x1 + 1):
                if (x + d * f * 3) % 9 < 6:
                    m.set(x, y)
        frames.append(m)
    return frames, 600


def l_precip(kind):
    """24x20 precipitation: two frames, each column's drops jumping half a
    band per frame, which reads as falling at the slow refresh of an STN
    panel and keeps the files tiny."""
    cl = cloud(W20, H20, *TOP20)
    y0, period, step = 12, 8, 4
    rain, pour = drop_line(3), drop_line(4)
    flake, hail = sprite_at(FLAKE3), sprite_at(HAIL2)
    items = {
        "rainy": [(5, 0, rain, None), (10, 4, rain, None), (15, 0, rain, None), (20, 4, rain, None)],
        "pouring": [(3, 0, pour, None), (6, 4, pour, None), (9, 0, pour, None), (12, 4, pour, None),
                    (15, 0, pour, None), (18, 4, pour, None), (21, 0, pour, None)],
        "snowy": [(3, 0, flake, None), (9, 4, flake, None), (14, 0, flake, None), (19, 4, flake, None)],
        "snowy-rainy": [(3, 0, flake, None), (10, 4, rain, None), (14, 0, flake, None), (21, 4, rain, None)],
        "hail": [(4, 0, hail, None), (9, 4, hail, None), (14, 0, hail, None), (19, 4, hail, None)],
        "lightning": [],
        "lightning-rainy": [(3, 0, rain, None), (6, 4, rain, None), (18, 0, rain, None), (21, 4, rain, None)],
    }[kind]
    frames = []
    for f in range(2):
        m = scroll(W20, H20, items, f, step, y0, period)
        stamp(m, cl, filled=(kind == "pouring"), halo=1)
        if kind in ("lightning", "lightning-rainy") and f == 0:
            b = Bm(W20, H20)
            sprite(b, BOLT20, 10, 11)
            stamp(m, b, filled=True, halo=1)
        frames.append(m)
    return frames, 450


def l_windy():
    specs = [(6, 1, 15, "up", 2.5), (10, 3, 21, None, 0), (14, 1, 12, "down", 2.5)]
    return [wind_lines(W20, H20, specs, f, 10, 2, 6) for f in range(2)], 500


def l_exceptional():
    tri = triangle(W20, H20, 12, 0.5, 22.5, 19, 1.5, 19)
    bang = Bm(W20, H20)
    rect(bang, 11, 6, 12, 13)
    rect(bang, 11, 15, 12, 16)
    frames = []
    for f in range(2):
        m = Bm(W20, H20)
        if f == 0:
            m.paint(outline(tri, 1))
            m.paint(bang)
        else:
            m.paint(tri)
            m.paint(bang, 0)
        frames.append(m)
    return frames, 700


# --------------------------------------------------------------------------
# Icon list and Home Assistant mapping
# --------------------------------------------------------------------------

ICONS = [
    "sunny", "clear-night", "partlycloudy", "partlycloudy-night", "cloudy",
    "fog", "rainy", "pouring", "snowy", "snowy-rainy", "hail", "lightning",
    "lightning-rainy", "windy", "exceptional",
]

# HA condition -> (day icon, night icon)
HA_MAP = {
    "clear-night": ("clear-night", "clear-night"),
    "cloudy": ("cloudy", "cloudy"),
    "exceptional": ("exceptional", "exceptional"),
    "fog": ("fog", "fog"),
    "hail": ("hail", "hail"),
    "lightning": ("lightning", "lightning"),
    "lightning-rainy": ("lightning-rainy", "lightning-rainy"),
    "partlycloudy": ("partlycloudy", "partlycloudy-night"),
    "pouring": ("pouring", "pouring"),
    "rainy": ("rainy", "rainy"),
    "snowy": ("snowy", "snowy"),
    "snowy-rainy": ("snowy-rainy", "snowy-rainy"),
    "sunny": ("sunny", "clear-night"),
    "windy": ("windy", "windy"),
    "windy-variant": ("windy", "windy"),
}

METEOCONS_REF = {
    "sunny": "clear-day", "clear-night": "clear-night",
    "partlycloudy": "partly-cloudy-day", "partlycloudy-night": "partly-cloudy-night",
    "cloudy": "cloudy", "fog": "fog", "rainy": "rain", "pouring": "extreme-rain",
    "snowy": "snow", "snowy-rainy": "sleet", "hail": "hail",
    "lightning": "thunderstorms", "lightning-rainy": "thunderstorms-rain",
    "windy": "wind", "exceptional": "code-red",
}


def build_oled():
    b = {
        "sunny": o_sunny, "clear-night": o_clear_night,
        "partlycloudy": lambda: o_partly(False), "partlycloudy-night": lambda: o_partly(True),
        "cloudy": o_cloudy, "fog": o_fog, "windy": o_windy, "exceptional": o_exceptional,
    }
    out = {}
    for name in ICONS:
        out[name] = b[name]() if name in b else o_precip(name)
    return out


def build_lcd():
    b = {
        "sunny": l_sunny, "clear-night": l_clear_night,
        "partlycloudy": lambda: l_partly(False), "partlycloudy-night": lambda: l_partly(True),
        "cloudy": l_cloudy, "fog": l_fog, "windy": l_windy, "exceptional": l_exceptional,
    }
    out = {}
    for name in ICONS:
        out[name] = b[name]() if name in b else l_precip(name)
    return out


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------


def save_gif(path, frames, ms):
    import gifwrite
    gifwrite.write(path, [f.p for f in frames], ms)


def check_gif(path, frames):
    """Decode the GIF exactly as ESPHome's image encoder does (seek, convert
    to mode 1) and compare with the source frames."""
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    assert n == len(frames), f"{path}: {n} frames in file, {len(frames)} drawn"
    for i, fr in enumerate(frames):
        im.seek(i)
        got = im.resize(im.size).convert("1")
        for y in range(fr.h):
            for x in range(fr.w):
                if bool(got.getpixel((x, y))) != bool(fr.p[y][x]):
                    raise SystemExit(f"{path}: frame {i} differs at {x},{y}")


def write_package(path, sname, prefix, icons):
    """An ESPHome package with one image (platform: animation) per icon,
    plus a lambda snippet that picks one from the HA condition."""
    y = [f"# Generated by weather_icons/tools/generate.py. Do not edit by hand.",
         f"# Include from a device YAML in /config/esphome/ with:",
         f"#   packages:",
         f"#     {prefix}: !include weather_icons/{sname}/images.yaml",
         f"# Ids are {prefix}_<icon>, e.g. {prefix}_partlycloudy_night.",
         "image:"]
    for name in ICONS:
        frames, ms = icons[name]
        y += [f"  - platform: animation",
              f"    id: {prefix}_{name.replace('-', '_')}",
              f"    file: weather_icons/{sname}/{name}.gif",
              f"    type: BINARY",
              f"    # {len(frames)} frames, {frames[0].w}x{frames[0].h}, step every {ms} ms"]
    with open(path, "w") as fh:
        fh.write("\n".join(y) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--sheets", default=None)
    ap.add_argument("--meteocons", default=None)
    a = ap.parse_args()

    import hd44780  # sibling module with the hand-drawn character art
    import sheets

    sets = {"oled32": build_oled(), "lcd20": build_lcd()}
    manifest = {"icons": {}, "ha_conditions": {k: {"day": v[0], "night": v[1]} for k, v in HA_MAP.items()}}
    for sname, icons in sets.items():
        d = os.path.join(a.out, sname)
        os.makedirs(d, exist_ok=True)
        for name, (frames, ms) in icons.items():
            # Two identical consecutive frames would be wasted flash.
            keys = [f.key() for f in frames]
            # (Pillow would also merge them, changing the frame count.)
            for i in range(len(keys)):
                if len(keys) > 1 and keys[i] == keys[(i + 1) % len(keys)]:
                    raise SystemExit(f"{sname}/{name}: frames {i} and {(i + 1) % len(keys)} are identical")
            p = os.path.join(d, name + ".gif")
            save_gif(p, frames, ms)
            check_gif(p, frames)
            manifest["icons"].setdefault(name, {})[sname] = {
                "file": f"weather_icons/{sname}/{name}.gif",
                "width": frames[0].w, "height": frames[0].h,
                "frames": len(frames), "interval_ms": ms,
                "bytes": os.path.getsize(p),
            }

    for sname, prefix in (("oled32", "wx32"), ("lcd20", "wx20")):
        write_package(os.path.join(a.out, sname, "images.yaml"), sname, prefix, sets[sname])

    glyphs = hd44780.build()
    hd44780.write(os.path.join(a.out, "hd44780"), glyphs, HA_MAP, ICONS)
    for name in ICONS:
        manifest["icons"][name]["hd44780"] = {"cells": "2x2", "frames": len(glyphs[name][0]),
                                              "interval_ms": glyphs[name][1]}
    with open(os.path.join(a.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")

    if a.sheets:
        os.makedirs(a.sheets, exist_ok=True)
        sheets.write_all(a.sheets, sets, glyphs, ICONS, a.meteocons, METEOCONS_REF)


if __name__ == "__main__":
    main()
