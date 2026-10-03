#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пиксельные гейты Фазы 4 по скринам гаунтлета (work/shots/ap_*.png).

0) Якорь (аудит В1): в каждом кадре обязаны присутствовать пиксели ТОЧНЫХ
   цветов движковой палитры. Без якоря все прочие гейты — про свойства
   картинки вообще, и шестнадцать кадров случайного шума с тёмными
   прямоугольниками в замеряемых зонах проходят их насквозь.
1) Маджента-гейт: ни одного пикселя R>200 ∧ B>200 ∧ G<80 ни на одном скрине.
2) WCAG-гейт: контраст UI-текста к фактическому фону плашек ≥ 7:1
   (диалог, цели, кнопка титула, легенда стенда, бейдж). Считается по
   НАРИСОВАННЫМ глифам, а не по гипотетическому тексту: сперва доказывается,
   что глифы в зоне есть (кластер пикселей текстового цвета, плотный по
   разбросу), и лишь потом меряется контраст их фактического цвета к
   фактическому фону.
3) Яркость: средняя luma ночных кадров комнат ≥ 0.45 (канон «читаемость
   прежде атмосферы»).
4) Силуэт-гейт: интерактивные зоны ночного вайда A отличимы от окружения
   (дельта средней luma к кольцу вокруг ≥ 0.015 или внутренняя std ≥ 0.02).
"""
import json, glob, os, sys
import numpy as np
from PIL import Image

ERR = []
def err(m): ERR.append(m)

# Палитра движка (src/ui.lua, local C) в 8-битном виде — эталон якоря.
PALETTE = {
    "brass": (0.72, 0.58, 0.34), "steel": (0.55, 0.70, 0.86),
    "text": (0.93, 0.91, 0.86), "dim": (0.65, 0.63, 0.58),
    "paper_ink": (0.17, 0.14, 0.10), "red_ink": (0.62, 0.10, 0.08),
    "ok": (0.35, 0.8, 0.4), "bad": (0.9, 0.3, 0.25),
}
PAL8 = {k: tuple(int(c * 255) for c in v) for k, v in PALETTE.items()}

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

def anchor_px(a):
    """сколько пикселей кадра лежат ТОЧНО на цветах движковой палитры"""
    m = np.zeros(a.shape[:2], dtype=bool)
    for r, g, b in PAL8.values():
        m |= (a[..., 0] == r) & (a[..., 1] == g) & (a[..., 2] == b)
    return int(m.sum())

# Порог якоря. Движок кладёт UI через love.graphics.setColor фиксированной
# палитрой, поэтому пиксели полного покрытия попадают в ТОЧНЫЕ 8-битные
# тройки. Замер по настоящим кадрам: минимум 2402 (ap_01_room_a_night),
# максимум 17850. Замер по атаке: равномерный шум 1920×1080 даёт 0–1,
# ровная заливка — 0. Порог 800 — втрое ниже худшего настоящего кадра и
# на три порядка выше любого кадра без игры.
ANCHOR_MIN = 800

# ---------- 0) якорь + 1) маджента ----------
shots = sorted(glob.glob("work/shots/ap_*.png"))
if len(shots) < 14:
    sys.exit(f"GATES FAIL: скринов {len(shots)} < 14 — гаунтлет не отработал, "
             f"мерить нечего")
worst = None
for p in shots:
    a = np.array(Image.open(p).convert("RGB")).astype(int)
    n = anchor_px(a)
    if worst is None or n < worst[0]:
        worst = (n, os.path.basename(p))
    if n < ANCHOR_MIN:
        err(f"якорь: {p} — пикселей палитры движка {n} < {ANCHOR_MIN}; "
            f"это не кадр игры, остальные гейты по нему ничего не значат")
    m = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 80)
    if m.sum() > 0:
        ys, xs = np.where(m)
        err(f"маджента: {p} ({m.sum()} px, напр. {xs[0]},{ys[0]})")
print(f"[0] якорь: {len(shots)} кадров, худший {worst[1]} — {worst[0]} px "
      f"палитры (порог {ANCHOR_MIN}, запас {worst[0] / ANCHOR_MIN:.1f}×)")
print(f"[1] маджента: {len(shots)} скринов проверено")

# ---------- 2) WCAG ≥7:1 по НАРИСОВАННЫМ глифам ----------
# Раньше здесь брался средний цвет пустого прямоугольника рядом с текстом и
# сравнивался с КОНСТАНТОЙ цвета текста. Такой гейт зелен на любом кадре, где
# в нужном месте достаточно темно, — текста там может не быть вовсе. Теперь
# порядок обратный: сперва доказывается, что глифы нарисованы, потом меряется
# контраст их ФАКТИЧЕСКОГО цвета к ФАКТИЧЕСКОМУ фону вокруг них.
TEXT = PAL8["text"]         # C.text
TEXT_L1 = 40                # радиус L1-шара вокруг цвета текста
GLYPH_MIN = 100             # столько пикселей глифов обязано найтись в зоне
GLYPH_STD = 8.0             # плотность кластера: у настоящих глифов разброс
                            # 0.7–4.6, у шума ~12.8–14.1 (шум заполняет шар
                            # равномерно, буквы — нет)
checks = [
    # (скрин, зона плашки ЦЕЛИКОМ — вместе с текстом, метка)
    ("ap_14_hint_badge", (100, 830, 1850, 935), "диалоговая плашка"),
    ("ap_09_a_night_exit", (30, 140, 232, 250), "плашка целей"),
    ("ap_00_title", (700, 548, 1220, 620), "кнопка титула"),
    ("ap_08_bench_done", (100, 1008, 1800, 1070), "легенда стенда"),
]
for shot, box, label in checks:
    p = f"work/shots/{shot}.png"
    a = np.array(Image.open(p).convert("RGB")).astype(float)
    x0, y0, x1, y1 = box
    px = a[y0:y1, x0:x1].reshape(-1, 3)
    d = np.abs(px - np.array(TEXT, dtype=float)).sum(axis=1)
    glyph, back = px[d < TEXT_L1], px[d >= TEXT_L1]
    if len(glyph) < GLYPH_MIN or len(back) < GLYPH_MIN:
        err(f"WCAG: {label} — глифов в зоне нет ({len(glyph)} px), "
            f"мерить контраст не к чему")
        print(f"[2] {label}: ГЛИФОВ НЕТ ({len(glyph)} px < {GLYPH_MIN}) FAIL")
        continue
    std = float(glyph.std(axis=0).max())
    if std > GLYPH_STD:
        err(f"WCAG: {label} — кластер «текстового» цвета рыхлый "
            f"(разброс {std:.1f} > {GLYPH_STD}), это не глифы, а шум")
        print(f"[2] {label}: КЛАСТЕР РЫХЛЫЙ (разброс {std:.1f}) FAIL")
        continue
    fg = glyph.mean(axis=0)
    bg = np.median(back, axis=0)
    c = contrast(fg, bg)
    status = "OK" if c >= 7.0 else "FAIL"
    print(f"[2] {label}: контраст {c:.1f}:1 {status} "
          f"(глифов {len(glyph)} px, разброс {std:.1f}, "
          f"текст {fg.astype(int)} на фоне {bg.astype(int)})")
    if c < 7.0:
        err(f"WCAG: {label} {c:.1f}:1 < 7:1")

# ---------- 3) яркость ночных кадров ----------
# Комната A: канон «читаемость прежде атмосферы», порог 45%.
# Комната B (подсобка): решение автора (раунд 7) — тёмная ночная подсобка;
# гейт 45% ОТКЛЮЧЁН, оставлен низкий пол 8% (защита от полностью чёрного
# кадра). Читаемость зон держит силуэт-гейт [4] ниже. (р.24) Пол стоял с
# hard=False — печатал WARN и упасть не мог, то есть не защищал ни от чего;
# теперь он блокирующий, негатив — в tools/test_negatives.py.
BRIGHT = [("ap_01_room_a_night", "комната A ночь", 0.45, True),
          ("ap_04_room_b", "комната B ночь (тёмная, раунд 7)", 0.08, True)]
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
