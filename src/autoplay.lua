-- src/autoplay.lua — исполнение сценария через реальный UI (гаунтлет Фазы 4)
local ap = {active = false}
local json = require("src.json")

local E            -- env: ui, scenes, state, texts, puzzles, scene
local steps, ip = {}, 1
local step_t = 0          -- время на текущем шаге (вотчдог)
local pace = 0            -- троттлинг между действиями
local shots_dir = "work/shots"
local pending_shot = nil  -- имя скрина, ждущего кадра
local shot_stage = 0
local log = io.stderr

local function die(msg)
  log:write("AUTOPLAY FAIL @step " .. ip .. ": " .. msg .. "\n")
  os.exit(1)
end

local function info(msg) log:write("[ap " .. ip .. "] " .. msg .. "\n") end

function ap.start(path, env)
  E = env
  local f = io.open(path, "rb")
  if not f then die("нет сценария " .. tostring(path)) end
  local raw = f:read("*a"); f:close()
  local doc = json.decode(raw)
  steps = doc.steps or doc
  os.execute('mkdir -p "' .. shots_dir .. '"')
  ap.active = true
  info("сценарий: " .. #steps .. " шагов")
end

-- ---------- примитивы ----------
local function click(x, y, btn) E.ui.mousepressed(x, y, btn or 1) end
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

local function badge_check(imgdata, want)
  -- сэмпл левой грани рамки портрета: x∈[20..34], y∈[840..980]
  local steel, brass = 0, 0
  local w, h = imgdata:getDimensions()
  local sx = w / 1920
  for yy = math.floor(840 * sx), math.floor(980 * sx), 2 do
    for xx = math.floor(20 * sx), math.floor(34 * sx) do
      if xx >= 0 and yy >= 0 and xx < w and yy < h then
        local r, g, b = imgdata:getPixel(xx, yy)
        if b > 0.45 and b > r * 1.25 then steel = steel + 1
        elseif r > 0.45 and r > b * 1.25 then brass = brass + 1 end
      end
    end
  end
  local got = (steel > brass) and "ПРЕДОК" or "ЛАПИДУС"
  info(("badge steel=%d brass=%d → %s"):format(steel, brass, got))
  if want and got ~= want then
    die("бейдж: ожидал " .. want .. ", вижу " .. got)
  end
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
  elseif op == "close_reader" then
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
    keypad_type(ans)
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
  elseif op == "assert_steps_ge" then
    if E.state.steps < s.n then die("шагов " .. E.state.steps .. " < " .. s.n) end
    return true
  elseif op == "quit" then
    info("DONE steps=" .. E.state.steps)
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
    print("AUTOPLAY OK")
    os.exit(0)
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
    s._w = s._w - 0.05
    if s._w <= 0 then ip = ip + 1; step_t = 0 end
  elseif r == "shot" then
    -- pending установлен; ip двинется после снятия
  end
end

return ap
