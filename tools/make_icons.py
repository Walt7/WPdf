"""Rigenera le icone raster da wpdf/assets/favicon.svg: python tools/make_icons.py

- favicon.ico          16..256 px (voci PNG, lette da browser e Windows Vista+)
- apple-touch-icon.png 180 px
Ogni formato è reso a 4x e poi ridotto: tratti sottili più puliti nelle misure piccole.
"""
import struct
from pathlib import Path

import pymupdf

ASSETS = Path(__file__).resolve().parent.parent / "wpdf" / "assets"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def png(svg, size):
    page = pymupdf.open(svg)[0]
    z = size * 4 / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=True)
    pix.shrink(2)   # 4x -> 1x con media dei pixel
    return pix.tobytes("png")


def ico(images):
    """images: [(size, png bytes)] -> file .ico con voci PNG."""
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries, data = b"", b""
    for size, blob in images:
        dim = 0 if size >= 256 else size   # 0 = 256 nel formato ICO
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(data))
        data += blob
    return head + entries + data


def main():
    svg = str(ASSETS / "favicon.svg")
    (ASSETS / "favicon.ico").write_bytes(ico([(s, png(svg, s)) for s in ICO_SIZES]))
    (ASSETS / "apple-touch-icon.png").write_bytes(png(svg, 180))
    print("favicon.ico, apple-touch-icon.png ->", ASSETS)


if __name__ == "__main__":
    main()
