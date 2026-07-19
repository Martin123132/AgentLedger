from __future__ import annotations

import argparse
import binascii
import struct
import zlib
from pathlib import Path


SIZE = 256
SCALE = 4


def _inside_rounded_square(x: int, y: int, *, inset: int, radius: int) -> bool:
    low = inset
    high = SIZE * SCALE - inset - 1
    if low + radius <= x <= high - radius or low + radius <= y <= high - radius:
        return low <= x <= high and low <= y <= high
    corner_x = low + radius if x < low + radius else high - radius
    corner_y = low + radius if y < low + radius else high - radius
    return (x - corner_x) ** 2 + (y - corner_y) ** 2 <= radius**2


def _sample(x: int, y: int) -> tuple[int, int, int, int]:
    outer = _inside_rounded_square(x, y, inset=28, radius=170)
    if not outer:
        return 0, 0, 0, 0
    inner = _inside_rounded_square(x, y, inset=54, radius=145)
    if not inner:
        return 70, 185, 129, 255

    if 260 <= x <= 342 and 230 <= y <= 794:
        return 70, 185, 129, 255
    if 342 <= x <= 760 and (230 <= y <= 282 or 742 <= y <= 794):
        return 70, 185, 129, 255
    if 410 <= x <= 760 and any(abs(y - center) <= 20 for center in (372, 512, 652)):
        return 238, 242, 245, 255
    if (x - 790) ** 2 + (y - 652) ** 2 <= 38**2:
        return 226, 103, 103, 255
    return 17, 20, 24, 255


def _rgba() -> bytes:
    pixels = bytearray()
    for y in range(SIZE):
        for x in range(SIZE):
            samples = [_sample(x * SCALE + sx, y * SCALE + sy) for sy in range(SCALE) for sx in range(SCALE)]
            pixels.extend(sum(sample[channel] for sample in samples) // len(samples) for channel in range(4))
    return bytes(pixels)


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", binascii.crc32(payload) & 0xFFFFFFFF)


def png_bytes() -> bytes:
    rgba = _rgba()
    stride = SIZE * 4
    scanlines = b"".join(b"\x00" + rgba[offset : offset + stride] for offset in range(0, len(rgba), stride))
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(scanlines, 9)) + _chunk(b"IEND", b"")


def write_icon(path: Path) -> None:
    png = png_bytes()
    icon_header = struct.pack("<HHH", 0, 1, 1)
    icon_entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(icon_header + icon_entry + png)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the deterministic AgentLedger Windows icon.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_icon(args.output)
    print(f"Desktop icon written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
