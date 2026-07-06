-- main.lua — «Латунный янычар 2.0» (LÖVE 11.5)
local json = require("src.json")
local State = require("src.core.state")
local scenes = require("src.scenes")
local ui = require("src.ui")

local IMG, AUD, F = {}, {}, {}
local S, P, T, ST
local letter = {sx = 1, sy = 1, ox = 0, oy = 0}
local AUTOPLAY = nil

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
      add(c.img)
      for _, fr in ipairs(c.frames or {}) do add(fr) end
    end
  end
  for _, z in pairs(S.zooms) do
    add(z.bg)
    for _, c in ipairs(z.cutouts) do
      add(c.img)
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
  "ambient","beep_err","beep_ok","bill","blip_anc","blip_lap","bolt_break",
  "breaker_click","coffee","creak","crunch","garland","hiss","key_turn",
  "knock","mop_hook","net_fall","paper","pickup","psh","pump","splash",
  "step_a","step_b","transition","tumbler","ui_click","utility_door",
  "valve","victory","zoom_in","zoom_out",
}

-- ---------- selftest ----------
local function selftest()
  local ok = true
  local function fail(msg) print("SELFTEST FAIL: " .. msg); ok = false end
  for p in pairs(gfx_manifest()) do
    if not love.filesystem.getInfo(p) then fail("нет файла " .. p) end
  end
  for _, a in ipairs(AUDIO_LIST) do
    if not love.filesystem.getInfo("assets/audio/" .. a .. ".ogg") then
      fail("нет аудио " .. a)
    end
  end
  for _, f in ipairs({"fonts/PTSans-Regular.ttf", "fonts/PTSans-Bold.ttf",
                      "fonts/Neucha.ttf"}) do
    if not love.filesystem.getInfo("assets/" .. f) then fail("нет " .. f) end
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
  S = json.decode(readfile("design/scene.json"))
  P = json.decode(readfile("design/puzzles.json"))
  T = json.decode(readfile("design/texts.json"))

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
    AUD[a] = love.audio.newSource("assets/audio/" .. a .. ".ogg",
      a == "ambient" and "stream" or "static")
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
    local ap = require("src.autoplay")
    ap.start(AUTOPLAY, {ui = ui, scenes = scenes, state = ST,
                        texts = T, puzzles = P, scene = S})
  end
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

-- ---------- цикл ----------
function love.update(dt)
  recalc_letterbox()
  scenes.set_letterbox(letter)
  if not ui.in_menu() then scenes.update(dt) end
  ui.update(dt)
  local ap = package.loaded["src.autoplay"]
  if ap and ap.active then ap.update(dt) end
  if not ui.in_menu() and not ui.dialog_active() and not ui.widget_kind() then
    local mx, my = to_world(love.mouse.getPosition())
    local h = scenes.hit(mx, my)
    local kind = h and (h.cursor or "act") or "normal"
    if ui.cursors[kind] then love.mouse.setCursor(ui.cursors[kind]) end
  elseif ui.cursors then
    love.mouse.setCursor(ui.cursors.normal)
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
end

function love.mousepressed(x, y, btn)
  local wx, wy = to_world(x, y)
  if wx < 0 or wx >= 1920 or wy < 0 or wy >= 1080 then return end
  ui.mousepressed(wx, wy, btn)
end

function love.keypressed(key)
  ui.keypressed(key)
end

function love.quit()
  if not ui.in_menu() and not ui.victory_done() then ui.save() end
end

function love.errorhandler(msg)
  io.stderr:write("FATAL: " .. tostring(msg) .. "\n" ..
    debug.traceback() .. "\n")
  os.exit(1)
end
