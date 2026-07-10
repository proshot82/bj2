#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор гаунтлет-сценария Фазы 4 → work/autoplay_full.json.

Прокладывает навигацию по design/scene.json (комнаты/зумы/стрелки),
кликает реальные хотспоты, вставляет негативы, скрины, сейв/континью.
Значения кодов в выходной файл НЕ пишутся (op "code" без value —
autoplay берёт ответ на рантайме); негативы — явные неверные значения.
"""
import json, sys

S = json.load(open("design/scene.json", encoding="utf-8"))
P = json.load(open("design/puzzles.json", encoding="utf-8"))
TXT = json.load(open("design/texts.json", encoding="utf-8"))
NODES = {n["id"]: n for n in P["nodes"]}
ITEMS = set(TXT["item_names"].keys())

# Механика «использовать предмет на объект» (раунд 4): узел-ДЕЙСТВИЕ,
# требующий предмет, срабатывает только если предмет ВЫБРАН в карманах.
# Возвращает предмет, который надо выбрать перед кликом, либо None.
def item_gated(nid):
    n = NODES.get(nid)
    if not n or n["type"] != "action":
        return None
    for need in n["needs"]:
        if need in ITEMS:
            return need
    return None

# ---------- карты ----------
site = {}          # node -> (view, hs_id)  (только прямые клики)
entry = {}         # zoom -> (view, hs_id)  (вход, предпочтительно из комнаты)
room_of = {z: S["zooms"][z]["room"] for z in S["zooms"]}
looks = {"A": [], "B": []}

def scan(view_id, hotspots, is_room):
    for h in hotspots:
        if h.get("node") and h["node"] not in site:
            site[h["node"]] = (view_id, h["id"])
        if h.get("goto"):
            g = h["goto"]
            if g not in entry or (is_room and not entry[g][2]):
                entry[g] = (view_id, h["id"], is_room)
        if is_room and h.get("look"):
            looks[view_id].append(h["id"])

for rid, room in S["rooms"].items():
    scan(rid, room["hotspots"], True)
for zid, z in S["zooms"].items():
    scan(zid, z["hotspots"], False)

def need(n):
    if n not in site:
        sys.exit("FAIL: нет точки для узла " + n)
    return site[n]

# ---------- сборка ----------
steps = []
cur = "TITLE"
shots, negatives = [], []

def add(**kw):
    steps.append(kw)

def dismiss():
    add(op="dismiss_all")

def shot(name):
    shots.append(name)
    add(op="shot", name=name)

def to_room(r):
    global cur
    if cur == r:
        return
    if cur in room_of:                    # мы в зуме
        dismiss(); add(op="esc")
        cur = room_of[cur]
    if cur != r:
        add(op="click_hs", id="arrow_right" if r == "B" else "arrow_left")
        cur = r

def to_zoom(z):
    global cur
    if cur == z:
        return
    ev, ehs, _ = entry[z]
    to_room(ev if ev in ("A", "B") else room_of[ev])
    add(op="click_hs", id=ehs)
    cur = z

def goto_view(v):
    if v in ("A", "B"):
        to_room(v)
    else:
        to_zoom(v)

def node(n, btn=1):
    v, hs = need(n)
    goto_view(v)
    gi = item_gated(n) if btn == 1 else None
    if gi:
        add(op="click_item", id=gi)   # выбрать предмет (механика раунда 4)
    add(op="click_hs", id=hs, btn=btn)

def neg(tag):
    negatives.append(tag)

# ---------- S0: титул → интро ----------
add(op="wait", s=0.6)
shot("ap_00_title")
shot("round4_01_title")
add(op="start_game"); cur = "A"
dismiss()
shot("ap_01_room_a_night")
shot("round4_02_room_a_night")

# ---------- S1: дверь — осмотр и ранние негативы ----------
node("survey_door"); dismiss()
to_zoom("zoom_exit_door")
shot("ap_02_exit_zoom_night")
add(op="click_hs", id="hs_z_bolt")            # засов рано
dismiss(); add(op="assert_not_flag", f="bolt_free"); neg("bolt_early")
add(op="click_hs", id="hs_z_reader_small")    # ридер рано
dismiss(); add(op="assert_not_flag", f="reader_green"); neg("reader_early")
add(op="click_hs", id="hs_z_plate", btn=2)    # табличка (ПКМ)
dismiss()

# ---------- S2: D0 — линейка, ящик, ручка, ятаган, подсобка ----------
node("h_window"); dismiss()
node("take_ruler"); dismiss()
node("pry_drawer"); dismiss()
to_zoom("zoom_lap_drawer")
node("take_handle"); dismiss()
node("search_drawer_again"); dismiss()
add(op="assert_item", id="relic_yatagan")
shot("ap_03_drawer_relic")
node("open_utility"); dismiss()
add(op="assert_flag", f="utility_open")

# ---------- S2.5: осмотр офиса (герринги A) ----------
for hn in ["h_intercom", "h_phone", "h_extinguisher"]:
    if hn in site and site[hn][0] == "A":
        node(hn); dismiss()
add(op="click_hs", id="hs_karaoke")          # список песен (док)
add(op="close_reader")
node("h_karaoke_sing"); dismiss()            # гэг «спеть»

# ---------- S3: сачок ----------
node("take_pointer"); dismiss()
to_room("B")
shot("ap_04_room_b")
shot("round4_06_room_b")
node("see_net"); dismiss()
node("push_net"); dismiss()                  # вентиляция из офиса (A)
node("take_net"); dismiss()
add(op="combine", a="net", b="pointer"); dismiss()
add(op="assert_item", id="longnet")

# ---------- S3.5: осмотр подсобки (герринги B) ----------
for hn in ["h_boiler", "h_sink_valve", "h_extinguisher"]:
    if hn in site and site[hn][0] == "B":
        node(hn); dismiss()

# ---------- S4: карта из аквариума ----------
to_zoom("zoom_aquarium")
node("h_fish_poke"); dismiss()
node("fish_card"); dismiss()
add(op="assert_item", id="card")
shot("ap_05_aquarium")
dismiss(); add(op="esc"); cur = "A"
add(op="rmb_item", id="card")
add(op="close_reader")

# ---------- S5: ёлка — ключик и подарок ----------
to_zoom("zoom_tree")
node("take_key_toy"); dismiss()
node("take_gift"); dismiss()
add(op="close_reader")                       # авто-открытка
add(op="assert_item", id="hundred")

# ---------- S6: ПК — негатив, код, доки ----------
to_zoom("zoom_pc")
shot("round4_03_zoom_pc_saver")              # скринсейвер (до разблокировки)
add(op="click_hs", id="hs_z_screen")         # кейпад
add(op="assert_widget", kind="keypad")
add(op="code", node="pc_unlock", value="0000"); dismiss(); neg("pc_code_0000")
add(op="assert_not_flag", f="pc_on")
add(op="code", node="pc_unlock"); dismiss()
add(op="assert_flag", f="pc_on")
add(op="click_hs", id="hs_z_screen")         # рабочий стол
add(op="assert_widget", kind="pc")
shot("ap_06_pc_desktop")
for i in range(1, 6):                        # 5 доков
    add(op="click", x=700, y=170 + (i - 1) * 62 + 26)
    add(op="close_reader")
add(op="click", x=1700, y=900, btn=2)        # закрыть виджет

# ---------- S7: тумба Иры — негатив, код, реестр-гэг ----------
to_zoom("zoom_drawer_keypad")
add(op="click_hs", id="hs_z_keypad")
add(op="assert_widget", kind="keypad")
shot("round4_05_keypad")                      # движковый кейпад с цифрами
add(op="code", node="ira_code", value="1111"); dismiss(); neg("ira_code_1111")
add(op="code", node="ira_code"); dismiss()
dismiss()                                    # (раунд 7) остаёмся в зуме тумбы
add(op="click_hs", id="hs_ira_drawer_out")   # реестр — теперь В ЗУМЕ тумбы
shot("ap_07_registry_gag")
add(op="close_reader")

# ---------- S8: форма СКУД ----------
to_zoom("zoom_pc")
add(op="click_hs", id="hs_z_screen")
add(op="assert_widget", kind="pc")
add(op="click", x=700, y=170 + 5 * 62 + 26)  # пункт 6: ФОРМА
add(op="assert_widget", kind="form")
shot("round4_04_form_skud")                   # форма СКУД
add(op="form", no="000000"); dismiss(); neg("form_000000")
add(op="assert_not_flag", f="card_active")
add(op="assert_widget", kind="form")         # форма жива, поле сброшено
add(op="form"); dismiss()
add(op="assert_flag", f="card_active")

# ---------- S9: верстак ----------
to_zoom("zoom_workbench")
node("open_workbench"); dismiss()
node("take_wrench"); dismiss()
add(op="assert_item", id="wrench")

# ---------- S10: стенд ----------
node("take_wheel"); dismiss()
to_zoom("zoom_bench")
node("install_wheel"); dismiss()
add(op="pump_early"); dismiss(); neg("pump_early")
add(op="bench_bad"); dismiss(); neg("bench_wrong_valve")
add(op="assert_bench_seq_len", n=0)
add(op="bench_seq"); dismiss()
add(op="bench_pumps"); dismiss()
shot("ap_08_bench_done")
node("take_collector"); dismiss()
dismiss(); add(op="esc"); cur = "B"
add(op="combine", a="collector", b="wrench"); dismiss()
add(op="assert_item", id="trikey")

# ---------- S11: щиток (ночь→день, ЁЛКА-гэг) ----------
to_room("A")
shot("ap_09_a_night_exit")
to_room("B")
node("open_panel"); dismiss()
to_zoom("zoom_panel")
shot("ap_10_panel")
add(op="breaker", i=1); add(op="wait", s=0.4); dismiss()   # ВВОД
add(op="assert_flag", f="power_on")
add(op="breaker", i=2); dismiss()                          # РОЗЕТКИ
add(op="assert_flag", f="sockets_on")
add(op="breaker", i=3); dismiss()                          # ЁЛКА (гэг)
add(op="breaker", i=4); dismiss()                          # СРВ (герринг)
add(op="breaker", i=6); dismiss()                          # мёртвый
dismiss(); add(op="esc"); cur = "B"

# ---------- S12: сейв/континью через реальный UI ----------
dismiss(); add(op="esc")                     # пауза
add(op="click", x=960, y=588)                # «Сохранить и выйти»
add(op="wait", s=0.4)
add(op="continue_game")                      # титул → ПРОДОЛЖИТЬ
add(op="wait", s=0.4); dismiss()
add(op="assert_flag", f="power_on")
add(op="assert_item", id="trikey")
cur = "B"
to_room("A")
shot("ap_11_a_day_garland")

# ---------- S13: копир + сигнализация ----------
node("copy_pass"); dismiss()
add(op="assert_item", id="copy")
to_zoom("zoom_alarm")
add(op="click_hs", id="hs_z_alarm_pad")
add(op="assert_widget", kind="keypad")
add(op="code", node="alarm_off", value="2222"); dismiss(); neg("alarm_2222")
add(op="code", node="alarm_off"); dismiss()
add(op="assert_flag", f="alarm_off")
shot("ap_12_alarm_off")
dismiss(); add(op="esc"); cur = "A"

# ---------- S14: кофе + валидол ----------
node("brew_coffee"); dismiss()
add(op="assert_item", id="coffee")
to_zoom("zoom_closet")
node("take_validol"); dismiss()
dismiss(); add(op="esc"); cur = "B"
add(op="combine", a="validol", b="coffee"); dismiss()
add(op="assert_flag", f="calm_down")

# ---------- S15: смазка + засов ----------
node("take_grease"); dismiss()
to_zoom("zoom_exit_door")
add(op="click_item", id="grease")     # выбрать смазку и применить на засов (нужен ещё разводник в инв.)
add(op="click_hs", id="hs_z_bolt")
add(op="wait", s=0.7); dismiss()
add(op="assert_flag", f="bolt_free")
shot("ap_13_bolt_open")

# ---------- S16: подсказка Предка (бейдж-чек) ----------
add(op="hint")
add(op="wait", s=0.35)
steps.append({"op": "shot_badge", "name": "ap_14_hint_badge", "v": "ПРЕДОК"})
shots.append("ap_14_hint_badge")
dismiss()

# ---------- S17: реликвии и корона ----------
node("relic_badge"); dismiss()
add(op="assert_item", id="relic_badge")
node("take_mop"); dismiss()
to_zoom("zoom_attic")
node("box_down"); add(op="wait", s=0.5); dismiss()
dismiss(); add(op="esc"); cur = "B"
node("open_box"); dismiss()
add(op="assert_item", id="relic_fez")
node("search_box_again"); dismiss()
add(op="assert_item", id="crown")
add(op="rmb_item", id="relic_fez")
add(op="wait", s=0.3)
shot("ap_15_crown_dialog")
dismiss()

# ---------- S18: финал ----------
node("reader_swipe"); dismiss()
add(op="assert_flag", f="reader_green")
to_zoom("zoom_exit_door")
add(op="click_hs", id="hs_z_door_push")
dismiss()
add(op="wait", s=0.5)
shot("ap_16_victory")
add(op="assert_steps_ge", n=40)
add(op="esc")
add(op="wait", s=0.4)
shot("ap_17_title_end")
add(op="quit")

# ---------- контроль ----------
herrings = {n["id"] for n in P["nodes"] if n.get("herring")}
clicked_h = set()
for st in steps:
    if st.get("op") == "click_hs":
        for hn, (v, hs) in site.items():
            if hs == st["id"] and hn in herrings:
                clicked_h.add(hn)
panel_h = {"h_br_elka", "h_br_srv", "h_br_rezerv"}
covered = clicked_h | panel_h  # щитковые кликаются оп-ом breaker
missed = herrings - covered
zooms_visited = {st["id"] for st in steps if st.get("op") == "click_hs"}
zoom_entries = {e[1] for e in entry.values()}
zoom_cov = {z for z, (v, hs, r) in entry.items()
            if any(st.get("op") == "click_hs" and st["id"] == hs for st in steps)}

assert len(shots) >= 14, "мало скринов"
assert len(negatives) >= 7, "мало негативов"
assert len(steps) >= 250, "мало шагов: %d" % len(steps)
assert len(zoom_cov) == len(S["zooms"]), "не все зумы: " + str(
    set(S["zooms"]) - zoom_cov)

json.dump({"steps": steps}, open("work/autoplay_full.json", "w",
          encoding="utf-8"), ensure_ascii=False, indent=1)
print("шагов=%d скринов=%d негативов=%d зумов=%d/12 герринги_пропущены=%s"
      % (len(steps), len(shots), len(negatives), len(zoom_cov),
         sorted(missed) if missed else "нет"))
