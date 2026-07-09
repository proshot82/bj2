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
    HS("hs_window", [0, 55, 345, 588], node="h_window", name="Окно",
       look=True),
    HS("hs_sofa_under", [20, 850, 320, 110], node="relic_badge", name="Под диваном",
       fail_without=["longnet"]),
    HS("hs_sofa", [0, 505, 420, 245], name="Диван", look=True),
    HS("hs_karaoke", [5, 700, 140, 62], doc="doc_karaoke", name="Караоке-список",
       cursor="zoom"),
    HS("hs_karaoke_sing", [30, 778, 225, 66], node="h_karaoke_sing",
       name="Спеть", show_on=["read:doc_karaoke"]),
    HS("hs_table_mugs", [305, 745, 265, 210], name="Журнальный столик", look=True),
    HS("hs_tree", [390, 150, 250, 460], goto="zoom_tree", name="Ёлка", cursor="zoom"),
    HS("hs_tree_base", [400, 590, 240, 110], goto="zoom_tree", name="Под ёлкой",
       cursor="zoom"),
    HS("hs_calendar", [683, 182, 95, 155], doc="doc_calendar", name="Календарь",
       cursor="zoom"),
    HS("hs_flipchart", [826, 162, 122, 175], name="Флипчарт", look=True),
    HS("hs_lap_desk", [645, 478, 300, 185], name="Стол Лапидуса", look=True),
    HS("hs_ruler", [1295, 695, 118, 100], node="take_ruler", name="Линейка",
       hide_on=["done:take_ruler"]),
    HS("hs_phone", [872, 445, 68, 58], node="h_phone", name="Телефон"),
    HS("hs_lap_drawer", [868, 514, 80, 148], goto="zoom_lap_drawer", show_on=["drawer_pried"], name="Ящик стола",
       cursor="zoom", needs_flag="drawer_pried"),
    HS("hs_lap_drawer_pry", [868, 514, 80, 148], node="pry_drawer",
       name="Запертый ящик", hide_on=["drawer_pried"]),
    HS("hs_aquarium", [935, 368, 230, 155], goto="zoom_aquarium", name="Аквариум",
       cursor="zoom"),
    HS("hs_aq_tumba", [930, 505, 240, 155], name="Тумба аквариума", look=True),
    HS("hs_coffee_machine", [1176, 386, 90, 94], node="brew_coffee",
       name="Кофемашина"),
    HS("hs_wheel_wall", [994, 198, 105, 150], node="take_wheel", name="Памятный маховик",
       hide_on=["done:take_wheel"]),
    HS("hs_vent_office", [1263, 135, 140, 110], node="push_net", name="Вентрешётка",
       rect_day=[1268, 145, 137, 112]),
    HS("hs_red_button", [1166, 296, 86, 86], name="Красная кнопка",
       look=True, show_on=["power_on"]),
    HS("hs_wardrobe", [1245, 180, 170, 460], name="Шкаф-гардероб", look=True),
    HS("hs_copier", [1362, 425, 142, 240], node="copy_pass", name="Копир",
       hide_on=["done:copy_pass"]),
    HS("hs_ira_desk", [1240, 660, 560, 135], name="Стол Иры", look=True),
    HS("hs_ira_pc", [1420, 500, 185, 245], goto="zoom_pc", name="Компьютер",
       cursor="zoom",
       rect_day=[1460, 530, 235, 200]),
    HS("hs_ira_tumba", [1345, 788, 140, 115], goto="zoom_drawer_keypad",
       name="Кодовая тумба", cursor="zoom"),
    HS("hs_ira_drawer_out", [1350, 905, 125, 105], doc="doc_registry",
       name="Открытый ящик", show_on=["drawer_ira_open"], cursor="zoom"),
    HS("hs_kpi_board", [1758, 278, 150, 200], name="KPI-доска", look=True,
       rect_day=[1785, 150, 120, 320]),
    HS("hs_pointer", [1798, 385, 92, 82], node="take_pointer", name="Указка",
       hide_on=["done:take_pointer"],
       rect_day=[1808, 398, 92, 80]),
    # --- правая зона: рассинхрон день/ночь, всюду rect_day ---
    HS("hs_exit_sign", [1504, 130, 100, 58], name="Табличка EXIT", look=True,
       rect_day=[1540, 126, 86, 62]),
    HS("hs_intercom", [1440, 284, 46, 146], node="h_intercom", name="Домофон",
       rect_day=[1460, 280, 48, 110]),
    HS("hs_main_door", [1483, 220, 140, 475], goto="zoom_exit_door",
       name="Главная дверь", cursor="zoom", show_on=["surveyed"],
       rect_day=[1517, 180, 133, 435]),
    HS("hs_main_door_survey", [1483, 220, 140, 475], node="survey_door",
       name="Осмотреть дверь", hide_on=["surveyed"],
       rect_day=[1517, 180, 133, 435]),
    HS("hs_poster_ot", [1506, 246, 94, 76], doc="doc_poster",
       name="Плакат по охране труда", cursor="zoom",
       rect_day=[1543, 236, 64, 58]),
    HS("hs_alarm", [1680, 376, 46, 74], goto="zoom_alarm", name="Сигнализация",
       cursor="zoom", rect_day=[1733, 323, 46, 64]),
    HS("hs_util_door", [1706, 285, 92, 320], node="open_utility",
       name="Дверь щитовой", hide_on=["utility_open"],
       rect_day=[1712, 278, 93, 332]),
    HS("hs_util_door_go", [1706, 285, 92, 320], goto_room="B",
       name="В щитовую", cursor="move", show_on=["utility_open"],
       rect_day=[1712, 278, 93, 332]),
    HS("hs_util_shaft", [1733, 358, 58, 74], name="Квадратный шток", look=True,
       hide_on=["utility_open"], rect_day=[1724, 300, 52, 62]),
    HS("hs_reader", [1578, 388, 46, 70], node="reader_swipe", name="Считыватель",
       rect_day=[1650, 382, 44, 80]),
    HS("hs_extinguisher", [1852, 425, 66, 190], node="h_extinguisher",
       name="Огнетушитель",
       rect_day=[1852, 425, 66, 190]),
]
A_cutouts = [
    # линейка — оригинальный катаут (восстановлен из git 5413efe), лежит на
    # столе Иры (правая столешница ~1240..1800 × 665..790, ночь=день)
    CO("cutouts/st_ruler_on_desk.png", [1143, 674], 2.8, z=20,
       hide_on=["done:take_ruler"]),
    # указка (диагональная) лежит ВНУТРИ силуэта KPI-доски (ночь/день)
    CO("cutouts/st_pointer_on_board.png", [1713, 376], 1.5, z=20,
       hide_on=["done:take_pointer"],
       pos_day=[1723, 386]),
    CO("cutouts/st_wheel_wall.png", [1002, 206], 0.52, z=20,
       hide_on=["done:take_wheel"]),
    # открытая решётка ТОЧНО поверх закрытой из фона (промер грили ночь/день)
    CO("cutouts/st_vent_open_office.png", [1241, 105], 0.88, z=20,
       show_on=["vents_open"], pos_day=[1246, 116]),
    CO("cutouts/st_gift.png", [430, 600], 0.62, z=20, hide_on=["done:take_gift"]),
    # ящик выдвигается ИЗ кодовой тумбы Иры (промер фронта тумбы), не лежит на полу
    CO("cutouts/st_ira_drawer_open.png", [1233, 880], 0.70, z=20,
       show_on=["drawer_ira_open"]),
    CO("cutouts/st_garland_on.png", [368, 175], 0.6, z=30,
       show_on=["garland_on"], glow=True),
    CO("cutouts/st_led_alarm_on.png", [1673, 382], 0.34, z=25,
       hide_on=["alarm_off"], pos_day=[1731, 328]),
    CO("cutouts/st_led_alarm_off.png", [1673, 382], 0.34, z=25,
       show_on=["alarm_off"], pos_day=[1731, 328]),
    CO("cutouts/st_led_reader_off.png", [1568, 325], 0.42, z=25,
       hide_on=["power_on"], pos_day=[1648, 330]),
    CO("cutouts/st_led_reader_red.png", [1568, 325], 0.42, z=25,
       show_on=["power_on"], hide_on=["reader_green"], pos_day=[1648, 330]),
    CO("cutouts/st_led_reader_green.png", [1568, 325], 0.42, z=25,
       show_on=["reader_green"], pos_day=[1648, 330]),
    # открытая дверь щитовой (перспективный кадр автора, ночь): дверь приоткрыта,
    # из щели льётся тёплый свет. Вырезана по контуру двери (край мягкий ~2px,
    # угол настольной лампы вымаскирован), гамма-подъём теней 0.9 под дневной фон.
    # Посажена ТОЧНО поверх закрытой двери. НОЧЬ: рамка x1695..1772, верх y285,
    # scale 1.03 (кадр подгонялся вручную). ДЕНЬ: отдельный катаут из дневного
    # кадра автора (дверь открыта шире); дневной кадр = дневная сцена в масштабе
    # 1.148, катаут предмасштабирован под общий scale 1.03, pos_day=[1695,287].
    # Раунд 5 (заменяет интерим R4-7); дневной вариант добавлен позже.
    CO("cutouts/st_util_door_open.png", [1697, 285], 1.03, z=15,
       show_on=["utility_open"],
       img_day="cutouts/st_util_door_open_day.png", pos_day=[1695, 287]),
    CO("cutouts/st_door_open_final.png", [1476, 178], 0.62, z=40,
       show_on=["victory"], pos_day=[1512, 176]),
    # идл: рыбка в аквариуме на вайде (мелкая), пар над кофе
    CO("cutouts/st_fish_a.png", [952, 412], 0.36, z=18, idle="fish_wide",
       frames=["cutouts/st_fish_a.png", "cutouts/st_fish_b.png"]),
    CO("cutouts/st_steam_a.png", [1150, 230], 0.5, z=22, idle="steam",
       frames=["cutouts/st_steam_a.png", "cutouts/st_steam_b.png",
               "cutouts/st_steam_c.png"], show_on=["sockets_on"]),
]
A_arrows = [
    {"dir": "right", "rect": [1855, 640, 65, 240], "goto_room": "B",
     "needs_flag": "utility_open"},
]

# ============================ ПОДСОБКА (B) ============================
B_hotspots = [
    HS("hs_b_door_office", [0, 70, 285, 910], goto_room="A", name="Дверь в офис",
       cursor="move"),
    HS("hs_panel", [370, 240, 195, 300], goto="zoom_panel", show_on=["panel_open"], name="Электрощиток",
       cursor="zoom", needs_flag="panel_open"),
    HS("hs_panel_locked", [370, 240, 195, 300], node="open_panel",
       name="Щиток (заперт)", hide_on=["panel_open"]),
    HS("hs_workbench", [495, 590, 585, 310], goto="zoom_workbench", name="Верстак",
       cursor="zoom"),
    HS("hs_bench", [585, 380, 480, 220], goto="zoom_bench", name="Стенд",
       cursor="zoom"),
    HS("hs_shelf_grease", [1150, 428, 112, 72], node="take_grease", name="Смазка",
       hide_on=["done:take_grease"]),
    HS("hs_shelf", [1005, 190, 310, 620], name="Стеллаж", look=True),
    HS("hs_attic", [1005, 190, 305, 115], goto="zoom_attic", name="Антресоль",
       cursor="zoom"),
    HS("hs_box_floor", [1010, 878, 260, 170], node="open_box", name="Коробка «НГ-2019»",
       show_on=["box_down"], hide_on=["item:relic_fez"]),
    HS("hs_box_search", [1010, 878, 260, 170], node="search_box_again",
       name="Коробка (ещё раз)", show_on=["item:relic_fez"], hide_on=["item:crown"]),
    HS("hs_closet", [1310, 190, 285, 690], goto="zoom_closet", name="Шкаф уборщицы",
       cursor="zoom"),
    HS("hs_net_top", [1398, 150, 122, 118], node="see_net", name="Верх шкафа",
       hide_on=["net_down"]),
    HS("hs_net_floor", [1290, 885, 240, 185], node="take_net", name="Сачок",
       show_on=["net_down"], hide_on=["done:take_net"]),
    HS("hs_vent_util", [1385, 50, 180, 145], name="Вентрешётка", look=True),
    HS("hs_mop", [1570, 340, 100, 230], node="take_mop", name="Швабра",
       hide_on=["done:take_mop"], doc_rmb="doc_mop_tag"),
    HS("hs_boiler", [1655, 80, 195, 440], node="h_boiler", name="Бойлер"),
    HS("hs_sink", [1600, 590, 255, 175], name="Раковина", look=True),
    HS("hs_sink_valve", [1700, 760, 120, 130], node="h_sink_valve",
       name="Вентиль под раковиной"),
    HS("hs_bucket", [1560, 780, 135, 160], name="Ведро", look=True),
]
B_cutouts = [
    # сачок лежит на крышке шкафа (y~205) с правдоподобным свесом за передний край
    CO("cutouts/st_net_on_top.png", [1360, 150], 0.80, z=20,
       hide_on=["net_down"]),
    CO("cutouts/st_net_on_floor.png", [1296, 892], 0.86, z=20,
       show_on=["net_down"], hide_on=["done:take_net"]),
    # открытая решётка ТОЧНО поверх закрытой грили (x1385..1560 y50..190)
    CO("cutouts/st_vent_open_util.png", [1321, 12], 1.5, z=20,
       show_on=["vents_open"]),
    CO("cutouts/st_mop_on_hook.png", [1556, 258], 0.78, z=20, hide_on=["done:take_mop"]),
    # банка литола стоит НА полке стеллажа (полка 4, y~490), в стороне от инструментов
    CO("cutouts/st_grease_on_shelf.png", [1134, 415], 0.82, z=20,
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
    CO("cutouts/st_gift.png", [430, 600], 1.05, z=20,
       hide_on=["done:take_gift"]),
]}

zooms["zoom_lap_drawer"] = {"room": "A", "needs_flag": "drawer_pried", "hotspots": [
    HS("hs_z_tray", [520, 190, 610, 640], node="take_handle",
       name="Лоток-органайзер", hide_on=["done:take_handle"]),
    HS("hs_z_junk", [1140, 150, 290, 700], node="search_drawer_again",
       name="Хлам справа", hide_on=["item:relic_yatagan"]),
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
    HS("hs_z_screen", [520, 160, 820, 470], node="pc_unlock", name="Экран",
       widget="pc", also_nodes=["skud_form"],
       pc_docs=["doc_chat", "doc_order", "doc_about", "doc_dict",
                "doc_skud_blank"]),
    HS("hs_z_sticker", [360, 660, 740, 200], doc="doc_sticker",
       name="Стикер под клавиатурой", cursor="zoom"),
    HS("hs_z_mouse", [1630, 820, 140, 85], name="Мышь", look=True),
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
    HS("hs_z_plate", [575, 85, 640, 270], name="Табличка", look=True,
       reader_note="door_plate"),
    HS("hs_z_door_push", [430, 300, 1030, 620], node="door_open",
       name="Толкнуть дверь", hide_on=["victory"]),
    HS("hs_z_reader_small", [1620, 462, 210, 200], node="reader_swipe",
       name="Считыватель"),
    HS("hs_z_bolt", [1385, 470, 92, 165], node="bolt_free", name="Засов",
       widget="bolt"),
    HS("hs_z_handle_lock", [820, 630, 220, 160], name="Ручка и замок",
       look=True),
    HS("hs_z_keyhole", [940, 720, 70, 70], name="Скважина", look=True),
    HS("hs_z_intercom2", [95, 160, 180, 690], node="h_intercom", name="Домофон"),
    HS("hs_z_alarm_go", [1596, 688, 262, 336], goto="zoom_alarm",
       name="Панель сигнализации", cursor="zoom"),
], "cutouts": [], "led": {"reader_small": [1768, 618]},
    "bolt_geom": {"plate": [1398, 480, 64, 140], "knob_closed": [1433, 512],
                  "knob_open": [1433, 588]}}

zooms["zoom_panel"] = {"room": "B", "needs_flag": "panel_open", "hotspots": [
    HS("hs_z_breaker_row", [845, 392, 282, 176], name="Автоматы",
       widget="breakers", breaker_map=["power_main", "sockets_on", "h_br_elka",
                                       "h_br_srv", "h_br_rezerv", None],
       breaker_x0=845, breaker_step=46.8),
    HS("hs_z_schema", [295, 405, 200, 150], doc="doc_schema", name="Схема",
       cursor="zoom"),
    HS("hs_z_ext_switch", [1028, 528, 100, 130], name="Рубильник", look=True),
], "cutouts": [
    # рычажки: базово все down; up при флаге
    CO("cutouts/st_breaker_down.png", [837, 456], 0.6, z=20, breaker_slot=0,
       hide_on=["power_on"]),
    CO("cutouts/st_breaker_up.png",   [841, 416], 0.6, z=20, breaker_slot=0,
       show_on=["power_on"]),
    CO("cutouts/st_breaker_down.png", [884, 456], 0.6, z=20, breaker_slot=1,
       hide_on=["sockets_on"]),
    CO("cutouts/st_breaker_up.png",   [888, 416], 0.6, z=20, breaker_slot=1,
       show_on=["sockets_on"]),
    CO("cutouts/st_breaker_down.png", [931, 456], 0.6, z=20, breaker_slot=2,
       hide_on=["garland_on"]),
    CO("cutouts/st_breaker_up.png",   [935, 416], 0.6, z=20, breaker_slot=2,
       show_on=["garland_on"]),
    CO("cutouts/st_breaker_down.png", [977, 456], 0.6, z=20, breaker_slot=3,
       toggle_visual="srv"),
    CO("cutouts/st_breaker_down.png", [1024, 456], 0.6, z=20, breaker_slot=4,
       toggle_visual="rezerv"),
    CO("cutouts/st_breaker_down.png", [1071, 456], 0.6, z=20, breaker_slot=5),
], "labels_engine": ["ГЛАВНЫЙ", "РОЗЕТКИ", "ЁЛКА", "СРВ", "РЕЗЕРВ", ""]}

zooms["zoom_bench"] = {"room": "B", "hotspots": [
    HS("hs_z_valve_p", [700, 150, 130, 300], node="bench_move_P", show_on=["wheel_on"], name="П",
       bench=True, needs_flag="wheel_on"),
    HS("hs_z_valve_p_empty", [700, 150, 130, 300], node="install_wheel",
       name="Голый шток «П»", hide_on=["wheel_on"]),
    HS("hs_z_valve_k1", [870, 150, 130, 290], node="bench_move_K1", name="К1",
       bench=True),
    HS("hs_z_valve_k2", [1050, 150, 130, 290], node="bench_move_K2", name="К2",
       bench=True),
    HS("hs_z_valve_s", [1240, 150, 115, 330], node="bench_move_S", name="С",
       bench=True),
    HS("hs_z_pump", [1330, 200, 190, 430], node="bench_pump", name="Насос",
       bench=True),
    HS("hs_z_reset", [150, 225, 90, 110], node="bench_reset", name="СБРОС",
       bench=True),
    HS("hs_z_gauge", [368, 92, 215, 222], name="Манометр", look=True),
    HS("hs_z_note", [545, 770, 340, 240], doc="doc_bench_note",
       name="Листок-инструкция", cursor="zoom"),
    HS("hs_z_collector", [1410, 690, 290, 185], node="take_collector",
       name="Коллектор в зажиме", show_on=["bench_solved"],
       hide_on=["done:take_collector"]),
    HS("hs_z_hatch", [1385, 82, 100, 135], name="Лючок", look=True),
], "cutouts": [
    # П: латунный маховик после установки; положение по bench-состоянию
    CO("cutouts/st_valve_wheel_off.png", [700, 180], 1.0, z=20, valve="P",
       state="off", show_on=["wheel_on"]),
    CO("cutouts/st_valve_wheel_on.png",  [700, 180], 1.0, z=20, valve="P",
       state="on", show_on=["wheel_on"]),
    CO("cutouts/st_valve_wheel_red_off.png", [870, 180], 1.0, z=20, valve="K1",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [870, 180], 1.0, z=20, valve="K1",
       state="on"),
    CO("cutouts/st_valve_wheel_red_off.png", [1050, 180], 1.0, z=20, valve="K2",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [1050, 180], 1.0, z=20, valve="K2",
       state="on"),
    CO("cutouts/st_valve_wheel_red_off.png", [1244, 187], 0.82, z=20, valve="S",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [1244, 187], 0.82, z=20, valve="S",
       state="on"),
    CO("cutouts/st_pump_lever_up.png",   [1305, 232], 1.0, z=22, pump="up"),
    CO("cutouts/st_pump_lever_down.png", [1305, 232], 1.0, z=22, pump="down"),
    CO("cutouts/st_collector_clamped.png", [1450, 705], 0.9, z=20,
       show_on=["bench_solved"], hide_on=["done:take_collector"]),
    CO("cutouts/st_gauge_glass.png", [366, 96], 0.84, z=30, always=True),
], "gauge": {"cx": 475, "cy": 205, "r": 80},
   "valve_labels": [["П", 765], ["К1", 935], ["К2", 1115], ["С", 1297]]}

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

def _hs_area(h):
    r = h["rect"]; return r[2] * r[3]
A_hotspots.sort(key=_hs_area)          # мелкие зоны раньше крупных (hit по порядку)
B_hotspots.sort(key=_hs_area)
for _z in zooms.values():
    _z["hotspots"].sort(key=_hs_area)

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
