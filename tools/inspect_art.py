#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Осмотр арта: сетки координат на вайдах/зумах, контакт-листы катаутов.
Выход: /home/claude/bj2/work/inspect/
"""
import os
from PIL import Image, ImageDraw, ImageFont

GFX = "/home/claude/bj2/assets/gfx"
OUT = "/home/claude/bj2/work/inspect"
os.makedirs(OUT, exist_ok=True)

FONT_B = ImageFont.truetype("/home/claude/bj2/assets/fonts/PTSans-Bold.ttf", 30)
FONT_S = ImageFont.truetype("/home/claude/bj2/assets/fonts/PTSans-Bold.ttf", 20)

def grid(src, dst, step=100, major=500):
    im = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(im)
    w, h = im.size
    for x in range(0, w, step):
        col = (255, 80, 80) if x % major == 0 else (255, 220, 0)
        wd = 3 if x % major == 0 else 1
        d.line([(x, 0), (x, h)], fill=col, width=wd)
    for y in range(0, h, step):
        col = (255, 80, 80) if y % major == 0 else (255, 220, 0)
        wd = 3 if y % major == 0 else 1
        d.line([(0, y), (w, y)], fill=col, width=wd)
    # подписи в узлах каждые 200
    for x in range(0, w, 200):
        for y in range(0, h, 200):
            t = f"{x},{y}"
            bb = d.textbbox((0, 0), t, font=FONT_S)
            d.rectangle([x+2, y+2, x+6+bb[2], y+6+bb[3]], fill=(0, 0, 0))
            d.text((x+4, y+4), t, font=FONT_S, fill=(0, 255, 120))
    im.save(dst)

def contact_sheet(files, dst, cols=5, cell=340):
    rows = (len(files)+cols-1)//cols
    sheet = Image.new("RGB", (cols*cell, rows*(cell+44)), (40, 40, 48))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        w, h = im.size
        # шахматка
        tile = Image.new("RGBA", (cell, cell), (90, 90, 100, 255))
        td = ImageDraw.Draw(tile)
        for ty in range(0, cell, 20):
            for tx in range(0, cell, 20):
                if (tx//20+ty//20) % 2 == 0:
                    td.rectangle([tx, ty, tx+19, ty+19], fill=(120, 120, 132, 255))
        sc = min(cell/w, cell/h, 1.0)
        im2 = im.resize((max(1, int(w*sc)), max(1, int(h*sc))), Image.LANCZOS)
        ox = (cell-im2.width)//2
        oy = (cell-im2.height)//2
        tile.alpha_composite(im2, (ox, oy))
        cx = (i % cols)*cell
        cy = (i//cols)*(cell+44)
        sheet.paste(tile.convert("RGB"), (cx, cy))
        name = os.path.basename(f).replace(".png", "")
        d.text((cx+6, cy+cell+2), f"{name}  {w}x{h}", font=FONT_S, fill=(255, 255, 255))
    sheet.save(dst)

# 1) вайды
for r in ["room_office_night", "room_office_day", "room_utility_night", "room_utility_day"]:
    grid(f"{GFX}/rooms/{r}.png", f"{OUT}/grid_{r}.png")

# 2) зумы
import glob
for z in sorted(glob.glob(f"{GFX}/zooms/*.png")):
    n = os.path.basename(z).replace(".png", "")
    grid(z, f"{OUT}/grid_{n}.png")

# 3) bg_title
grid(f"{GFX}/ui/bg_title.png", f"{OUT}/grid_bg_title.png")

# 4) контакт-листы катаутов (2 листа по 20)
cuts = sorted(glob.glob(f"{GFX}/cutouts/*.png"))
contact_sheet(cuts[:20], f"{OUT}/cutouts_1.png")
contact_sheet(cuts[20:], f"{OUT}/cutouts_2.png")
contact_sheet(sorted(glob.glob(f"{GFX}/icons/*.png")), f"{OUT}/icons_sheet.png")
contact_sheet(sorted(glob.glob(f"{GFX}/portraits/*.png")), f"{OUT}/portraits_sheet.png")
contact_sheet(sorted(glob.glob(f"{GFX}/cursors/*.png")) + sorted(glob.glob(f"{GFX}/ui/*.png")), f"{OUT}/misc_sheet.png")

print("OK", len(os.listdir(OUT)), "files ->", OUT)
