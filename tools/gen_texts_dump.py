#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Дамп всех игровых текстов для вычитки → docs/GAME_TEXTS_FULL.md.

(р.24) Дамп заказан автором в р.3 («полный текст игры для редактуры») и
числился генерируемым, но генератора в tools/ не было: файл застыл на раунде 7
и разошёлся с игрой (нет «Быстрый текст», реплик «не подходит», UI архива
бумаг р.19 и др.). Теперь он выводится из данных и перегенерируется вместе с
ними — шаг стоит в конвейере сразу за gen_texts.py (MIGRATION.md §3).

Формат прежний: каждая строковая ячейка design/texts.json — пункт
«`путь`: текст» в порядке файла, в конце — подписи зон из design/scene.json.
Числа (индексы рукописных строк) не печатаются — они не текст. Ответов замков
в texts.json нет (только токены {ANS:…}/{TOK:…}), так что дамп спойлеров не
несёт. Правки — не сюда, а в tools/gen_texts.py и tools/gen_scene.py.

Запуск из корня репозитория:  python3 tools/gen_texts_dump.py
"""
import json
import os
import sys

if not os.path.isdir("design"):
    sys.exit("запускать из корня репозитория")

OUT = "docs/GAME_TEXTS_FULL.md"
HEAD = """# ПОЛНЫЙ ТЕКСТ ИГРЫ — для ручной редактуры

> ВАЖНО: файл сгенерирован (tools/gen_texts_dump.py). Правки вносить НЕ сюда, а в tools/gen_texts.py
> (реплики/документы/UI) и tools/gen_scene.py (названия зон), затем перегенерация.
> Данный файл — слепок design/texts.json + подписей зон для вычитки.
"""


def main():
    T = json.load(open("design/texts.json", encoding="utf-8"))
    S = json.load(open("design/scene.json", encoding="utf-8"))
    lines = [HEAD]

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        elif isinstance(v, str):
            lines.append(f"- `{path}`: {v}")

    walk(T, "")
    lines.append("\n## Названия зон (hover-подписи)")
    n_zones = 0
    for group in (S["rooms"], S["zooms"]):
        for vid, view in group.items():
            for h in view.get("hotspots", []):
                if h.get("name"):
                    lines.append(f"- `{vid}/{h['id']}`: {h['name']}")
                    n_zones += 1
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{OUT}: строк текста {len(lines) - 2 - n_zones}, подписей зон {n_zones}")


if __name__ == "__main__":
    main()
