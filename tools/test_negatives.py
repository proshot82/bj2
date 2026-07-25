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
    а не ступенькой ниже игрока.

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


GATE2 = [sys.executable, "tools/validate_scene.py"]

CASES = [
    ("К3 реплика без спикера роняет GATE2", m_no_speaker, GATE2, "реплика без поля 's'"),
    ("К3 реплика без эмоции роняет GATE2", m_no_emotion, GATE2, "реплика без поля 'e'"),
    ("К3 нестроковый текст роняет GATE2", m_bad_type, GATE2, "поле 't' не строка"),
    ("К1 потеря дырки в рейке роняет GATE2", m_breaker_hole_lost, GATE2,
     "карта автоматов"),
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
     [f"версия {SAVE_V - 1} ≠ {SAVE_V}", TAIL],
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


GATES_CASES = [
    ("В1 кадры шума не проходят пиксельные гейты", p_noise, "якорь", []),
    ("В1 плашка без букв не проходит WCAG-гейт", p_no_glyphs,
     "глифов в зоне нет", ["ap_14_hint_badge.png"]),
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
    broken = _click_through_window(
        src.replace("love.mousepressed(sx, sy", "E.ui.mousepressed(x, y", 1))
    ok = live and not broken
    (PASSED if ok else FAILED).append(name)
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {name}: живой исходник "
          f"{'через окно' if live else 'МИМО ОКНА'}, подмена на прямой вызов UI "
          f"{'ловится' if not broken else 'НЕ ЛОВИТСЯ'}")


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
    if "--fast" in sys.argv:
        SKIPPED.append(SMOKE_NEG)
        print("[ПРОПУСК] движковый негатив смока — режим --fast")
    else:
        case_smoke_teeth()

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
