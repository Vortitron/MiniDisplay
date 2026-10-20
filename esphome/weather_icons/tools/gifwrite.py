"""A minimal GIF89a writer for two-colour animations.

Pillow writes these icons with an 8-bit LZW code size and a four-entry
palette; for 1-bit art a 2-bit code size, a two-entry palette and frames
cropped to the area that changed are a good deal smaller. The output is
checked by decoding it again with Pillow (see generate.check_gif).
"""

import struct


def _lzw(indices, min_size=2):
    clear = 1 << min_size
    eoi = clear + 1
    out = bytearray()
    acc = 0
    nbits = 0

    def emit(code, size):
        nonlocal acc, nbits
        acc |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8

    def reset():
        return {(i,): i for i in range(clear)}, eoi + 1, min_size + 1

    table, nxt, size = reset()
    emit(clear, size)
    w = ()
    for c in indices:
        wc = w + (c,)
        if wc in table:
            w = wc
            continue
        emit(table[w], size)
        if nxt < 4096:
            table[wc] = nxt
            nxt += 1
            if nxt > (1 << size) and size < 12:
                size += 1
        else:
            emit(clear, size)
            table, nxt, size = reset()
        w = (c,)
    if w:
        emit(table[w], size)
    emit(eoi, size)
    if nbits:
        out.append(acc & 0xFF)
    return bytes(out)


def _blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out.append(len(chunk))
        out += chunk
    out.append(0)
    return bytes(out)


def write(path, frames, delay_ms):
    """frames: list of 2D lists (rows) of 0/1, all the same size."""
    h = len(frames[0])
    w = len(frames[0][0])
    out = bytearray(b"GIF89a")
    # Logical screen: global colour table of 2 entries (size field 0).
    out += struct.pack("<HHBBB", w, h, 0x80, 0, 0)
    out += bytes([0, 0, 0, 255, 255, 255])
    # Loop for ever.
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    prev = None
    delay = max(1, int(round(delay_ms / 10.0)))
    for fr in frames:
        if prev is None:
            x0, y0, x1, y1 = 0, 0, w - 1, h - 1
        else:
            diff = [(x, y) for y in range(h) for x in range(w) if fr[y][x] != prev[y][x]]
            if not diff:
                diff = [(0, 0)]
            x0 = min(p[0] for p in diff)
            x1 = max(p[0] for p in diff)
            y0 = min(p[1] for p in diff)
            y1 = max(p[1] for p in diff)
        # Graphic control: disposal 1 (leave in place), no transparency.
        out += b"\x21\xf9\x04" + bytes([1 << 2]) + struct.pack("<H", delay) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHHB", x0, y0, x1 - x0 + 1, y1 - y0 + 1, 0)
        pix = [fr[y][x] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
        out.append(2)
        out += _blocks(_lzw(pix, 2))
        prev = fr
    out += b"\x3b"
    with open(path, "wb") as fh:
        fh.write(out)
