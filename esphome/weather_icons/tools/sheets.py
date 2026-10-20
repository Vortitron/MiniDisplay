"""Contact sheets: every frame of every icon, scaled 8x, for checking by eye."""

import os

from PIL import Image, ImageDraw, ImageFont

SCALE = 8
PER_SHEET = 5

STYLES = {
    # name: (background, ink, grid)
    "oled32": ((0, 0, 0), (235, 245, 255), (28, 28, 28)),
    "lcd20": ((178, 192, 168), (35, 45, 55), (165, 179, 156)),
}


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_bm(bm, style, scale=SCALE, grid=True):
    bg, ink, gc = style
    im = Image.new("RGB", (bm.w * scale, bm.h * scale), bg)
    d = ImageDraw.Draw(im)
    for y in range(bm.h):
        for x in range(bm.w):
            if bm.p[y][x]:
                d.rectangle([x * scale, y * scale, x * scale + scale - 1, y * scale + scale - 1], fill=ink)
    if grid and scale >= 4:
        for x in range(0, bm.w * scale, scale):
            d.line([x, 0, x, bm.h * scale], fill=gc)
        for y in range(0, bm.h * scale, scale):
            d.line([0, y, bm.w * scale, y], fill=gc)
    return im


def render_hd(g, scale=SCALE):
    """A 2x2 block of HD44780 cells with the gaps between characters."""
    gap = scale
    w = 10 * scale + gap
    h = 16 * scale + gap
    im = Image.new("RGB", (w, h), (5, 10, 60))
    d = ImageDraw.Draw(im)
    for y in range(16):
        for x in range(10):
            px = x * scale + (gap if x >= 5 else 0)
            py = y * scale + (gap if y >= 8 else 0)
            col = (235, 245, 255) if g[y][x] else (25, 50, 190)
            m = 1 if scale >= 4 else 0
            d.rectangle([px + m, py + m, px + scale - 1 - m, py + scale - 1 - m], fill=col)
    return im


def sheet(path, rows, title):
    """rows: list of (label, ref image or None, small preview, [frame images])."""
    f = font(22)
    ft = font(26)
    pad = 16
    label_w = 300
    cell_w = max(im.width for r in rows for im in r[3])
    cell_h = max(im.height for r in rows for im in r[3])
    nmax = max(len(r[3]) for r in rows)
    ref_w = cell_h if any(r[1] is not None for r in rows) else 0
    W = pad + label_w + (ref_w + pad if ref_w else 0) + nmax * (cell_w + pad)
    H = 50 + len(rows) * (cell_h + pad + 30) + pad
    out = Image.new("RGB", (W, H), (120, 120, 120))
    d = ImageDraw.Draw(out)
    d.text((pad, 10), title, fill=(255, 255, 255), font=ft)
    y = 50
    for label, ref, small, frames in rows:
        d.text((pad, y + 4), label, fill=(255, 255, 255), font=f)
        d.text((pad, y + 32), f"{len(frames)} frames", fill=(220, 220, 220), font=f)
        if small is not None:
            out.paste(small, (pad, y + 70))
        x = pad + label_w
        if ref_w:
            if ref is not None:
                r = ref.convert("RGBA").resize((ref_w, ref_w), Image.LANCZOS)
                bgim = Image.new("RGBA", r.size, (255, 255, 255, 255))
                bgim.alpha_composite(r)
                out.paste(bgim.convert("RGB"), (x, y))
            x += ref_w + pad
        for i, im in enumerate(frames):
            out.paste(im, (x, y))
            d.text((x, y + im.height + 2), f"f{i}", fill=(255, 255, 255), font=f)
            x += cell_w + pad
        y += cell_h + pad + 30
    out.save(path)
    return path


def write_all(dirpath, sets, glyphs, order, meteocons_dir, ref_names):
    written = []

    def ref(name):
        if not meteocons_dir:
            return None
        p = os.path.join(meteocons_dir, ref_names.get(name, name) + ".png")
        return Image.open(p) if os.path.exists(p) else None

    for sname, icons in sets.items():
        st = STYLES[sname]
        chunks = [order[i:i + PER_SHEET] for i in range(0, len(order), PER_SHEET)]
        for ci, names in enumerate(chunks):
            rows = []
            for n in names:
                frames, ms = icons[n]
                small = Image.new("RGB", (frames[0].w * 2 * len(frames[:1]), frames[0].h * 2))
                small = render_bm(frames[0], st, 2, grid=False)
                rows.append((f"{n} {ms}ms", ref(n), small, [render_bm(fr, st) for fr in frames]))
            p = os.path.join(dirpath, f"sheet_{sname}_{ci + 1}.png")
            written.append(sheet(p, rows, f"{sname}  ({ci + 1}/{len(chunks)})  8x, small preview 2x"))

    chunks = [order[i:i + PER_SHEET] for i in range(0, len(order), PER_SHEET)]
    for ci, names in enumerate(chunks):
        rows = []
        for n in names:
            frames, ms = glyphs[n]
            rows.append((f"{n} {ms}ms", ref(n), render_hd(frames[0], 2), [render_hd(g) for g in frames]))
        p = os.path.join(dirpath, f"sheet_hd44780_{ci + 1}.png")
        written.append(sheet(p, rows, f"hd44780 2x2 cells ({ci + 1}/{len(chunks)})  8x, small preview 2x"))
    for p in written:
        print("sheet:", p)
    return written
