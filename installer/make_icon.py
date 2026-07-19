# -*- coding: utf-8 -*-
"""Tao installer/app.ico: bieu tuong khung phim + but ve cho AutoCartoon.

Chay: AIVoice\.venv\Scripts\python.exe installer\make_icon.py
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256.0

    def px(v):
        return max(1, round(v * s))

    # Nen bo goc mau tim dam (phong cach studio)
    r = px(48)
    d.rounded_rectangle([px(8), px(8), size - px(8), size - px(8)],
                        radius=r, fill=(76, 29, 149, 255))

    # Khung phim ngang mau trang
    top, bot = px(84), px(172)
    d.rounded_rectangle([px(28), top, size - px(28), bot],
                        radius=px(10), fill=(245, 243, 255, 255))
    # Lo ran phim (tren/duoi)
    hole = px(14)
    step = px(34)
    x = px(40)
    while x + hole < size - px(36):
        for y in (top + px(6), bot - px(6) - hole):
            d.rectangle([x, y, x + hole, y + hole], fill=(76, 29, 149, 255))
        x += step
    # Ba o hinh giua khung phim
    mid_top, mid_bot = top + px(28), bot - px(28)
    w = px(46)
    gap = px(12)
    x = px(44)
    colors = [(251, 191, 36, 255), (52, 211, 153, 255), (96, 165, 250, 255)]
    for c in colors:
        d.rounded_rectangle([x, mid_top, x + w, mid_bot], radius=px(6), fill=c)
        x += w + gap

    # Tam giac "play" o giua
    cx, cy = size // 2, (mid_top + mid_bot) // 2
    t = px(22)
    d.polygon([(cx - t + px(4), cy - t), (cx - t + px(4), cy + t),
               (cx + t, cy)], fill=(76, 29, 149, 255))
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = draw_icon(256)
    out = os.path.join(HERE, "app.ico")
    base.save(out, format="ICO",
              sizes=[(n, n) for n in sizes])
    print(f"Da tao {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
