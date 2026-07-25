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
node("take_gift")
# (аудит С3) Единственная точка игры, где документ открывается САМ и поверх
# него сразу ложатся реплики (scene.doc_auto: take_gift → doc_postcard).
# Рисуется читалка, поверх — диалог; значит и ввод обязан идти сверху вниз.
# Открытка одностраничная, поэтому промах слоя виден сразу: клик, ушедший в
# читалку вместо реплики, закрывает её первым же нажатием — человек так и не
# успевает её прочитать.
add(op="assert_reader", open=True)
add(op="assert_dialog_over_reader")
dismiss()                                    # очередь гасим кликами…
add(op="assert_reader", open=True)           # …документ обязан их пережить
add(op="close_reader")                       # авто-открытка
add(op="assert_reader", open=False)
add(op="assert_item", id="hundred")
neg("reader_under_dialog")

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
# (аудит К1) пятый и шестой рычаги проверяются ПО ТЕКСТУ и в обе стороны:
# при потере null в разборе JSON карта схлопывалась до пяти элементов и
# клик по шестому клампился в пятый — оба клика давали один и тот же
# герринг, а гаунтлет этого не замечал. Подстроки берём из texts.json,
# в сценарий не зашиваем ничего, чего нет в данных.
_DEAD = TXT["breaker_dead"][0]["t"][:24]
_REZ = TXT["nodes"]["h_br_rezerv"]["do"][0]["t"][:24]
assert _DEAD != _REZ, "реплики пятого и шестого рычага неразличимы"
add(op="breaker", i=5)                                     # РЕЗЕРВ (герринг)
add(op="assert_line", sub=_REZ, nosub=_DEAD); dismiss()
add(op="breaker", i=6)                                     # мёртвый
add(op="assert_line", sub=_DEAD, nosub=_REZ); dismiss()
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
# (аудит С2) Метки идл-анимаций живут в state, но не сериализуются и не
# чистятся в deserialize — значит переживали и загрузку, и новую игру, а болт
# рисуется ПО МЕТКЕ, а не по флагу. Проверяем механизм с обеих сторон в
# единственной точке сценария, где метка заведомо свежая: сразу после клика
# она обязана стоять, через её длительность — обязана быть снята. Именно
# истечение и лечит видимый баг: пережить новую игру метка теперь не может
# физически. Сброс на старте/загрузке — вторая линия обороны, её смоук ниже.
add(op="assert_anim", m="_bolt_anim")
add(op="wait", s=0.7); dismiss()
add(op="assert_no_anim")
add(op="assert_flag", f="bolt_free")
shot("ap_13_bolt_open")

# ---------- S16: подсказка Предка (бейдж-чек) ----------
# (аудит В4) Бейдж-чеков должно быть минимум ДВА и на РАЗНЫХ спикеров:
# одиночная проверка «рамка стальная» проходит и на намертво залипшем
# портрете Предка. Пара «Предок → Лапидус» подряд доказывает именно смену.
add(op="hint")
add(op="wait", s=0.35)
add(op="assert_speaker", s="anc")
steps.append({"op": "shot_badge", "name": "ap_14_hint_badge", "v": "ПРЕДОК"})
shots.append("ap_14_hint_badge")
dismiss()

# ---------- S17: реликвии и корона ----------
node("relic_badge")
assert TXT["nodes"]["relic_badge"]["do"][0]["s"] == "lap", "спикер реликвии сменился"
add(op="wait", s=0.35)
add(op="assert_speaker", s="lap")
steps.append({"op": "shot_badge", "name": "ap_14b_relic_badge", "v": "ЛАПИДУС"})
shots.append("ap_14b_relic_badge")
dismiss()
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
# (аудит В3) терминальное условие утверждается явно: без этого шага op quit
# откажется печатать успех — прогон, оборвавшийся до финала, обязан падать
add(op="assert_flag", f="victory")
add(op="assert_steps_ge", n=40)
add(op="esc")
add(op="wait", s=0.4)
shot("ap_17_title_end")

# ---------- S19: вторая игра в том же процессе (аудит С2) ----------
# Гаунтлет за всю историю ни разу не начинал игру заново в одном процессе —
# поэтому и не видел, что часть состояния переживает «Новую игру». Сегмент
# дешёвый и ловит целый класс таких протечек: если что-то из прошлого прогона
# осталось, второй старт начнётся не с нуля.
add(op="start_game")
add(op="wait", s=0.4); dismiss()
add(op="assert_no_anim")                     # метки не унаследованы
add(op="assert_not_flag", f="bolt_free")     # прогресс не унаследован
add(op="assert_not_flag", f="victory")
add(op="assert_no_item", id="crown")         # карманы пусты
add(op="assert_view", id="A")                # и мы в стартовой комнате
add(op="quit")

# ---------- пост-проход: автоматические assert_speaker (аудит В4) ----------
# Канон «портрет = спикер» держался на трёх ручных утверждениях, поставленных
# руками в трёх местах. Это не сеть, а три гвоздя. Здесь утверждение спикера
# навешивается на КАЖДЫЙ пригодный клик автоматически и выводится из данных,
# так что рассинхрон «движок сказал одним ртом, данные — другим» ловится сразу.
#
# Пригодность считается консервативно: утверждаем только там, где спикер
# ОДИН И ТОТ ЖЕ во всех ветках, которые движок вообще способен запросить на
# пути «простого узлового хотспота» (см. ui.lua: already / fail / do). Тогда
# утверждение верно независимо от того, сработал узел, уже сработал или
# отказал, — и не превращается в предсказание игрового состояния.
#
# Пустота очереди перед кликом не предполагается, а доказана: op click_hs
# (autoplay.lua) сам сначала гасит активный диалог и только потом жмёт, так
# что сразу после клика в очереди лежат ровно реплики этого клика. Ветка
# «предмет не подошёл» (T.item_wrong) целиком за Лапидусом, поэтому даже
# залипший выбор предмета не ломает утверждение на lap-узлах.
HS_ALL = {}
for _v in list(S["rooms"].values()) + list(S["zooms"].values()):
    for _h in _v["hotspots"]:
        assert _h["id"] not in HS_ALL, "дубль id хотспота: " + _h["id"]
        HS_ALL[_h["id"]] = _h

_SPECIAL = ("widget", "goto", "goto_room", "doc", "bench")


def _plain_node(h):
    """хотспот, который идёт по ветке `if h.node then` в ui.lua"""
    return h.get("node") and not any(h.get(k) for k in _SPECIAL)


def _node_speaker(nid):
    """единственный спикер узла или None, если ветки расходятся/пусты"""
    v = TXT["nodes"].get(nid)
    if not v:
        return None
    sp = set()
    for key in ("do", "already"):
        if key in v:
            if not v[key]:
                return None          # пустая ветка → очередь может остаться пустой
            sp.add(v[key][0]["s"])
    if "fail" in v:
        if not v["fail"]:
            return None
        sp.add(v["fail"][0]["s"])
    else:
        sp.add("lap")                # движковый фолбэк «Пока не выходит.» — Лапидус
    return sp.pop() if len(sp) == 1 else None


_seen_hs = set()
_auto = []
_out = []
for _i, _st in enumerate(steps):
    _out.append(_st)
    if _st.get("op") != "click_hs":
        continue
    _first = _st["id"] not in _seen_hs
    _seen_hs.add(_st["id"])
    if not _first or _st.get("btn") == 2:
        continue
    _h = HS_ALL.get(_st["id"])
    if not _h or not _plain_node(_h):
        continue
    if NODES.get(_h["node"], {}).get("herring"):
        continue                     # герринги идут своей веткой fire_herring
    _sp = _node_speaker(_h["node"])
    if not _sp:
        continue
    _nxt = steps[_i + 1] if _i + 1 < len(steps) else {}
    if _nxt.get("op") == "assert_speaker":
        continue                     # уже утверждено вручную — не дублируем
    _out.append({"op": "assert_speaker", "s": _sp})
    _auto.append((_st["id"], _h["node"], _sp))
steps = _out
assert len(_auto) >= 12, "автоспикер-утверждений слишком мало: %d" % len(_auto)
# Рты считаются по ВСЕМУ сценарию, а не по автопроходу: в данных ни один узел
# не открывается репликой Предка (проверено), поэтому автоутверждения всегда
# лягут на Лапидуса, а Предок утверждается там, где он и говорит, — на подсказке.
# Если дизайнер отдаст узел Предку, автопроход сам выпишет s="anc".
_mouths = {st["s"] for st in steps if st.get("op") == "assert_speaker"}
assert len(_mouths) >= 2, "спикер утверждается только для одного рта: " + str(_mouths)

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
print("автоспикер: +%d утверждений, всего по сценарию %d на рты [%s]"
      % (len(_auto),
         sum(1 for st in steps if st.get("op") == "assert_speaker"),
         ", ".join(sorted(_mouths))))

# ---------- смок в «кривом» разрешении ----------
# Последним шагом конвейера (MIGRATION §3) гоняется сценарий work/ap_smoke.json —
# проверить letterbox: если пересчёт экранных координат в мировые врёт, промахиваются
# вообще все клики, и поймать это можно только на окне с другим соотношением сторон.
# Размер окна задаётся ИЗНУТРИ сценария (op resize, три геометрии подряд), а не
# ключом xvfb: X разрешает окну быть больше экрана, поэтому прежний «--screen
# 1536x864» окно не ограничивал и смок годами шёл в тех же 1920×1080, что и
# основной гаунтлет, то есть не проверял ровно то, ради чего стоит в конвейере.
#
# Раньше этот файл лежал в work/ РУКАМИ. Каталог не под контролем версий, так что
# на чистом клоне шага конвейера просто не существовало: команда падала с «нет
# сценария». Сам файл при этом успел протухнуть — он заканчивался op quit без
# победы, а после аудита В3 это запрещено, то есть даже найденный он бы не прошёл.
# Поэтому смок теперь ВЫВОДИТСЯ ИЗ ПОЛНОГО СЦЕНАРИЯ и разойтись с игрой не может:
# те же шаги, тот же финал, только без скриншотов.
#
# Скрины выброшены по двум причинам. Пиксельные гейты считают кадры при 1920×1080,
# и перезапись их кадрами «кривых» размеров испортила бы gates.py на следующем прогоне; а
# сам смок проверяет не картинку, а попадание кликов. Два кадра с бейджем оставлены
# намеренно: op quit требует не меньше двух проверок смены портрета (тот же В3), и
# без них финал бы не засчитался. Их имена получают префикс smoke_, чтобы не
# затирать кадры основного прогона.
smoke = [st for st in steps if st.get("op") != "shot"]
smoke = [dict(st, name="smoke_" + st["name"]) if st.get("op") == "shot_badge"
         else st for st in smoke]

# Геометрии подобраны так, чтобы полосы легли в обе стороны и масштаб выходил
# дробным: letterbox всегда вписывает мир по МЕНЬШЕЙ стороне, поэтому одна из
# полос по построению нулевая — одним размером обе не проверить.
#   1600×1000 — масштаб 0.8333, полосы сверху/снизу (oy=50)
#   1920×864  — масштаб 0.8,    полосы слева/справа (ox=192)
#   1500×900  — масштаб 0.78125, полоса дробная (oy=28.125) — проверка округления
# Размер меняется на dismiss_all: это спокойные точки сценария, где ничего не
# выбрано и ничего не летит, а сам op ничего в игре не трогает, кроме окна.
GEOM = [(1600, 1000), (1920, 864), (1500, 900)]
_quiet = [i for i, st in enumerate(smoke) if st.get("op") == "dismiss_all"]
assert len(_quiet) >= len(GEOM) * 2, "мало спокойных точек для смены размера"
_at = {}
for k, g in enumerate(GEOM):
    # 10 %, 40 %, 70 % длины — прогон целиком идёт в «кривых» размерах
    _at[_quiet[int(len(_quiet) * (0.10 + 0.30 * k))]] = g
_smoke = []
for i, st in enumerate(smoke):
    _smoke.append(st)
    if i in _at:
        w, h = _at[i]
        _smoke.append({"op": "resize", "w": w, "h": h})
smoke = _smoke

_badges = sum(1 for st in smoke if st.get("op") == "shot_badge")
assert _badges >= 2, "в смоке %d кадров с бейджем — op quit не засчитает финал" % _badges
assert smoke[-1]["op"] == "quit", "смок обязан заканчиваться штатным op quit"
assert sum(1 for st in smoke if st.get("op") == "resize") == len(GEOM), \
    "не все смены размера попали в смок"
json.dump({"steps": smoke}, open("work/ap_smoke.json", "w",
          encoding="utf-8"), ensure_ascii=False, indent=1)
print("смок letterbox: шагов=%d, размеров %s, кадров с бейджем %d"
      % (len(smoke), " → ".join("%dx%d" % g for g in GEOM), _badges))
