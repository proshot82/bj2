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
    HS("hs_ruler", [1238, 706, 96, 62], node="take_ruler", name="Линейка",
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
    HS("hs_kpi_board", [1758, 278, 150, 200], name="KPI-доска", look=True,
       rect_day=[1785, 150, 120, 320]),
    HS("hs_pointer", [1795, 266, 68, 68], node="take_pointer", name="Магнитная указка",
       hide_on=["done:take_pointer"],
       rect_day=[1808, 256, 68, 68]),
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
    # (р.19) автор не нашёл словарь глифов: зона была впритык по белому листу,
    # днём вообще 64x58. Расширена с запасом по обе стороны листа, оба времени
    # суток промерены по сетке (work/rov/grid_night.png, grid_day.png).
    HS("hs_poster_ot", [1499, 238, 100, 90], doc="doc_poster",
       name="Плакат по охране труда", cursor="zoom",
       rect_day=[1529, 241, 100, 88]),
    HS("hs_alarm", [1711, 376, 46, 48], goto="zoom_alarm", name="Сигнализация",
       cursor="zoom", rect_day=[1725, 372, 48, 50]),   # (р.13) на короб дневной
       # створки; (р.20) день +13px вправо — центр ровно на X-коробку по промеру
    HS("hs_util_door", [1706, 285, 92, 320], node="open_utility",
       name="Дверь щитовой", hide_on=["utility_open"],
       rect_day=[1712, 278, 93, 332]),
    HS("hs_util_door_go", [1706, 285, 92, 320], goto_room="B",
       name="В щитовую", cursor="move", show_on=["utility_open"],
       rect_day=[1712, 278, 93, 332]),
    HS("hs_util_shaft", [1733, 358, 58, 74], name="Квадратный шток", look=True,
       hide_on=["utility_open"], rect_day=[1724, 300, 52, 62]),
    HS("hs_reader", [1615, 332, 48, 74], node="reader_swipe", name="Считыватель",
       rect_day=[1641, 322, 44, 80]),
    HS("hs_extinguisher", [1852, 425, 66, 190], node="h_extinguisher",
       name="Огнетушитель",
       rect_day=[1852, 425, 66, 190]),
]
A_cutouts = [
    # линейка — оригинальный катаут (восстановлен из git 5413efe), лежит на
    # столе Иры (правая столешница ~1240..1800 × 665..790, ночь=день)
    # (раунд 7) линейка меньше (×0.6 от 2.8) и на СВОБОДНОЙ части столешницы
    # Иры слева от факса (промер занятых колонок), не задевает принтер/клаву
    CO("cutouts/st_ruler_on_desk.png", [1150, 702], 1.68, z=20,
       hide_on=["done:take_ruler"]),
    # указка (диагональная) лежит ВНУТРИ силуэта KPI-доски (ночь/день)
    # (раунд 9) уменьшена (1.5->1.35) и отцентрована в белом поле щита с запасом
    # от кромок: ночь щит x1755..1898 y150..475, день x1778..1905 y58..510
    CO("cutouts/st_pointer_on_board.png", [1721, 260], 1.35, z=20,
       hide_on=["done:take_pointer"],
       pos_day=[1737, 248]),
    CO("cutouts/st_wheel_wall.png", [1002, 206], 0.52, z=20,
       hide_on=["done:take_wheel"]),
    # открытая решётка накрывает закрытую грилю офиса (x1282..1405 y138..203)
    # (раунд 7) цветокоррекция, высота ×0.75; (раунд 8) ×0.95, центр по гриле
    # день+ночь + тёмный бэкинг (gen_vents_r7)
    CO("cutouts/st_vent_open_office.png", [1242, 116], 0.95, z=20,
       show_on=["vents_open"],
       img_day="cutouts/st_vent_open_office_day.png", pos_day=[1244, 114]),
    # (раунд 19) подарок под ёлкой УБРАН с общего плана: на вайде под ёлкой
    # только тень еловых лап, коробка живёт исключительно в zoom_tree
    # (замечание автора: «подарок не должен быть виден на общем плане —
    # только если посмотреть под ёлкой»). Зона hs_tree_base туда и ведёт.
    # (раунд 7) открытый ящик Иры перенесён В ЗУМ тумбы (zoom_drawer_keypad):
    # на вайде тумба остаётся ЗАКРЫТОЙ (см. zoom cutouts + hs_ira_drawer_out там)
    # процедурная гирлянда по силуэту ёлки (tools/gen_garland.py):
    # нити+лампочки glow, обрезаны маской ёлки; ночь ярче, день бледнее (img_day)
    # (раунд 8: дневные лампочки/glow усилены — читаются в масштабе комнаты)
    CO("cutouts/st_garland_on.png", [360, 150], 1.0, z=30,
       show_on=["garland_on"], glow=True,
       img_day="cutouts/st_garland_on_day.png"),
    # (раунд 9) pos_day LED выправлены по дневному фону: индикатор считывателя
    # ~(1663,365), плата сигнализации на синей двери x1735..1770 y378..425
    # (раунд 10) ДНЕВНАЯ сирена — основа панели сигнализации. Ночной арт
    # офиса содержит коробку-сирену с X-узором на синей двери
    # (~x1717..1747 y382..416); дневной арт её НЕ имеет (плоская плита).
    # Катаут st_siren_day (день-only, day_only=True) кладёт X-коробку на
    # дневную дверь; масштаб под ночную коробку. Кроп по альфе (гало убрано).
    # LED alarm (ниже) садится днём на КУПОЛ-ЛАМПУ сирены (отн.0.763,0.187).
    # (раунд 11) LED-индикаторы уменьшены до «маленького огонька» (диаметр
    # линзы ~9-14px под арт): reader scale 0.42->0.28, alarm 0.34->0.24.
    # Сирена день ПЕРЕСАЖЕНА со створки (днём дверь всегда открыта — катаут
    # st_util_door_open_day) на СТЕНУ над дверной коробкой (центр ~1740,248,
    # под тан-распредкоробкой, чистая от полотна/KPI/зон). Ночь: LED reader
    # на овал СКУД (1636,358), alarm на центр X-коробки (1734,399); зоны
    # hs_reader/hs_alarm ночь подвинуты на эти арт-объекты (был рассинхрон ~50px).
    # (раунд 13) st_siren_day УБРАН: короб сигнализации запечён в дневном катауте
    # открытой двери (st_util_door_open_day); дневной LED/зона сидят на нём.
    # (микрораунд 12) LED сигнализации разделены по состоянию двери щитовой.
    # Ночью X-короб сигнализации НАРИСОВАН на полотне двери и «уезжает» с
    # распахнутой створкой (катаут st_util_door_open). Поэтому:
    #  ЗАКРЫТАЯ дверь (ночь до utility_open) — LED на родном коробе арта
    #  (центр X ~1734,399) pos [1727,392]; прячем при utility_open.
    #  ОТКРЫТАЯ дверь — LED на уехавшем коробе. Ночь: центр X на распахнутой
    #  створке промерен = (1721,367) -> pos [1714,360]. День: дверь всегда
    #  открыта (power_on=>utility_open). Раунд 13: короб запечён в
    #  st_util_door_open_day, центр (1737,395) -> pos_day [1730,388].
    # Состояние on/off — прежний флаг alarm_off (у обеих пар одинаково).
    CO("cutouts/st_led_alarm_on.png", [1727, 392], 0.24, z=25,
       hide_on=["alarm_off", "utility_open"]),
    CO("cutouts/st_led_alarm_off.png", [1727, 392], 0.24, z=25,
       show_on=["alarm_off"], hide_on=["utility_open"]),
    CO("cutouts/st_led_alarm_on.png", [1714, 360], 0.24, z=25,
       show_on=["utility_open"], hide_on=["alarm_off"], pos_day=[1730, 388]),
    CO("cutouts/st_led_alarm_off.png", [1714, 360], 0.24, z=25,
       show_on=["utility_open", "alarm_off"], pos_day=[1730, 388]),
    CO("cutouts/st_led_reader_off.png", [1628, 350], 0.28, z=25,
       hide_on=["power_on"], pos_day=[1655, 357]),
    CO("cutouts/st_led_reader_red.png", [1627, 350], 0.28, z=25,
       show_on=["power_on"], hide_on=["reader_green"], pos_day=[1654, 357]),
    CO("cutouts/st_led_reader_green.png", [1628, 350], 0.28, z=25,
       show_on=["reader_green"], pos_day=[1655, 357]),
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
    # идл: рыбка в аквариуме (мелкая), пар над кофе.
    # (раунд 8) пар — ОДИН катаут frames=[a,b,c] idle="steam" (чередует по
    # одному кадру, не суммирует); посажен вплотную над кружкой
    CO("cutouts/st_fish_a.png", [952, 412], 0.36, z=18, idle="fish_wide",
       frames=["cutouts/st_fish_a.png", "cutouts/st_fish_b.png"]),
    # (раунд 9) пар сдвинут влево — база над чашкой (ночь x~1216 / день x~1233)
    CO("cutouts/st_steam_a.png", [1186, 378], 0.42, z=22, idle="steam",
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
    HS("hs_shelf_grease", [1150, 462, 112, 72], node="take_grease", name="Смазка",
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
    HS("hs_net_top", [1398, 108, 122, 120], node="see_net", name="Верх шкафа",
       hide_on=["net_down"]),
    HS("hs_net_floor", [1290, 885, 240, 185], node="take_net", name="Сачок",
       show_on=["net_down"], hide_on=["done:take_net"]),
    HS("hs_vent_util", [1385, 50, 180, 145], name="Вентрешётка", look=True),
    # (раунд 9) швабра ПЕРЕНЕСЕНА в zoom_closet (крючки внутри шкафа уборщицы)
    HS("hs_boiler", [1655, 80, 195, 440], node="h_boiler", name="Бойлер"),
    HS("hs_sink", [1600, 590, 255, 175], name="Раковина", look=True),
    HS("hs_sink_valve", [1700, 760, 120, 130], node="h_sink_valve",
       name="Вентиль под раковиной"),
    HS("hs_bucket", [1560, 780, 135, 160], name="Ведро", look=True),
]
B_cutouts = [
    # (раунд 20) открытый щиток на вайде: вырезка из zoom_panel (коробка +
    # распахнутая дверца, петли слева — согласовано с зумом), скейл ×0.33,
    # тон подогнан к ночи/дню по якорям стена+тень. Закрывает MIGRATION §5.4.
    # Дверца честно заслоняет декор-выключатели слева. z=16 — под LED и прочим.
    CO("cutouts/st_panel_open_wide.png", [223, 243], 1.0, z=16,
       show_on=["panel_open"], img_day="cutouts/st_panel_open_wide_day.png"),
    # сачок лежит на КРЫШКЕ шкафа со свесом за передний край
    # (раунд 8: +17px; раунд 9: ещё +30px — низ со свесом на крышке)
    CO("cutouts/st_net_on_top.png", [1360, 103], 0.80, z=20,
       hide_on=["net_down"]),
    CO("cutouts/st_net_on_floor.png", [1296, 892], 0.86, z=20,
       show_on=["net_down"], hide_on=["done:take_net"]),
    # открытая решётка ПОЛНОСТЬЮ накрывает закрытую грилю (x1390..1577 y62..183)
    # (раунд 7) цветокоррекция; (раунд 8) ×1.58 + тёмный бэкинг под грилю
    CO("cutouts/st_vent_open_util.png", [1327, 24], 1.58, z=20,
       show_on=["vents_open"], img_day="cutouts/st_vent_open_util_day.png"),
    # (раунд 9) катаут швабры st_mop_on_hook ПЕРЕНЕСЁН в zoom_closet (крючки)
    # банка литола СТОИТ на полке, тень-эллипс под ней
    # (раунд 8: опущена ещё на 12px — низ строго на полке ~y527)
    CO("cutouts/st_grease_on_shelf.png", [1134, 452], 0.82, z=20,
       shadow=True, hide_on=["done:take_grease"]),
    CO("cutouts/st_box_on_floor.png", [1012, 872], 0.72, z=20,
       show_on=["box_down"]),
]
B_arrows = [
    {"dir": "left", "rect": [0, 420, 60, 240], "goto_room": "A"},
]

# =============================== ЗУМЫ ================================
zooms = {}

zooms["zoom_tree"] = {"room": "A", "hotspots": [
    # (раунд 19) промер альфы st_key_toy: арт x640..725 y321..401
    HS("hs_z_keytoy", [630, 308, 105, 105], node="take_key_toy",
       name="Ключик-«игрушка»", hide_on=["done:take_key_toy"]),
    # (раунд 19) подарок разрезан ПО АРТУ (промер st_gift@1.05 построчно):
    # бант/узел y629..682 x504..640, корпус коробки y686..782 x493..645.
    # Раньше обе зоны стартовали с [480,620] и «чуть ниже коробки» срабатывал
    # take_gift — замечание автора. Теперь верх = бирка, низ = развернуть.
    HS("hs_z_santa", [498, 620, 145, 64], doc="doc_santa",
       name="Бирка Тайного Санты", hide_on=["done:take_gift"], cursor="zoom",
       comment="бирка на банте — читается до вскрытия"),
    HS("hs_z_gift", [490, 686, 155, 98], node="take_gift",
       name="Развернуть подарок", hide_on=["done:take_gift"],
       doc_rmb="doc_santa"),
    HS("hs_z_balls", [60, 0, 480, 600], name="Игрушки", look=True),
    HS("hs_z_stand", [55, 685, 660, 280], name="Крестовина", look=True),
    HS("hs_z_bin", [1555, 175, 220, 265], name="Корзина", look=True),
], "cutouts": [
    CO("cutouts/st_key_toy.png", [640, 306], 1.0, z=20,
       hide_on=["done:take_key_toy"]),
    CO("cutouts/st_gift.png", [430, 600], 1.05, z=20,
       hide_on=["done:take_gift"]),
]}

zooms["zoom_lap_drawer"] = {"room": "A", "needs_flag": "drawer_pried", "hotspots": [
    # (раунд 19) промер по сетке: лоток x638..1268 y293..803,
    # хлам x1268..1440 y225..810, фотки x510..638 y225..810
    HS("hs_z_tray", [635, 290, 640, 515], node="take_handle",
       name="Лоток-органайзер", hide_on=["done:take_handle"]),
    HS("hs_z_junk", [1265, 225, 180, 590], node="search_drawer_again",
       name="Хлам справа", hide_on=["item:relic_yatagan"]),
    HS("hs_z_photos", [505, 225, 135, 590], name="Фотки с корпоратива",
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
    # (раунд 19) промер: замок x1050..1470 y353..750, водоросли x173..495 y90..705
    HS("hs_z_castle", [1045, 350, 430, 410], name="Замок", look=True),
    HS("hs_z_weed", [170, 85, 330, 630], name="Водоросли", look=True),
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
    # (раунд 19) зона стикера ОПУЩЕНА на клавиатуру (замечание автора):
    # клавиатура по промеру x480..1463 y758..900; было y660 — висело в воздухе
    HS("hs_z_sticker", [480, 755, 985, 150], doc="doc_sticker",
       name="Стикер под клавиатурой", cursor="zoom"),
    HS("hs_z_mouse", [1540, 810, 180, 90], name="Мышь", look=True),
    HS("hs_z_pencils", [1420, 490, 290, 260], name="Карандашница", look=True),
], "cutouts": []}

zooms["zoom_drawer_keypad"] = {"room": "A", "hotspots": [
    # (раунд 19) ВСЕ зоны выправлены по промеру арта — были смещены влево
    # на ~175px (замечание автора: «зоны кодовой панели и ящичка смещены влево»).
    # Кейпад x680..900 y275..640; щель шредера x1140..1500 y150..210;
    # ящичек x1140..1515 y228..417.
    HS("hs_z_keypad", [680, 275, 220, 365], node="ira_code", name="Кейпад",
       widget="keypad", widget_len=4),
    HS("hs_z_slot", [1140, 148, 365, 66], name="Щель шредера", look=True),
    HS("hs_z_mini_drawer", [1150, 235, 360, 180], name="Ящичек", look=True,
       hide_on=["drawer_ira_open"]),
    # (раунд 19, зам.3) катаут-заплатка st_ira_drawer_open отправлен на пенсию:
    # открытый ящик — отдельный полнокадровый зум по схеме Лапидуса. Зона
    # сидит на самом ящичке (арт x1140..1515 y228..417) и ведёт в новый кадр.
    HS("hs_ira_drawer_out", [1150, 235, 360, 180], goto="zoom_ira_drawer",
       name="Открытый ящик", show_on=["drawer_ira_open"], cursor="zoom"),
], "cutouts": []}

zooms["zoom_ira_drawer"] = {"room": "A", "needs_flag": "drawer_ira_open",
                            "hotspots": [
    # (раунд 19, зам.3) полнокадровый открытый ящик Иры 1920×1080 вместо
    # катаута-заплатки. Промер финального арта: лист/стопка x700..1245
    # y215..695 (низ обрезан до y695, чтобы не сесть на жестянку y700+);
    # передняя стенка ящика x430..1520 y840..1015 — явный возврат к тумбе
    # (выход из зума ведёт в комнату, а не в родительский зум).
    HS("hs_z_registry", [700, 215, 545, 480], doc="doc_registry",
       name="Реестр отделов", cursor="zoom"),
    HS("hs_z_ira_back", [430, 840, 1090, 175], goto="zoom_drawer_keypad",
       name="Назад к тумбе", cursor="move"),
], "cutouts": []}

zooms["zoom_alarm"] = {"room": "A", "hotspots": [
    # (раунд 19) промер: корпус панели x790..1180 y150..890; ревун/камера
    # верхняя секция y150..330; клавиатура y380..890; бирка x1163..1245
    # y413..488 (свисает справа от панели); светодиод арта ~ (1060,316)
    HS("hs_z_alarm_pad", [790, 360, 390, 535], node="alarm_off",
       name="Панель сигнализации", widget="keypad", widget_len=4),
    HS("hs_z_alarm_tag", [1150, 400, 120, 110], name="Бирка монтажника",
       look=True),
    HS("hs_z_alarm_horn", [800, 155, 380, 190], name="Сирена", look=True),
], "cutouts": [], "led": {"alarm": [1060, 316]}}

zooms["zoom_exit_door"] = {"room": "A", "hotspots": [
    # (раунд 19) промер по сетке: табличка x750..1208 y120..360; ручка+рычаг
    # x1065..1385 y680..1035; скважина x1283..1313 y968..1020; считыватель
    # x1658..1793 y518..668 (светодиод ~1752,640); домофон x143..338 y233..660
    HS("hs_z_plate", [745, 112, 470, 252], name="Табличка", look=True,
       reader_note="door_plate"),
    HS("hs_z_door_push", [530, 300, 930, 620], node="door_open",
       name="Толкнуть дверь", hide_on=["victory"]),
    HS("hs_z_reader_small", [1650, 510, 145, 160], node="reader_swipe",
       name="Считыватель"),
    HS("hs_z_bolt", [1385, 470, 92, 165], node="bolt_free", name="Засов",
       widget="bolt"),
    HS("hs_z_handle_lock", [1065, 680, 320, 360], name="Ручка и замок",
       look=True),
    HS("hs_z_keyhole", [1272, 958, 62, 76], name="Скважина", look=True),
    HS("hs_z_intercom2", [140, 225, 205, 630], node="h_intercom", name="Домофон"),
    HS("hs_z_alarm_go", [1596, 688, 262, 336], goto="zoom_alarm",
       name="Панель сигнализации", cursor="zoom"),
], "cutouts": [], "led": {"reader_small": [1752, 640]},
    "bolt_geom": {"plate": [1398, 480, 64, 140], "knob_closed": [1433, 512],
                  "knob_open": [1433, 588]}}

zooms["zoom_panel"] = {"room": "B", "needs_flag": "panel_open", "hotspots": [
    HS("hs_z_breaker_row", [845, 392, 282, 176], name="Автоматы",
       widget="breakers", breaker_map=["power_main", "sockets_on", "h_br_elka",
                                       "h_br_srv", "h_br_rezerv", None],
       breaker_x0=845, breaker_step=46.8),
    # (раунд 19) промер: карточка схемы x420..623 y555..698;
    # рубильник x1373..1440 y705..818. Ряд автоматов НЕ трогать —
    # он совпадает с артом и от него зависят breaker_x0/breaker_step.
    HS("hs_z_schema", [415, 550, 215, 155], doc="doc_schema", name="Схема",
       cursor="zoom"),
    HS("hs_z_ext_switch", [1360, 698, 95, 128], name="Рубильник", look=True),
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
    # (раунд 19) ГОЛЫЙ ШТОК ПЕРЕЕХАЛ ВПРАВО. Замечание автора: на общем плане
    # подсобки шток без маховика — крайний ПРАВЫЙ, а в зуме был крайний левый.
    # Промер арта зума: три толстых латунных шпинделя с гайками — центры
    # 762 / 940 / 1118, четвёртый (тонкий хромированный пруток с шариком,
    # центр 1299) — это и есть голый шток. Значит «П» = правый тонкий,
    # К1/К2/С — три левых. Геометрия зон и катаутов не меняется, меняется
    # только привязка имён; логика стенда и порядок ответа не затронуты.
    HS("hs_z_valve_k1", [700, 150, 130, 300], node="bench_move_K1", name="К1",
       bench=True),
    HS("hs_z_valve_k2", [870, 150, 130, 290], node="bench_move_K2", name="К2",
       bench=True),
    HS("hs_z_valve_s", [1050, 150, 130, 290], node="bench_move_S", name="С",
       bench=True),
    HS("hs_z_valve_p", [1240, 150, 115, 330], node="bench_move_P",
       show_on=["wheel_on"], name="П", bench=True, needs_flag="wheel_on"),
    HS("hs_z_valve_p_empty", [1240, 150, 115, 330], node="install_wheel",
       name="Голый шток «П»", hide_on=["wheel_on"]),
    # (раунд 19) промер: насос x1343..1485 y345..780; коробка СБРОС
    # x150..240 y222..428; листок x518..803 y750..945; коллектор по альфе
    # катаута x1504..1655 y734..867
    HS("hs_z_pump", [1305, 255, 210, 530], node="bench_pump", name="Насос",
       bench=True),
    HS("hs_z_reset", [148, 220, 95, 205], node="bench_reset", name="СБРОС",
       bench=True),
    HS("hs_z_gauge", [368, 92, 215, 222], name="Манометр", look=True),
    HS("hs_z_note", [515, 745, 295, 205], doc="doc_bench_note",
       name="Листок-инструкция", cursor="zoom"),
    HS("hs_z_collector", [1496, 726, 168, 148], node="take_collector",
       name="Коллектор в зажиме", show_on=["bench_solved"],
       hide_on=["done:take_collector"]),
    HS("hs_z_hatch", [1385, 82, 100, 135], name="Лючок", look=True),
], "cutouts": [
    # три толстых шпинделя — красные маховики; правый тонкий пруток получает
    # латунный маховик «П» только после установки (install_wheel)
    CO("cutouts/st_valve_wheel_red_off.png", [700, 180], 1.0, z=20, valve="K1",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [700, 180], 1.0, z=20, valve="K1",
       state="on"),
    CO("cutouts/st_valve_wheel_red_off.png", [870, 180], 1.0, z=20, valve="K2",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [870, 180], 1.0, z=20, valve="K2",
       state="on"),
    CO("cutouts/st_valve_wheel_red_off.png", [1050, 180], 1.0, z=20, valve="S",
       state="off"),
    CO("cutouts/st_valve_wheel_red_on.png",  [1050, 180], 1.0, z=20, valve="S",
       state="on"),
    CO("cutouts/st_valve_wheel_off.png", [1244, 187], 0.82, z=20, valve="P",
       state="off", show_on=["wheel_on"]),
    CO("cutouts/st_valve_wheel_on.png",  [1244, 187], 0.82, z=20, valve="P",
       state="on", show_on=["wheel_on"]),
    CO("cutouts/st_pump_lever_up.png",   [1305, 232], 1.0, z=22, pump="up"),
    CO("cutouts/st_pump_lever_down.png", [1305, 232], 1.0, z=22, pump="down"),
    CO("cutouts/st_collector_clamped.png", [1450, 705], 0.9, z=20,
       show_on=["bench_solved"], hide_on=["done:take_collector"]),
    CO("cutouts/st_gauge_glass.png", [366, 96], 0.84, z=30, always=True),
], "gauge": {"cx": 472, "cy": 193, "r": 82},
   "valve_labels": [["К1", 765], ["К2", 935], ["С", 1115], ["П", 1297]]}

zooms["zoom_workbench"] = {"room": "B", "hotspots": [
    # (раунд 19) промер: журнал x717..1068 y308..450; тиски x1440..1590
    # y338..630; открытый ящик = альфа катаута + разводник, x412..591 y484..639
    HS("hs_z_journal", [710, 300, 365, 160], doc="doc_journal",
       name="Журнал испытаний", cursor="zoom"),
    HS("hs_z_padlock", [628, 590, 100, 120], node="open_workbench",
       name="Замочек", hide_on=["wb_open"]),
    # (раунд 19, зам.3) ящик больше не «взять ключ»: зона ведёт в полнокадровый
    # зум ящика; после взятия ключа на её месте — осмотр пустого ящика.
    HS("hs_z_wb_drawer", [408, 480, 190, 165], goto="zoom_wb_drawer",
       name="Ящик верстака", show_on=["wb_open"], hide_on=["done:take_wrench"],
       cursor="zoom"),
    HS("hs_z_wb_drawer_empty", [408, 480, 190, 165], name="Ящик верстака",
       look=True, show_on=["done:take_wrench"]),
    HS("hs_z_vise", [1435, 335, 165, 300], name="Тиски", look=True),
], "cutouts": [
    # (раунд 7) навесной замок повешен на ПЕТЛЮ ящика верстака (промер зума)
    # (раунд 19, зам.3) st_wb_drawer_open и ic_wrench-в-ящике на пенсии:
    # открытый ящик — полнокадровый zoom_wb_drawer, разводник впечатан в арт
    CO("cutouts/st_padlock_zoom.png", [622, 584], 0.42, z=20,
       hide_on=["wb_open"]),
    # (раунд 20) пустые тиски после взятия коллектора: гофра-«огрызок» из
    # зазора губок затёрта клоном фона, шток продлён до винта (инпейнт из
    # родного арта, периметр катаута нетронут — шва нет). MIGRATION §5.5.
    CO("cutouts/st_vise_empty.png", [1509, 440], 1.0, z=16,
       show_on=["done:take_collector"]),
]}

zooms["zoom_wb_drawer"] = {"room": "B", "needs_flag": "wb_open", "hotspots": [
    # (раунд 19, зам.3) полнокадровый ящик верстака 1920×1080; разводной ключ
    # впечатан в арт (иконка 128×128 растянулась бы вчетверо — мыло). Промер
    # финального арта по маске красной рукояти + голова: x745..1125 y345..780.
    # leave_zoom: после взятия ключа кадр закрывается сам — впечатанный ключ
    # игрок больше не увидит. Сторожится негативом (test_negatives, семья 6).
    HS("hs_z_wb_wrench", [745, 345, 380, 435], node="take_wrench",
       name="Разводной ключ", leave_zoom=True, hide_on=["done:take_wrench"]),
], "cutouts": []}

zooms["zoom_attic"] = {"room": "B", "hotspots": [
    # (раунд 19) промер: коробка = альфа катаута x378..918 y238..587;
    # мишура x1223..1373 y533..1080; полка (след) x300..1500 y412..660
    HS("hs_z_box_shelf", [380, 240, 540, 348], node="box_down",
       name="Коробка «НГ-2019»", hide_on=["box_down"]),
    HS("hs_z_tinsel", [1215, 525, 170, 555], name="Мишура", look=True),
    HS("hs_z_dust", [330, 420, 820, 190], name="Пыльный след", look=True,
       show_on=["box_down"]),
], "cutouts": [
    # (раунд 9) новый авторский арт коробки «НГ-2019» с мишурой (ракурс
    # сверху-сбоку — под антресоль). Полка: задний край y~400, передний ~600
    CO("cutouts/st_box_attic.png", [378, 238], 0.62, z=20,
       hide_on=["box_down"]),
]}

zooms["zoom_closet"] = {"room": "B", "hotspots": [
    # (раунд 19) промер: аптечка x1268..1440 y135..465; швабра (черенок+щётка
    # +бирка) x862..968 y68..510; левый крючок x792..858, правый x1028..1088,
    # оба y165..245; тряпка x720..915 y525..683; бутыли x900..1095 y720..990;
    # ведро x683..878 y750..990. Крючки РАЗДЕЛЕНЫ на два, чтобы не перехватывать
    # черенок швабры (мелкая зона выигрывает у крупной по площади).
    HS("hs_z_medkit", [1265, 130, 180, 340], node="take_validol", name="Аптечка",
       hide_on=["done:take_validol"]),
    # (раунд 9) швабра висит на крючках ВНУТРИ шкафа — зона взятия здесь
    HS("hs_mop", [865, 58, 120, 462], node="take_mop", name="Швабра",
       hide_on=["done:take_mop"], doc_rmb="doc_mop_tag"),
    HS("hs_z_hooks", [788, 155, 76, 100], name="Крючки", look=True),
    HS("hs_z_hooks2", [1018, 155, 112, 100], name="Крючки", look=True),
    HS("hs_z_rag", [715, 520, 205, 170], name="Тряпка", look=True),
    HS("hs_z_bottles", [895, 715, 205, 280], name="Бутыли", look=True),
    HS("hs_z_bucket2", [680, 745, 205, 250], name="Ведро", look=True),
], "cutouts": [
    # (раунд 9) швабра (черенок удлинён ~x2, gen_r9_cutouts) на среднем крючке
    CO("cutouts/st_mop_on_hook.png", [763, 50], 1.5, z=20,
       hide_on=["done:take_mop"]),
]}

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
    # (раунд 19) АРХИВ БУМАГ — кнопка «БУМАГИ» в HUD. Замечание автора:
    # прочитанную бирку с подарка после вскрытия было не посмотреть заново
    # (подарок исчезает, а сотка уходит в кофемашину вместе с открыткой).
    # Здесь — порядок строк в архиве; показываются только прочитанные.
    "doc_list": [
        "doc_santa", "doc_postcard", "doc_card", "doc_sticker", "doc_poster",
        "doc_calendar", "doc_karaoke", "doc_chat", "doc_order", "doc_about",
        "doc_dict", "doc_skud_blank", "doc_registry", "doc_journal",
        "doc_bench_note", "doc_schema", "doc_mop_tag",
    ],
}

os.makedirs("design", exist_ok=True)
with open("design/scene.json", "w", encoding="utf-8") as f:
    json.dump(scene, f, ensure_ascii=False, indent=1)
nhs = sum(len(r["hotspots"]) for r in scene["rooms"].values()) + \
      sum(len(z["hotspots"]) for z in scene["zooms"].values())
nco = sum(len(r["cutouts"]) for r in scene["rooms"].values()) + \
      sum(len(z["cutouts"]) for z in scene["zooms"].values())
print(f"scene.json: hotspots={nhs}, cutouts={nco}, zooms={len(scene['zooms'])}")
