-- src/autoplay.lua — исполнение сценария через реальный UI (гаунтлет Фазы 4)
local ap = {active = false}
local json = require("src.json")

local E            -- env: ui, scenes, state, texts, puzzles, scene
local steps, ip = {}, 1
local step_t = 0          -- время на текущем шаге (вотчдог)
local pace = 0            -- троттлинг между действиями
-- (видео 2.0.5) честный такт: паузы и ожидания декрементируются реальным dt
-- кадра (кламп 0.05..0.5), а не фиксированными 0.05 за тик — иначе под
-- faketime или при просадке FPS ожидания и вотчдог расходятся в разы.
local last_tick = 0.05
local shots_dir = "work/shots"
local pending_shot = nil  -- имя скрина, ждущего кадра
local shot_stage = 0
local log = io.stderr

-- (аудит В3) Успех гаунтлета обязан подтверждаться терминальным условием.
-- Раньше он печатался просто по исчерпании списка шагов: сценарий, который
-- сломался на середине и «доехал» до конца впустую, рапортовал AUTOPLAY OK.
local TERMINAL_FLAG = "victory"
local terminal_seen = false
-- (аудит В4) Счётчики бейдж-проверок: сколько снято, сколько подтверждено.
local badge_total, badge_checked = 0, 0

local function die(msg)
  log:write("AUTOPLAY FAIL @step " .. ip .. ": " .. msg .. "\n")
  os.exit(1)
end

local function info(msg) log:write("[ap " .. ip .. "] " .. msg .. "\n") end

-- (аудит Н4) Каталог скринов создавался слепым `os.execute("mkdir -p …")`:
-- код возврата не проверялся, на не-POSIX системе команда просто не та, и
-- отказ всплывал позже — падением на первом же скриншоте. Теперь: сперва
-- проба на запись, каталог создаётся только если пробы нет, результат
-- перепроверяется, и невозможность писать — внятная ошибка сразу на старте.
local function ensure_shots_dir()
  local function writable()
    local probe = io.open(shots_dir .. "/.probe", "wb")
    if not probe then return false end
    probe:close(); os.remove(shots_dir .. "/.probe"); return true
  end
  if writable() then return end
  local win = (package.config:sub(1, 1) == "\\")
  os.execute(win and ('mkdir "' .. shots_dir:gsub("/", "\\") .. '"')
                  or ('mkdir -p "' .. shots_dir .. '"'))
  if not writable() then
    die("каталог скринов недоступен для записи: " .. shots_dir)
  end
end

function ap.start(path, env)
  E = env
  local f = io.open(path, "rb")
  if not f then die("нет сценария " .. tostring(path)) end
  local raw = f:read("*a"); f:close()
  local doc = json.decode(raw)
  steps = doc.steps or doc
  ensure_shots_dir()
  ap.active = true
  info("сценарий: " .. #steps .. " шагов")
end

-- ---------- примитивы ----------
-- (аудит: смок в «кривом» разрешении) Клик идёт ЧЕРЕЗ ОКНО, а не прямо в UI.
-- Раньше здесь стояло E.ui.mousepressed(x, y) — то есть автоплей входил в игру
-- на ступеньку ниже игрока и перепрыгивал love.mousepressed вместе с пересчётом
-- экранных координат в мировые. Смок при 1536×864 из-за этого не проверял ровно
-- то, ради чего стоит в конвейере: сломанный letterbox он проходил насквозь.
-- Теперь мировая точка переводится в экранную сценой и отдаётся в love.mousepressed
-- — тот же вход, что у настоящей мыши. При 1920×1080 масштаб единичный и сдвиг
-- нулевой, так что основной гаунтлет ведёт себя в точности как прежде.
local function click(x, y, btn)
  local sx, sy = E.scenes.to_screen(x, y)
  love.mousepressed(sx, sy, btn or 1)
end
local function key(k) E.ui.keypressed(k) end

local function dismiss_once()
  if E.ui.dialog_active() then click(1200, 900, 1); return true end
  return false
end

local function hs_center(id)
  local cx, cy, h = E.scenes.hotspot_center(id)
  return cx, cy, h
end

-- клик по клавише кейпада (реальные координаты виджета)
local KEYPOS = {}
do
  local keys = {"1","2","3","4","5","6","7","8","9","C","0","OK"}
  for i, k in ipairs(keys) do
    -- центр кнопки кейпада = keypad_geom(770,360,120,88): шаг 130/98, центр +60/+44
    KEYPOS[k] = {770 + ((i - 1) % 3) * 130 + 60, 360 + math.floor((i - 1) / 3) * 98 + 44}
  end
end
local function keypad_type(code)
  for ch in tostring(code):gmatch(".") do
    click(KEYPOS[ch][1], KEYPOS[ch][2], 1)
  end
  click(KEYPOS.OK[1], KEYPOS.OK[2], 1)
end

-- ---------- скрин + бейдж-чек ----------
local function request_shot(name, and_badge)
  pending_shot = {name = name, badge = and_badge}
  shot_stage = 1
end

local function save_shot(imgdata, name)
  local fd = imgdata:encode("png")
  local out = io.open(shots_dir .. "/" .. name .. ".png", "wb")
  if not out then die("не открыть " .. shots_dir .. "/" .. name .. ".png") end
  out:write(fd:getString()); out:close()
  info("shot " .. name)
end

-- (аудит В4) Проверка цвета рамки портрета — единственный пиксельный
-- свидетель того, что портрет реально сменился по спикеру. Прежняя версия
-- была неверна трижды: (1) масштаб w/1920 применялся к ОБЕИМ осям и без
-- сдвига леттербокса — в нештатном разрешении окно сэмпла уезжало мимо
-- рамки; (2) грубая эвристика по каналам ловила и тона портрета под
-- рамкой; (3) при нуле совпадений «steel > brass» ложно давало ЛАПИДУСА,
-- то есть слепой кадр молча засчитывался как успешная проверка.
-- Теперь: честный мир→экран через леттербокс, классификация по эталонным
-- цветам рамки и явные пороги уверенности — мало точек или ничья роняют
-- гаунтлет вместо тихого вердикта.
local BADGE_REF = {                 -- держать синхронно с C.brass/C.steel в ui.lua
  ["ЛАПИДУС"] = {0.72, 0.58, 0.34},
  ["ПРЕДОК"]  = {0.55, 0.70, 0.86},
}
local function badge_check(imgdata, want)
  local w, h = imgdata:getDimensions()
  local s = math.min(w / 1920, h / 1080)          -- как recalc_letterbox()
  local ox, oy = (w - 1920 * s) / 2, (h - 1080 * s) / 2
  -- мировая полоса левой грани рамки портрета (24±дрожь, ширина линии 4):
  -- берём с запасом на дрожь плашки ±6 px
  local X0, X1, Y0, Y1 = 14, 40, 820, 1000
  local hit, total = {}, 0
  for name in pairs(BADGE_REF) do hit[name] = 0 end
  for wy = Y0, Y1 do
    for wx = X0, X1 do
      local xx, yy = math.floor(ox + wx * s), math.floor(oy + wy * s)
      if xx >= 0 and yy >= 0 and xx < w and yy < h then
        local r, g, b = imgdata:getPixel(xx, yy)
        local best, bd = nil, 1e9
        for name, c in pairs(BADGE_REF) do
          local d = (r - c[1])^2 + (g - c[2])^2 + (b - c[3])^2
          if d < bd then best, bd = name, d end
        end
        if bd < 0.01 then hit[best] = hit[best] + 1; total = total + 1 end
      end
    end
  end
  local lap, anc = hit["ЛАПИДУС"], hit["ПРЕДОК"]
  local got = (anc > lap) and "ПРЕДОК" or "ЛАПИДУС"
  local win, lose = math.max(lap, anc), math.min(lap, anc)
  info(("badge ЛАПИДУС=%d ПРЕДОК=%d → %s"):format(lap, anc, got))
  badge_total = badge_total + 1
  -- порог уверенности: рамка обязана быть найдена, и однозначно
  local need = math.max(40, math.floor(120 * s * s))
  if total < need then
    die(("бейдж: рамка не опознана (совпадений %d < %d) — кадр пустой " ..
         "или сэмпл мимо"):format(total, need))
  end
  if lose * 3 > win then
    die(("бейдж: неуверенный вердикт ЛАПИДУС=%d ПРЕДОК=%d"):format(lap, anc))
  end
  if want and got ~= want then
    die("бейдж: ожидал " .. want .. ", вижу " .. got)
  end
  if want then badge_checked = badge_checked + 1 end
end

-- ---------- исполнение шага ----------
local function exec(s)
  local op = s.op
  if op == "click" then click(s.x, s.y, s.btn or 1); return true
  elseif op == "key" then key(s.k); return true
  elseif op == "esc" then key("escape"); return true
  elseif op == "wait" then
    s._w = (s._w or s.s or 0.5)
    return "wait"
  elseif op == "dismiss" then
    if dismiss_once() then return false end
    return true
  elseif op == "dismiss_all" then
    if dismiss_once() then return false end
    return true
  elseif op == "talk" then
    -- (видео 2.0.5) зрительский темп: реплика висит столько, сколько её
    -- печатать (40 симв/с) и читать, потом клик «дальше». Вотчдог шага
    -- сбрасывается вручную — у опа свой сторож на 60 с суммарно.
    step_t = 0
    s._total = (s._total or 0) + last_tick
    if s._total > 20 then die("talk: одна реплика висит дольше 20с") end
    if not E.ui.dialog_active() then return true end
    if s._pause == nil then
      local txt = E.ui.dialog_line() or ""
      s._pause = math.min(7.5, 0.9 + (#txt / 1.7) * 0.062)
    end
    s._pause = s._pause - last_tick
    if s._pause <= 0 then dismiss_once(); s._pause = nil; s._total = 0 end
    return false
  elseif op == "hint_ready" then
    -- (видео 2.0.5) дождаться истечения кулдауна Предка и нажать совет —
    -- без этого в кадр попадала бы служебная кулдаун-реплика.
    step_t = 0
    s._total = (s._total or 0) + last_tick
    if s._total > 75 then die("hint_ready: кулдаун не истёк за 75с") end
    if E.ui.dialog_active() then dismiss_once(); return false end
    if E.ui.hint_ready() then E.ui.hint(); return true end
    return false
  elseif op == "read_doc" then
    -- (видео 2.0.5) листать читалку с паузой на чтение каждой страницы;
    -- ЛКМ листает, на последней странице ЛКМ закрывает (семантика ui).
    step_t = 0
    s._total = (s._total or 0) + last_tick
    if s._total > 25 then die("read_doc: одна страница/реплика висит дольше 25с") end
    if E.ui.dialog_active() then
      -- реплики поверх читалки (авто-открытка) читаются в темпе talk
      if s._dp == nil then
        local txt = E.ui.dialog_line() or ""
        s._dp = math.min(7.5, 0.9 + (#txt / 1.7) * 0.062)
      end
      s._dp = s._dp - last_tick
      if s._dp <= 0 then dismiss_once(); s._dp = nil; s._total = 0 end
      return false
    end
    if not E.ui.reader_open() then return true end
    if s._pause == nil then
      local _, _, chars = E.ui.reader_info()
      s._pause = math.min(14, 3.0 + (chars / 1.7) * 0.028)
    end
    s._pause = s._pause - last_tick
    if s._pause <= 0 then click(1200, 500, 1); s._pause = nil; s._total = 0 end
    return false
  elseif op == "close_reader" then
    -- (аудит С3) реплики теперь разбираются раньше читалки — ровно как рисуются.
    -- Значит ПКМ по документу под очередью реплик уйдёт в диалог, а не в
    -- читалку: сперва дочитываем очередь, потом закрываем документ. Без этого
    -- шаг крутился бы до таймаута.
    if E.ui.dialog_active() then dismiss_once(); return false end
    if E.ui.reader_open() then click(1200, 500, 2); return false end
    return true
  elseif op == "bench_bad" then
    -- кликнуть заведомо неверный ПЕРВЫЙ вентиль (рантайм сам выбирает)
    if E.ui.dialog_active() then dismiss_once(); return false end
    local first
    for _, m in ipairs(E.puzzles.answers.bench_seq) do
      if not m:match("^PUMP") then first = m; break end
    end
    local fbase = first:match("^(%u+%d?)")
    local map = {P = "hs_z_valve_p", K1 = "hs_z_valve_k1",
                 K2 = "hs_z_valve_k2", S = "hs_z_valve_s"}
    local pick
    for _, v in ipairs({"K1", "K2", "S", "P"}) do
      if v ~= fbase then pick = v; break end
    end
    local cx, cy = hs_center(map[pick])
    if not cx then die("нет вентиля для bench_bad") end
    click(cx, cy, 1)
    return true
  elseif op == "pump_early" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    local cx, cy = hs_center("hs_z_pump")
    if not cx then die("нет насоса") end
    click(cx, cy, 1)
    return true
  elseif op == "assert_bench_seq_len" then
    if #E.state.bench.seq ~= s.n then
      die("bench seq " .. #E.state.bench.seq .. " ≠ " .. s.n)
    end
    return true
  elseif op == "start_game" then
    -- реальный клик по «НАЧАТЬ НОВУЮ» на титуле
    click(960, 596, 1); return true
  elseif op == "continue_game" then
    click(960, 688, 1); return true
  elseif op == "setflag" then
    -- ТОЛЬКО для смок-рендеров: форсировать флаг состояния (utility_open/power_on)
    E.state.flags[s.f] = (s.v ~= false); return true
  elseif op == "click_hs" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    local cx, cy, h = hs_center(s.id)
    if not cx then return false end -- ждём появления (вотчдог поймает)
    click(cx, cy, s.btn or 1)
    return true
  elseif op == "rmb_hs" then
    s.btn = 2; s.op = "click_hs"; return false
  elseif op == "look_hs" then
    -- (видео 2.0.5) ПКМ-осмотр look-зоны: центр может быть перехвачен
    -- интерактивной зоной (rank-приоритет в scenes.hit — «Ручка и замок»
    -- под «Толкнуть дверь»), поэтому точка ищется перебором по сетке 5×5,
    -- пока hit не вернёт саму зону — так целился бы и живой игрок.
    if E.ui.dialog_active() then dismiss_once(); return false end
    local cx, cy, h = hs_center(s.id)
    if not cx then return false end       -- ждём появления (вотчдог поймает)
    local r = (E.scenes.mode() == "day" and h.rect_day) and h.rect_day or h.rect
    local px, py
    for gy = 1, 5 do
      for gx = 1, 5 do
        local x = r[1] + r[3] * gx / 6
        local y = r[2] + r[4] * gy / 6
        local hh = E.scenes.hit(x, y)
        if hh and hh.id == s.id then px, py = x, y; break end
      end
      if px then break end
    end
    if not px then
      die("look_hs: у зоны " .. s.id .. " нет точки, куда можно ткнуть")
    end
    click(px, py, 2)
    return true
  elseif op == "click_item" or op == "rmb_item" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    local idx
    for i, id in ipairs(E.state.inv_order) do
      if id == s.id then idx = i end
    end
    if not idx then die("нет предмета " .. s.id) end
    click(20 + (idx - 1) * 76 + 34, 8 + 34, op == "rmb_item" and 2 or 1)
    return true
  elseif op == "combine" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    local pos = {}
    for i, id in ipairs(E.state.inv_order) do pos[id] = i end
    if not (pos[s.a] and pos[s.b]) then die("нет пары " .. s.a .. "+" .. s.b) end
    click(20 + (pos[s.a] - 1) * 76 + 34, 42, 1)
    click(20 + (pos[s.b] - 1) * 76 + 34, 42, 1)
    return true
  elseif op == "code" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    if E.ui.widget_kind() ~= "keypad" then die("кейпад не открыт для " .. s.node) end
    local ans = s.value
    if not ans then
      local n = E.state.nodes[s.node]
      ans = E.puzzles.answers[n.lock.id]
    end
    if s.kp then
      -- (р.24) набор с цифрового блока: kp0..kp9 + kpenter через настоящий
      -- keypressed — так, как его шлёт LÖVE с NumPad
      for ch in tostring(ans):gmatch(".") do key("kp" .. ch) end
      key("kpenter")
    else
      keypad_type(ans)
    end
    return true
  elseif op == "form" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    if E.ui.widget_kind() ~= "form" then die("форма не открыта") end
    for _ = 1, 10 do key("backspace") end
    local no = s.no or tostring(E.puzzles.answers.skud.card_number)
    for ch in no:gmatch(".") do key(ch) end
    if not s.no then
      -- верная отправка: выставить отдел из ответов (форма сброшена на 1)
      key("tab")
      local depts = E.puzzles.tokens.depts
      local want
      for i, d in ipairs(depts) do
        if d == E.puzzles.answers.skud.dept then want = i end
      end
      for _ = 1, (want - 1) % #depts do key("right") end
    end
    click(660 + 190 + 110, 280 + 310 + 32, 1)
    return true
  elseif op == "bench_seq" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    if not s._vents then
      s._vents = {}
      for _, m in ipairs(E.puzzles.answers.bench_seq) do
        if not m:match("^PUMP") then s._vents[#s._vents + 1] = m end
      end
    end
    s._i = (s._i or 0) + 1
    if s._i > #s._vents then return true end
    local mv = s._vents[s._i]
    local base, dir = mv:match("^(%u+%d?)([+%-])$")
    if not base then die("плохой ход стенда: " .. tostring(mv)) end
    local map = {P = "hs_z_valve_p", K1 = "hs_z_valve_k1",
                 K2 = "hs_z_valve_k2", S = "hs_z_valve_s"}
    local cx, cy = hs_center(map[base])
    if not cx then die("нет вентиля " .. base) end
    click(cx, cy, dir == "-" and 2 or 1)
    return false
  elseif op == "bench_pumps" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    s._i = (s._i or 0) + 1
    if s._i > E.puzzles.answers.bench_pumps then return true end
    local cx, cy = hs_center("hs_z_pump")
    click(cx, cy, 1)
    return false
  elseif op == "breaker" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    local cx, cy, h = hs_center("hs_z_breaker_row")
    if not cx then die("нет рейки автоматов") end
    click(h.breaker_x0 + (s.i - 0.5) * h.breaker_step, cy, 1)
    return true
  elseif op == "hint" then
    if E.ui.dialog_active() then dismiss_once(); return false end
    click(1640 + 125, 12 + 24, 1)
    return true
  elseif op == "save" then E.ui.save(); return true
  elseif op == "load" then E.ui.load_save(); return true
  elseif op == "shot" then
    request_shot(s.name, nil); return "shot"
  elseif op == "shot_badge" then
    request_shot(s.name, s.v or "ПРЕДОК"); return "shot"
  elseif op == "assert_flag" then
    if not E.state:has_flag(s.f) then die("нет флага " .. s.f) end
    -- (аудит В3) факт достижения финала защёлкивается: op quit проверит его
    if s.f == TERMINAL_FLAG then terminal_seen = true end
    info("flag ok: " .. s.f); return true
  elseif op == "assert_not_flag" then
    if E.state:has_flag(s.f) then die("флаг не должен стоять: " .. s.f) end
    return true
  elseif op == "assert_item" then
    if not E.state.inv[s.id] then die("нет предмета " .. s.id) end
    info("item ok: " .. s.id); return true
  elseif op == "assert_no_item" then
    if E.state.inv[s.id] then die("предмет должен отсутствовать: " .. s.id) end
    return true
  elseif op == "assert_speaker" then
    if E.ui.current_speaker() ~= s.s then
      die("спикер " .. tostring(E.ui.current_speaker()) .. " ≠ " .. s.s)
    end
    return true
  elseif op == "assert_line" then
    -- (аудит К1) утверждение по тексту текущей реплики: s.sub — обязана
    -- содержаться, s.nosub — обязана отсутствовать (plain-поиск, не паттерн)
    local txt = E.ui.current_text()
    if not txt then die("нет активной реплики для assert_line") end
    if s.sub and not txt:find(s.sub, 1, true) then
      die("реплика не содержит " .. string.format("%q", s.sub) ..
          ": " .. txt:sub(1, 90))
    end
    if s.nosub and txt:find(s.nosub, 1, true) then
      die("реплика содержит запрещённое " .. string.format("%q", s.nosub) ..
          ": " .. txt:sub(1, 90))
    end
    info("line ok: " .. txt:sub(1, 40))
    return true
  elseif op == "assert_view" then
    local v = E.scenes.view()
    local cur = (v.kind == "zoom") and v.zoom or v.room
    if cur ~= s.id then die("вид " .. tostring(cur) .. " ≠ " .. s.id) end
    return true
  elseif op == "assert_widget" then
    if E.ui.widget_kind() ~= s.kind then
      die("виджет " .. tostring(E.ui.widget_kind()) .. " ≠ " .. tostring(s.kind))
    end
    return true
  -- ---- (р.24) регресс состояния интерфейса между партиями ----
  elseif op == "assert_menu" then
    local m = E.ui.state().menu            -- nil = меню закрыто
    if m ~= s.menu then
      die("меню " .. tostring(m) .. ", ожидалось " .. tostring(s.menu))
    end
    return true
  elseif op == "assert_no_selection" then
    local sel = E.ui.state().inv.selected
    if sel then die("выбран предмет «" .. sel .. "» — хвост прошлой партии") end
    return true
  elseif op == "assert_setting" then
    local v = E.ui.settings_table()[s.k]
    if v ~= s.v then
      die("настройка " .. tostring(s.k) .. " = " .. tostring(v) ..
          ", ожидалось " .. tostring(s.v))
    end
    return true
  elseif op == "assert_steps_ge" then
    if E.state.steps < s.n then die("шагов " .. E.state.steps .. " < " .. s.n) end
    return true
  -- ---- (р.19) АРХИВ БУМАГ ----
  elseif op == "hud" then
    -- жмём настоящую кнопку HUD её же координатами (ui.hud_button_rect)
    local x, y, w, h = E.ui.hud_button_rect(s.id)
    if not x then die("нет кнопки HUD «" .. tostring(s.id) .. "»") end
    click(x + w / 2, y + h / 2, 1)
    return true
  elseif op == "archive_doc" then
    local x, y, w, h = E.ui.docs_slot_of(s.id)
    if not x then die("в архиве нет бумаги «" .. tostring(s.id) .. "»") end
    click(x + w / 2, y + h / 2, 1)
    return true
  elseif op == "assert_archive_missing" then
    -- архив не должен быть оглавлением ненайденного: непрочитанной бумаги
    -- в нём нет вовсе (иначе список сам себе спойлер)
    if E.ui.docs_slot_of(s.id) then
      die("бумага " .. tostring(s.id) .. " лежит в архиве, хотя не прочитана")
    end
    return true
  elseif op == "assert_doc" then
    local r = E.ui.state().reader
    if not r then die("документ закрыт, ожидался " .. tostring(s.id)) end
    if r.doc ~= s.id then
      die("открыт " .. tostring(r.doc) .. " ≠ " .. tostring(s.id))
    end
    return true
  elseif op == "assert_no_widget" then
    if E.ui.widget_kind() then
      die("виджет «" .. tostring(E.ui.widget_kind()) .. "» открыт, ждали закрытый")
    end
    return true
  elseif op == "assert_reader" then
    local want = (s.open ~= false)
    if E.ui.reader_open() ~= want then
      die("документ " .. (E.ui.reader_open() and "открыт" or "закрыт") ..
          ", ожидалось " .. (want and "открыт" or "закрыт"))
    end
    return true
  elseif op == "assert_dialog_over_reader" then
    -- (аудит С3) Порядок разбора ввода обязан совпадать с порядком отрисовки.
    -- Здесь одновременно открыт документ и не пуста очередь реплик, а реплики
    -- рисуются ПОВЕРХ документа (draw_overlays: widget → reader → dlg).
    -- Значит клик обязан достаться реплике, а документ — остаться нетронутым.
    -- Прежде клик забирала читалка: человек листал невидимые ему страницы
    -- вслепую под чужой плашкой, а у одностраничного документа — закрывал его
    -- первым же кликом, так и не увидев.
    if not E.ui.reader_open() then
      die("нет открытого документа — проверять порядок слоёв не на чем")
    end
    if not E.ui.dialog_active() then
      die("очередь реплик пуста — проверять порядок слоёв не на чем")
    end
    local page0 = (E.ui.state().reader or {}).page
    click(1200, 500, 1)
    if not E.ui.reader_open() then
      die("клик закрыл документ: его забрала читалка, хотя сверху нарисована реплика")
    end
    if (E.ui.state().reader or {}).page ~= page0 then
      die("клик перелистнул документ: его забрала читалка, хотя сверху нарисована реплика")
    end
    return true
  elseif op == "assert_anim" then
    -- (аудит С2) метка идл-анимации ПОСТАВЛЕНА: без этого утверждения парный
    -- assert_no_anim ниже был бы зелен и на движке, который меток не ставит
    -- вовсе, — то есть проверял бы отсутствие механизма, а не его исправность
    local marks = E.scenes.anim_marks()
    for _, m in ipairs(marks) do if m == s.m then return true end end
    die("метка анимации " .. tostring(s.m) .. " не поставлена (висят: " ..
        (#marks > 0 and table.concat(marks, ",") or "нет") .. ")")
  elseif op == "assert_no_anim" then
    -- (аудит С2) метка снята: положение болта снова определяет флаг, а не
    -- отметка времени, застрявшая с прошлого прогона
    local marks = E.scenes.anim_marks()
    if #marks > 0 then
      die("метки анимации не сняты: " .. table.concat(marks, ","))
    end
    return true
  elseif op == "resize" then
    -- (аудит: смок в «кривом» разрешении) Смена размера окна прямо посреди
    -- прогона. Так проверяется letterbox: дальше сценарий продолжает бить по тем
    -- же мировым точкам, а попадать они обязаны через пересчёт.
    --
    -- Размер задаётся ИЗНУТРИ игры намеренно. Прежний конвейер полагался на
    -- «xvfb-run --screen 1536x864», но X разрешает окну быть больше экрана: окно
    -- оставалось 1920×1080, масштаб единичным, и смок годами гонялся ровно в том
    -- же разрешении, что и основной гаунтлет.
    local w, h = love.graphics.getDimensions()
    if w == s.w and h == s.h then
      -- Тождественный letterbox означал бы, что проверять нечего: такой прогон
      -- обязан падать, а не молча зеленеть.
      local px, py = E.scenes.to_screen(1920, 1080)
      if px == 1920 and py == 1080 then
        die(("окно %dx%d, но letterbox тождественный — смоку нечего проверять")
            :format(w, h))
      end
      info(("окно %dx%d, угол мира 1920,1080 → экран %.1f,%.1f")
           :format(w, h, px, py))
      return true
    end
    if not s.asked then
      s.asked = true
      love.window.setMode(s.w, s.h, {resizable = true, vsync = 1})
    end
    return false  -- ждём применения; не применится — поймает вотчдог
  elseif op == "assert_title" then
    -- (аудит С1) остались мы на титуле или нет. Отвергнутый сейв обязан
    -- оставить игрока в меню (ui.load_save вернула false, menu не снялся);
    -- принятый — увести в игру. Без этой проверки негативы на сейв мерили бы
    -- только текст в консоли, а не то, пустил ли движок в прогон.
    local want = (s.open ~= false)
    if E.ui.title_shown() ~= want then
      die("титул " .. (E.ui.title_shown() and "показан" or "снят") ..
          ", ожидалось " .. (want and "показан" or "снят"))
    end
    return true
  elseif op == "quit" then
    -- (аудит В3) успех печатается ТОЛЬКО здесь и только при подтверждённом
    -- терминальном условии
    if not terminal_seen then
      die("финал не подтверждён: за прогон не было assert_flag " .. TERMINAL_FLAG)
    end
    if badge_checked < 2 then
      die(("бейдж-проверок с ожиданием %d < 2 — смена портрета не доказана")
          :format(badge_checked))
    end
    info(("DONE steps=%d бейджей=%d/%d"):format(E.state.steps,
         badge_checked, badge_total))
    print("AUTOPLAY OK")
    os.exit(s.code or 0)
  else
    die("неизвестный op " .. tostring(op))
  end
end

function ap.update(dt)
  if not ap.active then return end
  step_t = step_t + dt
  pace = pace - dt
  if pace > 0 then return end
  last_tick = math.min(0.5, math.max(0.05, dt))
  pace = 0.05
  if step_t > 10 then
    local s = steps[ip]
    die("вотчдог 10с на " .. (s and s.op or "?") ..
        " (" .. tostring(s and (s.id or s.node or s.name) or "") .. ")" ..
        " dialog=" .. tostring(E.ui.dialog_active()) ..
        " widget=" .. tostring(E.ui.widget_kind()))
  end
  -- скрин: двухфазный (дать кадру отрисоваться)
  if pending_shot then
    if shot_stage == 1 then shot_stage = 2; return end
    local ps = pending_shot
    pending_shot = nil
    love.graphics.captureScreenshot(function(imgdata)
      save_shot(imgdata, ps.name)
      if ps.badge then badge_check(imgdata, ps.badge) end
    end)
    ip = ip + 1; step_t = 0
    return
  end
  local s = steps[ip]
  if not s then
    -- (аудит В3) сценарий кончился, не дойдя до op quit: раньше это молча
    -- печаталось как успех — прогон, оборвавшийся на середине, рапортовал OK
    die("сценарий исчерпан без op quit (шагов в файле " .. #steps ..
        ") — финал не подтверждён")
  end
  if not s._logged then
    s._logged = true
    info(tostring(s.op) .. " " ..
      tostring(s.id or s.node or s.name or s.f or s.i or s.a or ""))
  end
  local r = exec(s)
  if r == true then
    ip = ip + 1; step_t = 0
  elseif r == "wait" then
    s._w = s._w - last_tick
    if s._w <= 0 then ip = ip + 1; step_t = 0 end
  elseif r == "shot" then
    -- pending установлен; ip двинется после снятия
  end
end

return ap
