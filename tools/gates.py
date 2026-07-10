#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пиксельные гейты Фазы 4 по скринам гаунтлета (work/shots/ap_*.png).

1) Маджента-гейт: ни одного пикселя R>200 ∧ B>200 ∧ G<80 ни на одном скрине.
2) WCAG-гейт: контраст UI-текста к фактическому фону плашек ≥ 7:1
   (диалог, цели, кнопка титула, легенда стенда, бейдж).
3) Яркость: средняя luma ночных кадров комнат ≥ 0.45 (канон «читаемость
   прежде атмосферы»).
4) Силуэт-гейт: интерактивные зоны ночного вайда A отличимы от окружения
   (дельта средней luma к кольцу вокруг ≥ 0.015 или внутренняя std ≥ 0.02).
"""
import json, glob, sys
import numpy as np
from PIL import Image

ERR = []
def err(m): ERR.append(m)

def luma(rgb):
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(rgb1, rgb2):
    l1, l2 = luma(rgb1), luma(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)

def mean_rgb(img, box):
    x0, y0, x1, y1 = box
    return img[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)

# ---------- 1) маджента ----------
shots = sorted(glob.glob("work/shots/ap_*.png"))
assert len(shots) >= 14, "мало скринов"
for p in shots:
    a = np.array(Image.open(p).convert("RGB")).astype(int)
    m = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 80)
    if m.sum() > 0:
        ys, xs = np.where(m)
        err(f"маджента: {p} ({m.sum()} px, напр. {xs[0]},{ys[0]})")
print(f"[1] маджента: {len(shots)} скринов проверено")

# ---------- 2) WCAG ≥7:1 ----------
TEXT = (237, 232, 219)      # C.text
BADGE_BRASS = (184, 148, 87)
checks = [
    # (скрин, зона фона плашки без текста, цвет текста, метка)
    ("ap_14_hint_badge", (1650, 980, 1850, 1040), TEXT, "диалоговая плашка"),
    ("ap_09_a_night_exit", (232, 140, 258, 240), TEXT, "плашка целей"),
    ("ap_00_title", (790, 566, 860, 584), TEXT, "кнопка титула"),
    ("ap_08_bench_done", (600, 1022, 660, 1052), TEXT, "легенда стенда"),
]
for shot, box, tcol, label in checks:
    p = f"work/shots/{shot}.png"
    a = np.array(Image.open(p).convert("RGB")).astype(float)
    bg = mean_rgb(a, box)
    c = contrast(tcol, bg)
    status = "OK" if c >= 7.0 else "FAIL"
    print(f"[2] {label}: контраст {c:.1f}:1 {status} (фон {bg.astype(int)})")
    if c < 7.0:
        err(f"WCAG: {label} {c:.1f}:1 < 7:1")

# ---------- 3) яркость ночных кадров ----------
# Комната A: канон «читаемость прежде атмосферы», порог 45%.
# Комната B (подсобка): решение автора (раунд 7) — тёмная ночная подсобка;
# гейт 45% ОТКЛЮЧЁН, оставлен мягкий пол 8% (защита от полностью чёрного кадра)
# и предупреждение-репорт. Читаемость зон держит силуэт-гейт [4] ниже.
BRIGHT = [("ap_01_room_a_night", "комната A ночь", 0.45, True),
          ("ap_04_room_b", "комната B ночь (тёмная, раунд 7)", 0.08, False)]
for shot, label, thr, hard in BRIGHT:
    a = np.array(Image.open(f"work/shots/{shot}.png").convert("L")).astype(float)
    mean = a.mean() / 255.0
    status = "OK" if mean >= thr else ("FAIL" if hard else "WARN")
    print(f"[3] {label}: средняя яркость {mean*100:.0f}% (порог {thr*100:.0f}%) {status}")
    if mean < thr and hard:
        err(f"яркость: {label} {mean*100:.0f}% < {thr*100:.0f}%")

# ---------- 4) силуэты интерактива (ночь A и B) ----------
S = json.load(open("design/scene.json", encoding="utf-8"))
HUD = [(0, 0, 1920, 80), (10, 90, 275, 260), (1550, 0, 1920, 60)]
def in_hud(r):
    cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
    return any(hx0 <= cx < hx1 and hy0 <= cy < hy1 for hx0, hy0, hx1, hy1 in HUD)
weak = []
for room_id, shot in (("A", "ap_01_room_a_night"), ("B", "ap_04_room_b")):
  a = np.array(Image.open(f"work/shots/{shot}.png")
               .convert("L")).astype(float) / 255.0
  for h in S["rooms"][room_id]["hotspots"]:
    inter = h.get("node") or h.get("goto") or h.get("doc") or h.get("widget")
    r = h.get("rect")
    if not inter or not r or in_hud(r):
        continue
    x0, y0, w, hh = r
    x1, y1 = min(1920, x0 + w), min(1080, y0 + hh)
    x0, y0 = max(0, x0), max(0, y0)
    zone = a[y0:y1, x0:x1]
    rx0, ry0 = max(0, x0 - 24), max(0, y0 - 24)
    rx1, ry1 = min(1920, x1 + 24), min(1080, y1 + 24)
    ring_full = a[ry0:ry1, rx0:rx1].copy()
    ring_full[y0 - ry0:y1 - ry0, x0 - rx0:x1 - rx0] = np.nan
    ring = ring_full[~np.isnan(ring_full)]
    delta = abs(zone.mean() - ring.mean())
    std = zone.std()
    if delta < 0.015 and std < 0.02:
        weak.append((room_id, h["id"], round(delta, 3), round(std, 3)))
if weak:
    err("силуэты слились: " + str(weak))
print(f"[4] силуэты: слабых зон {len(weak)}")

if ERR:
    print("GATES FAIL:")
    for e in ERR: print(" -", e)
    sys.exit(1)
print("PIXEL GATES PASS")
