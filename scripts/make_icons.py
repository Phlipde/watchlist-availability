"""Draws the app icons (static/icons/icon-192.png, icon-512.png, maskable-512.png) without any image library.

Run it only when the design of the icon changes: `python scripts/make_icons.py`.
A dark rounded square with an amber film frame: the app's own colours (--bg and --accent).
"""

import struct
import zlib
from pathlib import Path

BACKGROUND = (16, 20, 18)
AMBER = (232, 184, 107)


def png(size: int, pixel) -> bytes:
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            row += bytes(pixel(x / size, y / size))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def icon(margin: float):
    """A film frame (outer ring with small holes on both sides) inside `margin` of safe space."""

    def pixel(x: float, y: float):
        u, v = (x - margin) / (1 - 2 * margin), (y - margin) / (1 - 2 * margin)
        if not (0 <= u <= 1 and 0 <= v <= 1):
            return BACKGROUND
        edge = min(u, 1 - u, v, 1 - v)
        if edge < 0.09:  # the outer ring
            return AMBER
        inside_hole = 0.09 <= edge < 0.2 and (u < 0.2 or u > 0.8) and (int(v * 8) % 2 == 0)
        if inside_hole:
            return BACKGROUND
        if (u < 0.2 or u > 0.8) and edge >= 0.09:  # the side strips of the frame
            return AMBER
        # the play triangle in the middle
        return AMBER if 0.4 <= u <= 0.64 and abs(v - 0.5) <= 0.18 * (0.64 - u) / 0.24 else BACKGROUND

    return pixel


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "static" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    (out / "icon-192.png").write_bytes(png(192, icon(0.1)))
    (out / "icon-512.png").write_bytes(png(512, icon(0.1)))
    (out / "maskable-512.png").write_bytes(png(512, icon(0.2)))  # more safe space for round masks


if __name__ == "__main__":
    main()
