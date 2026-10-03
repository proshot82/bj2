-- main.lua — «Латунный янычар 2.0» (LÖVE 11.5)
local json = require("src.json")
local State = require("src.core.state")
local scenes = require("src.scenes")
local ui = require("src.ui")
local touch = require("src.touch")

local IMG, AUD, F = {}, {}, {}
local S, P, T, ST
local letter = {sx = 1, sy = 1, ox = 0, oy = 0}
local AUTOPLAY = nil
local HEADLESS = false   -- true в selftest/autoplay: там нужен os.exit, а не экран ошибки
local cur_cursor = nil   -- (аудит F10) setCursor только при смене

local function readfile(p)
  local data = love.filesystem.read(p)
  assert(data, "no file " .. p)
  return data
end

-- ---------- сбор манифеста картинок из scene.json ----------
local function gfx_manifest()
  local set = {}
  local function add(p) if p then set["assets/gfx/" .. p] = true end end
  for _, room in pairs(S.rooms) do
    add(room.bg.night); add(room.bg.day)
    for _, c in ipairs(room.cutouts) do
      add(c.img); add(c.img_day)
      for _, fr in ipairs(c.frames or {}) do add(fr) end
    end
  end
  for _, z in pairs(S.zooms) do
    add(z.bg)
    for _, c in ipairs(z.cutouts) do
      add(c.img); add(c.img_day)
      for _, fr in ipairs(c.frames or {}) do add(fr) end
    end
  end
  add(S.fx.util_handle)
  local emo = {lap = {"neutral","tired","panic","inspired","smug",
                      "triumphant","worried","angry"},
               anc = {"calm","proud","stern","smug"}}
  for s, list in pairs(emo) do
    for _, e in ipairs(list) do
      set["assets/gfx/portraits/port_" .. s .. "_" .. e .. ".png"] = true
    end
  end
  set["assets/gfx/portraits/port_crown_overlay.png"] = true
  for id in pairs(T.item_names) do
    set["assets/gfx/icons/ic_" .. id:gsub("^relic_", "") .. ".png"] = true
  end
  for _, p in ipairs({"ui/bg_title.png", "ui/logo_title.png",
                      "ui/paper_reader.png", "ui/icon_512.png"}) do
    set["assets/gfx/" .. p] = true
  end
  for _, c in ipairs({"cursor_normal.png", "cursor_act.png",
                      "cursor_move.png", "cursor_zoom.png"}) do
    set["assets/gfx/cursors/" .. c] = true
  end
  return set
end

local AUDIO_LIST = {
  "beep_err","beep_ok","bill","blip_anc","blip_lap","bolt_break",
  "breaker_click","coffee","creak","crunch","garland","hiss","key_turn",
  "knock","mop_hook","net_fall","paper","pickup","psh","pump","splash",
  "step_a","step_b","transition","tumbler","ui_click","utility_door",
  "valve","victory","zoom_in","zoom_out",
}
-- музыка 2.0.5: фоны и слои — луп (stream), стингеры — one-shot (static)
local MUSIC_LIST = {
  "bgm_title","bgm_night_a","bgm_night_b","bgm_day_a","bgm_day_b","bgm_epilogue",
  "layer_nervous","layer_garland","sting_power","sting_crown","sting_solved",
}

-- (аудит Н1) Файлы, которые лежат в дереве, но движку не нужны. Список именно
-- ЗДЕСЬ, а не в документации: заметка в markdown устаревает молча, а этот
-- список сверяется селфтестом — и лишний файл, и запись о несуществующем
-- роняют сборку. (Релиз 2.0.5: st_siren_day.png и ambient.ogg убраны из
-- дерева в карантин work/orig_release205/ — список пуст, дерево чистое.)
local UNUSED_ASSETS = {}

-- рекурсивный обход дерева ассетов (love.filesystem, без команд оболочки)
local function asset_tree(dir, out)
  out = out or {}
  for _, name in ipairs(love.filesystem.getDirectoryItems(dir)) do
    local p = dir .. "/" .. name
    local info = love.filesystem.getInfo(p)
    if info and info.type == "directory" then asset_tree(p, out)
    elseif info then out[p] = true end
  end
  return out
end

-- ---------- selftest ----------
local function selftest()
  HEADLESS = true
  local ok = true
  local function fail(msg) print("SELFTEST FAIL: " .. msg); ok = false end
  for p in pairs(gfx_manifest()) do
    if not love.filesystem.getInfo(p) then fail("нет файла " .. p) end
  end
  for _, list in ipairs({AUDIO_LIST, MUSIC_LIST}) do
    for _, a in ipairs(list) do
      if not love.filesystem.getInfo("assets/audio/" .. a .. ".ogg") then
        fail("нет аудио " .. a)
      end
    end
  end
  for _, f in ipairs({"fonts/PTSans-Regular.ttf", "fonts/PTSans-Bold.ttf",
                      "fonts/Neucha.ttf"}) do
    if not love.filesystem.getInfo("assets/" .. f) then fail("нет " .. f) end
  end
  -- (аудит Н1) Дерево ассетов сверяется в ОБЕ стороны. Нехватку ловят проверки
  -- выше; здесь ловится лишнее: файл, который движок не грузит, едет в portable
  -- ZIP мёртвым весом, а через полгода никто уже не помнит, забытый он или
  -- нужный. Осознанно неиспользуемое перечислено в UNUSED_ASSETS с причиной.
  do
    local need = gfx_manifest()
    for _, list in ipairs({AUDIO_LIST, MUSIC_LIST}) do
      for _, a in ipairs(list) do need["assets/audio/" .. a .. ".ogg"] = true end
    end
    for _, f in ipairs({"fonts/PTSans-Regular.ttf", "fonts/PTSans-Bold.ttf",
                        "fonts/Neucha.ttf"}) do
      need["assets/" .. f] = true
    end
    local have = asset_tree("assets")
    local stray = {}
    for p in pairs(have) do
      if not need[p] and not UNUSED_ASSETS[p] then stray[#stray + 1] = p end
    end
    table.sort(stray)
    for _, p in ipairs(stray) do
      fail("файл в дереве, но движку не нужен: " .. p ..
           " — удалить или внести в UNUSED_ASSETS с причиной")
    end
    for p, why in pairs(UNUSED_ASSETS) do
      if not have[p] then
        fail("UNUSED_ASSETS ссылается на несуществующий файл: " .. p ..
             " (" .. why .. ") — запись протухла, убрать")
      elseif need[p] then
        fail("файл числится неиспользуемым, но движок его грузит: " .. p ..
             " — убрать из UNUSED_ASSETS")
      end
    end
    local function count(t) local k = 0; for _ in pairs(t) do k = k + 1 end; return k end
    print(("[selftest] ассеты: нужных %d, в дереве %d, осознанно лишних %d")
          :format(count(need), count(have), count(UNUSED_ASSETS)))
  end
  for _, p in ipairs({"assets/gfx/cutouts/st_gift.png",
                      "assets/gfx/cutouts/st_net_on_top.png"}) do
    local id = love.image.newImageData(p)
    local has_alpha = false
    for y = 0, id:getHeight() - 1, 7 do
      for x = 0, id:getWidth() - 1, 7 do
        local _, _, _, a = id:getPixel(x, y)
        if a < 0.99 then has_alpha = true; break end
      end
      if has_alpha then break end
    end
    if not has_alpha then fail("катаут без прозрачности: " .. p) end
  end
  local items = {}
  for k in pairs(T.item_names) do items[#items + 1] = k end
  local st2 = State.new(P, items)
  local sok, res = st2:solve(300)
  if not sok then fail("солвер: " .. tostring(res)) end
  if ok then
    print("SELFTEST OK (solver " .. tostring(res) .. " шагов)")
    os.exit(0)
  else
    os.exit(1)
  end
end

-- ---------- load ----------
function love.load(args)
  local function load_json(path)   -- (аудит F14) внятная ошибка при повреждённых данных
    local ok, v = pcall(json.decode, readfile(path))
    if not ok then error("повреждён файл данных " .. path .. ": " .. tostring(v)) end
    return v
  end
  S = load_json("design/scene.json")
  P = load_json("design/puzzles.json")
  T = load_json("design/texts.json")

  local mode = nil
  for i, a in ipairs(args or {}) do
    if a == "--selftest" then mode = "selftest" end
    if a == "--autoplay" then mode = "autoplay"; AUTOPLAY = args[i + 1] end
  end
  if mode == "selftest" then selftest() end

  local function fnt(path, size)
    return love.graphics.newFont("assets/fonts/" .. path, size)
  end
  F.dlg = fnt("PTSans-Regular.ttf", 34)
  F.small = fnt("PTSans-Regular.ttf", 24)
  F.tiny = fnt("PTSans-Regular.ttf", 18)
  F.badge = fnt("PTSans-Bold.ttf", 26)
  F.h1 = fnt("PTSans-Bold.ttf", 96)
  F.h2 = fnt("PTSans-Bold.ttf", 44)
  F.plate = fnt("PTSans-Bold.ttf", 30)
  F.paper = fnt("PTSans-Regular.ttf", 34)
  F.paper_small = fnt("PTSans-Regular.ttf", 26)
  F.paper_title = fnt("PTSans-Bold.ttf", 44)
  F.hand = fnt("Neucha.ttf", 36)

  for p in pairs(gfx_manifest()) do
    local key = p:gsub("^assets/gfx/", "")
    IMG[key] = love.graphics.newImage(p)
  end
  for _, a in ipairs(AUDIO_LIST) do
    AUD[a] = love.audio.newSource("assets/audio/" .. a .. ".ogg", "static")
  end
  for _, a in ipairs(MUSIC_LIST) do
    AUD[a] = love.audio.newSource("assets/audio/" .. a .. ".ogg",
      a:match("^sting_") and "static" or "stream")
  end

  local items = {}
  for k in pairs(T.item_names) do items[#items + 1] = k end
  ST = State.new(P, items)

  scenes.init(S, ST, IMG, T)
  scenes.set_fonts(F)
  ui.init(T, P, ST, scenes, IMG, AUD, F)
  ui.scene_json = S

  local curs = {}
  local hot = {normal = {14, 6}, act = {20, 10}, move = {14, 6}, zoom = {22, 22}}
  for _, n in ipairs({"normal", "act", "move", "zoom"}) do
    local cid = love.image.newImageData("assets/gfx/cursors/cursor_" .. n .. ".png")
    curs[n] = love.mouse.newCursor(cid, hot[n][1], hot[n][2])
  end
  ui.cursors = curs
  love.mouse.setCursor(curs.normal)

  love.graphics.setDefaultFilter("linear", "linear", 4)
  love.graphics.setBackgroundColor(0, 0, 0)

  if mode == "autoplay" then
    HEADLESS = true
    local ap = require("src.autoplay")
    ap.start(AUTOPLAY, {ui = ui, scenes = scenes, state = ST,
                        texts = T, puzzles = P, scene = S})
  end
  -- (р.24) Веб-оболочка (web/index.html) ловит эту строку в консоли и только
  -- тогда открывает кнопку «Играть»: до неё браузер ещё декодирует ассеты.
  if love.system.getOS() == "Web" then print("BJ2 READY") end
end

-- ---------- letterbox ----------
local function recalc_letterbox()
  local w, h = love.graphics.getDimensions()
  local s = math.min(w / 1920, h / 1080)
  letter.sx, letter.sy = s, s
  letter.ox = (w - 1920 * s) / 2
  letter.oy = (h - 1080 * s) / 2
end
function love.resize() recalc_letterbox() end
-- scenes получает живую ссылку на letterbox (для scissor снега)

local function to_world(x, y)
  return (x - letter.ox) / letter.sx, (y - letter.oy) / letter.sy
end

-- Клик экранной точкой. Один вход и для мыши, и для распознанного касания:
-- пересчёт через letterbox, точки на чёрных полосах мимо мира.
local function press(x, y, btn)
  local wx, wy = to_world(x, y)
  if wx < 0 or wx >= 1920 or wy < 0 or wy >= 1080 then return end
  ui.mousepressed(wx, wy, btn)
end
touch.init(press)

-- ---------- цикл ----------
function love.update(dt)
  recalc_letterbox()
  scenes.set_letterbox(letter)
  touch.update(dt)   -- (р.25) удержание пальца: ПКМ, как только выйдет срок
  if not ui.in_menu() then scenes.update(dt) end
  ui.update(dt)
  local ap = package.loaded["src.autoplay"]
  if ap and ap.active then ap.update(dt) end
  local want = "normal"
  if not ui.in_menu() and not ui.dialog_active() and not ui.widget_kind() then
    local mx, my = to_world(love.mouse.getPosition())
    local h = scenes.hit(mx, my)
    want = h and (h.cursor or "act") or "normal"
  end
  if want ~= cur_cursor and ui.cursors and ui.cursors[want] then
    love.mouse.setCursor(ui.cursors[want]); cur_cursor = want   -- (аудит F10) только при смене
  end
end

function love.draw()
  love.graphics.push()
  love.graphics.translate(letter.ox, letter.oy)
  love.graphics.scale(letter.sx, letter.sy)
  if not ui.title_shown() then
    scenes.draw(ui.space_down())
  end
  ui.draw_overlays()
  love.graphics.pop()
  love.graphics.setColor(0, 0, 0)
  local w, h = love.graphics.getDimensions()
  if letter.ox > 0 then
    love.graphics.rectangle("fill", 0, 0, letter.ox, h)
    love.graphics.rectangle("fill", w - letter.ox, 0, letter.ox + 1, h)
  end
  if letter.oy > 0 then
    love.graphics.rectangle("fill", 0, 0, w, letter.oy)
    love.graphics.rectangle("fill", 0, h - letter.oy, w, letter.oy + 1)
  end
  love.graphics.setColor(1, 1, 1)
  touch.draw()   -- (р.25) кольцо удержания — поверх всего, в координатах окна
end

-- (р.25) Касание SDL присылает сюда же — ЛКМ с istouch=true (на love.js в
-- браузере проверено в Chromium; сенсорный экран под Windows SDL отдаёт так
-- же, но на живом устройстве это не проверялось). Его разбирает распознаватель
-- src/touch.lua: тап = ЛКМ, удержание = ПКМ, сдвиг пальца — отмена. Мышь идёт
-- прежним путём: клик срабатывает на нажатии, как и раньше.
function love.mousepressed(x, y, btn, istouch)
  if istouch then touch.pressed(x, y); return end
  touch.mouse()
  press(x, y, btn)
end

function love.mousereleased(x, y, btn, istouch)
  if istouch then touch.released(x, y) end
end

function love.mousemoved(x, y, dx, dy, istouch)
  if istouch then touch.moved(x, y) end
end

function love.keypressed(key)
  touch.mouse()
  ui.keypressed(key)
end

function love.quit()
  if ui.in_session() and not ui.victory_done() then ui.save() end
end

function love.errorhandler(msg)
  -- (аудит F03) headless (selftest/autoplay) — прежний os.exit; иначе экран ошибки
  -- + запись crash.log в каталог сохранений (stderr на Windows-GUI не виден).
  local report = "FATAL: " .. tostring(msg) .. "\n" .. debug.traceback() .. "\n"
  io.stderr:write(report)
  pcall(function()
    love.filesystem.append("crash.log", os.date("%Y-%m-%d %H:%M:%S ") .. report)
  end)
  if HEADLESS then os.exit(1) end
  if love.audio then pcall(love.audio.stop) end
  local ok_font, font = pcall(function() return love.graphics.newFont(18) end)
  return function()
    love.event.pump()
    for e in love.event.poll() do
      if e == "quit" or e == "keypressed" or e == "mousepressed" then return 1 end
    end
    love.graphics.origin()
    love.graphics.setScissor()
    love.graphics.clear(0.10, 0.10, 0.13)
    love.graphics.setColor(1, 1, 1)
    if ok_font and font then love.graphics.setFont(font) end
    love.graphics.printf(
      "Что-то сломалось.\nПодробности сохранены в crash.log (папка сохранений).\n\n"
      .. tostring(msg) .. "\n\n[любая клавиша или закрыть окно] — выход",
      80, 80, love.graphics.getWidth() - 160)
    love.graphics.present()
    love.timer.sleep(0.05)
  end
end
