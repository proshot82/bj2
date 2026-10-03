#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Раунд 10: нарезка авторского LED-грида (leds_grid.png) в 5 катаутов
и кроп дневной сирены (siren_day.png).

Раскладка грида (ПРОВЕРЕНА ГЛАЗАМИ, генераторы врут — и соврали про нижний
ряд: 3-я ячейка НЕ пустая, там чёрный погашенный купол, он не нужен):
  ряд0: серый-off · КРАСНЫЙ-горит · зелёный-горит   (считыватель)
  ряд1: янтарный · тревожный оранжево-красный · чёрный-off(лишний)  (сигнализация)

Метод: центры кнопок промерены центроидом плотного тела (alpha>190) в окне
вокруг приближённых центров; гало горящих кнопок симметрично — центр не сносит.
Кроп РАВНЫМ боксом (единый физический размер кнопки для всех состояний, иначе
кнопка «сжимается» при свечении: reader off->red->green — одна кнопка), масштаб
к 60x60 под существующие катауты (круглая кнопка ~40px в кадре).

Сирена: кроп по плотной альфе (коробка), мягкое серое гало отброшено.
"""
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CO = os.path.join(ROOT, "assets/gfx/cutouts")
GRID = os.path.join(ROOT, "work/orig_leds_grid.png")
SIREN = os.path.join(ROOT, "work/orig_siren_day.png")

APPROX = {
    "r0c0": (563, 390), "r0c1": (766, 399), "r0c2": (959, 391),
    "r1c0": (561, 605), "r1c1": (766, 608),
}
CELL_TO_CUT = {
    "r0c0": "st_led_reader_off",
    "r0c1": "st_led_reader_red",
    "r0c2": "st_led_reader_green",
    "r1c0": "st_led_alarm_off",
    "r1c1": "st_led_alarm_on",
}
BOX = 222
OUT = 60


def refine_center(al, cx, cy, r=88):
    x0, x1, y0, y1 = cx - r, cx + r, cy - r, cy + r
    sub = al[y0:y1, x0:x1]
    ys, xs = np.where(sub > 190)
    if len(xs) < 50:
        ys, xs = np.where(sub > 60)
    return int(x0 + xs.mean()), int(y0 + ys.mean())


def slice_leds():
    im = Image.open(GRID).convert("RGBA")
    al = np.array(im)[:, :, 3]
    half = BOX // 2
    report = []
    for cell, (ax, ay) in APPROX.items():
        cx, cy = refine_center(al, ax, ay)
        crop = im.crop((cx - half, cy - half, cx + half, cy + half))
        crop = crop.resize((OUT, OUT), Image.LANCZOS)
        a2 = np.array(crop)[:, :, 3]
        ys, xs = np.where(a2 > 24)
        name = CELL_TO_CUT[cell]
        crop.save(os.path.join(CO, name + ".png"))
        rgb = np.array(crop)[:, :, :3][a2 > 200]
        mc = rgb.mean(axis=0) if len(rgb) else np.zeros(3)
        report.append((name, cell, (cx, cy),
                       (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                       tuple(int(v) for v in mc)))
    return report


def crop_siren():
    im = Image.open(SIREN).convert("RGBA")
    al = np.array(im)[:, :, 3]
    ys, xs = np.where(al > 96)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    pad = 4
    box = im.crop((max(0, x0 - pad), max(0, y0 - pad),
                   min(im.width, x1 + pad + 1), min(im.height, y1 + pad + 1)))
    arr = np.array(box)
    arr[:, :, 3] = np.where(arr[:, :, 3] < 20, 0, arr[:, :, 3])
    box = Image.fromarray(arr, "RGBA")
    box.save(os.path.join(CO, "st_siren_day.png"))
    bw, bh = box.size
    q = arr[: int(bh * 0.42), int(bw * 0.55):]
    L = q[:, :, :3].mean(axis=2) * (q[:, :, 3] > 128)
    yy, xx = np.where(L > L.max() * 0.82)
    lamp_rx = (int(bw * 0.55) + xx.mean()) / bw
    lamp_ry = (yy.mean()) / bh
    return (bw, bh), (lamp_rx, lamp_ry)


if __name__ == "__main__":
    print("=== LED катауты (равный бокс %d -> %dx%d) ===" % (BOX, OUT, OUT))
    for name, cell, ctr, bb, mc in slice_leds():
        w, h = bb[2] - bb[0] + 1, bb[3] - bb[1] + 1
        print("  %-22s <- %s центр%s  видимо %dx%d  ядроRGB%s"
              % (name, cell, ctr, w, h, mc))
    # (р.24) Дневная сирена снята релизом 2.0.5 (карантин work/orig_release205/):
    # селфтест main.lua роняет сборку на любом лишнем файле в assets/, и
    # повторный прогон рецепта воскрешал бы st_siren_day.png. Кроп оставлен
    # для истории и вызывается только явно: --siren (пишет в work/, не в assets/).
    import sys
    if "--siren" in sys.argv:
        CO = os.path.join(ROOT, "work")
        size, lamp = crop_siren()
        print("=== Сирена → work/st_siren_day.png (в игру не идёт) ===")
        print("  кроп коробки %dx%d; лампа-купол отн.(%.3f,%.3f)"
              % (size[0], size[1], lamp[0], lamp[1]))
