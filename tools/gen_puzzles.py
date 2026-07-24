#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_puzzles.py — «Латунный янычар 2.0», Фаза 1.
Строит design/puzzles.json: граф узлов D0–D6, замки, ответы (генерируются
здесь и живут ТОЛЬКО в puzzles.json / WALKTHROUGH_SPOILERS.md), документы,
токены улик. Ответы в stdout НЕ печатаются.

ОСТОРОЖНО (аудит К4). Ответы здесь СЛУЧАЙНЫЕ. Голый запуск поверх готового
puzzles.json сменил бы коды, глиф-карту и порядок стенда — и с игрой молча
разошлись бы документы, walkthrough, скриншоты и чужие сохранения. Поэтому
перезапись без ключей запрещена, а штатный путь правки — `--pin`:

  gen_puzzles.py --pin                    структура заново, ответы прежние
  gen_puzzles.py --new-answers --force    новые ответы, осознанно
  gen_puzzles.py --new-answers --seed N   новые ответы от фиксированного сида
  gen_puzzles.py --pin --out PATH         песочница, боевой файл не тронут
"""
import argparse, json, secrets, random, shutil, sys, os, time

R = secrets.SystemRandom()

# ---------------------------------------------------------------- глифы
GLYPH_NAMES = ["fez", "yatagan", "crescent", "star", "drum",
               "horseshoe", "teapot", "key", "fish", "snowflake"]
GLYPH_RU = {"fez": "феска", "yatagan": "ятаган", "crescent": "полумесяц",
            "star": "звезда", "drum": "барабан", "horseshoe": "подкова",
            "teapot": "чайник", "key": "ключ", "fish": "рыба",
            "snowflake": "снежинка"}

# печатная версия стенда отличается от верной ровно одним перевёрнутым шагом
WRONGMAP = {"P+": "P-", "K1+": "K1-", "S-": "S+", "K2+": "K2-"}

def gen_answers():
    a = {}
    # PIN ПК: 4 цифры, без банальностей
    while True:
        pin = "".join(str(R.randrange(10)) for _ in range(4))
        if len(set(pin)) >= 3 and pin not in ("1234", "4321", "0000"):
            break
    a["pc_pin"] = pin
    # Глиф-карта: перестановка цифр 0-9 по глифам
    digits = list("0123456789"); R.shuffle(digits)
    a["glyph_map"] = {GLYPH_NAMES[i]: digits[i] for i in range(10)}
    inv = {v: k for k, v in a["glyph_map"].items()}
    a["pin_glyphs"] = [inv[d] for d in pin]
    # Ящик Иры: год основания «ВАЛТЕК» из «О компании», код = год наоборот
    year = R.randrange(1993, 2010)
    a["about_year"] = str(year)
    a["ira_code"] = str(year)[::-1]
    # Сигнализация: ДДММ, декабрь (календарь в офисе — декабрьский лист)
    day = R.randrange(3, 29)
    a["alarm_day"] = f"{day:02d}"
    a["alarm_code"] = f"{day:02d}12"
    # СКУД-2: номер пропуска Гены (6 цифр) + отдел из реестра
    a["card_number"] = "".join(str(R.randrange(10)) for _ in range(6))
    depts = ["АХО", "ОП-1", "ОП-2", "БУХ", "СКЛАД"]
    a["gena_dept"] = R.choice(["ОП-1", "ОП-2", "СКЛАД"])
    a["depts"] = depts
    # Стенд: печатный порядок и рукописная правка одного шага.
    # Вентили: P (подача, маховик ставится), K1, K2, S (красные).
    # Целевая последовательность: 4 вентильных хода + качки насосом.
    base = ["P+", "K1+", "S-", "K2+"]
    R.shuffle(base)
    # рукописная правка: печатная версия имеет ОДИН неверный шаг
    idx = R.randrange(4)
    printed = list(base)
    printed[idx] = WRONGMAP[base[idx]]
    pumps = R.randrange(4, 8)
    a["bench_seq"] = base + [f"PUMP{pumps}"]
    a["bench_printed"] = printed
    a["bench_fix_idx"] = idx
    a["bench_pumps"] = pumps
    return a

# ------------------------------------------------ защита ответов (аудит К4)
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "design", "puzzles.json")

# Поля, из которых собирается ПОЛНЫЙ набор ответов уже готового файла.
PIN_FROM_ANSWERS = ["pc_pin", "glyph_map", "pin_glyphs", "ira_code",
                    "alarm_code", "bench_seq", "bench_fix_idx", "bench_pumps"]
PIN_FROM_TOKENS  = ["about_year", "alarm_day", "card_number", "gena_dept", "depts"]

def die(msg):
    """Отказ: внятная причина в stderr и ненулевой код возврата."""
    print(msg, file=sys.stderr)
    sys.exit(2)

def pin_answers(path):
    """Достаёт прежние ответы из существующего puzzles.json.
    Значения не печатаются. Нехватка любого поля — отказ, а не тихая замена
    случайным: молчаливая подмена ровно та беда, от которой мы защищаемся."""
    try:
        with open(path, encoding="utf-8") as f:
            cur = json.load(f)
    except OSError as e:
        die(f"ОТКАЗ: неоткуда взять прежние ответы — {path} не читается ({e}).")
    except ValueError as e:
        die(f"ОТКАЗ: {path} повреждён и разобрать его не удалось ({e}).")
    A = cur.get("answers") or {}
    T = cur.get("tokens") or {}
    miss = ([f"answers/{k}" for k in PIN_FROM_ANSWERS if k not in A] +
            [f"tokens/{k}"  for k in PIN_FROM_TOKENS  if k not in T])
    if miss:
        die(f"ОТКАЗ: в {path} нет полей {', '.join(miss)} — прежние ответы "
            "восстановить нечем. Файл от другой версии схемы?")
    a = {k: A[k] for k in PIN_FROM_ANSWERS}
    a.update({k: T[k] for k in PIN_FROM_TOKENS})
    # печатный порядок стенда однозначно выводится из верного и номера правки
    base, idx = list(a["bench_seq"])[:4], a["bench_fix_idx"]
    if len(base) != 4 or not (0 <= idx < 4) or base[idx] not in WRONGMAP:
        die(f"ОТКАЗ: в {path} последовательность стенда несовместима с текущим "
            "генератором — перегенерация с прежними ответами невозможна.")
    printed = list(base)
    printed[idx] = WRONGMAP[base[idx]]
    a["bench_printed"] = printed
    return a

def cli():
    """Разбирает ключи и решает судьбу ответов ДО того, как что-то построено."""
    ap = argparse.ArgumentParser(
        description="Сборка design/puzzles.json. Ответы случайны, поэтому "
                    "перезапись готового файла без явного ключа запрещена.")
    ap.add_argument("--pin", action="store_true",
                    help="перестроить структуру, ответы взять из готового файла "
                         "(штатный путь правки)")
    ap.add_argument("--pin-from", metavar="PATH",
                    help="откуда брать прежние ответы "
                         "(по умолчанию — боевой design/puzzles.json)")
    ap.add_argument("--new-answers", action="store_true",
                    help="сгенерировать НОВЫЕ ответы; поверх готового файла "
                         "требует ещё и --force")
    ap.add_argument("--seed", type=int, metavar="N",
                    help="фиксированный сид для --new-answers (воспроизводимо)")
    ap.add_argument("--force", action="store_true",
                    help="разрешить перезапись готового файла новыми ответами")
    ap.add_argument("--out", metavar="PATH", default=DEFAULT_OUT,
                    help="куда писать (по умолчанию design/puzzles.json)")
    ap.add_argument("--no-backup", action="store_true",
                    help="не делать резервную копию перед перезаписью")
    o = ap.parse_args()
    global ARGS_NO_BACKUP
    ARGS_NO_BACKUP = o.no_backup

    out = os.path.abspath(o.out)
    # ответы приколачиваются от боевого файла, а писать можно куда угодно:
    # «--pin --out /tmp/проба.json» обязан работать без лишних ключей
    src = os.path.abspath(o.pin_from) if o.pin_from else os.path.abspath(DEFAULT_OUT)
    exists = os.path.exists(out)

    if o.pin and o.new_answers:
        die("ОТКАЗ: --pin и --new-answers взаимоисключающи.")
    if o.seed is not None and not o.new_answers:
        die("ОТКАЗ: --seed управляет генерацией новых ответов, поэтому имеет "
            "смысл только вместе с --new-answers.")
    if o.pin_from and not o.pin:
        die("ОТКАЗ: --pin-from имеет смысл только вместе с --pin.")

    if o.pin:
        if not os.path.exists(src):
            die(f"ОТКАЗ: --pin просит прежние ответы из {src}, а его нет.")
        return out, pin_answers(src), "прежние ответы (--pin)"

    if exists and not o.new_answers:
        die(f"ОТКАЗ: {out} уже существует, а этот запуск сгенерировал бы НОВЫЕ "
            "случайные ответы.\n"
            "       Сменились бы коды, глиф-карта и порядок стенда — и с игрой "
            "молча разошлись бы\n"
            "       документы, walkthrough, скриншоты гаунтлета и чужие "
            "сохранения.\n"
            "  Правите генератор:   gen_puzzles.py --pin\n"
            "  Нужны новые ответы:  gen_puzzles.py --new-answers --force\n"
            "  Проба на стороне:    gen_puzzles.py --pin --out /tmp/proba.json")
    if exists and not o.force:
        die(f"ОТКАЗ: --new-answers поверх существующего {out} требует ещё и "
            "--force.\n       Прежние ответы будут потеряны безвозвратно.")

    global R
    if o.seed is not None:
        R = random.Random(o.seed)          # значение сида в вывод не идёт
        return out, None, "новые ответы от фиксированного сида"
    return out, None, "новые случайные ответы"

OUT, PINNED, MODE = cli()
ANS = PINNED if PINNED is not None else gen_answers()

VALVE_RU = {"P": "П", "K1": "К1", "K2": "К2", "S": "С"}
def seq_ru(seq):
    out = []
    for op in seq:
        if op.startswith("PUMP"):
            out.append(f"насос ×{op[4:]}")
        else:
            v, s = op[:-1], op[-1]
            out.append(f"{VALVE_RU[v]} {'открыть' if s == '+' else 'закрыть'}")
    return out

# ---------------------------------------------------------------- документы
# id, room доступа, узел-условие доступа (None = доступен по зуму/вайду сразу)
DOCS = [
    {"id": "doc_sticker",   "title": "Стикер под клавиатурой", "room": "A", "at": "zoom_pc",       "needs": []},
    {"id": "doc_poster",    "title": "Плакат по охране труда", "room": "A", "at": "wide",          "needs": []},
    {"id": "doc_calendar",  "title": "Календарь отдела",       "room": "A", "at": "wide",          "needs": []},
    {"id": "doc_karaoke",   "title": "Караоке-список",         "room": "A", "at": "wide",          "needs": []},
    {"id": "doc_santa",     "title": "Бирки Тайного Санты",    "room": "A", "at": "zoom_tree",     "needs": []},
    {"id": "doc_postcard",  "title": "Открытка «на кофе»",     "room": "A", "at": "inv",           "needs": ["take_gift"]},
    {"id": "doc_card",      "title": "Пропуск Гены",           "room": "A", "at": "inv",           "needs": ["fish_card"]},
    {"id": "doc_chat",      "title": "Чат отдела",             "room": "A", "at": "zoom_pc",       "needs": ["pc_unlock"]},
    {"id": "doc_order",     "title": "Приказ №7",              "room": "A", "at": "zoom_pc",       "needs": ["pc_unlock"]},
    {"id": "doc_about",     "title": "«О компании»",           "room": "A", "at": "zoom_pc",       "needs": ["pc_unlock"]},
    {"id": "doc_dict",      "title": "Словарь сокращений",     "room": "A", "at": "zoom_pc",       "needs": ["pc_unlock"]},
    {"id": "doc_registry",  "title": "Реестр отделов",         "room": "A", "at": "zoom_drawer",   "needs": ["ira_code"]},
    {"id": "doc_journal",   "title": "Журнал испытаний",       "room": "B", "at": "wide",          "needs": ["open_utility"]},
    {"id": "doc_bench_note","title": "Листок-инструкция стенда","room": "B", "at": "zoom_bench",   "needs": ["open_utility"]},
    {"id": "doc_schema",    "title": "Схема щитка",            "room": "B", "at": "zoom_panel",    "needs": ["open_panel"]},
    {"id": "doc_mop_tag",   "title": "Инвентарная бирка швабры","room": "B", "at": "zoom_closet",  "needs": ["open_utility"]},
    {"id": "doc_skud_blank","title": "Форма СКУД-2 (бланк)",   "room": "A", "at": "zoom_pc",       "needs": ["pc_unlock"]},
]

# ---------------------------------------------------------------- узлы
# t: pickup|action|combine|lock|doc-опосредованно|herring|win
# room: A|B|inv ; branch: D0..D6|H|WIN ; mand: обязателен для победы
N = []
def node(id, branch, room, t, needs=(), gives=(), mand=False, lock=None,
         consumes=(), herring=False, secret=False):
    N.append({"id": id, "branch": branch, "room": room, "type": t,
              "needs": list(needs), "gives": list(gives), "mand": mand,
              "lock": lock, "consumes": list(consumes),
              "herring": herring, "secret": secret})

# --- D0: открытие подсобки
node("survey_door", "D0", "A", "action", [], ["surveyed"], True)
node("take_ruler", "D0", "A", "pickup", [], ["ruler"], True)
node("pry_drawer", "D0", "A", "action", ["ruler"], ["drawer_pried"], True)
node("take_handle", "D0", "A", "pickup", ["drawer_pried"], ["handle"], True)
node("search_drawer_again", "D0", "A", "pickup",
     ["drawer_pried", "handle"], ["relic_yatagan"], False, secret=True)
# (раунд 13 / аудит F05) handle НЕ потребляется: иначе открытие щитовой навсегда
# лишает секретной реликвии relic_yatagan (search_drawer_again тоже требует handle).
node("open_utility", "D0", "A", "action", ["handle"], ["utility_open"], True)

# --- D1: пропуск (A<->B через вентиляцию)
node("see_net", "D1", "B", "action", ["utility_open"], ["seen_net"], True)
node("take_pointer", "D1", "A", "pickup", [], ["pointer"], True)
node("push_net", "D1", "A", "action", ["pointer", "seen_net"],
     ["net_down", "vents_open"], True)
node("take_net", "D1", "B", "pickup", ["net_down"], ["net"], True)
node("combine_longnet", "D1", "inv", "combine", ["net", "pointer"],
     ["longnet"], True, consumes=["net", "pointer"])
node("fish_card", "D1", "A", "action", ["longnet"], ["card"], True)
node("pc_unlock", "D1", "A", "lock", [], ["pc_on"], True,
     lock={"kind": "keypad", "id": "pc_pin", "len": 4,
           "clue_sources": ["doc_sticker", "doc_poster"]})
node("ira_code", "D1", "A", "lock", [], ["drawer_ira_open"], True,
     lock={"kind": "keypad", "id": "ira_code", "len": 4,
           "clue_sources": ["doc_chat", "doc_about"]})
node("skud_form", "D1", "A", "lock", ["card", "pc_on"], ["card_active"], True,
     lock={"kind": "form", "id": "skud",
           "clue_sources": ["doc_card", "doc_registry", "doc_order"]})
node("copy_pass", "D1", "A", "action", ["card", "sockets_on"], ["copy"],
     False)

# --- D2: сигнализация (короткая, параллельная; улика в B -> замок в A)
node("alarm_off", "D2", "A", "lock", [], ["alarm_off"], True,
     lock={"kind": "keypad", "id": "alarm_code", "len": 4,
           "clue_sources": ["doc_calendar", "doc_journal", "doc_chat"]})

# --- D3: силовая (самая длинная, A->B->A)
node("take_key_toy", "D3", "A", "pickup", [], ["key_toy"], True)
node("open_workbench", "D3", "B", "action", ["key_toy", "utility_open"],
     ["wb_open"], True, consumes=["key_toy"])
node("take_wrench", "D3", "B", "pickup", ["wb_open"], ["wrench"], True)
node("take_wheel", "D3", "A", "pickup", [], ["wheel"], True)
node("install_wheel", "D3", "B", "action", ["wheel", "utility_open"],
     ["wheel_on"], True, consumes=["wheel"])
node("bench_solve", "D3", "B", "lock", ["wheel_on"], ["bench_solved"], True,
     lock={"kind": "bench", "id": "bench_seq",
           "clue_sources": ["doc_bench_note", "doc_journal"]})
node("take_collector", "D3", "B", "pickup", ["bench_solved"], ["collector"],
     True)
node("combine_trikey", "D3", "inv", "combine", ["wrench", "collector"],
     ["trikey"], True, consumes=["collector"])
node("open_panel", "D3", "B", "action", ["trikey", "utility_open"],
     ["panel_open"], True)
node("power_main", "D3", "B", "action", ["panel_open"], ["power_on"], True)
node("sockets_on", "D3", "B", "action", ["panel_open"], ["sockets_on"], True)

# --- D4: руки
node("take_gift", "D4", "A", "pickup", [], ["hundred"], True)
node("brew_coffee", "D4", "A", "action", ["sockets_on", "hundred"],
     ["coffee"], True, consumes=["hundred"])
node("take_validol", "D4", "B", "pickup", ["utility_open"], ["validol"], True)
node("combine_calm", "D4", "inv", "combine", ["validol", "coffee"],
     ["calm_down"], True, consumes=["validol", "coffee"])

# --- D5: засов
node("take_grease", "D5", "B", "pickup", ["utility_open"], ["grease"], True)
node("bolt_free", "D5", "A", "action", ["grease", "wrench"], ["bolt_free"],
     True, consumes=["grease"])

# --- D6: секреты
node("relic_badge", "D6", "A", "action", ["longnet"], ["relic_badge"], False,
     secret=True)
node("take_mop", "D6", "B", "pickup", ["utility_open"], ["mop"], False)
node("box_down", "D6", "B", "action", ["mop", "utility_open"], ["box_down"],
     False)
node("open_box", "D6", "B", "action", ["box_down"], ["relic_fez"], False,
     secret=True)
node("search_box_again", "D6", "B", "action", ["relic_fez"], ["crown"],
     False, secret=True)

# --- WIN
node("reader_swipe", "WIN", "A", "action", ["card_active", "power_on"],
     ["reader_green"], True)
node("door_open", "WIN", "A", "win",
     ["surveyed", "reader_green", "alarm_off", "bolt_free", "calm_down"],
     ["victory"], True)

# --- герринги (>=6, с многостадийными репликами; эффектов на граф нет,
#     кроме видимого гэга br_elka — гирлянда)
for hid, room in [("h_window", "A"), ("h_intercom", "A"),
                  ("h_extinguisher", "A"), ("h_phone", "A"),
                  ("h_boiler", "B"), ("h_sink_valve", "B"),
                  ("h_br_elka", "B"), ("h_br_srv", "B"),
                  ("h_br_rezerv", "B"), ("h_fish_poke", "A"),
                  ("h_karaoke_sing", "A")]:
    extra = ["garland_on"] if hid == "h_br_elka" else []
    needs = ["panel_open"] if hid.startswith("h_br_") else []
    node(hid, "H", room, "herring", needs, extra, False, herring=True)

# ---------------------------------------------------------------- сборка
PUZ = {
    "meta": {"game": "Латунный янычар 2.0", "version": "2.0.0",
             "graph_rev": 1},
    "answers": {
        "pc_pin": ANS["pc_pin"],
        "pin_glyphs": ANS["pin_glyphs"],
        "glyph_map": ANS["glyph_map"],
        "ira_code": ANS["ira_code"],
        "alarm_code": ANS["alarm_code"],
        "skud": {"card_number": ANS["card_number"],
                 "dept": ANS["gena_dept"]},
        "bench_seq": ANS["bench_seq"],
        "bench_seq_ru": seq_ru(ANS["bench_seq"]),
        "bench_printed_ru": seq_ru(ANS["bench_printed"]),
        "bench_fix_idx": ANS["bench_fix_idx"],
        "bench_pumps": ANS["bench_pumps"],
    },
    # токены для подстановки в тексты документов (движок подставляет)
    "tokens": {
        "about_year": ANS["about_year"],
        "ira_rule": "год основания задом наперёд",
        "alarm_day": ANS["alarm_day"],
        "alarm_rule": "ДДММ",
        "card_number": ANS["card_number"],
        "gena_dept": ANS["gena_dept"],
        "depts": ANS["depts"],
        "bench_pumps": str(ANS["bench_pumps"]),
        "glyph_names_ru": GLYPH_RU,
    },
    "docs": DOCS,
    "nodes": N,
    "relics": ["relic_yatagan", "relic_badge", "relic_fez"],
    "bonus": "crown",
    "goals": [
        {"id": "g_card",  "flag": "card_active", "t": "Оживить пропуск"},
        {"id": "g_power", "flag": "power_on",    "t": "Дать свет"},
        {"id": "g_alarm", "flag": "alarm_off",   "t": "Снять сигнализацию"},
        {"id": "g_bolt",  "flag": "bolt_free",   "t": "Победить засов"},
        {"id": "g_calm",  "flag": "calm_down",   "t": "Унять тряску"},
    ],
}

if os.path.exists(OUT) and not ARGS_NO_BACKUP:
    bak = f"{OUT}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(OUT, bak)
    print(f"резервная копия: {os.path.basename(bak)}")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(PUZ, f, ensure_ascii=False, indent=1)
print(f"puzzles.json записан: узлов {len(N)}, доков {len(DOCS)}; "
      f"{MODE} (значения в консоль не выводятся)")
