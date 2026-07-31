#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify-листы: арт + катауты + рамки зон для ВСЕХ видов игры.

Раунд 19, замечание автора: «зоны кодовой панели и ящичка Иры смещены влево.
Вообще смещение зон на зумах — общая проблема». Дефект жил долго ровно потому,
что этот генератор рисовал ТРИ вида комнат и НИ ОДНОГО зума: смотреть было
не на что. Теперь рисуются все виды (A/B × ночь/день + все зумы), каждый
отдельным файлом в work/verify/ плюс два контактных листа.

Что на листе:
  • фон вида, поверх — все катауты (включая взаимоисключающие) с альфой 0.75,
    чтобы зона и арт под ней читались одновременно;
  • рамки зон, отсортированные по площади ПО ВОЗРАСТАНИЮ — тем же порядком,
    что и хит-лист движка, поэтому мелкая зона рисуется поверх крупной и
    видно, кто кого перехватывает;
  • подписи id на чёрных плашках, цвет рамки = цвет подписи;
  • для рядов-виджетов (автоматы) — внутренние границы слотов пунктиром;
  • стрелки переходов (комнаты) — зелёным, светодиоды — белыми кольцами.

Гейт «катаут без зоны»: доля НЕПРОЗРАЧНЫХ пикселей катаута, накрытая
объединением зон вида. Порог 50 %. Смысл: если на виде нарисован предмет,
а зоны на нём нет (или она уехала), игрок видит вещь и не может её тронуть.
Проверено на текущем дереве: худший катаут 64 %, ниже 50 % — ноль.

Сознательно НЕ добавлен гейт «плоской зоны» (зона на пустом арте): калибровка
показала, что старая дневная рамка hs_poster_ot (std=31.6, град=2.9) не выброс
на фоне корпуса (медиана std=35.6, град=6.7) — то есть настоящий дефект раунда
19 он бы не поймал, а шума дал бы вдоволь. Тот промах был смысловым (в игре
ничто не говорило, что на листе легенда) и лечится текстом, а не пикселями.
Проверка силуэтов зон по комнатам живёт в validate_scene.py (GATE2).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

G = "assets/gfx/"
OUT = "work/verify"
W, H = 1920, 1080
COVER_MIN = 0.50          # доля катаута под зонами
ALPHA_OPAQUE = 32         # порог «пиксель непрозрачен»
CUT_ALPHA = 0.75          # прозрачность катаутов на листе

# Палитра рамок: соседние по площади зоны обязаны различаться цветом.
PAL = [(255, 60, 60), (60, 255, 120), (80, 160, 255), (255, 220, 40),
       (255, 120, 255), (0, 230, 230), (255, 150, 60), (180, 120, 255),
       (120, 255, 220), (255, 90, 150), (150, 220, 90), (240, 240, 240)]
ARROW_C = (0, 255, 120)

S = json.load(open("design/scene.json", encoding="utf-8"))
F_LAB = ImageFont.truetype("assets/fonts/PTSans-Bold.ttf", 24)
F_TIT = ImageFont.truetype("assets/fonts/PTSans-Bold.ttf", 34)

_IMG = {}


def load(rel):
    """Катауты повторяются (шесть автоматов — одна картинка), читаем однажды."""
    if rel not in _IMG:
        _IMG[rel] = Image.open(G + rel).convert("RGBA")
    return _IMG[rel]


def views():
    """Все виды одним списком: комнаты в двух состояниях света + зумы."""
    out = []
    for rid, r in S["rooms"].items():
        for mode in ("night", "day"):
            art = (r.get("bg") or {}).get(mode)
            if not art:
                continue
            out.append(dict(vid=f"room_{rid}_{mode}", kind="room", day=(mode == "day"),
                            bg=art, cutouts=r.get("cutouts", []),
                            hotspots=r.get("hotspots", []), arrows=r.get("arrows", []),
                            led={}, title=f"КОМНАТА {rid} — {r.get('name', '')} "
                                          f"({'ДЕНЬ' if mode == 'day' else 'НОЧЬ'})"))
    for zid, z in S["zooms"].items():
        # дневных вариантов у зумов в данных нет — на вид по одному листу
        out.append(dict(vid=zid, kind="zoom", day=False, bg=z["bg"],
                        cutouts=z.get("cutouts", []), hotspots=z.get("hotspots", []),
                        arrows=[], led=z.get("led") or {},
                        title=f"ЗУМ {zid} (комната {z.get('room', '?')})"))
    return out


def rect_of(h, day):
    return h.get("rect_day") if (day and h.get("rect_day")) else h["rect"]


def compose(v):
    """Фон + катауты. Возвращает лист и геометрию катаутов для гейта."""
    sheet = load(v["bg"]).copy()
    geom = []
    for c in v["cutouts"]:
        rel = c.get("img_day") if (v["day"] and c.get("img_day")) else c["img"]
        pos = c.get("pos_day") if (v["day"] and c.get("pos_day")) else c["pos"]
        try:
            im = load(rel)
        except Exception as e:                       # noqa: BLE001
            print(f"  !! {v['vid']}: катаут {rel} не читается ({e})")
            geom.append((rel, (int(pos[0]), int(pos[1])), None))
            continue
        sc = float(c.get("scale", 1.0))
        if sc != 1.0:
            im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))),
                           Image.LANCZOS)
        alpha = np.asarray(im.split()[3], dtype=np.uint8)
        soft = im.copy()
        soft.putalpha(im.split()[3].point(lambda q: int(q * CUT_ALPHA)))
        sheet.alpha_composite(soft, (int(pos[0]), int(pos[1])))
        geom.append((rel, (int(pos[0]), int(pos[1])), alpha))
    return sheet, geom


def plate(d, x, y, text, col):
    """Подпись на чёрной плашке — иначе жёлтое по латуни не читается."""
    tw = int(d.textlength(text, font=F_LAB))
    px, py = max(0, min(x, W - tw - 14)), max(0, min(y, H - 32))
    d.rectangle([px, py, px + tw + 12, py + 30], fill=(0, 0, 0, 205))
    d.text((px + 6, py + 2), text, font=F_LAB, fill=col)


def draw_zones(sheet, v):
    d = ImageDraw.Draw(sheet, "RGBA")
    # порядок = порядок хит-листа движка: меньшая площадь ближе к игроку
    hs = sorted(v["hotspots"],
                key=lambda q: rect_of(q, v["day"])[2] * rect_of(q, v["day"])[3])
    for i, h in enumerate(hs):
        x, y, w, hh = rect_of(h, v["day"])
        col = PAL[i % len(PAL)]
        d.rectangle([x, y, x + w - 1, y + hh - 1], outline=col, width=4)
        # внутренние границы слотов ряда-виджета (автоматы): смещение
        # breaker_x0/breaker_step на глаз иначе не поймать
        if h.get("breaker_step"):
            x0, st = float(h["breaker_x0"]), float(h["breaker_step"])
            for k in range(1, len(h.get("breaker_map", []))):
                sx = int(round(x0 + st * k))
                for yy in range(y + 4, y + hh - 4, 14):
                    d.line([sx, yy, sx, yy + 7], fill=col, width=2)
        tag = h["id"].replace("hs_z_", "").replace("hs_", "")
        plate(d, x + 2, y - 32 if y >= 34 else y + 3, tag, col)
    for a in v["arrows"]:
        x, y, w, hh = a["rect"]
        d.rectangle([x, y, x + w - 1, y + hh - 1], outline=ARROW_C, width=4)
        # без «→»: в PTSans-Bold этого символа нет, плашка выходила квадратом
        plate(d, x + 2, y - 32 if y >= 34 else y + 3,
              "переход " + str(a.get("goto_room", "?")), ARROW_C)
    for k, p in v["led"].items():
        d.ellipse([p[0] - 14, p[1] - 14, p[0] + 14, p[1] + 14],
                  outline=(255, 255, 255), width=3)
        plate(d, p[0] + 18, p[1] - 15, "led:" + k, (255, 255, 255))
    d.rectangle([0, 0, W, 46], fill=(0, 0, 0, 190))
    d.text((14, 6), f"{v['title']}   зон {len(v['hotspots'])} · "
                    f"катаутов {len(v['cutouts'])}", font=F_TIT, fill=(255, 220, 120))
    return sheet


def zone_mask(v):
    m = np.zeros((H, W), dtype=bool)
    for h in v["hotspots"]:
        x, y, w, hh = rect_of(h, v["day"])
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + hh)
        if x1 > x0 and y1 > y0:
            m[y0:y1, x0:x1] = True
    return m


def coverage(v, geom):
    """Доля непрозрачных пикселей катаута под объединением зон вида."""
    m = zone_mask(v)
    out = []
    for rel, pos, alpha in geom:
        if alpha is None:
            continue
        x0, y0 = pos
        ah, aw = alpha.shape
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x0 + aw), min(H, y0 + ah)
        if cx1 <= cx0 or cy1 <= cy0:
            out.append((0.0, rel, pos, 0))
            continue
        sub = alpha[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] > ALPHA_OPAQUE
        n = int(sub.sum())
        if n == 0:
            continue                                  # полностью прозрачный — не наш случай
        hit = int((sub & m[cy0:cy1, cx0:cx1]).sum())
        out.append((hit / n, rel, pos, n))
    return out


def contact(imgs, cols, cell, path):
    rows = max(1, (len(imgs) + cols - 1) // cols)
    sh = Image.new("RGB", (cols * cell[0], rows * cell[1]), (18, 18, 22))
    for i, im in enumerate(imgs):
        sh.paste(im.convert("RGB").resize(cell, Image.LANCZOS),
                 ((i % cols) * cell[0], (i // cols) * cell[1]))
    sh.save(path)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    rooms, zooms, cov, errs = [], [], [], []
    for v in views():
        sheet, geom = compose(v)
        draw_zones(sheet, v)
        p = f"{OUT}/{v['vid']}.png"
        sheet.convert("RGB").save(p)
        (rooms if v["kind"] == "room" else zooms).append(sheet)
        for h in v["hotspots"]:
            x, y, w, hh = rect_of(h, v["day"])
            if x < 0 or y < 0 or x + w > W or y + hh > H:
                errs.append(f"{v['vid']}/{h['id']}: зона вне канваса {[x, y, w, hh]}")
        for frac, rel, pos, n in coverage(v, geom):
            cov.append((frac, v["vid"], rel, pos, n))
        print(f"  {p}  зон {len(v['hotspots'])} · катаутов {len(v['cutouts'])}")

    contact(rooms, 2, (960, 540), "work/verify_all.png")     # имя из MIGRATION.md
    contact(rooms, 2, (960, 540), f"{OUT}/_rooms.png")
    contact(zooms, 4, (640, 360), f"{OUT}/_zooms.png")

    cov.sort()
    print(f"\nвидов {len(rooms) + len(zooms)} (комнат {len(rooms)}, зумов {len(zooms)}) "
          f"→ {OUT}/, контакт-листы _rooms.png / _zooms.png и work/verify_all.png")
    print(f"\nпокрытие катаутов зонами (порог {COVER_MIN:.0%}), худшие:")
    for frac, vid, rel, pos, n in cov[:8]:
        print(f"  {frac * 100:5.1f}%  {vid:<20} {os.path.basename(rel):<28} "
              f"@{pos[0]},{pos[1]}  ({n} px)")
    bad = [c for c in cov if c[0] < COVER_MIN]
    for frac, vid, rel, pos, n in bad:
        errs.append(f"{vid}: катаут {os.path.basename(rel)} @{pos[0]},{pos[1]} "
                    f"накрыт зонами на {frac * 100:.0f}% (< {COVER_MIN:.0%}) — "
                    f"предмет видно, а тронуть нельзя")
    print(f"катаутов проверено {len(cov)}, ниже порога {len(bad)}")
    if errs:
        print("\nVERIFY SHEETS FAIL:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print("VERIFY SHEETS PASS (смотреть глазами — урок №7, docs/LESSONS.md)")


if __name__ == "__main__":
    main()
