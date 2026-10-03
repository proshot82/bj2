#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Негативные тесты гейтов: гейт обязан ПАДАТЬ на порченых данных.

Мотив (аудит 2.0.5): гейт, который зелёный на данных без игры, — не гейт,
а украшение. Здесь каждый гейт проверяется в обратную сторону: данные
портятся ровно одной точечной мутацией, гейт обязан вернуть rc≠0 и назвать
причину. Оригиналы сохраняются и восстанавливаются в finally, целостность
подтверждается сверкой md5 до и после.

Спойлер-гигиена: мутации не читают и не печатают значения замков.

Четыре семьи кейсов:
  * данные → GATE2 (быстрые, чистая статика);
  * сценарий → гаунтлет через реальный движок (аудит В3/В4): проверяется,
    что автоплей отказывается печатать успех без терминального условия,
    ловит подменённого спикера, подменённый бейдж и пустой кадр. Прогоны
    идут на КОРОТКОМ префиксе настоящего сценария, а не на полном — падение
    и так наступает на первом же испорченном шаге;
  * кадры → пиксельные гейты (аудит В1): каталог скринов подменяется
    подделкой, и gates.py обязан её отвергнуть. Здесь воспроизводится ровно
    та атака, которой аудит вскрыл дыру, — шестнадцать кадров шума с тёмными
    прямоугольниками в замеряемых зонах, — и отдельно случай «плашка есть,
    букв нет», который якорь не ловит принципиально;
  * исходник → letterbox-смок: смок обязан ронять сломанный пересчёт
    экранных координат в мировые, а автоплей — входить в игру через окно,
    а не ступенькой ниже игрока;
  * исходник → гейт шрифтов (р.19): тофу-глиф возвращается и в реплику, и в
    строковый литерал Lua — обе ветки разбора обязаны его поймать и назвать
    место. Свою собственную слепоту гейт сторожит канарейкой сам.
  * исходник → гаунтлет (р.19, р.22, р.24): признак или фикс в src/ui.lua
    глушится точечной мутацией, и укороченный прогон обязан упасть на своём
    сторожевом шаге (leave_zoom, enter_zoom, регресс интерфейса р.24);
  * исходник → гаунтлет и юнит-тест (р.25, сенсорный ввод): порог удержания,
    распознаватель в обход, мышиный ПКМ в распознавателе, сдвиг пальца,
    касание мимо letterbox, экранные цифры формы, уход с победы кликом и его
    защита от проскока. Кусок сценария вырезается до сторожа и гоняется на
    подложенном сейве; у каждой вырезки — позитивный контроль без порчи;
  * исходник → сенсорный гаунтлет (р.26, кадр «лёжа»): касание без обратного
    поворота и выключенный поворот обязаны уронить начало сенсорного прогона
    в портретном окне.

Запуск из корня репозитория:  python3 tools/test_negatives.py
                              python3 tools/test_negatives.py --fast  (без движка)
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile

if not os.path.isdir("design"):
    sys.exit("запускать из корня репозитория")

FILES = ["design/texts.json", "design/scene.json", "design/puzzles.json"]
FAILED = []
PASSED = []
SKIPPED = []


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def case(name, mutate, cmd, expect_sub):
    """mutate(dict-of-path->doc) правит документы на месте; гейт обязан упасть."""
    docs = {p: json.load(open(p, encoding="utf-8")) for p in FILES}
    mutate(docs)
    for p, d in docs.items():
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rc, out = run(cmd)
    ok = rc != 0 and expect_sub in out
    (PASSED if ok else FAILED).append(name)
    mark = "OK  " if ok else "ПРОВАЛ"
    print(f"[{mark}] {name}: rc={rc} ожидалось≠0, маркер {expect_sub!r} "
          f"{'найден' if expect_sub in out else 'НЕ НАЙДЕН'}")
    if not ok:
        print("     ---- вывод гейта ----")
        for line in out.strip().splitlines()[-12:]:
            print("     " + line)


# ---------------- мутации ----------------
def _first_replica_holder(T):
    """путь до первого списка реплик (для точечной порчи)"""
    return T["breaker_dead"]


def m_no_speaker(docs):
    """(К3) реплика без поля s — раньше проскакивала мимо линта"""
    r = dict(_first_replica_holder(docs["design/texts.json"])[0])
    r.pop("s", None)
    _first_replica_holder(docs["design/texts.json"])[0] = r


def m_no_emotion(docs):
    """(К3) реплика без поля e"""
    r = dict(_first_replica_holder(docs["design/texts.json"])[0])
    r.pop("e", None)
    _first_replica_holder(docs["design/texts.json"])[0] = r


def m_bad_type(docs):
    """(К3) поле t не строка"""
    _first_replica_holder(docs["design/texts.json"])[0]["t"] = 42


def m_breaker_hole_lost(docs):
    """(К1) дырка в карте автоматов затёрта — карта схлопнулась до 5 позиций"""
    for h in docs["design/scene.json"]["zooms"]["zoom_panel"]["hotspots"]:
        if h.get("widget") == "breakers":
            h["breaker_map"] = [x for x in h["breaker_map"] if x is not None]


def m_tofu_glyph(docs):
    """(р.19) в реплику вернулся «✓» — в шрифтах сборки его нет, на экране квадрат.

    Символ выбран не случайно: ровно он и стоял у каждой закрытой цели, пока
    раунд 19 не вскрыл целый класс таких дыр. Ни один прежний гейт их не ловил
    — движок молча рисует .notdef.
    """
    _first_replica_holder(docs["design/texts.json"])[0]["t"] += " ✓"


def m_tofu_zone_name(docs):
    """(р.24) тот же «✓» — в имени зоны: имя уходит на hover-плашку PTSans.
    До р.24 гейт шрифтов scene.json не читал, и такой символ проходил его."""
    room = docs["design/scene.json"]["rooms"]["A"]
    named = [h for h in room["hotspots"] if h.get("name")]
    named[0]["name"] += " ✓"


GATE2 = [sys.executable, "tools/validate_scene.py"]
FONTGATE = [sys.executable, "tools/check_fonts.py"]

CASES = [
    ("К3 реплика без спикера роняет GATE2", m_no_speaker, GATE2, "реплика без поля 's'"),
    ("К3 реплика без эмоции роняет GATE2", m_no_emotion, GATE2, "реплика без поля 'e'"),
    ("К3 нестроковый текст роняет GATE2", m_bad_type, GATE2, "поле 't' не строка"),
    ("К1 потеря дырки в рейке роняет GATE2", m_breaker_hole_lost, GATE2,
     "карта автоматов"),
    ("Р19 тофу-глиф в реплике роняет гейт шрифтов", m_tofu_glyph, FONTGATE,
     "FONT GATE FAIL"),
    ("Р24 тофу-глиф в имени зоны роняет гейт шрифтов", m_tofu_zone_name, FONTGATE,
     "(например scene/rooms/A/hotspots"),
]


# ---------------- семья 2: сценарий → гаунтлет ----------------
LOVE = shutil.which("love")
AP = "work/autoplay_full.json"


def _prefix():
    """префикс настоящего сценария до первого assert_speaker включительно"""
    doc = json.load(open(AP, encoding="utf-8"))
    steps = doc["steps"] if isinstance(doc, dict) else doc
    for i, st in enumerate(steps):
        if st.get("op") == "assert_speaker":
            return [dict(x) for x in steps[:i + 1]]
    raise SystemExit("в сценарии нет assert_speaker — автопроход не сработал")


SHOTS = "work/shots"


def ap_case(name, build, expect_sub, expect_ok=False, block_shots=False, pre=None):
    """build(prefix)->steps; гаунтлет обязан упасть с маркером expect_sub.

    expect_sub — строка ЛИБО список строк: обязаны найтись все. Список нужен
    негативам на сейв (аудит С1). Там прогон падает в любом случае — короткий
    сценарий физически не может дойти до победы, а без победы op quit запрещён
    (аудит В3). Поэтому одного маркера мало: первый подтверждает, что загрузчик
    сказал про порчу правильные слова, второй («сценарий исчерпан») — что все
    утверждения сценария прошли и прогон дошёл до конца файла, а не умер на
    первом же из них. Без второго кейс зеленел бы и на движке, который просто
    рухнул после нужной строчки в консоли.

    pre(home) вызывается ПОСЛЕ вычистки каталога сейвов и до запуска движка —
    в него подкладывается порченый сейв.
    """
    if not LOVE:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: love не найден в PATH — движковый негатив НЕ проверен")
        return
    steps = build(_prefix())
    tmp = tempfile.mkdtemp(prefix="ap_neg_")
    path = os.path.join(tmp, "neg.json")
    json.dump({"steps": steps}, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    home = os.path.expanduser("~/.local/share/love/BrassJanissary2")
    shutil.rmtree(home, ignore_errors=True)
    if pre:
        os.makedirs(home, exist_ok=True)
        pre(home)
    stash = None
    if block_shots:
        # (аудит Н4) каталог скринов подменяется ФАЙЛОМ: и проба на запись,
        # и mkdir обязаны отказать, а движок — сказать об этом внятно и сразу
        if os.path.isdir(SHOTS):
            stash = os.path.join(tmp, "shots_stash")
            shutil.move(SHOTS, stash)
        elif os.path.exists(SHOTS):
            os.remove(SHOTS)
        os.makedirs(os.path.dirname(SHOTS), exist_ok=True)
        open(SHOTS, "w").close()
    try:
        rc, out = run(["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                       "env", "SDL_AUDIODRIVER=dummy",
                       LOVE, ".", "--autoplay", path])
    finally:
        if block_shots:
            if os.path.isfile(SHOTS):
                os.remove(SHOTS)
            if stash:
                shutil.move(stash, SHOTS)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
        if os.path.isdir(SHOTS):                   # кейс не мусорит в кадры
            for junk in glob.glob(os.path.join(SHOTS, "neg_*.png")):
                os.remove(junk)
    subs = [expect_sub] if isinstance(expect_sub, str) else list(expect_sub)
    lost = [x for x in subs if x not in out]
    said_ok = "AUTOPLAY OK" in out
    ok = (said_ok == expect_ok) and not lost
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: rc={rc} "
          f"успех={'да' if said_ok else 'нет'} (ждали {'да' if expect_ok else 'нет'}), "
          f"маркеров {len(subs) - len(lost)}/{len(subs)}"
          + (f", НЕ НАЙДЕНЫ: {', '.join(repr(x) for x in lost)}" if lost else ""))
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


def b_wrong_speaker(pre):
    """(В4) ожидаемый спикер подменён — утверждение обязано поймать"""
    pre[-1] = dict(pre[-1], s="anc" if pre[-1]["s"] == "lap" else "lap")
    return pre


def b_no_quit(pre):
    """(В3) сценарий обрывается без op quit — успех печатать нельзя"""
    return pre


def b_quit_without_final(pre):
    """(В3) op quit без подтверждённого финала"""
    return pre + [{"op": "quit"}]


def b_blank_badge(pre):
    """(В4) бейдж-чек по кадру без плашки — порог уверенности обязан сработать"""
    return pre + [{"op": "dismiss_all"}, {"op": "wait", "s": 0.4},
                  {"op": "shot_badge", "name": "neg_blank", "v": "ЛАПИДУС"}]


def b_wrong_badge(pre):
    """(В4) бейдж-чек ждёт чужой портрет"""
    return pre + [{"op": "wait", "s": 0.4},
                  {"op": "shot_badge", "name": "neg_badge", "v": "ПРЕДОК"}]


# ---------------- С1: порченый сейв ----------------
# Сейв — единственный вход в игру, который правится СНАРУЖИ: его таскают между
# сборками, режут на полпути и правят руками. Поэтому здесь он подкладывается до
# старта движка, а короткий сценарий проверяет через реальный UI, что загрузчик
# сделал ровно обещанное: чужую версию не пустил, незнакомый зум откатил, чужие
# имена выбросил, про непроходимость предупредил.
TAIL = "сценарий исчерпан без op quit"


def _save_version():
    """номер версии берём из src/ui.lua, а не дублируем: дубль однажды разъедется
    с игрой, и кейс тихо начнёт проверять не то"""
    src = open("src/ui.lua", encoding="utf-8").read()
    m = re.search(r"^local SAVE_VERSION = (\d+)", src, re.M)
    if not m:
        raise SystemExit("в src/ui.lua не найдена SAVE_VERSION — "
                         "негативы на сейв не построить")
    return int(m.group(1))


SAVE_V = _save_version()


def _blob(state=None, view=None, version=SAVE_V):
    st = {"flags": [], "inv": [], "done": [], "read": [],
          "bench": {"seq": [], "pumps": 0}, "steps": 0}
    st.update(state or {})
    return {"version": version, "state": st,
            "view": view or {"kind": "room", "room": "A"},
            "settings": {}, "hint_idx": {}}


def _plant_as(name, blob):
    def pre(home):
        with open(os.path.join(home, name), "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False)
    return pre


def _plant(blob):
    def pre(home):
        with open(os.path.join(home, "save_bj2.json"), "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False)
    return pre


def _from_title(*ops):
    """сценарий с нуля, мимо префикса: движок стартует на титуле, где уже лежит
    подложенный сейв, — жмём «ПРОДОЛЖИТЬ» и смотрим, что вышло"""
    steps = [{"op": "wait", "s": 0.8}, {"op": "continue_game"},
             {"op": "wait", "s": 0.6}, {"op": "dismiss_all"}] + list(ops)
    return lambda _pre: [dict(s) for s in steps]


def _all_nodes():
    """все узлы разом в done при пустых флагах — состояние, из которого уже
    ничего не запустить. Спойлер-гигиена: читаются только имена узлов."""
    P = json.load(open("design/puzzles.json", encoding="utf-8"))
    return [n["id"] for n in P["nodes"]]


AP_CASES = [
    ("С1 сейв чужой версии не пускает в игру",
     _from_title({"op": "assert_title", "open": True}),
     # маркер повторяет формулировку ui.lua. Был «версия 2 ≠ 3»; «≠» выкинут
     # из движка в р.19 — символа нет в Neucha, а строка уходит в тост
     # (см. tools/check_fonts.py). Здесь, в консоли теста, «≠» был бы законен,
     # но маркер обязан совпадать с тем, что реально печатает игра.
     [f"версия {SAVE_V - 1}, нужна {SAVE_V}", TAIL],
     {"pre": _plant(_blob(version=SAVE_V - 1))}),
    ("С1 неизвестный зум в сейве откатывается в комнату",
     _from_title({"op": "assert_title", "open": False},
                 {"op": "assert_view", "id": "A"}),
     ["неизвестный зум", TAIL],
     {"pre": _plant(_blob(view={"kind": "zoom", "room": "A",
                                "zoom": "zoom_нет_такого"}))}),
    ("С1 чужие имена в сейве выбрасываются",
     _from_title({"op": "assert_title", "open": False},
                 {"op": "assert_item", "id": "card"},
                 {"op": "assert_no_item", "id": "нет_такого_предмета"}),
     ["выброшено чужих имён", TAIL],
     {"pre": _plant(_blob(state={"inv": ["card", "нет_такого_предмета"],
                                 "read": ["doc_нет_такого"]}))}),
    ("С1 непроходимый сейв — предупреждение, а не молчаливый тупик",
     _from_title({"op": "assert_title", "open": False}),
     ["победа недостижима", TAIL],
     {"pre": _plant(_blob(state={"done": _all_nodes()}))}),
    ("Р23 прогресс из .tmp старой схемы поднимается",
     # у жертв Windows-бага весь прогресс лежал в save_bj2.json.tmp: кнопка
     # «Продолжить» обязана появиться, а предмет из .tmp — оказаться в карманах
     _from_title({"op": "assert_title", "open": False},
                 {"op": "assert_item", "id": "card"}),
     [TAIL],
     {"pre": _plant_as("save_bj2.json.tmp", _blob(state={"inv": ["card"]}))}),
    ("В4 подменённый спикер роняет гаунтлет", b_wrong_speaker, "спикер", {}),
    ("В3 обрыв сценария не печатает успех", b_no_quit,
     "сценарий исчерпан без op quit", {}),
    ("В3 quit без финала роняет гаунтлет", b_quit_without_final,
     "финал не подтверждён", {}),
    ("В4 пустой кадр не проходит бейдж-чек", b_blank_badge, "рамка не опознана", {}),
    ("В4 чужой бейдж роняет гаунтлет", b_wrong_badge, "бейдж: ожидал ПРЕДОК", {}),
    ("Н4 недоступный каталог скринов — внятный отказ на старте", b_no_quit,
     "каталог скринов недоступен для записи", {"block_shots": True}),
]


# ---------------- семья 3: кадры → пиксельные гейты ----------------
GATES = [sys.executable, "tools/gates.py"]
C_TEXT = (237, 232, 219)     # C.text из src/ui.lua
TEXT_L1 = 40                 # тот же радиус, каким gates.py ищет глифы

# Зоны, которые атака заливает тёмным. Накрывают ВСЕ области, по которым
# гейт контраста когда-либо мерил, — и нынешние, и маленькие коробки фона,
# которые мерил прежний гейт. Это принципиально: подделка обязана проходить
# ПРЕЖНИЕ гейты насквозь, иначе кейс доказывал бы не дыру, а её отсутствие
# (проверено задним числом: с этими зонами старый набор гейтов зелёный).
# Дубль координат тут сознательный — кейс воспроизводит АТАКУ, а не гейт, и
# сверяется по якорному маркеру; если зоны в gates.py съедут, он уцелеет.
DARK_ZONES = {
    "ap_14_hint_badge.png": (100, 830, 1850, 1040),
    "ap_09_a_night_exit.png": (30, 140, 258, 250),
    "ap_00_title.png": (700, 548, 1220, 620),
    "ap_08_bench_done.png": (100, 1008, 1800, 1070),
}


def gates_case(name, paint, expect_sub, need):
    """paint(np, Image, src, dst, names) лепит поддельные кадры на месте
    настоящих; gates.py обязан вернуть rc≠0 и назвать причину."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: нет numpy/PIL ({e}) — пиксельный негатив НЕ проверен")
        return
    names = sorted(os.path.basename(p)
                   for p in glob.glob(os.path.join(SHOTS, "ap_*.png")))
    if len(names) < 14 or any(n not in names for n in need):
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: в {SHOTS} кадров {len(names)} и нужных нет — "
              f"сперва прогнать гаунтлет; пиксельный негатив НЕ проверен")
        return
    tmp = tempfile.mkdtemp(prefix="gates_neg_")
    stash = os.path.join(tmp, "shots")
    shutil.move(SHOTS, stash)
    os.makedirs(SHOTS)
    try:
        paint(np, Image, stash, SHOTS, names)
        rc, out = run(GATES)
    finally:
        shutil.rmtree(SHOTS, ignore_errors=True)
        shutil.move(stash, SHOTS)
        shutil.rmtree(tmp, ignore_errors=True)
    ok = rc != 0 and expect_sub in out
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: rc={rc} ожидалось≠0, "
          f"маркер {expect_sub!r} {'найден' if expect_sub in out else 'НЕ НАЙДЕН'}")
    if not ok:
        print("     ---- вывод гейта ----")
        for line in out.strip().splitlines()[-12:]:
            print("     " + line)


def p_noise(np, Image, src, dst, names):
    """(В1) атака аудита: кадры чистого шума, а в замеряемых зонах — тёмные
    прямоугольники, чтобы «гипотетический текст» на них читался. До якоря
    такой набор проходил пиксельные гейты насквозь."""
    rng = np.random.default_rng(20260725)
    for nm in names:
        a = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
        m = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 80)
        a[m, 1] = 128            # гасим случайную мадженту: ловить обязан якорь
        z = DARK_ZONES.get(nm)
        if z:
            a[z[1]:z[3], z[0]:z[2]] = 18
        Image.fromarray(a).save(os.path.join(dst, nm))


def p_no_glyphs(np, Image, src, dst, names):
    """(В1) кадры настоящие, якорь на месте, но в нижней полосе кадра с
    подсказкой стёрт весь текст: плашка есть, букв нет. Прежний гейт мерил
    константу цвета текста к пустому фону и от этого только зеленел."""
    for nm in names:
        shutil.copy2(os.path.join(src, nm), os.path.join(dst, nm))
    p = os.path.join(dst, "ap_14_hint_badge.png")
    a = np.array(Image.open(p).convert("RGB"))
    strip = a[800:, :]                      # вид на нижнюю полосу, правка на месте
    d = np.abs(strip.astype(float) - np.array(C_TEXT, dtype=float)).sum(axis=2)
    strip[d < TEXT_L1] = (24, 24, 28)
    Image.fromarray(a).save(p)


def p_dark_b(np, Image, src, dst, names):
    """(р.24) ночная подсобка затемнена примерно до 5 %: пол 8 % обязан
    уронить гейт. До р.24 пол стоял с hard=False и только предупреждал."""
    for nm in names:
        shutil.copy2(os.path.join(src, nm), os.path.join(dst, nm))
    p = os.path.join(dst, "ap_04_room_b.png")
    a = np.array(Image.open(p).convert("RGB")).astype(float)
    a[80:] *= 0.35                          # полоса HUD сверху цела — якорь не задет
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(p)


GATES_CASES = [
    # (р.24) маркер — текст ОШИБКИ якоря: просто «якорь» печатается строкой
    # «[0] якорь: …» на каждом прогоне, и негатив оставался зелёным даже с
    # выключенным якорем (шумовые кадры и так роняет WCAG-гейт)
    ("В1 кадры шума не проходят пиксельные гейты", p_noise,
     "пикселей палитры движка", []),
    ("В1 плашка без букв не проходит WCAG-гейт", p_no_glyphs,
     "глифов в зоне нет", ["ap_14_hint_badge.png"]),
    ("Р24 подсобка темнее пола 8 % роняет гейт яркости", p_dark_b,
     "яркость: комната B", ["ap_04_room_b.png"]),
]


# ---------------- семья 4: исходник → letterbox-смок ----------------
# Мотив (аудит «смок в кривом разрешении»). Смок work/ap_smoke.json всю жизнь
# проекта был украшением, и сразу по двум причинам. Автоплей звал ui.mousepressed
# напрямую — то есть входил в игру ступенькой ниже игрока и перепрыгивал
# love.mousepressed вместе с пересчётом экранных координат в мировые. А ключ
# «xvfb --screen 1536x864» окно не ограничивал вовсе: X разрешает окну быть
# больше экрана, так что смок гонялся ровно в тех же 1920×1080, что и основной
# гаунтлет, где letterbox тождественный. Проверять было нечего и нечем.
#
# Оба условия закрепляются здесь: первый кейс сторожит путь клика статически
# (в обе стороны, прямо по исходнику), второй ломает пересчёт и требует, чтобы
# смок это заметил.
SMOKE = "work/ap_smoke.json"
APLUA = "src/autoplay.lua"
MAIN = "main.lua"
SMOKE_NEG = "смок ловит сломанный пересчёт экран→мир"


def _click_body(src):
    """тело примитива click из src/autoplay.lua"""
    m = re.search(r"^local function click\(.*?^end$", src, re.M | re.S)
    if not m:
        raise SystemExit(f"в {APLUA} не найден примитив click — негатив ослеп")
    return m.group(0)


def _click_through_window(src):
    """клик обязан идти В ОКНО (love.mousepressed), а не прямо в UI"""
    body = _click_body(src)
    return "love.mousepressed(" in body and not re.search(r"\bui\.mousepressed\(", body)


def case_click_path():
    """(смок) автоплей не входит в игру ниже игрока.

    Проверяется в обе стороны прямо здесь: на живом исходнике условие обязано
    выполняться, на нём же с возвращённым старым вызовом — обязано падать.
    Без второй половины это было бы утверждение без доказательства, что оно
    вообще способно кого-нибудь поймать.
    """
    name = "смок: клик автоплея идёт через окно, а не мимо letterbox"
    src = open(APLUA, encoding="utf-8").read()
    live = _click_through_window(src)
    # (р.25) порча — строго в теле click: с пальцем (finger_down) вызов
    # love.mousepressed(sx, sy… есть и выше по файлу, и подмена первого
    # вхождения в файле уходила мимо проверяемой функции
    body = _click_body(src)
    broken = _click_through_window(src.replace(
        body, body.replace("love.mousepressed(sx, sy", "E.ui.mousepressed(x, y", 1), 1))
    ok = live and not broken
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: живой исходник "
          f"{'через окно' if live else 'МИМО ОКНА'}, подмена на прямой вызов UI "
          f"{'ловится' if not broken else 'НЕ ЛОВИТСЯ'}")


# ---------------- семья 5: исходник Lua → гейт шрифтов ----------------
# Кейс в CASES сторожит ветку texts.json. Но четыре из шести дыр раунда 19
# сидели не в данных, а в строковых литералах Lua («✓», «▸», «→», «←»), и
# ветку разбора исходников надо сторожить отдельно — иначе она может тихо
# ослепнуть (например, если сломается регулярка литерала), а гейт останется
# зелёным и будет выглядеть работающим.
FONT_SRC = "src/ui.lua"
FONT_NEG = "Р19 тофу-глиф в литерале Lua роняет гейт шрифтов"
FONT_ANCHOR = 'lg.print(g.t, x + 40, gy)'
FONT_BROKEN = 'lg.print("✓ " .. g.t, x + 40, gy)'


def case_font_gate_lua():
    """(р.19) гейт шрифтов обязан видеть тофу и в исходнике, не только в JSON."""
    src = open(FONT_SRC, encoding="utf-8").read()
    if src.count(FONT_ANCHOR) != 1:
        SKIPPED.append(FONT_NEG)
        print(f"[ПРОПУСК] {FONT_NEG}: якорь в {FONT_SRC} встречается "
              f"{src.count(FONT_ANCHOR)} раз(а), ждали 1 — негатив ослеп")
        return
    before = md5(FONT_SRC)
    tmp = tempfile.mkdtemp(prefix="font_neg_")
    shutil.copy2(FONT_SRC, os.path.join(tmp, "ui.lua"))
    try:
        open(FONT_SRC, "w", encoding="utf-8").write(
            src.replace(FONT_ANCHOR, FONT_BROKEN, 1))
        rc, out = run(FONTGATE)
    finally:
        shutil.copy2(os.path.join(tmp, "ui.lua"), FONT_SRC)
        shutil.rmtree(tmp, ignore_errors=True)
    if md5(FONT_SRC) != before:
        FAILED.append(f"НЕ ВОССТАНОВЛЕН {FONT_SRC}")
        print(f"[ПРОВАЛ] {FONT_SRC} не восстановлен после мутации!")
    said = "FONT GATE FAIL" in out
    named = FONT_SRC in out                     # гейт обязан назвать, где чинить
    ok = rc != 0 and said and named
    (PASSED if ok else FAILED).append(FONT_NEG)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {FONT_NEG}: rc={rc} ожидалось≠0, "
          f"маркер {'найден' if said else 'НЕ НАЙДЕН'}, "
          f"место {'названо' if named else 'НЕ НАЗВАНО'}")
    if not ok:
        print("     ---- вывод гейта ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


LB_ANCHOR = "  return (x - letter.ox) / letter.sx, (y - letter.oy) / letter.sy"
LB_BROKEN = "  return x / letter.sx, y / letter.sy"


def case_smoke_teeth():
    """(смок) сломанный пересчёт экран→мир обязан ронять letterbox-смок.

    Мутация выбрана реалистичная — забыт сдвиг полос. При 1920×1080 полос нет,
    поэтому прогон стартует как ни в чём не бывало и портится ровно там, где
    сценарий впервые меняет размер окна: падает именно смок, а не что-то ещё
    по дороге.

    Кадры smoke_*.png этот прогон перезаписывает своими, испорченными. Это
    безопасно: их не читает ни один гейт (gates.py считает кадры ap_*.png),
    они нужны только бейдж-чеку внутри самого прогона. Лишние удаляются.
    """
    if not LOVE:
        SKIPPED.append(SMOKE_NEG)
        print(f"[ПРОПУСК] {SMOKE_NEG}: love не найден в PATH")
        return
    if not os.path.exists(SMOKE):
        SKIPPED.append(SMOKE_NEG)
        print(f"[ПРОПУСК] {SMOKE_NEG}: нет {SMOKE} — сперва gen_autoplay.py")
        return
    src = open(MAIN, encoding="utf-8").read()
    if src.count(LB_ANCHOR) != 1:
        SKIPPED.append(SMOKE_NEG)
        print(f"[ПРОПУСК] {SMOKE_NEG}: якорь пересчёта в {MAIN} встречается "
              f"{src.count(LB_ANCHOR)} раз(а), ждали 1 — негатив ослеп")
        return
    before = md5(MAIN)
    tmp = tempfile.mkdtemp(prefix="smoke_neg_")
    shutil.copy2(MAIN, os.path.join(tmp, "main.lua"))
    home = os.path.expanduser("~/.local/share/love/BrassJanissary2")
    kept = set(glob.glob(os.path.join(SHOTS, "smoke_*.png")))
    shutil.rmtree(home, ignore_errors=True)
    try:
        open(MAIN, "w", encoding="utf-8").write(src.replace(LB_ANCHOR, LB_BROKEN, 1))
        rc, out = run(["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                       "env", "SDL_AUDIODRIVER=dummy",
                       LOVE, ".", "--autoplay", SMOKE])
    finally:
        shutil.copy2(os.path.join(tmp, "main.lua"), MAIN)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
        for junk in set(glob.glob(os.path.join(SHOTS, "smoke_*.png"))) - kept:
            os.remove(junk)
    if md5(MAIN) != before:
        FAILED.append(f"НЕ ВОССТАНОВЛЕН {MAIN}")
        print(f"[ПРОВАЛ] {MAIN} не восстановлен после мутации!")
    said_ok = "AUTOPLAY OK" in out
    said_fail = "AUTOPLAY FAIL" in out
    ok = (not said_ok) and said_fail
    (PASSED if ok else FAILED).append(SMOKE_NEG)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {SMOKE_NEG}: rc={rc} "
          f"успех={'да' if said_ok else 'нет'} (ждали нет), маркер 'AUTOPLAY FAIL' "
          f"{'найден' if said_fail else 'НЕ НАЙДЕН'}")
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


# ---------------- семья 6: исходник Lua → гаунтлет (leave_zoom, р.19) ----------------
# Разводной ключ впечатан в арт zoom_wb_drawer; после взятия признак leave_zoom
# обязан закрыть кадр (иначе игрок смотрит на взятый ключ). Динамику сторожит
# assert_view "B" в основном сценарии; этот кейс доказывает, что сторож ловит:
# признак глушится точечной мутацией ui.lua, укороченный прогон до этого
# assert_view обязан упасть и назвать вид.
LZ_SRC = "src/ui.lua"
LZ_NEG = "Р19 заглушенный leave_zoom роняет гаунтлет"
LZ_ANCHOR = "if h.leave_zoom and SC.view().kind == \"zoom\" then"
LZ_BROKEN = "if h.leave_zoom and false and SC.view().kind == \"zoom\" then"


def case_leave_zoom():
    if not LOVE:
        SKIPPED.append(LZ_NEG)
        print(f"[ПРОПУСК] {LZ_NEG}: love не найден в PATH")
        return
    if not os.path.exists(AP):
        SKIPPED.append(LZ_NEG)
        print(f"[ПРОПУСК] {LZ_NEG}: нет {AP} — сперва gen_autoplay.py")
        return
    doc = json.load(open(AP, encoding="utf-8"))
    steps = doc["steps"] if isinstance(doc, dict) else doc
    cut = None
    for i, st in enumerate(steps):
        if st.get("op") == "click_hs" and st.get("id") == "hs_z_wb_wrench":
            for j in range(i + 1, len(steps)):
                if steps[j].get("op") == "assert_view":
                    cut = j
                    break
            break
    if cut is None:
        SKIPPED.append(LZ_NEG)
        print(f"[ПРОПУСК] {LZ_NEG}: в сценарии нет клика по ключу с "
              f"последующим assert_view — негатив ослеп")
        return
    src = open(LZ_SRC, encoding="utf-8").read()
    if src.count(LZ_ANCHOR) != 1:
        SKIPPED.append(LZ_NEG)
        print(f"[ПРОПУСК] {LZ_NEG}: якорь в {LZ_SRC} встречается "
              f"{src.count(LZ_ANCHOR)} раз(а), ждали 1 — негатив ослеп")
        return
    before = md5(LZ_SRC)
    tmp = tempfile.mkdtemp(prefix="lz_neg_")
    shutil.copy2(LZ_SRC, os.path.join(tmp, "ui.lua"))
    path = os.path.join(tmp, "neg.json")
    json.dump({"steps": [dict(x) for x in steps[:cut + 1]]},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    home = os.path.expanduser("~/.local/share/love/BrassJanissary2")
    shutil.rmtree(home, ignore_errors=True)
    try:
        open(LZ_SRC, "w", encoding="utf-8").write(
            src.replace(LZ_ANCHOR, LZ_BROKEN, 1))
        rc, out = run(["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                       "env", "SDL_AUDIODRIVER=dummy",
                       LOVE, ".", "--autoplay", path])
    finally:
        shutil.copy2(os.path.join(tmp, "ui.lua"), LZ_SRC)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    if md5(LZ_SRC) != before:
        FAILED.append(f"НЕ ВОССТАНОВЛЕН {LZ_SRC}")
        print(f"[ПРОВАЛ] {LZ_SRC} не восстановлен после мутации!")
    said_ok = "AUTOPLAY OK" in out
    named = "вид zoom_wb_drawer" in out          # die называет застрявший вид
    ok = (not said_ok) and named
    (PASSED if ok else FAILED).append(LZ_NEG)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {LZ_NEG}: rc={rc} "
          f"успех={'да' if said_ok else 'нет'} (ждали нет), застрявший вид "
          f"{'назван' if named else 'НЕ НАЗВАН'}")
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


EZ_NEG = "Р22 заглушенный enter_zoom роняет гаунтлет"
EZ_ANCHOR = "if h.enter_zoom then"
EZ_BROKEN = "if h.enter_zoom and false then"


def case_enter_zoom():
    """(р.22) авто-вход в ящик после ключа: признак глушится мутацией ui.lua,
    укороченный прогон до assert_view zoom_wb_drawer обязан упасть."""
    if not LOVE:
        SKIPPED.append(EZ_NEG)
        print(f"[ПРОПУСК] {EZ_NEG}: love не найден в PATH")
        return
    if not os.path.exists(AP):
        SKIPPED.append(EZ_NEG)
        print(f"[ПРОПУСК] {EZ_NEG}: нет {AP} — сперва gen_autoplay.py")
        return
    doc = json.load(open(AP, encoding="utf-8"))
    steps = doc["steps"] if isinstance(doc, dict) else doc
    cut = None
    for i, st in enumerate(steps):
        if st.get("op") == "click_hs" and st.get("id") == "hs_z_padlock":
            for j in range(i + 1, len(steps)):
                if steps[j].get("op") == "assert_view":
                    cut = j
                    break
            break
    if cut is None:
        SKIPPED.append(EZ_NEG)
        print(f"[ПРОПУСК] {EZ_NEG}: в сценарии нет клика замка с "
              f"последующим assert_view — негатив ослеп")
        return
    src = open(LZ_SRC, encoding="utf-8").read()
    if src.count(EZ_ANCHOR) != 1:
        SKIPPED.append(EZ_NEG)
        print(f"[ПРОПУСК] {EZ_NEG}: якорь в {LZ_SRC} встречается "
              f"{src.count(EZ_ANCHOR)} раз(а), ждали 1 — негатив ослеп")
        return
    before = md5(LZ_SRC)
    tmp = tempfile.mkdtemp(prefix="ez_neg_")
    shutil.copy2(LZ_SRC, os.path.join(tmp, "ui.lua"))
    path = os.path.join(tmp, "neg.json")
    json.dump({"steps": [dict(x) for x in steps[:cut + 1]]},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    home = os.path.expanduser("~/.local/share/love/BrassJanissary2")
    shutil.rmtree(home, ignore_errors=True)
    try:
        open(LZ_SRC, "w", encoding="utf-8").write(
            src.replace(EZ_ANCHOR, EZ_BROKEN, 1))
        rc, out = run(["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                       "env", "SDL_AUDIODRIVER=dummy",
                       LOVE, ".", "--autoplay", path])
    finally:
        shutil.copy2(os.path.join(tmp, "ui.lua"), LZ_SRC)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    if md5(LZ_SRC) != before:
        FAILED.append(f"НЕ ВОССТАНОВЛЕН {LZ_SRC}")
        print(f"[ПРОВАЛ] {LZ_SRC} не восстановлен после мутации!")
    said_ok = "AUTOPLAY OK" in out
    named = "вид zoom_workbench" in out          # застряли в родительском зуме
    ok = (not said_ok) and named
    (PASSED if ok else FAILED).append(EZ_NEG)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {EZ_NEG}: rc={rc} "
          f"успех={'да' if said_ok else 'нет'} (ждали нет), застрявший вид "
          f"{'назван' if named else 'НЕ НАЗВАН'}")
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


# ---------------- семья 7: исходник Lua → гаунтлет (регресс р.24) ----------------
# Четыре находки ревью р.24 сторожатся утверждениями основного сценария (шаги с
# меткой tag, см. блок «Р24» в gen_autoplay.py). Каждый кейс возвращает баг
# точечной мутацией исходника и гоняет префикс сценария до сторожевого шага:
# прогон обязан упасть и назвать причину. Механика та же, что у семьи 6.
R24_CASES = [
    # (имя, файл, якорь, порча, метка шага-сторожа, op сторожа, маркер падения)
    ("Р24 выбранный предмет переживает «Продолжить» — гаунтлет падает",
     "src/ui.lua",
     "  reset_transient()                                         -- (р.24) хвосты прошлой партии",
     "  -- reset_transient() вырезан негативом",
     "r24_selection", "assert_no_selection", "выбран предмет"),
    ("Р24 «Продолжить» откатывает настройки — гаунтлет падает",
     "src/ui.lua",
     "  -- (р.24) Настройки сейва больше НЕ применяются.",
     "  for k, v in pairs(blob.settings or {}) do settings[k] = v end\n"
     "  -- (р.24) Настройки сейва больше НЕ применяются.",
     "r24_settings", "assert_setting", "настройка music"),
    ("Р24 Esc закрывает зум под паузой — гаунтлет падает",
     "src/ui.lua",
     "    if menu == \"pause\" then menu = nil\n",
     "    if false then menu = nil\n",
     "r24_esc", "assert_menu", "меню pause"),
    ("Р24 цифровой блок не вводит код — гаунтлет падает",
     "src/ui.lua",
     "  key = key:match(\"^kp(%d)$\") or (key == \"kpenter\" and \"return\") or key\n",
     "  key = key\n",
     "r24_numpad", "assert_flag", "нет флага pc_on"),
]


def case_r24(name, src_path, anchor, broken, tag, guard_op, marker):
    if not LOVE:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: love не найден в PATH")
        return
    if not os.path.exists(AP):
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: нет {AP} — сперва gen_autoplay.py")
        return
    doc = json.load(open(AP, encoding="utf-8"))
    steps = doc["steps"] if isinstance(doc, dict) else doc
    cut = None
    for i, st in enumerate(steps):
        if st.get("tag") == tag:
            # сторож — первый шаг нужного op начиная с помеченного
            for j in range(i, len(steps)):
                if steps[j].get("op") == guard_op:
                    cut = j
                    break
            break
    if cut is None:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: в сценарии нет шага с меткой {tag} и "
              f"сторожем {guard_op} — негатив ослеп")
        return
    src = open(src_path, encoding="utf-8").read()
    if src.count(anchor) != 1:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: якорь в {src_path} встречается "
              f"{src.count(anchor)} раз(а), ждали 1 — негатив ослеп")
        return
    before = md5(src_path)
    tmp = tempfile.mkdtemp(prefix="r24_neg_")
    shutil.copy2(src_path, os.path.join(tmp, "orig.lua"))
    path = os.path.join(tmp, "neg.json")
    json.dump({"steps": [dict(x) for x in steps[:cut + 1]]},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    home = os.path.expanduser("~/.local/share/love/BrassJanissary2")
    shutil.rmtree(home, ignore_errors=True)
    try:
        open(src_path, "w", encoding="utf-8").write(src.replace(anchor, broken, 1))
        rc, out = run(["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                       "env", "SDL_AUDIODRIVER=dummy",
                       LOVE, ".", "--autoplay", path])
    finally:
        shutil.copy2(os.path.join(tmp, "orig.lua"), src_path)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    if md5(src_path) != before:
        FAILED.append(f"НЕ ВОССТАНОВЛЕН {src_path}")
        print(f"[ПРОВАЛ] {src_path} не восстановлен после мутации!")
    said_ok = "AUTOPLAY OK" in out
    named = marker in out
    ok = (not said_ok) and named
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: rc={rc} "
          f"успех={'да' if said_ok else 'нет'} (ждали нет), маркер {marker!r} "
          f"{'найден' if named else 'НЕ НАЙДЕН'}")
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


# ---------------- семья 8: исходник Lua → гаунтлет (сенсорный ввод, р.25) ----------------
# Сенсорный ввод сторожат шаги r25_* основного сценария и целый прогон пальцем
# (work/ap_touch.json). Каждый кейс возвращает баг точечной порчей исходника,
# прогон обязан упасть на своём стороже и назвать причину.
#
# Чтобы не гонять по минуте префикс до середины игры, кейс берёт из сценария
# только нужный кусок — от его начала до сторожа — и подкладывает сейв с
# состоянием, в котором этот кусок стоит в настоящем прогоне (прецедент —
# кейсы С1). Кусок не копия: он вырезается из work/autoplay_full.json, и правка
# сценария доходит сюда сама. Подложенный сейв — уже не настоящая игра, поэтому
# у каждой вырезки есть ПОЗИТИВНЫЙ КОНТРОЛЬ: без порчи тот же прогон обязан
# дойти до конца куска (все утверждения прошли — маркер TAIL) и не дать маркер
# порчи. Без контроля кейс зеленел бы и на сломанном сейве.
TOUCH_AP = "work/ap_touch.json"
TOUCH_SRC = "src/touch.lua"
TOUCH_TEST = ["luajit", "tools/test_touch.lua"]


def _steps(path):
    doc = json.load(open(path, encoding="utf-8"))
    return doc["steps"] if isinstance(doc, dict) else doc


def _cut(start, tag, op):
    """кусок основного сценария: от шага start(step)==True (ищется назад от
    сторожа) до сторожа — первого шага op с меткой tag — включительно.
    Кадры выброшены: мини-прогон не должен затирать кадры гаунтлета."""
    st = _steps(AP)
    g = next((j for j, s in enumerate(st)
              if s.get("tag") == tag and s.get("op") == op), None)
    if g is None:
        return None
    f = next((i for i in range(g, -1, -1) if start(st[i])), None)
    if f is None:
        return None
    return [dict(s) for s in st[f:g + 1] if s.get("op") not in ("shot", "shot_badge")]


def _boot():
    """титул → «ПРОДОЛЖИТЬ» по подложенному сейву"""
    return [{"op": "wait", "s": 0.8}, {"op": "continue_game"},
            {"op": "wait", "s": 0.6}, {"op": "dismiss_all"}]


# состояния, в которых куски стоят в настоящем прогоне (только имена узлов и
# флагов — ответов здесь нет)
SAVE_R25 = _blob(state={"flags": ["surveyed"], "inv": ["ruler"],
                        "done": ["survey_door", "take_ruler"], "steps": 2})
SAVE_FORM = _blob(state={"flags": ["surveyed", "pc_on"], "inv": ["ruler", "card"],
                         "done": ["survey_door", "take_ruler", "pc_unlock", "fish_card"],
                         "steps": 20},
                  view={"kind": "zoom", "room": "A", "zoom": "zoom_pc"})
SAVE_WIN = _blob(state={"flags": ["surveyed", "reader_green", "alarm_off",
                                  "bolt_free", "calm_down"], "steps": 60},
                 view={"kind": "zoom", "room": "A", "zoom": "zoom_exit_door"})

SLICES = {
    # имя: (сейв, начало куска (ищется назад от сторожа), метка сторожа,
    #       op сторожа, ops, без которых кусок не тот)
    "r25": (SAVE_R25, lambda s: s.get("op") == "tap" and s.get("tag") == "r25_tap",
            "r25_mouse_rmb", "assert_view", {"tap", "hold", "drag", "click"}),
    "form": (SAVE_FORM, lambda s: s.get("op") == "click_hs" and s.get("id") == "hs_z_screen",
             "r25_form_pad", "assert_form_len", {"form", "assert_widget"}),
    "win": (SAVE_WIN, lambda s: s.get("op") == "click_hs" and s.get("id") == "hs_z_door_push",
            "r25_victory", "assert_title", {"click", "assert_flag"}),
}


def _run_engine(steps, pre=None):
    tmp = tempfile.mkdtemp(prefix="r25_neg_")
    path = os.path.join(tmp, "neg.json")
    json.dump({"steps": steps}, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    home = os.path.expanduser("~/.local/share/love/BrassJanissary2")
    shutil.rmtree(home, ignore_errors=True)
    if pre:
        os.makedirs(home, exist_ok=True)
        pre(home)
    try:
        return run(["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                    "env", "SDL_AUDIODRIVER=dummy", LOVE, ".", "--autoplay", path])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


def _mutated(muts, fn):
    """muts: [(файл, якорь, порча)] — каждый якорь обязан встретиться ровно
    раз; fn() выполняется на испорченных исходниках, оригиналы
    восстанавливаются со сверкой md5. None — якорь не найден (негатив ослеп)."""
    srcs = {}
    for p, anchor, _ in muts:
        srcs.setdefault(p, open(p, encoding="utf-8").read())
        if srcs[p].count(anchor) != 1:
            return None, f"якорь в {p} встречается {srcs[p].count(anchor)} раз(а), ждали 1"
    sums = {p: md5(p) for p in srcs}
    tmp = tempfile.mkdtemp(prefix="r25_src_")
    for p in srcs:
        shutil.copy2(p, os.path.join(tmp, p.replace("/", "__")))
    try:
        broken = dict(srcs)
        for p, anchor, bad in muts:
            broken[p] = broken[p].replace(anchor, bad, 1)
        for p, text in broken.items():
            open(p, "w", encoding="utf-8").write(text)
        return fn(), None
    finally:
        for p in srcs:
            shutil.copy2(os.path.join(tmp, p.replace("/", "__")), p)
        shutil.rmtree(tmp, ignore_errors=True)
        for p, m in sums.items():
            if md5(p) != m:
                FAILED.append(f"НЕ ВОССТАНОВЛЕН {p}")
                print(f"[ПРОВАЛ] {p} не восстановлен после мутации!")


_CONTROLLED = set()


def _control(key, steps, pre):
    """позитивный контроль куска: без порчи прогон доходит до конца куска"""
    if key in _CONTROLLED:
        return True
    name = f"Р25 контроль: кусок «{key}» на подложенном сейве проходит без порчи"
    rc, out = _run_engine(steps, pre)
    ok = TAIL in out and "AUTOPLAY OK" not in out
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: "
          f"{'дошёл до конца куска' if ok else 'НЕ ДОШЁЛ'}")
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)
    _CONTROLLED.add(key)
    return ok


def case_r25(name, muts, where, marker):
    """where: ключ SLICES (кусок + сейв) либо "touch" — префикс сенсорного
    прогона до первого утверждения спикера"""
    if not LOVE:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: love не найден в PATH")
        return
    if where == "touch":
        if not os.path.exists(TOUCH_AP):
            SKIPPED.append(name)
            print(f"[ПРОПУСК] {name}: нет {TOUCH_AP} — сперва gen_autoplay.py")
            return
        st = _steps(TOUCH_AP)
        k = next((i for i, s in enumerate(st) if s.get("op") == "assert_speaker"), None)
        steps, pre = [dict(s) for s in st[:k + 1]], None
    else:
        save, start, tag, op, need = SLICES[where]
        cut = _cut(start, tag, op) if os.path.exists(AP) else None
        # кусок обязан быть тем самым: без своих ops он проверял бы пустоту, а
        # позитивный контроль на пустом куске зеленеет (так и было при отладке)
        lost = need - {s.get("op") for s in cut} if cut else need
        if not cut or lost:
            SKIPPED.append(name)
            print(f"[ПРОПУСК] {name}: в {AP} нет куска до сторожа {tag}/{op}"
                  + (f" (нет ops {sorted(lost)})" if cut else "") + " — негатив ослеп")
            return
        steps, pre = _boot() + cut, _plant(save)
        if not _control(where, steps, pre):
            SKIPPED.append(name)
            print(f"[ПРОПУСК] {name}: контроль куска «{where}» не прошёл — "
                  f"падение под порчей ничего бы не доказало")
            return
    res, why = _mutated(muts, lambda: _run_engine(steps, pre))
    if res is None:
        SKIPPED.append(name)
        print(f"[ПРОПУСК] {name}: {why} — негатив ослеп")
        return
    rc, out = res
    said_ok = "AUTOPLAY OK" in out
    named = marker in out
    ok = (not said_ok) and named
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: rc={rc} "
          f"успех={'да' if said_ok else 'нет'} (ждали нет), маркер {marker!r} "
          f"{'найден' if named else 'НЕ НАЙДЕН'}")
    if not ok:
        print("     ---- хвост прогона ----")
        for line in out.strip().splitlines()[-10:]:
            print("     " + line)


PRESS_ANCHOR = "  if istouch then touch.pressed(x, y); return end\n"
R25_CASES = [
    # (имя, [(файл, якорь, порча)], где, маркер падения)
    ("Р25 медленный тап 0,25 с стал ПКМ (порог 0,1 с) — гаунтлет падает",
     [(TOUCH_SRC, "  HOLD = 0.45,", "  HOLD = 0.1,")],
     "r25", "[r25_slow_tap]: вид A ≠ zoom_exit_door"),
    ("Р25 касание мимо распознавателя (удержание = ЛКМ) — гаунтлет падает",
     [(MAIN, PRESS_ANCHOR, "")],
     "r25", "[r25_hold_zoom]: вид zoom_exit_door ≠ A"),
    ("Р25 мышиный ПКМ ушёл в распознаватель касаний — гаунтлет падает",
     [(MAIN, PRESS_ANCHOR,
       "  if istouch or btn == 2 then touch.pressed(x, y); return end\n")],
     "r25", "[r25_mouse_rmb]: вид zoom_exit_door ≠ A"),
    ("Р25 сдвиг пальца не отменяет тап — гаунтлет падает",
     [(TOUCH_SRC, "  return dx * dx + dy * dy > touch.SLOP * touch.SLOP\n",
       "  return false\n")],
     "r25", "[r25_drag]: вид zoom_exit_door ≠ A"),
    ("Р25 касание мимо letterbox — сенсорный гаунтлет падает",
     [(MAIN, "touch.init(press)\n",
       "touch.init(function(x, y, b) ui.mousepressed(x, y, b) end)\n")],
     "touch", "спикер"),
    ("Р25 экранные цифры формы не вводят номер — гаунтлет падает",
     [("src/ui.lua", "    elseif #widget.no < 6 then widget.no = widget.no .. k end\n",
       "    elseif false then widget.no = widget.no .. k end\n")],
     "form", "[r25_form_pad]: форма: в поле номера 0 знаков"),
    ("Р25 клик не уводит с экрана победы — гаунтлет падает",
     [("src/ui.lua",
       "  if victory_stage and not ui.dialog_active() then victory_click(); return end\n",
       "  if victory_stage and not ui.dialog_active() then return end\n")],
     "win", "[r25_victory]: титул снят, ожидалось показан"),
    ("Р25 плашка победы без защиты от проскока — гаунтлет падает",
     [("src/ui.lua", "local VICTORY_GRACE = 1.0\n", "local VICTORY_GRACE = 0\n")],
     "win", "[r25_victory_grace]: титул показан, ожидалось снят"),
]

# (р.26) Кадр «лёжа»: на сенсорном устройстве портретное окно рисует мир
# повёрнутым, и касание обязано пройти обратный поворот. Сторож — начало
# сенсорного прогона (окно 960×2080): assert_rotated и первое утверждение
# спикера, оба с меткой r26_portrait.
R26_CASES = [
    ("Р26 касание без обратного поворота кадра — сенсорный гаунтлет падает",
     [(MAIN, "  x, y = scenes.unrotate(x, y)   -- (р.26) экран → кадр «лёжа» (без поворота — как есть)\n", "")],
     "touch", "[r26_portrait]: спикер"),
    ("Р26 флаг сенсорного устройства не кладёт кадр — гаунтлет падает",
     [(MAIN, "  letter.rot = TOUCH_DEVICE and h > w\n", "  letter.rot = false\n")],
     "touch", "[r26_portrait]: кадр стоя, ожидался лёжа"),
]

TT_NEG = "Р25 юнит-тест касаний ловит ЛКМ вместо ПКМ"


def case_touch_unit():
    """(р.25) tools/test_touch.lua обязан упасть, если удержание шлёт ЛКМ."""
    res, why = _mutated([(TOUCH_SRC, "    emit(g.x, g.y, 2)\n", "    emit(g.x, g.y, 1)\n")],
                        lambda: run(TOUCH_TEST))
    if res is None:
        SKIPPED.append(TT_NEG)
        print(f"[ПРОПУСК] {TT_NEG}: {why} — негатив ослеп")
        return
    rc, out = res
    said = "TOUCH TEST FAIL" in out
    ok = rc != 0 and said
    (PASSED if ok else FAILED).append(TT_NEG)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {TT_NEG}: rc={rc} ожидалось≠0, "
          f"маркер {'найден' if said else 'НЕ НАЙДЕН'}")


def main():
    before = {p: md5(p) for p in FILES}
    tmp = tempfile.mkdtemp(prefix="negatives_")
    for p in FILES:
        shutil.copy2(p, os.path.join(tmp, os.path.basename(p)))
    try:
        for name, mut, cmd, sub in CASES:
            case(name, mut, cmd, sub)
            for p in FILES:                       # откат после каждого кейса
                shutil.copy2(os.path.join(tmp, os.path.basename(p)), p)
    finally:
        for p in FILES:
            shutil.copy2(os.path.join(tmp, os.path.basename(p)), p)
        shutil.rmtree(tmp, ignore_errors=True)
    after = {p: md5(p) for p in FILES}
    for p in FILES:
        if before[p] != after[p]:
            FAILED.append(f"НЕ ВОССТАНОВЛЕН {p}")
            print(f"[ПРОВАЛ] {p} не восстановлен после мутаций!")

    if "--fast" in sys.argv:
        for c in AP_CASES:
            SKIPPED.append(c[0])
        print(f"[ПРОПУСК] движковые негативы ({len(AP_CASES)}) — режим --fast")
    elif not os.path.exists(AP):
        for c in AP_CASES:
            SKIPPED.append(c[0])
        print(f"[ПРОПУСК] нет {AP} — сперва python3 tools/gen_autoplay.py")
    else:
        for name, build, sub, kw in AP_CASES:
            ap_case(name, build, sub, **kw)

    if not os.path.isdir(SHOTS):
        for c in GATES_CASES:
            SKIPPED.append(c[0])
        print(f"[ПРОПУСК] нет каталога {SHOTS} — сперва гаунтлет "
              f"({len(GATES_CASES)} пиксельных негатива)")
    else:
        for name, paint, sub, need in GATES_CASES:
            gates_case(name, paint, sub, need)

    case_click_path()                 # статика, движок не нужен
    case_font_gate_lua()              # статика, движок не нужен
    case_touch_unit()                 # (р.25) юнит-тест касаний, движок не нужен
    if "--fast" in sys.argv:
        SKIPPED.append(SMOKE_NEG)
        SKIPPED.append(LZ_NEG)
        SKIPPED.append(EZ_NEG)
        SKIPPED.extend(c[0] for c in R24_CASES)
        SKIPPED.extend(c[0] for c in R25_CASES)
        SKIPPED.extend(c[0] for c in R26_CASES)
        print("[ПРОПУСК] движковые негативы смока, leave_zoom, enter_zoom, "
              "регресса р.24, сенсорного ввода р.25 и кадра «лёжа» р.26 — режим --fast")
    else:
        case_smoke_teeth()
        case_leave_zoom()
        case_enter_zoom()
        for c in R24_CASES:
            case_r24(*c)
        for c in R25_CASES:
            case_r25(*c)
        for c in R26_CASES:
            case_r25(*c)

    print(f"\nнегативов: {len(PASSED)} OK, {len(FAILED)} провалов, "
          f"{len(SKIPPED)} пропущено")
    if SKIPPED:
        print("НЕ ПРОВЕРЕНО (гейт не даёт гарантии по этим пунктам):")
        for s in SKIPPED:
            print(" ~", s)
    if FAILED:
        print("NEGATIVE GATES FAIL:")
        for f in FAILED:
            print(" -", f)
        sys.exit(1)
    print("NEGATIVE GATES PASS")


if __name__ == "__main__":
    main()
