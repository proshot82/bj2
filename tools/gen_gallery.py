#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор ГАЛЕРЕЙНОГО автоплей-сценария → work/gallery_full.json.

Одноразовый инструмент для авторской ревизии: строит один сквозной проход
по игре (на базе того же солвера навигации, что и gen_autoplay.py) и снимает
ВСЕ значимые экраны в логическом порядке прохождения:
  титул · пауза/настройки · комната A ночь (плашка целей развёрнута/свёрнута) ·
  каждый из 12 зумов в актуальном состоянии (ПК — и скринсейвер, и включённый) ·
  все 17 документов-читалок (по первой странице) · виджеты (кейпад тумбы,
  форма СКУД, ПК-интерфейс) · комнаты B ночь, A/B день · открытая дверь щитовой
  ночь и день · открытые вент-решётки · включённая гирлянда · диалог с Предком ·
  инвентарь (3+ предметов и с выбранным предметом) · момент применения предмета ·
  победа/эпилог · финальный титул.
  (р.25) Сенсорный экран: кольцо долгого касания, подписи под палец на реплике,
  читалке, форме СКУД (с экранными цифрами), легенде стенда и плашке победы —
  кадры «sensor_*»: тот же экран, но последним вводом было касание.
  (р.26) Телефон вертикально: кадр «лёжа» в окне 960×2080.

Скрины именуются "NN_имя" (двузначный номер = порядок в галерее). Коды в файл
НЕ пишутся (op "code"/"form" без value — autoplay берёт ответ на рантайме).
Запуск: love . --autoplay work/gallery_full.json  → work/shots/NN_*.png.
"""
import json, sys

S = json.load(open("design/scene.json", encoding="utf-8"))
P = json.load(open("design/puzzles.json", encoding="utf-8"))
TXT = json.load(open("design/texts.json", encoding="utf-8"))
NODES = {n["id"]: n for n in P["nodes"]}
ITEMS = set(TXT["item_names"].keys())
DOCS = TXT["docs"]

def item_gated(nid):
    n = NODES.get(nid)
    if not n or n["type"] != "action":
        return None
    for nd in n["needs"]:
        if nd in ITEMS:
            return nd
    return None

site = {}
entry = {}
room_of = {z: S["zooms"][z]["room"] for z in S["zooms"]}

def scan(view_id, hotspots, is_room):
    for h in hotspots:
        if h.get("node") and h["node"] not in site:
            site[h["node"]] = (view_id, h["id"])
        if h.get("goto"):
            g = h["goto"]
            if g not in entry or (is_room and not entry[g][2]):
                entry[g] = (view_id, h["id"], is_room)

for rid, room in S["rooms"].items():
    scan(rid, room["hotspots"], True)
for zid, z in S["zooms"].items():
    scan(zid, z["hotspots"], False)

def need(n):
    if n not in site:
        sys.exit("FAIL: нет точки для узла " + n)
    return site[n]

parts = [[]]
cur = "TITLE"
gallery = []
_docs_shot = set()
_zooms_shot = set()
_n = 0

def add(**kw):
    parts[-1].append(dict(kw))

def dismiss():
    add(op="dismiss_all")

def shot(name, doc=None, zoom=None):
    global _n
    _n += 1
    full = "%02d_%s" % (_n, name)
    add(op="shot", name=full)
    gallery.append((_n, full))
    if doc:
        _docs_shot.add(doc)
    if zoom:
        _zooms_shot.add(zoom)

def to_room(r):
    global cur
    if cur == r:
        return
    if cur in room_of:
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
    if ev in ("A", "B"):
        to_room(ev)
    else:
        # (раунд 19) вход только из родительского зума — сперва до родителя
        to_zoom(ev)
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
        add(op="click_item", id=gi)
    add(op="click_hs", id=hs, btn=btn)

def read_hs(hs_id, view, doc_id, name, btn=1):
    goto_view(view)
    add(op="click_hs", id=hs_id, btn=btn)
    add(op="wait", s=0.15)
    shot(name, doc=doc_id)
    add(op="close_reader")

def read_item(item_id, doc_id, name):
    add(op="rmb_item", id=item_id)
    add(op="wait", s=0.15)
    shot(name, doc=doc_id)
    add(op="close_reader")

def pc_doc(idx, doc_id, name):
    add(op="click", x=700, y=170 + (idx - 1) * 62 + 26)
    add(op="wait", s=0.15)
    shot(name, doc=doc_id)
    add(op="close_reader")

# ===================== ПРОХОД =====================
add(op="wait", s=0.6)
shot("titul")
add(op="start_game"); cur = "A"
dismiss()

node("survey_door"); dismiss()
shot("komnata_A_noch_celi")
add(op="click", x=185, y=140)
add(op="wait", s=0.1)
shot("komnata_A_noch_celi_min")

add(op="esc"); add(op="wait", s=0.1)
shot("pauza")
add(op="click", x=960, y=492)
add(op="wait", s=0.1)
shot("nastroyki")
add(op="click", x=960, y=722)
add(op="click", x=960, y=396)
add(op="wait", s=0.15)

to_zoom("zoom_exit_door")
shot("zoom_exit_door_noch", zoom="zoom_exit_door")
to_room("A")

# (р.25) сенсорный экран: палец лежит в пустом месте — кольцо удержания
# (кадр посреди удержания), потом реплика и бумага, открытые касанием
add(op="finger_down", empty=True)
add(op="wait", s=0.3)                        # кольцо растёт, после ПКМ замкнуто до отпускания
shot("sensor_kolco_uderzhaniya")
add(op="finger_up")
add(op="tap", id="hs_window")                # реплика по касанию (окно — герринг)
add(op="wait", s=3.0)
shot("sensor_replika")
dismiss()
add(op="tap", id="hs_karaoke")              # бумага без ответов головоломок
add(op="wait", s=0.15)
shot("sensor_chitalka")
add(op="hold", empty=True)                   # долгое касание закрывает бумагу
# (р.26) телефон вертикально: кадр «лёжа» (снег обязан остаться в стёклах)
add(op="touch_device", on=True)
add(op="resize", w=960, h=2080)
add(op="assert_rotated", on=True)
add(op="wait", s=0.3)
shot("sensor_telefon_vertikalno")
add(op="resize", w=1920, h=1080, restore=True)
add(op="touch_device", on=False)
add(op="assert_rotated", on=False)
# подписи вернутся к мыши сами — на первом же клике мышью (read_hs ниже)

read_hs("hs_poster_ot", "A", "doc_poster", "doc_plakat_ot")
read_hs("hs_calendar", "A", "doc_calendar", "doc_kalendar")
read_hs("hs_karaoke", "A", "doc_karaoke", "doc_karaoke")

node("h_window"); dismiss()
node("take_ruler"); dismiss()
node("pry_drawer"); dismiss()
to_zoom("zoom_lap_drawer")
shot("zoom_yaschik_stola", zoom="zoom_lap_drawer")
node("take_handle"); dismiss()
node("search_drawer_again"); dismiss()
add(op="assert_item", id="relic_yatagan")
node("open_utility"); dismiss()
add(op="assert_flag", f="utility_open")

to_room("A")
shot("dver_schitovoy_noch")

node("take_pointer"); dismiss()
to_room("B")
shot("komnata_B_noch")
read_hs("hs_mop", "zoom_closet", "doc_mop_tag", "doc_birka_shvabra", btn=2)  # (р9) швабра в зуме шкафа
node("see_net"); dismiss()
node("push_net"); dismiss()
add(op="assert_flag", f="vents_open")

to_room("A")
shot("ventreshetki_otkryty")
to_room("B")
node("take_net"); dismiss()
add(op="combine", a="net", b="pointer"); dismiss()
add(op="assert_item", id="longnet")

to_zoom("zoom_aquarium")
shot("zoom_akvarium", zoom="zoom_aquarium")
node("h_fish_poke"); dismiss()
node("fish_card"); dismiss()
add(op="assert_item", id="card")
to_room("A")
read_item("card", "doc_card", "doc_propusk")

to_zoom("zoom_tree")
shot("zoom_yolka", zoom="zoom_tree")
read_hs("hs_z_santa", "zoom_tree", "doc_santa", "doc_birki_santa")
node("take_key_toy"); dismiss()
node("take_gift")
add(op="wait", s=0.2)
shot("doc_otkrytka", doc="doc_postcard")
add(op="close_reader")
add(op="assert_item", id="hundred")

to_zoom("zoom_pc")
shot("zoom_pc_skrinsever", zoom="zoom_pc")
read_hs("hs_z_sticker", "zoom_pc", "doc_sticker", "doc_stiker")
add(op="click_hs", id="hs_z_screen")
add(op="assert_widget", kind="keypad")
add(op="code", node="pc_unlock"); dismiss()
add(op="assert_flag", f="pc_on")
add(op="click_hs", id="hs_z_screen")
add(op="assert_widget", kind="pc")
shot("widget_pc_rabstol")
_zooms_shot.add("zoom_pc")
pc_doc(1, "doc_chat", "doc_chat_otdela")
pc_doc(2, "doc_order", "doc_prikaz7")
pc_doc(3, "doc_about", "doc_o_kompanii")
pc_doc(4, "doc_dict", "doc_slovar_sokr")
pc_doc(5, "doc_skud_blank", "doc_forma_skud_blank")
add(op="click", x=700, y=170 + 5 * 62 + 26)
add(op="assert_widget", kind="form")
shot("widget_forma_skud")
dismiss()
add(op="tap", x=815, y=402)                  # (р.25) касание поля «№ карты»
add(op="wait", s=0.1)
shot("sensor_forma_skud")
add(op="form"); dismiss()
add(op="assert_flag", f="card_active")

# ---- ГРАНИЦА ЧАСТЕЙ: сейв→выход, вторая часть с ПРОДОЛЖИТЬ ----
def split_here():
    global cur
    to_room("A")
    add(op="save"); add(op="quit")
    parts.append([])
    add(op="wait", s=0.6); add(op="continue_game")
    add(op="wait", s=0.5); dismiss(); dismiss()
    cur = "A"
split_here()

to_zoom("zoom_drawer_keypad")
shot("zoom_keypad_tumba", zoom="zoom_drawer_keypad")
add(op="click_hs", id="hs_z_keypad")
add(op="assert_widget", kind="keypad")
shot("widget_keypad_tumba")
add(op="code", node="ira_code"); dismiss()
add(op="assert_flag", f="drawer_ira_open")
# (раунд 19, зам.3) открытый ящик Иры — полнокадровый зум по схеме Лапидуса
add(op="click_hs", id="hs_ira_drawer_out")
cur = "zoom_ira_drawer"
add(op="wait", s=0.15)
shot("zoom_yaschik_iry", zoom="zoom_ira_drawer")
add(op="click_hs", id="hs_z_registry")
add(op="wait", s=0.15)
shot("doc_reestr", doc="doc_registry")
add(op="close_reader")
add(op="click_hs", id="hs_z_ira_back")     # явный возврат к тумбе
cur = "zoom_drawer_keypad"

to_zoom("zoom_workbench")
shot("zoom_verstak", zoom="zoom_workbench")
read_hs("hs_z_journal", "zoom_workbench", "doc_journal", "doc_zhurnal")
node("open_workbench"); dismiss()
cur = "zoom_wb_drawer"                     # (р.22) enter_zoom открыл кадр сам
# (раунд 19, зам.3) ящик верстака — полнокадровый зум, ключ впечатан в арт
to_zoom("zoom_wb_drawer")
shot("zoom_yaschik_verstaka", zoom="zoom_wb_drawer")
add(op="click_hs", id="hs_z_wb_wrench"); dismiss()
cur = "B"                                  # leave_zoom закрыл кадр сам
add(op="assert_item", id="wrench")

to_room("B")
shot("inventar_predmety")
add(op="click_item", id="wrench")
add(op="wait", s=0.1)
shot("inventar_vybran")
add(op="click_item", id="wrench")

node("take_wheel"); dismiss()
to_zoom("zoom_bench")
shot("zoom_stend", zoom="zoom_bench")
add(op="tap", empty=True)                    # (р.25) касание пустого места
add(op="wait", s=0.1)
shot("sensor_stend")
read_hs("hs_z_note", "zoom_bench", "doc_bench_note", "doc_listok_stenda")
node("install_wheel"); dismiss()
add(op="bench_seq"); dismiss()
add(op="bench_pumps"); dismiss()
node("take_collector"); dismiss()
to_room("B")
add(op="combine", a="collector", b="wrench"); dismiss()
add(op="assert_item", id="trikey")

node("open_panel"); dismiss()
to_zoom("zoom_panel")
shot("zoom_schitok", zoom="zoom_panel")
read_hs("hs_z_schema", "zoom_panel", "doc_schema", "doc_shema_schitka")
add(op="breaker", i=1); add(op="wait", s=0.4); dismiss()
add(op="assert_flag", f="power_on")
add(op="breaker", i=2); dismiss()
add(op="breaker", i=3); dismiss()
add(op="assert_flag", f="garland_on")
add(op="breaker", i=4); dismiss()
to_room("B")

shot("komnata_B_den")
to_room("A")
shot("komnata_A_den_girlyanda")
add(op="wait", s=0.1)
shot("dver_schitovoy_den")

node("copy_pass"); dismiss()
add(op="assert_item", id="copy")
to_zoom("zoom_alarm")
shot("zoom_signalizaciya", zoom="zoom_alarm")
add(op="click_hs", id="hs_z_alarm_pad")
add(op="assert_widget", kind="keypad")
add(op="code", node="alarm_off"); dismiss()
add(op="assert_flag", f="alarm_off")
to_room("A")

node("brew_coffee"); dismiss()
to_zoom("zoom_closet")
shot("zoom_shkaf", zoom="zoom_closet")
node("take_validol"); dismiss()
to_room("B")
add(op="combine", a="validol", b="coffee"); dismiss()

node("take_grease"); dismiss()
to_zoom("zoom_exit_door")
add(op="click_item", id="grease")
add(op="click_hs", id="hs_z_bolt")
add(op="wait", s=0.35)
shot("primenenie_smazki")
add(op="wait", s=0.5); dismiss()
add(op="assert_flag", f="bolt_free")
to_room("A")

add(op="hint"); add(op="wait", s=0.35)
shot("dialog_predok")
dismiss()

node("relic_badge"); dismiss()
node("take_mop"); dismiss()
to_zoom("zoom_attic")
shot("zoom_cherdak", zoom="zoom_attic")
node("box_down"); add(op="wait", s=0.5); dismiss()
to_room("B")
node("open_box"); dismiss()
node("search_box_again"); dismiss()
add(op="assert_item", id="crown")

node("reader_swipe"); dismiss()
add(op="assert_flag", f="reader_green")
to_zoom("zoom_exit_door")
add(op="click_hs", id="hs_z_door_push")
dismiss()
# (р.25) касание сразу после эпилога плашку не пропускает (секунда защиты от
# проскока) и переводит подписи под палец; пробел возвращает их мыши
add(op="tap", x=960, y=900)
add(op="wait", s=0.3)
shot("sensor_pobeda")
add(op="key", k="space")
add(op="wait", s=0.3)
shot("pobeda_epilog")
add(op="assert_steps_ge", n=40)
add(op="esc"); add(op="wait", s=0.4)
shot("titul_final")
add(op="quit")

# ===================== КОНТРОЛЬ =====================
all_docs = set(DOCS.keys())
missed_docs = all_docs - _docs_shot
all_zooms = set(S["zooms"].keys())
missed_zooms = all_zooms - _zooms_shot
assert not missed_docs, "НЕ сняты доки: " + str(sorted(missed_docs))
assert not missed_zooms, "НЕ сняты зумы: " + str(sorted(missed_zooms))
assert len(gallery) >= 45, "мало кадров: %d" % len(gallery)

nsteps = sum(len(pp) for pp in parts)
for i, pp in enumerate(parts, 1):
    json.dump({"steps": pp}, open("work/gallery_p%d.json" % i, "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)
print("галерея: кадров=%d доков=%d/%d зумов=%d/%d частей=%d шагов=%d" % (
    len(gallery), len(_docs_shot), len(all_docs),
    len(_zooms_shot), len(all_zooms), len(parts), nsteps))
for i, pp in enumerate(parts, 1):
    print("  часть %d: %d шагов" % (i, len(pp)))
for nnn, nm in gallery:
    print("  " + nm)
