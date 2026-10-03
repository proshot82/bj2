#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Гейт шрифтов: каждый символ игрового текста обязан рисоваться всеми
шрифтами сборки. Иначе на экране квадрат-тофу вместо буквы.

Зачем. Раунд 19 вскрыл сразу шесть таких дыр, и все они жили молча:
  • «🗎» и «⚿» на рабочем столе Иры — с раунда 4;
  • «✓» у каждой закрытой цели и «▸» на свёрнутой плашке целей;
  • «→»/«←» — подпись дверного перехода, то есть тофу при наведении на дверь;
  • «🤦» в чате отдела и «ト» в караоке-списке.
Ни один существующий гейт этого не ловил: движок молча рисует .notdef, а
скриншот-проверки смотрели на портреты, не на глифы.

Как проверяем. Не по cmap (лишняя зависимость), а тем же способом, каким
рисует движок: PIL/FreeType отдаёт битмап символа, и он побайтно сравнивается
с битмапом заведомо отсутствующего символа из области частного использования.
Совпало — значит рисуется .notdef, значит на экране квадрат.

Почему «во всех шрифтах», а не «в том, которым рисуют». Статически связать
строку со шрифтом нельзя: одна и та же реплика уходит и в диалог (PTSans), и
в бумагу с рукописной страницей (Neucha). Символ, живущий в одном шрифте из
трёх, — мина замедленного действия. Дешевле держать общий знаменатель.

Источники текста: design/texts.json и design/scene.json (р.24: имена зон,
подписи щитка, бирки вентилей) целиком плюс строковые литералы Lua.
src/autoplay.lua исключён сознательно — это тестовый стенд, его сообщения
уходят в консоль (там «≠» законен), на экран не попадают.
"""
import glob
import json
import os
import re
import sys

from PIL import ImageFont

FONTS = sorted(glob.glob("assets/fonts/*.ttf"))
LUA_SKIP = {"src/autoplay.lua"}          # только консоль, см. шапку
ALLOW = set()                            # осознанно разрешённые исключения — нет
PROBE = "\ue000"                          # частная область: .notdef гарантирован
CANARY = "\U0001f926"                    # заведомо отсутствует во всех трёх
SIZE = 40
# PROBE и CANARY записаны escape-последовательностями намеренно: невидимый
# символ прямо в исходнике редактор молча съедает, PROBE превращается в
# пустую строку, маска — в нулевую, и гейт начинает пропускать ВСЁ. Ровно
# так он однажды и «прошёл» при отладке, поэтому ниже стоит самопроверка
# канарейкой: детектор обязан увидеть заведомо отсутствующий символ.


def draw_key(font, ch):
    m = font.getmask(ch, mode="L")
    return (m.size, bytes(bytearray(m)))


def missing(path, chars):
    f = ImageFont.truetype(path, SIZE)
    ref = draw_key(f, PROBE)
    out = set()
    for ch in chars:
        if ch in " \n\r\t" or ch in ALLOW:
            continue
        try:
            if draw_key(f, ch) == ref:
                out.add(ch)
        except Exception:                # noqa: BLE001 — не нарисовался вовсе
            out.add(ch)
    return out


def texts_chars():
    """Символы из design/texts.json с путём до строки — чтобы было что чинить."""
    src = {}
    data = json.load(open("design/texts.json", encoding="utf-8"))

    def walk(o, path):
        if isinstance(o, str):
            for ch in o:
                src.setdefault(ch, path)
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k, path)
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(data, "texts")
    return src


def scene_chars():
    """(р.24) design/scene.json целиком: имена зон уходят на hover-плашку
    (PTSans), подписи щитка и бирки вентилей рисует движок. Раньше гейт их не
    читал вовсе — «✓» в имени зоны проходил его насквозь. Остальные строки
    файла — пути и идентификаторы, ASCII, им проверка ничего не стоит."""
    src = {}
    data = json.load(open("design/scene.json", encoding="utf-8"))

    def walk(o, path):
        if isinstance(o, str):
            for ch in o:
                src.setdefault(ch, path)
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(data, "scene")
    return src


def lua_chars():
    """Строковые литералы Lua. Комментарии не трогаем: они на экран не идут."""
    src = {}
    files = [p for p in sorted(glob.glob("src/*.lua")) + ["main.lua"]
             if p not in LUA_SKIP and os.path.exists(p)]
    lit = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'')
    for p in files:
        for n, line in enumerate(open(p, encoding="utf-8"), 1):
            for m in lit.finditer(line):
                for ch in (m.group(1) or m.group(2) or ""):
                    src.setdefault(ch, f"{p}:{n}")
    return src


def main():
    if not FONTS:
        print("НЕТ ШРИФТОВ в assets/fonts — проверять нечего")
        sys.exit(1)
    # самопроверка детектора: канарейку он обязан поймать в каждом шрифте,
    # иначе «PASS» ничего не значит (см. комментарий у PROBE)
    for f in FONTS:
        if CANARY not in missing(f, [CANARY]):
            print(f"FONT GATE BROKEN: детектор не видит канарейку в {f}")
            sys.exit(1)
    src = {}
    for d in (texts_chars(), scene_chars(), lua_chars()):
        for ch, where in d.items():
            src.setdefault(ch, where)
    bad = {}
    for f in FONTS:
        for ch in missing(f, sorted(src)):
            bad.setdefault(ch, []).append(os.path.basename(f))
    print(f"шрифтов {len(FONTS)}, различных символов {len(src)}")
    if bad:
        print("FONT GATE FAIL — эти символы рисуются квадратом:")
        for ch in sorted(bad):
            print(f" - {ch!r} U+{ord(ch):04X}: нет в {', '.join(bad[ch])}"
                  f"  (например {src[ch]})")
        print("Лечение: заменить символ текстом или нарисовать значок вектором.")
        sys.exit(1)
    print("FONT GATE PASS (тофу-глифов нет)")


if __name__ == "__main__":
    main()
