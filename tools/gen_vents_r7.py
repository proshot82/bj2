#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Раунд 7, замечание 4: открытые вентрешётки — цветокоррекция под фон
(moment-matching mean+std непрозрачных пикселей под область ЗАКРЫТОЙ решётки
фона) + вертикальное сжатие офисной (высота ×0.75). Ночь/день варианты (img_day).
ИСХОДНИК всегда — карантинные оригиналы work/orig_st_vent_open_*_v0.png.
"""
import numpy as np
from PIL import Image
CO='assets/gfx/cutouts/'; RM='assets/gfx/rooms/'
def bg_stats(fn,box):
    a=np.array(Image.open(RM+fn).convert('RGB')).astype(float); x0,y0,x1,y1=box
    s=a[y0:y1,x0:x1].reshape(-1,3); return s.mean(0),s.std(0)
def transfer(src,box_fn,box,strength,vsquash,dst):
    tgt_m,tgt_s=bg_stats(box_fn,box)
    im=Image.open(src).convert('RGBA'); a=np.array(im).astype(float); m=a[...,3]>20
    for c in range(3):
        ch=a[...,c][m]; cm=ch.mean(); cs=ch.std()+1e-3
        new=(ch-cm)*(tgt_s[c]/cs)+tgt_m[c]; a[...,c][m]=np.clip(ch*(1-strength)+new*strength,0,255)
    out=Image.fromarray(a.astype('uint8'),'RGBA')
    if vsquash: w,h=out.size; out=out.resize((w,int(round(h*vsquash))),Image.LANCZOS)
    out.save(CO+dst); nt=np.array(out)[np.array(out)[...,3]>40][:,:3]
    print(f"  {dst} {out.size} mean={nt.mean(0).astype(int)}")
OG='work/orig_st_vent_open_office_v0.png'; OU='work/orig_st_vent_open_util_v0.png'
GB=(1262,145,1397,205); UB=(1390,55,1560,185)
transfer(OG,'room_office_night.png',GB,0.85,0.75,'st_vent_open_office.png')
transfer(OG,'room_office_day.png',  GB,0.85,0.75,'st_vent_open_office_day.png')
transfer(OU,'room_utility_night.png',UB,0.80,None,'st_vent_open_util.png')
transfer(OU,'room_utility_day.png',  UB,0.85,None,'st_vent_open_util_day.png')
