#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Раунд 7, замечание 5: нанести читаемые метки на кнопки СТАТИЧНОГО арта
кейпада тумбы (zoom_drawer_keypad.png) — раскладка как в движковом виджете
(1..9 / C 0 OK). Интерактивный ввод кода идёт через виджет (там цифры уже есть).
Оригинал без цифр -> work/orig_zoom_drawer_keypad_nodigits.png.
"""
from PIL import Image, ImageDraw, ImageFont
im=Image.open('work/orig_zoom_drawer_keypad_nodigits.png').convert('RGBA')
d=ImageDraw.Draw(im)
cols=[743,794,844]; rows=[444,494,540,589]  # р8: перепромер центров кнопок
labels=[["1","2","3"],["4","5","6"],["7","8","9"],["C","0","OK"]]
def fnt(sz): return ImageFont.truetype('assets/fonts/PTSans-Bold.ttf',sz)
for ri,row in enumerate(rows):
    for ci,col in enumerate(cols):
        lab=labels[ri][ci]; sz=26 if len(lab)==1 else 20
        f=fnt(sz)
        bb=d.textbbox((0,0),lab,font=f); w=bb[2]-bb[0]; h=bb[3]-bb[1]
        x=col-w/2-bb[0]; y=row-h/2-bb[1]
        # лёгкая светлая подложка-тень для читаемости на сером
        d.text((x+1,y+1),lab,font=f,fill=(210,210,205,150))
        d.text((x,y),lab,font=f,fill=(38,38,44,255))
im.convert('RGBA').save('assets/gfx/zooms/zoom_drawer_keypad.png')
print("digits drawn on keypad art")
