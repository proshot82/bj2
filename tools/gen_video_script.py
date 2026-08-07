#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор ЗРИТЕЛЬСКОГО сценария → work/video_script.json.

Видео полного 100%-прохождения (запись xvfb+ffmpeg поверх реального движка):
тот же маршрут, что у гаунтлета (gen_autoplay.py), но в темпе человека:
  * op talk — каждая реплика висит, пока её печатает и читает игрок;
  * op read_doc — читалка листается с паузой на каждую страницу;
  * op hint_ready — «СОВЕТ ПРЕДКА» жмётся по истечении кулдауна: за игру
    снимаются ВСЕ доступные уровни всех тем (3×N);
  * все look-осмотры комнат и зумов (ПКМ), все герринги, все документы,
    все реликвии, корона и полный эпилог;
  * никаких негативов, ресайзов, сейв-тестов и неверных кодов.
Кадры/значения кодов в файл не пишутся (op code/form без value — рантайм
подставляет ответы сам). Два shot_badge остаются: op quit требует ≥2
бейдж-проверок (аудит В4), в кадре они не видны.
"""
import json, sys

S = json.load(open("design/scene.json", encoding="utf-8"))
P = json.load(open("design/puzzles.json", encoding="utf-8"))
TXT = json.load(open("design/texts.json", encoding="utf-8"))
NODES = {n["id"]: n for n in P["nodes"]}
ITEMS = set(TXT["item_names"].keys())

def item_gated(nid):
    n = NODES.get(nid)
    if not n or n["type"] != "action":
        return None
    for nd in n["needs"]:
        if nd in ITEMS:
            return nd
    return None

site, entry = {}, {}
room_of = {z: S["zooms"][z]["room"] for z in S["zooms"]}
looks = {}   # view -> [hs_id] (и комнаты, и зумы)

def scan(view_id, hotspots, is_room):
    for h in hotspots:
        if h.get("node") and h["node"] not in site:
            site[h["node"]] = (view_id, h["id"])
        if h.get("goto"):
            g = h["goto"]
            if g not in entry or (is_room and not entry[g][2]):
                entry[g] = (view_id, h["id"], is_room)
        if h.get("look"):
            looks.setdefault(view_id, []).append(h["id"])

for rid, room in S["rooms"].items():
    scan(rid, room["hotspots"], True)
for zid, z in S["zooms"].items():
    scan(zid, z["hotspots"], False)

def need(n):
    if n not in site:
        sys.exit("FAIL: нет точки для узла " + n)
    return site[n]

steps = []
cur = "TITLE"
hints_planned = 0
looked = set()

def add(**kw): steps.append(kw)
def talk(): add(op="talk")
def read(): add(op="read_doc")

def to_room(r):
    global cur
    if cur == r: return
    if cur in room_of:
        talk(); add(op="esc")
        cur = room_of[cur]
    if cur != r:
        add(op="click_hs", id="arrow_right" if r == "B" else "arrow_left")
        add(op="wait", s=0.6)
        add(op="assert_view", id=r)
        cur = r

def to_zoom(z):
    global cur
    if cur == z: return
    ev, ehs, _ = entry[z]
    if ev in ("A", "B"): to_room(ev)
    else: to_zoom(ev)
    add(op="click_hs", id=ehs)
    add(op="wait", s=0.8)
    cur = z

def goto_view(v):
    if v in ("A", "B"): to_room(v)
    else: to_zoom(v)

def node(n, btn=1):
    v, hs = need(n)
    goto_view(v)
    gi = item_gated(n) if btn == 1 else None
    if gi: add(op="click_item", id=gi); add(op="wait", s=0.4)
    add(op="click_hs", id=hs, btn=btn)
    talk()

def look(view, hs):
    """ПКМ-осмотр с чтением реплики; каждый хотспот — один раз за видео."""
    if (view, hs) in looked: return
    looked.add((view, hs))
    goto_view(view)
    add(op="look_hs", id=hs)
    talk()

def look_all(view, only=None, skip=()):
    for hs in looks.get(view, []):
        if only and hs not in only: continue
        if hs in skip: continue
        look(view, hs)

def hint():
    global hints_planned
    hints_planned += 1
    add(op="hint_ready")
    talk()

# ================= С0: титул, интро =================
add(op="wait", s=3.0)
add(op="start_game"); cur = "A"
talk()                                        # интро-диалог целиком

# первые советы Предка (тема t_start) — сразу, между осмотрами
hint()
look_all("A", only=["hs_window", "hs_sofa", "hs_lap_desk", "hs_table_mugs"])
node("survey_door"); talk()
to_zoom("zoom_exit_door")
look_all("zoom_exit_door")                    # табличка/скважина/замок
hint()
add(op="click_hs", id="hs_z_bolt")            # ранняя попытка засова — сюжетно
talk()
talk(); add(op="esc"); cur = "A"
look_all("A", only=["hs_flipchart", "hs_kpi_board", "hs_ira_desk"])
hint()                                        # t_start #3

# ================= С1: линейка → ящик → ручка → подсобка =================
node("h_window")
node("take_ruler")
node("pry_drawer")
to_zoom("zoom_lap_drawer")
look_all("zoom_lap_drawer")                   # фотки с корпоратива
node("take_handle")
node("search_drawer_again")                   # ятаган (реликвия 1)
hint()                                        # t_utility #1
look("A", "hs_exit_sign")   # (штырь ПКМ недостижим: зона под дверью — в журнал)
node("open_utility")
hint()                                        # t_utility #2 (или следующая тема)

# герринги офиса
for hn in ["h_intercom", "h_phone", "h_extinguisher"]:
    if hn in site and site[hn][0] == "A":
        node(hn)
add(op="click_hs", id="hs_karaoke")           # караоке-список (док)
read()
node("h_karaoke_sing")                        # гэг «спеть»
hint()

# ================= С2: сачок, аквариум, пропуск =================
node("take_pointer")
to_room("B")
look_all("B")                                 # ведро/раковина/стеллаж/решётка
node("see_net")
node("push_net")
node("take_net")
add(op="combine", a="net", b="pointer"); talk()
hint()                                        # t_card
for hn in ["h_boiler", "h_sink_valve", "h_extinguisher"]:
    if hn in site and site[hn][0] == "B":
        node(hn)
to_zoom("zoom_aquarium")
look_all("zoom_aquarium")                     # замок/водоросли
node("h_fish_poke")
hint()
node("fish_card")
talk(); add(op="esc"); cur = "A"
add(op="rmb_item", id="card")                 # разглядеть мёртвый пропуск
read()
hint()

# ================= С3: ёлка — ключик, подарок, архив =================
to_zoom("zoom_tree")
look_all("zoom_tree")
node("take_key_toy")
add(op="click_hs", id="hs_z_santa")           # бирка Тайного Санты
read()
node("take_gift")                             # авто-открытка + сотка
read()
talk()
add(op="hud", id="docs")                      # архив бумаг: бирку можно перечитать
add(op="wait", s=1.6)
add(op="archive_doc", id="doc_santa")
read()
add(op="esc")
talk(); add(op="esc"); cur = "A"

# ================= С4: ПК Иры — глифы, доки =================
hint()                                        # t_pc
to_zoom("zoom_pc")
look_all("zoom_pc")                           # мышь/карандашница
add(op="click_hs", id="hs_z_sticker")         # стикер с глифами
read()
hint()
to_room("A")                                  # к двери — легенда знаков
add(op="click_hs", id="hs_poster_ot")
read()
hint()
to_zoom("zoom_pc")
add(op="click_hs", id="hs_z_screen")
add(op="wait", s=1.0)
add(op="code", node="pc_unlock"); talk()
add(op="click_hs", id="hs_z_screen")          # рабочий стол
add(op="wait", s=1.2)
for i in range(1, 6):                         # пять доков ПК подряд
    add(op="click", x=700, y=170 + (i - 1) * 62 + 26)
    read()
add(op="click", x=1700, y=900, btn=2)         # закрыть ПК
talk(); add(op="esc"); cur = "A"

# ================= С5: тумба Иры — код, реестр =================
hint()                                        # t_skud цепочка начинается
to_zoom("zoom_drawer_keypad")
look_all("zoom_drawer_keypad")                # щель шредера, ящичек
add(op="click_hs", id="hs_z_keypad")
add(op="wait", s=1.0)
add(op="code", node="ira_code"); talk()
talk()
add(op="click_hs", id="hs_ira_drawer_out")    # полнокадровый ящик (р.19)
add(op="wait", s=1.2)
add(op="click_hs", id="hs_z_registry")        # реестр отделов
read()
add(op="click_hs", id="hs_z_ira_back")
add(op="wait", s=0.8)
talk(); add(op="esc"); cur = "A"
hint()

# ================= С6: форма СКУД =================
to_zoom("zoom_pc")
add(op="click_hs", id="hs_z_screen")
add(op="wait", s=1.0)
add(op="click", x=700, y=170 + 5 * 62 + 26)   # пункт 6: ФОРМА
add(op="wait", s=1.4)
add(op="form"); talk()
add(op="assert_flag", f="card_active")
talk(); add(op="esc"); cur = "A"
hint()
node("copy_pass")                             # гэг: копир пока обесточен
add(op="click", x=40, y=1045, btn=2)          # фейл не снимает выбор — снимаем ПКМ

# ================= С7: верстак — замок, ключ =================
hint()                                        # t_power
to_zoom("zoom_workbench")
look(  "zoom_workbench", "hs_z_vise")
add(op="click_hs", id="hs_z_journal")         # журнал испытаний
read()
node("open_workbench")
cur = "zoom_wb_drawer"                        # (р.22) enter_zoom открыл кадр сам
to_zoom("zoom_wb_drawer")                     # полнокадровый ящик (р.19)
add(op="wait", s=1.5)
add(op="click_hs", id="hs_z_wb_wrench")       # leave_zoom закроет кадр сам
talk()
cur = "B"
look("zoom_workbench", "hs_z_wb_drawer_empty")# осмотр пустого ящика
talk(); add(op="esc"); cur = "B"
hint()

# ================= С8: стенд — колесо, вентили, коллектор =================
node("take_wheel")
to_zoom("zoom_bench")
look_all("zoom_bench")                        # люк/манометр
add(op="click_hs", id="hs_z_note")            # листок стенда
read()
node("install_wheel")
hint()
add(op="bench_seq"); talk()
add(op="bench_pumps"); talk()
node("take_collector")
talk(); add(op="esc"); cur = "B"
add(op="combine", a="collector", b="wrench"); talk()
add(op="rmb_item", id="trikey")
talk()

# ================= С9: щиток — свет, ёлка, герринги =================
hint()
node("open_panel")
to_zoom("zoom_panel")
look_all("zoom_panel")                        # рубильник-мираж
add(op="click_hs", id="hs_z_schema")          # схема щитка
read()
add(op="breaker", i=1); add(op="wait", s=1.2); talk()   # ВВОД — свет!
add(op="breaker", i=2); talk()                # РОЗЕТКИ
add(op="breaker", i=3); talk()                # ЁЛКА (гэг)
add(op="breaker", i=4); talk()                # СРВ (герринг)
add(op="breaker", i=5); talk()                # РЕЗЕРВ (герринг)
add(op="breaker", i=6); talk()                # мёртвый рычаг
talk(); add(op="esc"); cur = "B"
to_room("A")                                  # дневной офис с гирляндой
add(op="wait", s=2.5)
look("A", "hs_red_button")                    # красная кнопка видна при свете
node("copy_pass")                             # гэг: ксерокопия пропуска
add(op="rmb_item", id="copy")
talk()
add(op="assert_reader", open=False)
add(op="assert_view", id="A")
hint()

# ================= С10: сигнализация =================
to_zoom("zoom_alarm")
look_all("zoom_alarm")                        # бирка монтажника, сирена
hint()
add(op="click_hs", id="hs_z_alarm_pad")
add(op="wait", s=1.0)
add(op="code", node="alarm_off"); talk()
talk(); add(op="esc"); cur = "A"
hint()

# ================= С11: кофе + валидол (t_calm) =================
node("brew_coffee")
to_zoom("zoom_closet")
look_all("zoom_closet")                       # крючки/тряпка/бутылки
node("take_validol")
talk(); add(op="esc"); cur = "B"
hint()
add(op="combine", a="validol", b="coffee"); talk()
hint()

# ================= С12: смазка + засов (t_bolt) =================
node("take_grease")
hint()
to_zoom("zoom_exit_door")
add(op="click_item", id="grease")
add(op="click_hs", id="hs_z_bolt")
add(op="wait", s=1.2)
talk()
hint()

# бейдж-чеки для финального сторожа (в кадре не видны)
add(op="hint_ready")
add(op="wait", s=0.35)
steps.append({"op": "shot_badge", "name": "vid_badge_anc", "v": "ПРЕДОК"})
talk()

# ================= С13: реликвии и корона =================
_v, _hs = need("relic_badge")                 # клик без talk: бейджу нужен живой диалог
goto_view(_v)
_gi = item_gated("relic_badge")
if _gi: add(op="click_item", id=_gi); add(op="wait", s=0.4)
add(op="click_hs", id=_hs)
add(op="wait", s=0.35)
steps.append({"op": "shot_badge", "name": "vid_badge_lap", "v": "ЛАПИДУС"})
talk()
node("take_mop")
to_zoom("zoom_attic")
look("zoom_attic", "hs_z_tinsel")             # мишура
node("box_down")
add(op="wait", s=1.0)
look("zoom_attic", "hs_z_dust")               # пыльный след — после коробки
talk(); add(op="esc"); cur = "B"
node("open_box")                              # феска (реликвия 3)
node("search_box_again")                      # корона
add(op="rmb_item", id="relic_fez")
talk()
add(op="rmb_item", id="crown")
talk()

# архив бумаг под завязку — все 17 документов собраны
add(op="hud", id="docs")
add(op="wait", s=3.0)
add(op="esc")

# ================= С14: финал — свайп, дверь, эпилог =================
hint()                                        # t_final / t_secret
node("reader_swipe")
hint()
to_zoom("zoom_exit_door")
hint()                                        # последние уровни советов
add(op="click_hs", id="hs_z_door_push")
talk()
add(op="wait", s=1.5)
talk()                                        # эпилог целиком, с короной
add(op="assert_flag", f="victory")
add(op="wait", s=6.0)                         # финальный кадр подержать
add(op="esc")
add(op="wait", s=5.0)                         # титул
add(op="quit")

json.dump({"steps": steps}, open("work/video_script.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
n_talk = sum(1 for s in steps if s["op"] == "talk")
n_read = sum(1 for s in steps if s["op"] == "read_doc")
print(f"video_script: шагов={len(steps)} talk={n_talk} read_doc={n_read} "
      f"hint={hints_planned} осмотров={len(looked)}")
