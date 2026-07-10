#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Раунд 7, замечание 8: ПРОЦЕДУРНАЯ гирлянда по силуэту ёлки.
Маска зелени ёлки (numpy) -> провисающие нити (катенары) по ширине маски на
разных высотах + лампочки-кружки с тёплым glow, обрезка по маске ёлки.
Два файла: st_garland_on.png (ночь, ярче glow) и st_garland_on_day.png (день,
бледнее). Оригинал -> work/orig_st_garland_on_v0.png.
Катаут кладётся pos=[TREE_X0,TREE_Y0] scale=1.0 (см. печать координат).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import math, random

RM='assets/gfx/rooms/'; CO='assets/gfx/cutouts/'
random.seed(20190101)

# --- маска зелени ёлки по НОЧНОМУ фону (силуэт одинаков день/ночь) ---
bg=np.array(Image.open(RM+'room_office_night.png').convert('RGB')).astype(int)
X0,Y0,X1,Y1=360,150,650,620
reg=bg[Y0:Y1,X0:X1]
r,g,b=reg[...,0],reg[...,1],reg[...,2]
mask=(g>55)&(g>=r-4)&(g>=b-2)&((g.astype(int)-b)>-25)
# морфология: закрыть дырки
from scipy import ndimage
mask=ndimage.binary_closing(mask,iterations=3)
mask=ndimage.binary_opening(mask,iterations=2)
# крупнейшая компонента
lbl,n=ndimage.label(mask); 
if n>1:
    sizes=ndimage.sum(mask,lbl,range(1,n+1)); mask=(lbl==(1+np.argmax(sizes)))
ys,xs=np.where(mask)
mh,mw=mask.shape
print("tree mask bbox local:",xs.min(),ys.min(),xs.max(),ys.max(),"canvas",mw,mh)
print("PLACE pos=[%d,%d] scale=1.0"%(X0,Y0))

def build(night=True):
    W,H=mw,mh
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    glow=Image.new('RGBA',(W,H),(0,0,0,0))
    d=ImageDraw.Draw(layer); dg=ImageDraw.Draw(glow)
    # цвета лампочек (тёплые)
    cols=[(255,120,90),(255,210,110),(255,240,200),(150,220,255),(255,160,120)]
    # р8: дневная гирлянда заметно ярче (читается в полнокадровом масштабе),
    #     но всё же бледнее ночной
    wire=(210,205,190,150) if night else (200,193,178,175)
    # уровни нитей по высоте ёлки (доля высоты маски)
    for frac in [0.30,0.42,0.55,0.68,0.82]:
        yy=int(mh*frac)
        row=np.where(mask[yy])[0]
        if len(row)<10: continue
        lx,rx=row.min()+4,row.max()-4
        if rx-lx<20: continue
        sag=int((rx-lx)*0.12)+6
        pts=[]
        N=40
        for i in range(N+1):
            t=i/N; x=lx+(rx-lx)*t
            # катенара (парабола) + лёгкая случайная волна
            y=yy+sag*math.sin(math.pi*t)+math.sin(t*9+frac*7)*2
            pts.append((x,y))
        # нить рисуем только там, где маска (обрезка по ёлке)
        for i in range(len(pts)-1):
            x0,y0=pts[i]; x1,y1=pts[i+1]
            mx,my=int((x0+x1)/2),int((y0+y1)/2)
            if 0<=my<mh and 0<=mx<mw and mask[my,mx]:
                d.line([x0,y0,x1,y1],fill=wire,width=2)
        # лампочки вдоль нити
        nb=max(5,int((rx-lx)/34))
        for k in range(nb):
            t=(k+0.5)/nb; x=lx+(rx-lx)*t
            y=yy+sag*math.sin(math.pi*t)+math.sin(t*9+frac*7)*2+3
            xi,yi=int(x),int(y)
            if not(0<=yi<mh and 0<=xi<mw and mask[min(yi,mh-1),xi]): continue
            col=cols[(k+int(frac*10))%len(cols)]
            gr=11 if night else 10
            dg.ellipse([x-gr,y-gr,x+gr,y+gr],fill=(col[0],col[1],col[2],115 if night else 100))
            cr=4 if night else 5
            cb=30 if night else 48
            d.ellipse([x-cr,y-cr,x+cr,y+cr],fill=(min(255,col[0]+cb),min(255,col[1]+cb),min(255,col[2]+cb),255))
            d.ellipse([x-1.5,y-1.5,x+1.5,y+1.5],fill=(255,255,245,255))
    glow=glow.filter(ImageFilter.GaussianBlur(5 if night else 5))
    out=Image.alpha_composite(glow,layer)
    # финальная обрезка по маске (нити/glow только на ёлке; лампочкам даём +2px)
    md=ndimage.binary_dilation(mask,iterations=3)
    arr=np.array(out); arr[...,3]=np.where(md,arr[...,3],0)
    return Image.fromarray(arr,'RGBA')

build(True).save(CO+'st_garland_on.png')
build(False).save(CO+'st_garland_on_day.png')
print("saved st_garland_on.png (ночь) + st_garland_on_day.png (день)")
