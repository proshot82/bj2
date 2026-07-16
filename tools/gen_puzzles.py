#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_puzzles.py — «Латунный янычар 2.0», Фаза 1.
Строит design/puzzles.json: граф узлов D0–D6, замки, ответы (генерируются
здесь и живут ТОЛЬКО в puzzles.json / WALKTHROUGH_SPOILERS.md), документы,
токены улик. Ответы в stdout НЕ печатаются.
"""
import json, secrets, sys, os

R = secrets.SystemRandom()

# ---------------------------------------------------------------- глифы
GLYPH_NAMES = ["fez", "yatagan", "crescent", "star", "drum",
               "horseshoe", "teapot", "key", "fish", "snowflake"]
GLYPH_RU = {"fez": "феска", "yatagan": "ятаган", "crescent": "полумесяц",
            "star": "звезда", "drum": "барабан", "horseshoe": "подкова",
            "teapot": "чайник", "key": "ключ", "fish": "рыба",
            "snowflake": "снежинка"}

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
    wrongmap = {"P+": "P-", "K1+": "K1-", "S-": "S+", "K2+": "K2-"}
    printed = list(base)
    printed[idx] = wrongmap[base[idx]]
    pumps = R.randrange(4, 8)
    a["bench_seq"] = base + [f"PUMP{pumps}"]
    a["bench_printed"] = printed
    a["bench_fix_idx"] = idx
    a["bench_pumps"] = pumps
    return a

ANS = gen_answers()

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

out = os.path.join(os.path.dirname(__file__), "..", "design", "puzzles.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(PUZ, f, ensure_ascii=False, indent=1)
print(f"puzzles.json записан: узлов {len(N)}, доков {len(DOCS)} "
      f"(ответы сгенерированы, в консоль не выводятся)")
