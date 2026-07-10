#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Раунд 9: катауты из авторского арта.
1) Коробка «НГ-2019» (антресоль): кроп авторского box_attic по альфе +
   edge-bleed (заливка цвета в прозрачные соседи, чтобы при масштабировании
   не тянулся красный мат подложки) -> cutouts/st_box_attic.png.
2) Швабра: удлинение черенка ~x2 вставкой чистого сегмента черенка между
   бирко-ручкой и щёткой (щётку и крюк не искажаем) -> cutouts/st_mop_on_hook.png.
Оригиналы уже в карантине: work/orig_box_attic_v2.png, work/orig_st_mop_on_hook_v0.png.
"""
import numpy as np
from PIL import Image
import os

CUT = "assets/gfx/cutouts"

def edge_bleed(im, iters=6):
    """RGB прозрачных пикселей = среднее непрозрачных соседей (итеративно).
    Убирает цветовую бахрому по краю при билинейном масштабировании."""
    a = np.array(im).astype(np.float32)
    rgb = a[:, :, :3]; al = a[:, :, 3]
    known = al > 8
    for _ in range(iters):
        unk = ~known
        if not unk.any():
            break
        # суммируем соседей по 4 сторонам
        s = np.zeros_like(rgb); c = np.zeros(al.shape, np.float32)
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            k = np.roll(known, (dy, dx), (0,1))
            v = np.roll(rgb, (dy, dx), (0,1))
            m = k & unk
            s[m] += v[m]; c[m] += 1
        fill = c > 0
        rgb[fill] = s[fill] / c[fill][:, None]
        known = known | fill
    a[:, :, :3] = rgb
    return Image.fromarray(a.astype(np.uint8), "RGBA")

def gen_box():
    im = Image.open("work/orig_box_attic_v2.png").convert("RGBA")
    a = np.array(im); al = a[:, :, 3]
    ys, xs = np.where(al > 16)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    m = 3
    x0 = max(0, x0-m); y0 = max(0, y0-m)
    x1 = min(im.width-1, x1+m); y1 = min(im.height-1, y1+m)
    crop = im.crop((x0, y0, x1+1, y1+1))
    crop = edge_bleed(crop, iters=6)
    crop.save(os.path.join(CUT, "st_box_attic.png"))
    print("st_box_attic.png", crop.size)

def gen_mop():
    im = Image.open("work/orig_st_mop_on_hook_v0.png").convert("RGBA")
    W, H = im.size                       # 220x420
    INSERT = 95                          # удлинение черенка (~x2 видимой ручки)
    SEAM = 229                           # низ ручки/бирки, верх щётки ~230
    # экструзия ОДНОЙ чистой строки черенка (y226, ниже бирки) — гладко, без
    # бандинга (тайлинг многострочного среза размножал вертикальную тень стержня)
    row = im.crop((0, 226, W, 227))      # 1 строка чистого стержня
    upper = im.crop((0, 0, W, SEAM+1))   # крюк+ручка+бирка
    head = im.crop((0, 230, W, H))       # щётка (+пустой низ)
    new = Image.new("RGBA", (W, H+INSERT), (0,0,0,0))
    new.paste(upper, (0, 0), upper)
    end = SEAM+1+INSERT
    for y in range(SEAM+1, end):
        new.paste(row, (0, y), row)
    new.paste(head, (0, end), head)
    # обрезка пустых вертикальных полей (чтобы pos в сцене был положительным)
    aa = np.array(new)[:, :, 3]
    ys, xs = np.where(aa > 8)
    top = max(0, ys.min()-3); bot = min(new.height, ys.max()+4)
    new = new.crop((0, top, new.width, bot))
    new.save(os.path.join(CUT, "st_mop_on_hook.png"))
    # промер новой геометрии
    a = np.array(new)[:, :, 3]
    ys, xs = np.where(a > 16)
    print("st_mop_on_hook.png", new.size, "content y%d..%d" % (ys.min(), ys.max()))

if __name__ == "__main__":
    gen_box()
    gen_mop()
