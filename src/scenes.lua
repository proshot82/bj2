-- src/scenes.lua — представление мира: фоны, катауты, хит-тест, идл-анимации
local scenes = {}
local lg = love.graphics

local S, ST, IMG   -- scene.json, state, кэш картинок
local view = {kind = "room", room = "A", zoom = nil}
local t_global = 0
local snow = nil
local LB = {sx = 1, sy = 1, ox = 0, oy = 0}   -- letterbox из main.lua

function scenes.init(scene_json, state, images, texts)
  S, ST, IMG = scene_json, state, images
  scenes.texts = texts
  snow = {}
  local rng = love.math.newRandomGenerator(20190101)
  for i = 1, 60 do
    snow[i] = {x = rng:random(6, 324), y = rng:random(70, 590),
               v = 14 + rng:random() * 26, ph = rng:random() * 6.28}
  end
end

function scenes.set_letterbox(lb) LB = lb end
function scenes.view() return view end
function scenes.mode() return ST.flags.power_on and "day" or "night" end

function scenes.goto_room(r) view.kind, view.room, view.zoom = "room", r, nil end
function scenes.goto_zoom(z)
  view.kind, view.zoom = "zoom", z
end
function scenes.leave_zoom()
  if view.kind == "zoom" then view.kind, view.zoom = "room", nil end
end

function scenes.mark_pump() ST._pump_anim = t_global end
function scenes.mark_bolt() ST._bolt_anim = t_global end
function scenes.time() return t_global end

local function flag_list_ok(obj)
  for _, f in ipairs(obj.show_on or {}) do
    if not ST:has_flag(f) then return false end
  end
  for _, f in ipairs(obj.hide_on or {}) do
    if ST:has_flag(f) then return false end
  end
  if obj.needs_flag and not ST:has_flag(obj.needs_flag) then return false end
  return true
end
scenes.visible = flag_list_ok

local function cur_container()
  if view.kind == "zoom" then return S.zooms[view.zoom] end
  return S.rooms[view.room]
end

local function pick_rect(h)
  if scenes.mode() == "day" and h.rect_day then return h.rect_day end
  return h.rect
end
local function pick_pos(c)
  if scenes.mode() == "day" and c.pos_day then return c.pos_day end
  return c.pos
end

-- ---------- катаут: специальная state-логика ----------
local function cutout_visible(c)
  if c.valve then
    -- вентиль: state on = вентиль уже переложен в bench.seq
    local placed = false
    for _, op in ipairs(ST.bench.seq) do
      if op == c.valve then placed = true end
    end
    if ST.done.bench_solve then placed = true end
    if c.valve == "P" and not ST.flags.wheel_on then return false end
    return (c.state == "on") == placed and flag_list_ok(c)
  end
  if c.pump then
    local down = (t_global % 0.9) < 0.28 and ST._pump_anim and
                 (t_global - ST._pump_anim) < 0.9
    return (c.pump == "down") == (down or false)
  end
  return flag_list_ok(c)
end

function scenes.update(dt)
  t_global = t_global + dt
  for _, f in ipairs(snow) do
    f.y = f.y + f.v * dt
    f.x = f.x + math.sin(t_global * 0.8 + f.ph) * 8 * dt
    if f.y > 596 then f.y = 66; end
    if f.x < 4 then f.x = 322 elseif f.x > 326 then f.x = 8 end
  end
end

local function draw_cutout(c)
  local img = IMG[c.img]
  local p = pick_pos(c)
  local a = 1
  if c.idle and c.frames then
    local period = (c.idle == "steam") and 0.5 or 0.62
    local fi = (math.floor(t_global / period) % #c.frames) + 1
    img = IMG[c.frames[fi]]
    if c.idle == "fish_wide" or c.idle == "fish_zoom" then
      local amp = (c.idle == "fish_zoom") and 26 or 8
      lg.draw(img, p[1] + math.sin(t_global * 0.9) * amp,
        p[2] + math.sin(t_global * 1.7) * amp * 0.35, 0, c.scale, c.scale)
      return
    end
  end
  if c.glow then a = 0.72 + 0.28 * math.sin(t_global * 3.2) end
  if c.glint then a = 0.55 + 0.45 * math.abs(math.sin(t_global * 2.1)) end
  lg.setColor(1, 1, 1, a)
  lg.draw(img, p[1], p[2], 0, c.scale, c.scale)
  lg.setColor(1, 1, 1, 1)
end

-- снег за окном офиса (ночь и день)
local function draw_snow()
  -- scissor в ЭКРАННЫХ координатах: учитываем letterbox
  lg.setScissor(LB.ox + 6 * LB.sx, LB.oy + 64 * LB.sy, 320 * LB.sx, 534 * LB.sy)
  lg.setColor(1, 1, 1, 0.85)
  for _, f in ipairs(snow) do
    lg.circle("fill", f.x, f.y, 2.1)
  end
  lg.setColor(1, 1, 1, 1)
  lg.setScissor()
end

function scenes.draw(highlight)
  local cont = cur_container()
  local bg
  if view.kind == "room" then
    bg = IMG[cont.bg[scenes.mode()]]
  else
    bg = IMG[cont.bg]
  end
  lg.draw(bg, 0, 0)
  if view.kind == "room" and view.room == "A" then draw_snow() end

  local cs = {}
  for _, c in ipairs(cont.cutouts or {}) do
    if cutout_visible(c) then cs[#cs + 1] = c end
  end
  table.sort(cs, function(a, b) return (a.z or 10) < (b.z or 10) end)
  for _, c in ipairs(cs) do draw_cutout(c) end

  -- движковые оверлеи зумов
  if view.kind == "zoom" then scenes.draw_zoom_engine(view.zoom) end

  if highlight then
    lg.setColor(1, 0.87, 0.35, 0.24)
    for _, h in ipairs(scenes.active_hotspots()) do
      local r = pick_rect(h)
      lg.rectangle("fill", r[1], r[2], r[3], r[4], 8, 8)
    end
    lg.setColor(1, 0.87, 0.35, 0.9)
    for _, h in ipairs(scenes.active_hotspots()) do
      local r = pick_rect(h)
      lg.rectangle("line", r[1], r[2], r[3], r[4], 8, 8)
    end
    lg.setColor(1, 1, 1, 1)
  end
end

function scenes.active_hotspots()
  local cont = cur_container()
  local out = {}
  for _, h in ipairs(cont.hotspots or {}) do
    if flag_list_ok(h) then out[#out + 1] = h end
  end
  if view.kind == "room" then
    for _, a in ipairs(cont.arrows or {}) do
      if not a.needs_flag or ST:has_flag(a.needs_flag) then
        out[#out + 1] = {id = "arrow_" .. a.dir, rect = a.rect,
                         goto_room = a.goto_room, cursor = "move",
                         _arrow = true,
                         name = (a.dir == "right") and "→" or "←"}
      end
    end
  end
  -- приоритет попадания: интерактивные раньше фоновых «осмотров»,
  -- мелкие раньше крупных (стикер на мониторе, указка на доске)
  for i, h in ipairs(out) do h._seq = i end
  local function rank(h)
    if h._arrow then return 1 end
    if h.node or h["goto"] or h.goto_room or h.doc
       or h.widget or h.bench then return 0 end
    return 2
  end
  table.sort(out, function(a, b)
    local ia, ib = rank(a), rank(b)
    if ia ~= ib then return ia < ib end
    local ra, rb = pick_rect(a), pick_rect(b)
    local sa, sb = ra[3] * ra[4], rb[3] * rb[4]
    if sa ~= sb then return sa < sb end
    return a._seq < b._seq
  end)
  return out
end

function scenes.hit(x, y)
  local list = scenes.active_hotspots()
  for _, h in ipairs(list) do
    local r = pick_rect(h)
    if x >= r[1] and x < r[1] + r[3] and y >= r[2] and y < r[2] + r[4] then
      return h
    end
  end
  return nil
end

-- центр хотспота (для автоплея)
function scenes.hotspot_center(id)
  for _, h in ipairs(scenes.active_hotspots()) do
    if h.id == id then
      local r = pick_rect(h)
      return r[1] + r[3] / 2, r[2] + r[4] / 2, h
    end
  end
  return nil
end

-- ---------- движковые элементы зумов ----------
local FontS
function scenes.set_fonts(fonts) FontS = fonts end

function scenes.draw_zoom_engine(zid)
  local z = S.zooms[zid]
  if zid == "zoom_exit_door" then
    -- табличка «Закрыто по 8.01» (движком, PT)
    lg.setColor(0.16, 0.13, 0.10, 0.9)
    lg.setFont(FontS.plate)
    local txt = scenes.texts.ui.door_plate
    lg.printf(txt, 785, 158, 360, "center")
    lg.setColor(1, 1, 1, 1)
    -- засов: пластина запечена, головка движком
    local g = z.bolt_geom
    local k = ST.flags.bolt_free and g.knob_open or g.knob_closed
    if ST._bolt_anim then
      local f = math.min(1, (t_global - ST._bolt_anim) / 0.5)
      k = {g.knob_closed[1],
           g.knob_closed[2] + (g.knob_open[2] - g.knob_closed[2]) * f}
    end
    lg.setColor(0.78, 0.65, 0.4)
    lg.rectangle("fill", k[1] - 13, k[2] - 22, 26, 44, 5, 5)
    lg.setColor(0.35, 0.27, 0.15)
    lg.rectangle("line", k[1] - 13, k[2] - 22, 26, 44, 5, 5)
    lg.setColor(1, 1, 0.9, 0.35)
    lg.rectangle("fill", k[1] - 10, k[2] - 19, 8, 38, 3, 3)
    lg.setColor(1, 1, 1, 1)
    -- мини-LED считывателя
    local led = z.led.reader_small
    local col = {0.35, 0.35, 0.35}
    if ST.flags.reader_green then col = {0.25, 0.95, 0.35}
    elseif ST.flags.power_on then col = {0.95, 0.25, 0.2} end
    lg.setColor(col[1], col[2], col[3],
      0.75 + 0.25 * math.sin(t_global * 3))
    lg.circle("fill", led[1], led[2], 9)
    lg.setColor(1, 1, 1, 1)
  elseif zid == "zoom_alarm" then
    local led = z.led.alarm
    if ST.flags.alarm_off then lg.setColor(0.3, 0.9, 0.4, 0.9)
    else lg.setColor(1, 0.2, 0.15, 0.6 + 0.4 * math.sin(t_global * 4.5)) end
    lg.circle("fill", led[1], led[2], 13)
    lg.setColor(1, 1, 1, 1)
  elseif zid == "zoom_panel" then
    lg.setFont(FontS.tiny)
    local row
    for _, h in ipairs(z.hotspots) do
      if h.breaker_x0 then row = h end
    end
    local ly = row.rect[2] + row.rect[4] + 16
    for i, name in ipairs(z.labels_engine) do
      if name ~= "" then
        local cx = row.breaker_x0 + (i - 0.5) * row.breaker_step
        lg.setColor(0, 0, 0, 0.55)
        lg.push()
        lg.translate(cx + 1 + 7, ly + 1); lg.rotate(math.rad(90))
        lg.printf(name, 0, 0, 120, "left")
        lg.pop()
        lg.setColor(0.95, 0.93, 0.86, 0.98)
        lg.push()
        lg.translate(cx + 7, ly); lg.rotate(math.rad(90))
        lg.printf(name, 0, 0, 120, "left")
        lg.pop()
      end
    end
    lg.setColor(1, 1, 1, 1)
  elseif zid == "zoom_bench" then
    -- бирки вентилей
    lg.setFont(FontS.plate)
    for _, vl in ipairs(z.valve_labels or {}) do
      local w = FontS.plate:getWidth(vl[1]) + 22
      lg.setColor(0.13, 0.11, 0.08, 0.88)
      lg.rectangle("fill", vl[2] - w / 2, 452, w, 40, 6, 6)
      lg.setColor(0.72, 0.58, 0.34)
      lg.rectangle("line", vl[2] - w / 2, 452, w, 40, 6, 6)
      lg.setColor(0.93, 0.88, 0.75)
      lg.printf(vl[1], vl[2] - w / 2, 457, w, "center")
    end
    lg.setColor(1, 1, 1, 1)
    -- стрелка манометра
    local g = z.gauge
    local frac = ST:gauge_frac()
    local a0, a1 = math.rad(210), math.rad(-30)
    local a = a0 + (a1 - a0) * frac
    lg.setColor(0.85, 0.15, 0.1)
    lg.setLineWidth(5)
    lg.line(g.cx, g.cy, g.cx + math.cos(a) * g.r, g.cy - math.sin(a) * g.r)
    lg.setLineWidth(1)
    lg.setColor(0.2, 0.75, 0.3, frac >= 0.99 and 1 or 0)
    lg.circle("fill", g.cx, g.cy, 10)
    -- легенда управления вентилями
    lg.setColor(0, 0, 0, 0.55)
    lg.rectangle("fill", 560, 1016, 800, 44, 10, 10)
    lg.setColor(0.9, 0.88, 0.8)
    lg.setFont(FontS.small)
    lg.printf("ЛКМ — по часовой (+)   ·   ПКМ — против часовой (−)",
      560, 1026, 800, "center")
    lg.setColor(1, 1, 1, 1)
  elseif zid == "zoom_pc" then
    if not ST.flags.pc_on then
      -- скринсейвер DVD-style
      local w, h = 250, 84
      local x = 390 + math.abs(((t_global * 120) % (2 * (645 - w))) - (645 - w))
      local y = 110 + math.abs(((t_global * 88) % (2 * (555 - h))) - (555 - h))
      lg.setColor(0.05, 0.07, 0.13)
      lg.rectangle("fill", 392, 112, 641, 551)
      lg.setColor(0.83, 0.68, 0.35)
      lg.setFont(FontS.h2)
      lg.printf("ВАЛТЕК", x, y + 18, w, "center")
      lg.setFont(FontS.small)
      lg.printf("нажми, если смелый", x, y + 54, w, "center")
      lg.setColor(1, 1, 1, 1)
    end
  end
end

return scenes
