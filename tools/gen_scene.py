#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор design/scene.json v2 для «Латунный янычар 2.0».
Координаты сняты с осмотра арта (сетки/кропы, work/inspect/).
Правая треть офиса структурно расходится день/ночь -> rect_day/pos_day.
"""
import json, os

def HS(id, rect, cursor="act", **kw):
    d = {"id": id, "rect": rect, "cursor": cursor}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d

def CO(img, pos, scale=1.0, z=10, **kw):
    d = {"img": img, "pos": pos, "scale": scale, "z": z}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d

# ============================== ОФИС (A) ==============================
A_hotspots = [
    # --- левая стабильная зона ---
    HS("hs_window", [0, 60, 330, 540], node="h_window", name="Окно",
       look=True),
    HS("hs_sofa_под", [30, 800, 300, 130], node="relic_badge", name="Под диваном",
       fail_without=["longnet"]),
    HS("hs_sofa", [0, 470, 350, 320], name="Диван", look=True),
    HS("hs_karaoke", [255, 470, 110, 90], doc="doc_karaoke", name="Караоке-список",
       cursor="zoom"),
    HS("hs_karaoke_sing", [255, 470, 110, 90], node="h_karaoke_sing",
       name="Спеть", show_on=["read:doc_karaoke"]),
    HS("hs_table_mugs", [160, 560, 300, 200], name="Журнальный столик", look=True),
    HS("hs_tree", [280, 170, 220, 420], goto="zoom_tree", name="Ёлка", cursor="zoom"),
    HS("hs_tree_base", [300, 590, 200, 80], goto="zoom_tree", name="Под ёлкой",
       cursor="zoom"),
    HS("hs_calendar", [498, 186, 96, 148], doc="doc_calendar", name="Календарь",
       cursor="zoom"),
    HS("hs_flipchart", [606, 146, 178, 190], name="Флипчарт", look=True),
    HS("hs_lap_desk", [480, 340, 220, 130], name="Стол Лапидуса", look=True),
    HS("hs_ruler", [560, 350, 110, 44], node="take_ruler", name="Линейка",
       hide_on=["done:take_ruler"]),
    HS("hs_phone", [648, 322, 60, 48], node="h_phone", name="Телефон"),
    HS("hs_lap_drawer", [636, 420, 80, 210], goto="zoom_lap_drawer", name="Ящик стола",
       cursor="zoom", needs_flag="drawer_pried"),
    HS("hs_lap_drawer_pry", [636, 420, 80, 210], node="pry_drawer",
       name="Запертый ящик", hide_on=["drawer_pried"]),
    HS("hs_aquarium", [880, 270, 285, 130], goto="zoom_aquarium", name="Аквариум",
       cursor="zoom"),
    HS("hs_aq_tumba", [878, 395, 285, 240], name="Тумба аквариума", look=True),
    HS("hs_coffee_machine", [1150, 296, 96, 100], node="brew_coffee",
       name="Кофемашина"),
    HS("hs_wheel_wall", [1156, 196, 90, 90], node="take_wheel", name="Маховик-«экспонат»",
       hide_on=["done:take_wheel"]),
    HS("hs_vent_office", [1182, 92, 120, 76], node="push_net", name="Вентрешётка"),
    HS("hs_wardrobe", [1180, 170, 172, 450], name="Шкаф-гардероб", look=True),
    HS("hs_copier", [1326, 348, 138, 216], node="copy_pass", name="Копир",
       hide_on=["done:copy_pass"]),
    HS("hs_ira_desk", [940, 460, 420, 200], name="Стол Иры", look=True),
    HS("hs_ira_pc", [1090, 400, 240, 200], goto="zoom_pc", name="Компьютер",
       cursor="zoom"),
    HS("hs_ira_tumba", [1030, 620, 150, 180], goto="zoom_drawer_keypad",
       name="Кодовая тумба", cursor="zoom"),
    HS("hs_ira_drawer_out", [1005, 610, 200, 90], doc="doc_registry",
       name="Открытый ящик", show_on=["drawer_ira_open"], cursor="zoom"),
    HS("hs_kpi_board", [1740, 140, 180, 300], name="KPI-доска", look=True,
       rect_day=[1795, 175, 125, 290]),
    HS("hs_pointer", [1748, 408, 164, 44], node="take_pointer", name="Указка",
       hide_on=["done:take_pointer"],
       rect_day=[1800, 445, 120, 44]),
    # --- правая зона: рассинхрон день/ночь, всюду rect_day ---
    HS("hs_exit_sign", [1487, 112, 124, 76], name="Табличка EXIT", look=True,
       rect_day=[1544, 88, 122, 84]),
    HS("hs_intercom", [1414, 424, 44, 172], node="h_intercom", name="Домофон",
       rect_day=[1446, 424, 44, 170]),
    HS("hs_main_door", [1490, 200, 128, 560], goto="zoom_exit_door",
       name="Главная дверь", cursor="zoom", show_on=["surveyed"],
       rect_day=[1524, 196, 148, 560]),
    HS("hs_main_door_survey", [1490, 200, 128, 560], node="survey_door",
       name="Осмотреть дверь", hide_on=["surveyed"],
       rect_day=[1524, 196, 148, 560]),
    HS("hs_poster_ot", [1642, 232, 106, 104], doc="doc_poster",
       name="Плакат по охране труда", cursor="zoom",
       rect_day=[1680, 242, 94, 106]),
    HS("hs_alarm", [1612, 420, 46, 192], goto="zoom_alarm", name="Сигнализация",
       cursor="zoom", rect_day=[1598, 382, 60, 180]),
    HS("hs_util_door", [1662, 408, 98, 386], node="open_utility",
       name="Дверь щитовой", hide_on=["utility_open"],
       rect_day=[1672, 414, 120, 380]),
    HS("hs_util_door_go", [1662, 408, 98, 386], goto_room="B",
       name="В щитовую", cursor="move", show_on=["utility_open"],
       rect_day=[1672, 414, 120, 380]),
    HS("hs_util_shaft", [1678, 598, 44, 50], name="Квадратный шток", look=True,
       hide_on=["utility_open"], rect_day=[1713, 600, 50, 56]),
    HS("hs_reader", [1758, 668, 46, 52], node="reader_swipe", name="Считыватель",
       rect_day=[1848, 694, 44, 72]),
    HS("hs_extinguisher", [1832, 328, 88, 234], node="h_extinguisher",
       name="Огнетушитель", rect_day=[1876, 388, 44, 196]),
]
A_cutouts = [
    CO("cutouts/st_ruler_on_desk.png", [563, 352], 0.72, z=20,
       hide_on=["done:take_ruler"]),
    CO("cutouts/st_pointer_on_board.png", [1750, 410], 1.0, z=20,
       hide_on=["done:take_pointer"],
       pos_day=[1802, 447]),
    CO("cutouts/st_wheel_wall.png", [1158, 198], 0.52, z=20,
       hide_on=["done:take_wheel"]),
    CO("cutouts/st_vent_open_office.png", [1180, 96], 0.56, z=20,
       show_on=["vents_open"]),
    CO("cutouts/st_gift.png", [400, 590], 0.62, z=20, hide_on=["done:take_gift"]),
    CO("cutouts/st_ira_drawer_open.png", [1008, 618], 0.40, z=20,
       show_on=["drawer_ira_open"]),
    CO("cutouts/st_garland_on.png", [268, 205], 0.60, z=30,
       show_on=["garland_on"], glow=True),
    CO("cutouts/st_led_alarm_on.png", [1626, 428], 0.34, z=25,
       hide_on=["alarm_off"], pos_day=[1616, 388]),
    CO("cutouts/st_led_alarm_off.png", [1626, 428], 0.34, z=25,
       show_on=["alarm_off"], pos_day=[1616, 388]),
    CO("cutouts/st_led_reader_off.png", [1766, 672], 0.42, z=25,
       hide_on=["power_on"], pos_day=[1856, 700]),
    CO("cutouts/st_led_reader_red.png", [1766, 672], 0.42, z=25,
       show_on=["power_on"], hide_on=["reader_green"], pos_day=[1856, 700]),
    CO("cutouts/st_led_reader_green.png", [1766, 672], 0.42, z=25,
       show_on=["reader_green"], pos_day=[1856, 700]),
    CO("cutouts/st_util_door_open.png", [1622, 372], 0.50, z=15,
       show_on=["utility_open"], pos_day=[1642, 380]),
    CO("cutouts/st_door_open_final.png", [1476, 178], 0.62, z=40,
       show_on=["victory"], pos_day=[1512, 176]),
    # идл: рыбка в аквариуме на вайде (мелкая), пар над кофе
    CO("cutouts/st_fish_a.png", [952, 412], 0.36, z=18, idle="fish_wide",
       frames=["cutouts/st_fish_a.png", "cutouts/st_fish_b.png"]),
    CO("cutouts/st_steam_a.png", [1176, 236], 0.5, z=22, idle="steam",
       frames=["cutouts/st_steam_a.png", "cutouts/st_steam_b.png",
               "cutouts/st_steam_c.png"], show_on=["sockets_on"]),
]
A_arrows = [
    {"dir": "right", "rect": [1860, 420, 60, 240], "goto_room": "B",
     "needs_flag": "utility_open"},
]

# ============================ ПОДСОБКА (B) ============================
B_hotspots = [
    HS("hs_b_door_office", [0, 60, 205, 940], goto_room="A", name="Дверь в офис",
       cursor="move"),
    HS("hs_panel", [282, 188, 196, 436], goto="zoom_panel", name="Электрощиток",
       cursor="zoom", needs_flag="panel_open"),
    HS("hs_panel_locked", [282, 188, 196, 436], node="open_panel",
       name="Щиток (заперт)", hide_on=["panel_open"]),
    HS("hs_workbench", [380, 560, 470, 300], goto="zoom_workbench", name="Верстак",
       cursor="zoom"),
    HS("hs_bench", [430, 280, 430, 200], goto="zoom_bench", name="Стенд",
       cursor="zoom"),
    HS("hs_shelf_grease", [1000, 420, 120, 90], node="take_grease", name="Смазка",
       hide_on=["done:take_grease"]),
    HS("hs_shelf", [985, 170, 315, 700], name="Стеллаж", look=True),
    HS("hs_attic", [995, 172, 300, 110], goto="zoom_attic", name="Антресоль",
       cursor="zoom"),
    HS("hs_box_floor", [1010, 878, 260, 170], node="open_box", name="Коробка «НГ-2019»",
       show_on=["box_down"], hide_on=["relic_fez"]),
    HS("hs_box_search", [1010, 878, 260, 170], node="search_box_again",
       name="Коробка (ещё раз)", show_on=["relic_fez"], hide_on=["crown"]),
    HS("hs_closet", [1300, 145, 260, 735], goto="zoom_closet", name="Шкаф уборщицы",
       cursor="zoom"),
    HS("hs_net_top", [1300, 128, 256, 52], node="see_net", name="Верх шкафа",
       hide_on=["net_down"]),
    HS("hs_net_floor", [1288, 880, 210, 120], node="take_net", name="Сачок",
       show_on=["net_down"], hide_on=["done:take_net"]),
    HS("hs_vent_util", [1352, 40, 206, 104], name="Вентрешётка", look=True),
    HS("hs_mop", [1560, 262, 96, 322], node="take_mop", name="Швабра",
       hide_on=["done:take_mop"], doc_rmb="doc_mop_tag"),
    HS("hs_boiler", [1590, 55, 212, 398], node="h_boiler", name="Бойлер"),
    HS("hs_sink", [1560, 588, 254, 196], name="Раковина", look=True),
    HS("hs_sink_valve", [1642, 790, 130, 160], node="h_sink_valve",
       name="Вентиль под раковиной"),
    HS("hs_bucket", [1518, 748, 146, 156], name="Ведро", look=True),
]
B_cutouts = [
    CO("cutouts/st_net_on_top.png", [1318, 118], 0.92, z=20,
       hide_on=["net_down"]),
    CO("cutouts/st_net_on_floor.png", [1296, 892], 0.86, z=20,
       show_on=["net_down"], hide_on=["done:take_net"]),
    CO("cutouts/st_vent_open_util.png", [1354, 44], 1.0, z=20,
       show_on=["vents_open"]),
    CO("cutouts/st_mop_on_hook.png", [1556, 258], 0.78, z=20, hide_on=["done:take_mop"]),
    CO("cutouts/st_grease_on_shelf.png", [1006, 428], 0.82, z=20,
       hide_on=["done:take_grease"]),
    CO("cutouts/st_box_on_floor.png", [1012, 872], 0.72, z=20,
       show_on=["box_down"]),
]
B_arrows = [
    {"dir": "left", "rect": [0, 420, 60, 240], "goto_room": "A"},
]

# =============================== ЗУМЫ ================================
zooms = {}

zooms["zoom_tree"] = {"room": "A", "hotspots": [
    HS("hs_z_keytoy", [640, 300, 110, 150], node="take_key_toy",
       name="Ключик-«игрушка»", hide_on=["done:take_key_toy"]),
    HS("hs_z_gift", [480, 620, 260, 220], node="take_gift", name="Подарок",
       hide_on=["done:take_gift"]),
    HS("hs_z_santa", [480, 620, 260, 110], doc="doc_santa", name="Бирки Санты",
       hide_on=["done:take_gift"], cursor="zoom",
       comment="бирка на подарке — читается до вскрытия"),
    HS("hs_z_balls", [60, 0, 480, 600], name="Игрушки", look=True),
    HS("hs_z_stand", [60, 530, 500, 250], name="Крестовина", look=True),
    HS("hs_z_bin", [1180, 130, 170, 210], name="Корзина", look=True),
], "cutouts": [
    CO("cutouts/st_key_toy.png", [640, 306], 1.0, z=20,
       hide_on=["done:take_key_toy"]),
    CO("cutouts/st_gift.png", [488, 640], 1.05, z=20,
       hide_on=["done:take_gift"]),
]}

zooms["zoom_lap_drawer"] = {"room": "A", "needs_flag": "drawer_pried", "hotspots": [
    HS("hs_z_tray", [520, 190, 610, 640], node="take_handle",
       name="Лоток-органайзер", hide_on=["done:take_handle"]),
    HS("hs_z_junk", [1140, 150, 290, 700], node="search_drawer_again",
       name="Хлам справа", hide_on=["relic_yatagan"]),
    HS("hs_z_photos", [390, 150, 130, 660], name="Фотки с корпоратива",
       look=True),
], "cutouts": [
    CO("icons/ic_handle.png", [760, 420], 1.15, z=20,
       hide_on=["done:take_handle"], comment="ручка в лотке до взятия"),
]}

zooms["zoom_aquarium"] = {"room": "A", "hotspots": [
    HS("hs_z_glint", [1020, 730, 190, 120], node="fish_card",
       name="Что-то блестит", hide_on=["done:fish_card"]),
    HS("hs_z_fish", [700, 250, 400, 260], node="h_fish_poke", name="Рыбка",
       track_idle="fish_zoom"),
    HS("hs_z_castle", [820, 280, 630, 500], name="Замок", look=True),
    HS("hs_z_weed", [140, 80, 300, 720], name="Водоросли", look=True),
], "cutouts": [
    CO("cutouts/st_card_glint.png", [1050, 760], 1.0, z=18, hide_on=["done:fish_card"],
       glint=True),
    CO("cutouts/st_fish_a.png", [760, 320], 1.0, z=22, idle="fish_zoom",
       frames=["cutouts/st_fish_a.png", "cutouts/st_fish_b.png"]),
]}

zooms["zoom_pc"] = {"room": "A", "hotspots": [
    HS("hs_z_screen", [390, 110, 645, 555], node="pc_unlock", name="Экран",
       widget="pc", also_nodes=["skud_form"],
       pc_docs=["doc_chat", "doc_order", "doc_about", "doc_dict",
                "doc_skud_blank"]),
    HS("hs_z_sticker", [360, 660, 740, 200], doc="doc_sticker",
       name="Стикер под клавиатурой", cursor="zoom"),
    HS("hs_z_mouse", [1120, 770, 200, 140], name="Мышь", look=True),
    HS("hs_z_pencils", [1370, 330, 240, 240], name="Карандашница", look=True),
], "cutouts": []}

zooms["zoom_drawer_keypad"] = {"room": "A", "hotspots": [
    HS("hs_z_keypad", [505, 195, 200, 310], node="ira_code", name="Кейпад",
       widget="keypad", widget_len=4),
    HS("hs_z_slot", [1075, 82, 330, 66], name="Щель шредера", look=True),
    HS("hs_z_mini_drawer", [865, 175, 310, 260], name="Ящичек", look=True),
], "cutouts": []}

zooms["zoom_alarm"] = {"room": "A", "hotspots": [
    HS("hs_z_alarm_pad", [615, 280, 240, 580], node="alarm_off",
       name="Панель сигнализации", widget="keypad", widget_len=4),
    HS("hs_z_alarm_tag", [850, 290, 120, 190], name="Бирка монтажника",
       look=True),
    HS("hs_z_alarm_horn", [610, 150, 200, 130], name="Сирена", look=True),
], "cutouts": [], "led": {"alarm": [810, 250]}}

zooms["zoom_exit_door"] = {"room": "A", "hotspots": [
    HS("hs_z_plate", [560, 80, 370, 200], name="Табличка", look=True,
       reader_note="door_plate"),
    HS("hs_z_door_push", [430, 300, 860, 620], node="door_open",
       name="Толкнуть дверь", hide_on=["victory"]),
    HS("hs_z_reader_small", [1592, 468, 62, 82], node="reader_swipe",
       name="Считыватель"),
    HS("hs_z_bolt", [1330, 340, 120, 300], node="bolt_free", name="Засов",
       widget="bolt"),
    HS("hs_z_handle_lock", [820, 630, 220, 160], name="Ручка и замок",
       look=True),
    HS("hs_z_keyhole", [940, 720, 70, 70], name="Скважина", look=True),
    HS("hs_z_intercom2", [95, 160, 180, 690], node="h_intercom", name="Домофон"),
    HS("hs_z_bell", [1548, 388, 145, 145], name="Звонок", look=True),
    HS("hs_z_alarm_go", [1550, 630, 210, 450], goto="zoom_alarm",
       name="Сигнализация", cursor="zoom"),
], "cutouts": [], "led": {"reader_small": [1622, 505]},
    "bolt_geom": {"plate": [1352, 356, 66, 268], "knob_closed": [1385, 420],
                  "knob_open": [1385, 566]}}

zooms["zoom_panel"] = {"room": "B", "needs_flag": "panel_open", "hotspots": [
    HS("hs_z_breaker_row", [634, 292, 246, 176], name="Автоматы",
       widget="breakers", breaker_map=["power_main", "sockets_on", "h_br_elka",
                                       "h_br_srv", "h_br_rezerv", None],
       breaker_x0=641, breaker_step=38),
    HS("hs_z_schema", [295, 405, 200, 150], doc="doc_schema", name="Схема",
       cursor="zoom"),
    HS("hs_z_ext_switch", [1028, 528, 100, 130], name="Рубильник", look=True),
], "cutouts": [
    # рычажки: базово все down; up при флаге
    CO("cutouts/st_breaker_down.png", [646, 352], 0.42, z=20, breaker_slot=0,
       hide_on=["power_on"]),
    CO("cutouts/st_breaker_up.png",   [646, 348], 0.42, z=20, breaker_slot=0,
       show_on=["power_on"]),
    CO("cutouts/st_breaker_down.png", [684, 352], 0.42, z=20, breaker_slot=1,
       hide_on=["sockets_on"]),
    CO("cutouts/st_breaker_up.png",   [684, 348], 0.42, z=20, breaker_slot=1,
       show_on=["sockets_on"]),
    CO("cutouts/st_breaker_down.png", [722, 352], 0.42, z=20, breaker_slot=2,
       hide_on=["garland_on"]),
    CO("cutouts/st_breaker_up.png",   [722, 348], 0.42, z=20, breaker_slot=2,
       show_on=["garland_on"]),
    CO("cutouts/st_breaker_down.png", [760, 352], 0.42, z=20, breaker_slot=3,
       toggle_visual="srv"),
    CO("cutouts/st_breaker_down.png", [798, 352], 0.42, z=20, breaker_slot=4,
       toggle_visual="rezerv"),
    CO("cutouts/st_breaker_down.png", [836, 352], 0.42, z=20, breaker_slot=5),
], "labels_engine": ["ГЛАВНЫЙ", "РОЗЕТКИ", "ЁЛКА", "СРВ", "РЕЗЕРВ", ""]}

zooms["zoom_bench"] = {"room": "B", "hotspots": [
    HS("hs_z_valve_p", [520, 130, 120, 290], node="bench_move_P", name="П",
       bench=True, needs_flag="wheel_on"),
    HS("hs_z_valve_p_empty", [520, 130, 120, 290], node="install_wheel",
       name="Голый шток «П»", hide_on=["wheel_on"]),
    HS("hs_z_valve_k1", [660, 120, 120, 300], node="bench_move_K1", name="К1",
       bench=True),
    HS("hs_z_valve_k2", [795, 130, 120, 290], node="bench_move_K2", name="К2",
       bench=True),
    HS("hs_z_valve_s", [935, 130, 100, 280], node="bench_move_S", name="С",
       bench=True),
    HS("hs_z_pump", [1240, 200, 220, 380], node="bench_pump", name="Насос",
       bench=True),
    HS("hs_z_reset", [150, 225, 90, 110], node="bench_reset", name="СБРОС",
       bench=True),
    HS("hs_z_gauge", [270, 60, 190, 220], name="Манометр", look=True),
    HS("hs_z_note", [545, 770, 340, 240], doc="doc_bench_note",
       name="Листок-инструкция", cursor="zoom"),
    HS("hs_z_collector", [1400, 660, 260, 300], node="take_collector",
       name="Коллектор в зажиме", show_on=["bench_solved"],
       hide_on=["done:take_collector"]),
    HS("hs_z_hatch", [1428, 76, 140, 152], name="Лючок", look=True),
], "cutouts": [
    # П: латунный маховик после установки; положение по bench-состоянию
    CO("cutouts/st_valve_wheel_off.png", [575, 172], 1.0, z=20, valve="P",
       state="off", show_on=["wheel_on"]),
    CO("cutouts/st_valve_wheel_on.png",  [575, 172], 1.0, z=20, valve="P",
       state="on", show_on=["wheel_on"]),
    CO("cutouts/st_valve_wheel_red_off.png", [712, 165], 1.0, z=20, valve="K1",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [712, 165], 1.0, z=20, valve="K1",
       state="on"),
    CO("cutouts/st_valve_wheel_red_off.png", [847, 172], 1.0, z=20, valve="K2",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [847, 172], 1.0, z=20, valve="K2",
       state="on"),
    CO("cutouts/st_valve_wheel_red_off.png", [978, 168], 0.82, z=20, valve="S",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [978, 168], 0.82, z=20, valve="S",
       state="on"),
    CO("cutouts/st_pump_lever_up.png",   [1305, 232], 1.0, z=22, pump="up"),
    CO("cutouts/st_pump_lever_down.png", [1305, 232], 1.0, z=22, pump="down"),
    CO("cutouts/st_collector_clamped.png", [1418, 700], 0.9, z=20,
       show_on=["bench_solved"], hide_on=["done:take_collector"]),
    CO("cutouts/st_gauge_glass.png", [278, 68], 0.68, z=30, always=True),
], "gauge": {"cx": 360, "cy": 165, "r": 62}}

zooms["zoom_workbench"] = {"room": "B", "hotspots": [
    HS("hs_z_journal", [520, 220, 320, 150], doc="doc_journal",
       name="Журнал испытаний", cursor="zoom"),
    HS("hs_z_padlock", [455, 425, 130, 130], node="open_workbench",
       name="Замочек", hide_on=["wb_open"]),
    HS("hs_z_wb_drawer", [300, 430, 440, 200], node="take_wrench",
       name="Ящик верстака", show_on=["wb_open"], hide_on=["done:take_wrench"]),
    HS("hs_z_vise", [1400, 370, 210, 300], name="Тиски", look=True),
], "cutouts": [
    CO("cutouts/st_padlock_zoom.png", [478, 438], 0.42, z=20,
       hide_on=["wb_open"]),
    CO("cutouts/st_wb_drawer_open.png", [335, 452], 1.0, z=18,
       show_on=["wb_open"]),
    CO("icons/ic_wrench.png", [455, 505], 1.05, z=20, show_on=["wb_open"],
       hide_on=["done:take_wrench"], comment="разводник в ящике до взятия"),
]}

zooms["zoom_attic"] = {"room": "B", "hotspots": [
    HS("hs_z_box_shelf", [380, 300, 560, 260], node="box_down",
       name="Коробка «НГ-2019»", hide_on=["box_down"]),
    HS("hs_z_tinsel", [890, 400, 200, 640], name="Мишура", look=True),
    HS("hs_z_dust", [300, 320, 700, 200], name="Пыльный след", look=True,
       show_on=["box_down"]),
], "cutouts": [
    CO("cutouts/st_box_on_floor.png", [510, 330], 0.86, z=20,
       hide_on=["box_down"]),
]}

zooms["zoom_closet"] = {"room": "B", "hotspots": [
    HS("hs_z_medkit", [1128, 88, 186, 388], node="take_validol", name="Аптечка",
       hide_on=["done:take_validol"]),
    HS("hs_z_hooks", [640, 105, 380, 140], name="Крючки", look=True),
    HS("hs_z_rag", [520, 385, 360, 140], name="Тряпка", look=True),
    HS("hs_z_bottles", [780, 530, 240, 480], name="Бутыли", look=True),
    HS("hs_z_bucket2", [510, 550, 300, 460], name="Ведро", look=True),
], "cutouts": []}

# ============================ СБОРКА JSON ============================
scene = {
    "meta": {"game": "Латунный янычар 2.0", "rev": 1, "canvas": [1920, 1080]},
    "rooms": {
        "A": {"name": "Офис",
              "bg": {"night": "rooms/room_office_night.png",
                     "day": "rooms/room_office_day.png"},
              "hotspots": A_hotspots, "cutouts": A_cutouts, "arrows": A_arrows,
              "idle_engine": ["snow_window", "screensaver_hint"]},
        "B": {"name": "Щитовая-подсобка",
              "bg": {"night": "rooms/room_utility_night.png",
                     "day": "rooms/room_utility_day.png"},
              "hotspots": B_hotspots, "cutouts": B_cutouts, "arrows": B_arrows,
              "idle_engine": []},
    },
    "zooms": {k: dict(v, bg="zooms/" + k + ".png") for k, v in zooms.items()},
    "bench_geom": {"order_labels": ["П", "К1", "К2", "С"]},
    "fx": {"util_handle": "cutouts/st_util_handle.png"},
    "doc_items": {"doc_card": "card", "doc_postcard": "hundred"},
    "doc_auto": {"take_gift": "doc_postcard"},
}

os.makedirs("design", exist_ok=True)
with open("design/scene.json", "w", encoding="utf-8") as f:
    json.dump(scene, f, ensure_ascii=False, indent=1)
nhs = sum(len(r["hotspots"]) for r in scene["rooms"].values()) + \
      sum(len(z["hotspots"]) for z in scene["zooms"].values())
nco = sum(len(r["cutouts"]) for r in scene["rooms"].values()) + \
      sum(len(z["cutouts"]) for z in scene["zooms"].values())
print(f"scene.json: hotspots={nhs}, cutouts={nco}, zooms={len(scene['zooms'])}")
