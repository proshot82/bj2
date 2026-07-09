#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify-листы: арт + катауты + рамки зон (A ночь/день, B) -> work/verify_all.png.
Смотреть глазами перед релизом (урок №7, docs/LESSONS.md)."""
import json
from PIL import Image, ImageDraw, ImageFont
s = json.load(open('design/scene.json'))
f = ImageFont.truetype('assets/fonts/PTSans-Bold.ttf', 26)
def render(room, mode, art_name):
    art = Image.open('assets/gfx/rooms/' + art_name).convert('RGBA')
    for c in s['rooms'][room]['cutouts']:
        im = Image.open('assets/gfx/' + c['img']).convert('RGBA')
        sc = c.get('scale', 1.0)
        pos = c.get('pos_day') if (mode == 'day' and c.get('pos_day')) else c['pos']
        if sc != 1.0:
            im = im.resize((round(im.width*sc), round(im.height*sc)), Image.LANCZOS)
        art.alpha_composite(im, tuple(pos))
    d = ImageDraw.Draw(art)
    for h in s['rooms'][room]['hotspots']:
        r = h.get('rect_day') if (mode == 'day' and h.get('rect_day')) else h['rect']
        d.rectangle([r[0], r[1], r[0]+r[2], r[1]+r[3]], outline=(255,60,60,255), width=4)
        d.text((r[0]+4, r[1]+2), h['id'][3:], fill=(255,255,0,255), font=f)
    for a in s['rooms'][room].get('arrows', []):
        r = a['rect']; d.rectangle([r[0],r[1],r[0]+r[2],r[1]+r[3]], outline=(0,255,120,255), width=4)
    return art.convert('RGB')
imgs = [render('A','night','room_office_night.png'),
        render('A','day','room_office_day.png'),
        render('B','night','room_utility_night.png')]
sheet = Image.new('RGB', (1920, 1080*3))
for i, im in enumerate(imgs): sheet.paste(im, (0, 1080*i))
sheet.save('work/verify_all.png')
print('work/verify_all.png готов (3 вида)')
