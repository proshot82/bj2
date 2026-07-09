-- src/ui.lua — интерфейс: диалоги, инвентарь, цели, читалка, виджеты, меню
local ui = {}
local lg = love.graphics
local json = require("src.json")
local utf8 = require("utf8")

local T, P, ST, SC, IMG, AUD, F
local settings = {music = true, sound = true, fullscreen = false, noshake = false}
local savefile = "save_bj2.json"

-- палитра
local C = {
  panel = {0.086, 0.094, 0.125, 0.92},
  panel_line = {0.72, 0.58, 0.34},
  brass = {0.72, 0.58, 0.34}, steel = {0.55, 0.70, 0.86},
  text = {0.93, 0.91, 0.86}, dim = {0.65, 0.63, 0.58},
  paper_ink = {0.17, 0.14, 0.10}, red_ink = {0.62, 0.10, 0.08},
  ok = {0.35, 0.8, 0.4}, bad = {0.9, 0.3, 0.25},
}

-- ================= состояние UI =================
local dlg = {queue = {}, cur = nil, shown = 0, t = 0, blip_t = 0}
local inv = {selected = nil}
local widget = nil        -- {kind=..., ...}
local reader = nil        -- {doc=..., page=1}
local menu = "title"      -- title|nil|pause|settings|confirm_quit
local hint = {last = -1e9, topic_idx = {}}
local toast = nil
local idle_timer = 0
local shake_seed = 0
local victory_stage = nil   -- объявлен выше менеджера музыки/стингеров

ui.autoplay_hooks = {}    -- заполняет autoplay

function ui.init(texts, puzzles, state, scenes_mod, images, audio, fonts)
  T, P, ST, SC, IMG, AUD, F = texts, puzzles, state, scenes_mod, images, audio, fonts
  SC.set_fonts(fonts)
end

function ui.state() return {dlg = dlg, widget = widget, reader = reader,
                            menu = menu, inv = inv} end
function ui.in_menu() return menu ~= nil end
function ui.title_shown() return menu == "title" end
function ui.reader_open() return reader ~= nil end

-- ================= звук =================
local function snd(name)
  if not settings.sound then return end
  local s = AUD[name]
  if s then s:stop(); s:play() end
end
ui.snd = snd

-- ================= МУЗЫКА: BGM-менеджер 2.0.5 =================
-- 2 канала кроссфейда (лерп ~1.5с) + 2 слоя (nervous/garland) + стингеры.
-- Уровни зашиты в файлы пик-нормализацией (фоны -5, слои -11, стингеры -1 dBFS),
-- в движке общий множитель MUS_MASTER. settings.music гейтит ВСЮ музыку
-- (фоны+слои+стингеры) через лерп mus.gain; звуки snd() это не трогает.
local MUS_MASTER = 0.85
local BGM_FADE, LAYER_FADE, GATE_FADE = 1.5, 2.0, 0.4
local mus = {
  slots = {{name = nil, vol = 0, src = nil}, {name = nil, vol = 0, src = nil}},
  cur = 0, gain = 0, ln_vol = 0, lg_vol = 0, prev = nil,
}

local function mus_apply(src, vol)
  if not src then return end
  if vol > 0.001 then
    src:setLooping(true); src:setVolume(vol)
    if not src:isPlaying() then src:play() end
  elseif src:isPlaying() then src:stop() end
end

local function approach(v, target, dt, dur)
  local step = dt / (dur > 0.01 and dur or 0.01)
  if v < target then return math.min(target, v + step) end
  if v > target then return math.max(target, v - step) end
  return v
end

-- стингер: one-shot поверх музыки, гейтится settings.music
local function sting(name)
  if not settings.music then return end
  local s = AUD[name]
  if s then s:stop(); s:setVolume(MUS_MASTER); s:play() end
end
ui.sting = sting

-- целевой фон: титул→title, победа→epilogue, иначе комната(A/B) + режим(день/ночь)
local function mus_target_bgm()
  if menu == "title" then return "bgm_title" end
  if victory_stage then return "bgm_epilogue" end
  local v = SC.view()
  local room = (v and v.room) or "A"
  local day = ST.flags.power_on
  if room == "B" then return day and "bgm_day_b" or "bgm_night_b" end
  return day and "bgm_day_a" or "bgm_night_a"
end

-- снимок флагов, чтобы не стрелять стингером на загрузке/старте
local function mus_sync_flags()
  mus.prev = {power_on = ST.flags.power_on or false,
              crown = (ST.flags.crown or ST.inv.crown) or false}
end
local function mus_boot() mus_sync_flags() end

local function mus_update(dt)
  mus.gain = approach(mus.gain, settings.music and 1 or 0, dt, GATE_FADE)
  if not mus.prev then mus_sync_flags() end

  -- кроссфейд фонового трека между двумя каналами
  local want = mus_target_bgm()
  local cs = mus.slots[mus.cur]
  if mus.cur == 0 or (cs and cs.name ~= want) then
    local ni = (mus.cur == 1) and 2 or 1
    local ns = mus.slots[ni]
    if ns.src and ns.src:isPlaying() then ns.src:stop() end
    ns.name, ns.vol, ns.src = want, 0, AUD[want]
    mus.cur = ni
  end
  for i, s in ipairs(mus.slots) do
    s.vol = approach(s.vol, (i == mus.cur) and 1 or 0, dt, BGM_FADE)
    mus_apply(s.src, s.vol * mus.gain * MUS_MASTER)
  end

  -- слой «нервы»: с начала игры до calm_down; на титуле/победе молчит
  local ln_on = menu ~= "title" and not victory_stage and not ST.flags.calm_down
  mus.ln_vol = approach(mus.ln_vol, ln_on and 1 or 0, dt, LAYER_FADE)
  mus_apply(AUD.layer_nervous, mus.ln_vol * mus.gain * MUS_MASTER)

  -- слой «гирлянда»: при garland_on
  local lg_on = ST.flags.garland_on and menu ~= "title" and not victory_stage
  mus.lg_vol = approach(mus.lg_vol, lg_on and 1 or 0, dt, LAYER_FADE)
  mus_apply(AUD.layer_garland, mus.lg_vol * mus.gain * MUS_MASTER)

  -- стингеры на переходах флагов: власть и корона
  if ST.flags.power_on and not mus.prev.power_on then sting("sting_power") end
  mus.prev.power_on = ST.flags.power_on or false
  local crown_now = (ST.flags.crown or ST.inv.crown) or false
  if crown_now and not mus.prev.crown then sting("sting_crown") end
  mus.prev.crown = crown_now
end

-- ================= тряска =================
local function shake_amp()
  if settings.noshake then return 0 end
  if ST.flags.calm_down then return 0 end
  if ST.inv.coffee or ST.inv.validol then return 0.9 end
  return 2.6
end
local function shk(k)
  local a = shake_amp()
  if a == 0 then return 0, 0 end
  local t = SC.time() * 13 + k * 7.3
  return math.sin(t) * a, math.cos(t * 1.31) * a * 0.7
end

-- ================= диалог =================
local function push_lines(lines)
  for _, r in ipairs(lines or {}) do dlg.queue[#dlg.queue + 1] = r end
end
ui.say = push_lines

local function say_node(id, key)
  local n = T.nodes[id]
  if n and n[key] then push_lines(n[key]) end
end
ui.say_node = say_node

local function dlg_next()
  dlg.cur = table.remove(dlg.queue, 1)
  dlg.shown, dlg.t, dlg.blip_t = 0, 0, 0
end

function ui.dialog_active() return dlg.cur ~= nil or #dlg.queue > 0 end
function ui.current_speaker() return dlg.cur and dlg.cur.s or nil end

local function dlg_update(dt)
  if not dlg.cur and #dlg.queue > 0 then dlg_next() end
  local cur = dlg.cur
  if not cur then return end
  local full = utf8.len(cur.t)
  if dlg.shown < full then
    dlg.t = dlg.t + dt * 40
    local new = math.min(full, math.floor(dlg.t))
    if new > dlg.shown then
      dlg.blip_t = dlg.blip_t + (new - dlg.shown)
      if dlg.blip_t >= 3 then
        dlg.blip_t = 0
        snd(cur.s == "anc" and "blip_anc" or "blip_lap")
      end
    end
    dlg.shown = new
  end
end

local function dlg_click()
  local cur = dlg.cur
  if not cur then return false end
  local full = utf8.len(cur.t)
  if dlg.shown < full then dlg.shown = full; dlg.t = full
  else
    dlg.cur = nil
    if #dlg.queue > 0 then dlg_next() end
  end
  return true
end

local function draw_badge(x, y, s)
  local name = T.speaker_names[s]
  local col = (s == "anc") and C.steel or C.brass
  lg.setFont(F.badge)
  local w = F.badge:getWidth(name) + 26
  lg.setColor(0.05, 0.06, 0.09, 0.95)
  lg.rectangle("fill", x, y, w, 34, 6, 6)
  lg.setColor(col[1], col[2], col[3])
  lg.setLineWidth(3)
  lg.rectangle("line", x, y, w, 34, 6, 6)
  lg.setLineWidth(1)
  lg.print(name, x + 13, y + 5)
  lg.setColor(1, 1, 1)
  return w
end

local function dlg_draw()
  local cur = dlg.cur
  if not cur then return end
  local ox, oy = shk(1)
  local px, py = 24 + ox, 776 + oy
  -- портрет
  local port = IMG["portraits/port_" .. cur.s .. "_" .. cur.e .. ".png"]
  lg.setColor(C.panel)
  lg.rectangle("fill", px, py, 268, 280, 10, 10)
  lg.setColor(1, 1, 1)
  lg.draw(port, px + 6, py + 6, 0, 0.5, 0.5)
  if (ST.flags.crown or ST.inv.crown) and cur.s == "lap" then
    lg.draw(IMG["portraits/port_crown_overlay.png"], px + 128, py + 22,
      -0.09, 0.36, 0.36, 261, 256)
  end
  local bcol = (cur.s == "anc") and C.steel or C.brass
  lg.setColor(bcol[1], bcol[2], bcol[3])
  lg.setLineWidth(4)
  lg.rectangle("line", px, py, 268, 280, 10, 10)
  lg.setLineWidth(1)
  -- плашка текста
  local tx, ty, tw = px + 284, py + 44, 1580
  lg.setColor(C.panel)
  lg.rectangle("fill", tx, ty, tw, 236, 10, 10)
  lg.setColor(C.panel_line)
  lg.rectangle("line", tx, ty, tw, 236, 10, 10)
  draw_badge(tx + 14, ty - 18, cur.s)
  lg.setFont(F.dlg)
  lg.setColor(C.text)
  local full = utf8.len(cur.t)
  local bend = (dlg.shown >= full) and #cur.t
    or (utf8.offset(cur.t, dlg.shown + 1) - 1)
  lg.printf(cur.t:sub(1, bend), tx + 26, ty + 30, tw - 52, "left")
  lg.setFont(F.small)
  lg.setColor(C.dim)
  lg.printf(dlg.shown < full and "…" or "[ЛКМ] дальше", tx + 26,
    ty + 200, tw - 52, "right")
  lg.setColor(1, 1, 1)
end

-- невроз-суффикс к осмотрам (случайно, до calm)
local nerve_i = 0
local function maybe_nervous()
  if ST.flags.calm_down then return end
  nerve_i = nerve_i + 1
  if nerve_i % 3 == 0 then
    push_lines({T.nervous_suffix[(nerve_i / 3 - 1) % #T.nervous_suffix + 1]})
  end
end

-- ================= токены/доки =================
local function tok(k)
  local v = P.tokens[k]
  if type(v) == "table" then return table.concat(v, ", ") end
  return tostring(v)
end

local function ans_line(k)
  if k == "bench_printed_ru" then return P.answers.bench_printed_ru end
  if k == "bench_seq_ru" then return P.answers.bench_seq_ru end
  if k == "bench_fix_ru" then
    local i = P.answers.bench_fix_idx
    local pr = {}
    for w in P.answers.bench_printed_ru:gmatch("[^%s→]+") do pr[#pr + 1] = w end
    local rt = {}
    for w in P.answers.bench_seq_ru:gmatch("[^%s→]+") do rt[#rt + 1] = w end
    return ("шаг %d: не «%s», а «%s»"):format(i, pr[i] or "?", rt[i] or "?")
  end
  return "?"
end

local function subst(line)
  line = line:gsub("{TOK:([%w_]+)}", function(k) return tok(k) end)
  line = line:gsub("{ANS:([%w_]+)}", function(k) return ans_line(k) end)
  return line
end

-- глифы-пиктограммы (векторные)
local function draw_glyph(name, x, y, s, col)
  col = col or C.paper_ink
  lg.setColor(col[1], col[2], col[3])
  lg.setLineWidth(3)
  lg.push(); lg.translate(x, y); lg.scale(s / 40)
  if name == "fez" then
    lg.polygon("line", -14, 12, 14, 12, 10, -10, -10, -10)
    lg.line(10, -10, 18, -16); lg.circle("fill", 18, -16, 2.5)
  elseif name == "yatagan" then
    lg.line(-16, 12, -6, 2)
    local pts = {}
    for i = 0, 8 do
      local t2 = i / 8
      pts[#pts + 1] = -6 + t2 * 22
      pts[#pts + 1] = 2 - math.sin(t2 * 2.6) * 12
    end
    lg.line(pts)
  elseif name == "crescent" then
    lg.arc("line", "open", 0, 0, 14, math.rad(-60), math.rad(240))
    lg.arc("line", "open", 5, -2, 11, math.rad(-45), math.rad(225))
  elseif name == "star" then
    local pts = {}
    for i = 0, 9 do
      local r = (i % 2 == 0) and 15 or 6
      local a = math.rad(-90 + i * 36)
      pts[#pts + 1] = math.cos(a) * r; pts[#pts + 1] = math.sin(a) * r
    end
    lg.polygon("line", pts)
  elseif name == "drum" then
    lg.rectangle("line", -13, -8, 26, 18)
    lg.ellipse("line", 0, -8, 13, 5)
    lg.line(-13, 10, 13, -4); lg.line(13, 10, -13, -4)
  elseif name == "horseshoe" then
    lg.arc("line", "open", 0, 2, 13, math.rad(-40), math.rad(220))
    lg.circle("fill", -10, 10, 2); lg.circle("fill", 10, 10, 2)
  elseif name == "teapot" then
    lg.ellipse("line", 0, 4, 12, 9)
    lg.line(12, 0, 19, -6); lg.line(-12, 2, -18, -4)
    lg.arc("line", "open", 0, -6, 6, math.rad(180), math.rad(360))
  elseif name == "key" then
    lg.circle("line", -9, 0, 6)
    lg.line(-3, 0, 16, 0); lg.line(11, 0, 11, 7); lg.line(16, 0, 16, 7)
  elseif name == "fish" then
    lg.ellipse("line", -2, 0, 12, 7)
    lg.polygon("line", 10, 0, 18, -7, 18, 7)
    lg.circle("fill", -8, -2, 1.6)
  elseif name == "snowflake" then
    for i = 0, 2 do
      local a = math.rad(i * 60)
      lg.line(-math.cos(a) * 14, -math.sin(a) * 14,
              math.cos(a) * 14, math.sin(a) * 14)
    end
  end
  lg.pop()
  lg.setLineWidth(1)
  lg.setColor(1, 1, 1)
end

local MONTH_DAYS, MONTH_START = 31, 6 -- декабрь 2018: 1-е — суббота (индекс 6, пн=1)

local function draw_special(token, x, y, w)
  if token == "PIN_GLYPHS" then
    local g = P.answers.pin_glyphs
    for i, name in ipairs(g) do
      draw_glyph(name, x + w / 2 + (i - (#g + 1) / 2) * 84, y + 26, 46)
    end
    return 70
  elseif token == "LEGEND" then
    local names = {}
    for k in pairs(P.answers.glyph_map) do names[#names + 1] = k end
    table.sort(names)
    local cols, cw = 2, w / 2
    for i, name in ipairs(names) do
      local cx = x + ((i - 1) % cols) * cw + 60
      local cy = y + math.floor((i - 1) / cols) * 56 + 22
      draw_glyph(name, cx, cy, 36)
      lg.setFont(F.paper)
      lg.setColor(C.paper_ink)
      lg.print("= " .. tostring(P.answers.glyph_map[name]), cx + 36, cy - 16)
      lg.setColor(1, 1, 1)
    end
    return math.ceil(#names / cols) * 56 + 16
  elseif token == "CAL" then
    lg.setFont(F.paper_small)
    local wd = {"пн", "вт", "ср", "чт", "пт", "сб", "вс"}
    local cw2 = 64
    local x0 = x + (w - cw2 * 7) / 2
    for i, d in ipairs(wd) do
      lg.setColor(C.paper_ink)
      lg.print(d, x0 + (i - 1) * cw2 + 16, y)
    end
    local day = 1
    local row = 1
    while day <= MONTH_DAYS do
      local colw = ((day + MONTH_START - 2) % 7) + 1
      local cx = x0 + (colw - 1) * cw2 + 16
      local cy = y + row * 44
      lg.setColor(C.paper_ink)
      lg.print(tostring(day), cx, cy)
      if day == tonumber(tok("alarm_day")) then
        lg.setColor(C.red_ink)
        lg.setLineWidth(3)
        lg.circle("line", cx + 14, cy + 12, 22)
        lg.setLineWidth(1)
      end
      if colw == 7 then row = row + 1 end
      day = day + 1
    end
    lg.setColor(1, 1, 1)
    return (row + 1) * 44 + 10
  end
  return 0
end

function ui.open_doc(doc_id)
  reader = {doc = doc_id, page = 1}
  ST.read[doc_id] = true
  snd("paper")
end

local function reader_draw()
  if not reader then return end
  local d = T.docs[reader.doc]
  local img = IMG["ui/paper_reader.png"]
  local x, y = (1920 - 1400) / 2, (1080 - 980) / 2
  lg.setColor(0, 0, 0, 0.55); lg.rectangle("fill", 0, 0, 1920, 1080)
  lg.setColor(1, 1, 1); lg.draw(img, x, y)
  lg.setFont(F.paper_title)
  lg.setColor(C.paper_ink)
  lg.printf(d.title, x + 90, y + 70, 1220, "center")
  local page = d.pages[reader.page]
  local cy = y + 160
  local hw = {}
  for _, i in ipairs(d.handwritten or {}) do hw[i] = true end
  for li, raw in ipairs(page) do
    local spec = raw:match("^{([A-Z_]+)}$")
    if spec then
      cy = cy + draw_special(spec, x + 120, cy, 1160) + 14
    else
      local line = subst(raw)
      if hw[li - 1] then
        lg.setFont(F.hand)
        lg.setColor(line:find("ОПЕЧАТКА") and C.red_ink or
                    {0.13, 0.18, 0.42})
        lg.push(); lg.translate(x + 130, cy); lg.rotate(-0.012)
        lg.printf(line, 0, 0, 1140, "left")
        lg.pop()
        cy = cy + F.hand:getHeight() * 1.22
      else
        lg.setFont(F.paper)
        lg.setColor(C.paper_ink)
        lg.printf(line, x + 130, cy, 1140, "left")
        local _, wrapped = F.paper:getWrap(line, 1140)
        cy = cy + #wrapped * F.paper:getHeight() * 1.14
      end
      cy = cy + 8
    end
  end
  lg.setFont(F.small)
  lg.setColor(C.dim)
  local pg = (#d.pages > 1) and
    ("стр. " .. reader.page .. "/" .. #d.pages .. "  [ЛКМ]  ·  ") or ""
  lg.printf(pg .. T.ui.reader_close, x + 90, y + 900, 1220, "center")
  lg.setColor(1, 1, 1)
end

-- ================= инвентарь =================
local INV_Y = 8
local function inv_slots()
  local out = {}
  for i, id in ipairs(ST.inv_order) do
    out[#out + 1] = {id = id, x = 20 + (i - 1) * 76, y = INV_Y, w = 68, h = 68}
  end
  return out
end

local function inv_draw()
  local ox, oy = shk(2)
  lg.setFont(F.small)
  for _, s in ipairs(inv_slots()) do
    local x, y = s.x + ox, s.y + oy
    lg.setColor(C.panel)
    lg.rectangle("fill", x, y, s.w, s.h, 8, 8)
    local sel = (inv.selected == s.id)
    lg.setColor(sel and C.ok or C.panel_line)
    lg.setLineWidth(sel and 4 or 2)
    lg.rectangle("line", x, y, s.w, s.h, 8, 8)
    lg.setLineWidth(1)
    local ic = IMG["icons/ic_" .. s.id:gsub("^relic_", "") .. ".png"]
    if ic then
      local iw = ic:getWidth()
      lg.setColor(1, 1, 1)
      lg.draw(ic, x + 6, y + 6, 0, 56 / iw, 56 / iw)
    end
  end
  if inv.selected then
    lg.setColor(C.text)
    lg.print(T.item_names[inv.selected] or inv.selected,
      20 + ox, INV_Y + 76 + oy)
    lg.setColor(1, 1, 1)
  end
end

local function combine_try(a, b)
  for _, n in ipairs(P.nodes) do
    if n.room == "inv" then
      local na, nb = n.needs[1], n.needs[2]
      if (na == a and nb == b) or (na == b and nb == a) then
        local ok = select(1, ST:fire(n.id))
        if ok then
          snd("pickup"); say_node(n.id, "do"); ui.after_fire(n.id)
        end
        return ok
      end
    end
  end
  push_lines({{s = "lap", e = "neutral", t = T.ui.combine_fail}})
  return false
end

local function item_doc_map()
  local map = {}
  for did, iid in pairs((ui.scene_json and ui.scene_json.doc_items) or {}) do
    map[iid] = did
  end
  return map
end

local function inv_click(x, y, btn)
  for _, s in ipairs(inv_slots()) do
    if x >= s.x and x < s.x + s.w and y >= s.y and y < s.y + s.h then
      if btn == 2 then
        local m = item_doc_map()
        if m[s.id] then ui.open_doc(m[s.id])
        else
          local d = T.item_desc[s.id]
          if d then push_lines({d}) end
        end
        return true
      end
      if inv.selected and inv.selected ~= s.id then
        combine_try(inv.selected, s.id)
        inv.selected = nil
      elseif inv.selected == s.id then inv.selected = nil
      else inv.selected = s.id; snd("ui_click") end
      return true
    end
  end
  return false
end

-- ================= цели =================
local goal_texts = nil
local goals_min = false          -- свёрнута ли плашка (тоггл кликом)
local function goals_rect()
  if not ST.flags.surveyed then return nil end
  local h = goals_min and 34 or (34 + #P.goals * 30 + 32)
  return 20, 120, 330, h
end
function ui.goals_click(mx, my)
  local x, y, w, h = goals_rect()
  if not x then return false end
  if mx >= x and mx < x + w and my >= y and my < y + h then
    goals_min = not goals_min
    return true
  end
  return false
end
local function goals_draw()
  if not ST.flags.surveyed then return end
  local ox, oy = shk(3)
  local x, y = 20 + ox, 120 + oy
  if goals_min then
    lg.setColor(C.panel)
    lg.rectangle("fill", x, y, 330, 34, 10, 10)
    lg.setColor(C.panel_line)
    lg.rectangle("line", x, y, 330, 34, 10, 10)
    lg.setFont(F.badge)
    lg.setColor(C.brass)
    local dn, tot = 0, #P.goals
    for _, g in ipairs(P.goals) do if ST.flags[g.flag] then dn = dn + 1 end end
    lg.print(T.ui.goals .. "  " .. dn .. "/" .. tot .. "  ▸", x + 14, y + 6)
    lg.setColor(1, 1, 1)
    return
  end
  lg.setColor(C.panel)
  lg.rectangle("fill", x, y, 330, 34 + #P.goals * 30 + 32, 10, 10)
  lg.setColor(C.panel_line)
  lg.rectangle("line", x, y, 330, 34 + #P.goals * 30 + 32, 10, 10)
  lg.setFont(F.badge)
  lg.setColor(C.brass)
  lg.print(T.ui.goals, x + 14, y + 6)
  lg.setFont(F.small)
  for i, g in ipairs(P.goals) do
    local done = ST.flags[g.flag]
    lg.setColor(done and C.ok or C.text)
    lg.print((done and "✓ " or "· ") .. g.t, x + 16, y + 34 + (i - 1) * 30)
  end
  local rn = 0
  for _, r in ipairs(P.relics) do if ST.inv[r] then rn = rn + 1 end end
  lg.setColor(rn > 0 and C.brass or C.dim)
  lg.print(T.ui.secret_goal:format(rn), x + 16, y + 34 + #P.goals * 30)
  lg.setColor(1, 1, 1)
end

-- ================= подсказки =================
local topic_order = {
  {"t_start", function() return not ST.flags.drawer_pried end},
  {"t_utility", function() return not ST.flags.utility_open end},
  {"t_card", function() return not ST.flags.card_active end},
  {"t_power", function() return not ST.flags.power_on end},
  {"t_alarm", function() return not ST.flags.alarm_off end},
  {"t_bolt", function() return not ST.flags.bolt_free end},
  {"t_calm", function() return not ST.flags.calm_down end},
  {"t_final", function() return not ST.flags.victory end},
  {"t_secret", function() return true end},
}
local hint_intro_done = false

function ui.hint()
  local now = SC.time()
  if now - hint.last < 45 then
    push_lines(T.hints.cooldown); return
  end
  hint.last = now
  if not hint_intro_done then
    hint_intro_done = true
    push_lines(T.hints.intro)
  end
  local topic
  for _, tp in ipairs(topic_order) do
    if tp[2]() then topic = tp[1]; break end
  end
  local tier = (hint.topic_idx[topic] or 0) + 1
  if tier > 3 then tier = 3 end
  hint.topic_idx[topic] = tier
  push_lines({T.hints.topics[topic][tier]})
end

-- ================= сейвы =================
function ui.save()
  local blob = {state = ST:serialize(), view = SC.view(),
                settings = settings, hint_idx = hint.topic_idx}
  love.filesystem.write(savefile, json.encode(blob))
end
function ui.has_save() return love.filesystem.getInfo(savefile) ~= nil end
function ui.load_save()
  local s = love.filesystem.read(savefile)
  if not s then return false end
  local blob = json.decode(s)
  ST:deserialize(blob.state)
  for k, v in pairs(blob.settings or {}) do settings[k] = v end
  hint.topic_idx = blob.hint_idx or {}
  local v = blob.view
  if v and v.kind == "zoom" and v.zoom then
    SC.goto_room(v.room); SC.goto_zoom(v.zoom)
  else SC.goto_room((v and v.room) or "A") end
  return true
end

-- ================= toasts (взятие предметов) =================
function ui.toast(txt)
  toast = {t = txt, until_t = SC.time() + 2.2}
end
local function toast_draw()
  if toast and SC.time() < toast.until_t then
    lg.setFont(F.small)
    local w = F.small:getWidth(toast.t) + 40
    lg.setColor(C.panel)
    lg.rectangle("fill", 960 - w / 2, 96, w, 40, 8, 8)
    lg.setColor(C.brass)
    lg.rectangle("line", 960 - w / 2, 96, w, 40, 8, 8)
    lg.setColor(C.text)
    lg.print(toast.t, 960 - w / 2 + 20, 104)
    lg.setColor(1, 1, 1)
  end
end

-- ================= after_fire: эффекты узлов =================
function ui.after_fire(id)
  idle_timer = 0
  local sfx = {
    take_ruler = "pickup", take_handle = "pickup", take_pointer = "pickup",
    take_net = "pickup", take_key_toy = "pickup", take_wrench = "pickup",
    take_wheel = "pickup", take_gift = "bill", take_validol = "pickup",
    take_grease = "pickup", take_mop = "pickup", take_collector = "pickup",
    search_drawer_again = "pickup", relic_badge = "pickup",
    open_box = "pickup", search_box_again = "pickup",
    pry_drawer = "crunch", open_utility = "utility_door",
    push_net = "net_fall", fish_card = "splash",
    open_workbench = "key_turn", install_wheel = "valve",
    open_panel = "key_turn", power_main = "breaker_click",
    sockets_on = "breaker_click", h_br_elka = "garland",
    h_br_srv = "breaker_click", h_br_rezerv = "breaker_click",
    brew_coffee = "coffee", combine_calm = "psh",
    bolt_free = "bolt_break", reader_swipe = "beep_ok",
    box_down = "mop_hook", copy_pass = "paper", survey_door = "knock",
  }
  if sfx[id] then snd(sfx[id]) end
  local n = ST.nodes[id]
  for _, g in ipairs(n.gives) do
    if ST.items_set[g] and T.item_names[g] then
      ui.toast("+ " .. T.item_names[g])
    end
  end
  if id == "bolt_free" then SC.mark_bolt() end
  if ui.scene_json.doc_auto[id] then ui.open_doc(ui.scene_json.doc_auto[id]) end
  if id == "door_open" then ui.start_victory() end
end

-- ================= победа =================
function ui.start_victory()
  victory_stage = {i = 0, t0 = SC.time()}
  snd("victory")
  push_lines(T.victory)
  local rn = 0
  for _, r in ipairs(P.relics) do if ST.inv[r] then rn = rn + 1 end end
  push_lines(T.epilogues[tostring(rn)])
  if ST.flags.crown or ST.inv.crown then push_lines(T.crown_epilogue) end
end

local function victory_draw()
  if not victory_stage then return end
  if ui.dialog_active() then return end
  -- финальная плашка
  lg.setColor(0, 0, 0, 0.72)
  lg.rectangle("fill", 0, 0, 1920, 1080)
  lg.setFont(F.h1)
  lg.setColor(C.brass)
  lg.printf(T.ui.victory_title, 0, 300, 1920, "center")
  lg.setFont(F.dlg)
  lg.setColor(C.text)
  local rn = 0
  for _, r in ipairs(P.relics) do if ST.inv[r] then rn = rn + 1 end end
  local lines = {T.ui.stats_steps:format(ST.steps),
                 T.ui.stats_relics:format(rn)}
  if ST.flags.crown or ST.inv.crown then lines[#lines + 1] = T.ui.stats_crown end
  lg.printf(table.concat(lines, "\n"), 0, 430, 1920, "center")
  lg.setFont(F.small)
  lg.setColor(C.dim)
  lg.printf("[Esc] — на титул", 0, 640, 1920, "center")
  lg.setColor(1, 1, 1)
end
function ui.victory_done()
  return victory_stage ~= nil and not ui.dialog_active()
end
function ui.reset_to_title()
  victory_stage = nil
  menu = "title"
end

-- ================= ВИДЖЕТЫ =================
function ui.open_widget(kind, node_id, hs)
  widget = {kind = kind, node = node_id, buf = "", hs = hs,
            dept_i = 1, field = 1, no = ""}
  snd("ui_click")
end
function ui.widget_kind() return widget and widget.kind end
function ui.close_widget() widget = nil end

-- Кейпад — самодостаточная движковая панель по центру экрана (общая для
-- всех кодовых замков; арт зума под ней перекрыт). Раунд 4: крупные цифры.
-- Сетка 3x4: gx,gy — левый-верх первой кнопки; шаг = bw+10 / bh+10.
local function keypad_geom()
  return 770, 360, 120, 88
end

local function widget_draw()
  if not widget then return end
  local w = widget
  lg.setColor(0, 0, 0, 0.45); lg.rectangle("fill", 0, 0, 1920, 1080)
  if w.kind == "keypad" then
    local x, y, bw, bh = keypad_geom()
    local pw, ph = 3 * bw + 80, 4 * bh + 250
    local px, py = x - 40, y - 152
    lg.setColor(C.panel); lg.rectangle("fill", px, py, pw, ph, 16, 16)
    lg.setColor(C.panel_line); lg.setLineWidth(2)
    lg.rectangle("line", px, py, pw, ph, 16, 16); lg.setLineWidth(1)
    lg.setFont(F.badge); lg.setColor(C.brass)
    lg.printf("ВВЕДИТЕ КОД", px, py + 18, pw, "center")
    -- табло введённого кода (зелёные крупные символы)
    lg.setColor(0.05, 0.08, 0.06); lg.rectangle("fill", x, y - 100, 3 * bw, 62, 8, 8)
    lg.setColor(C.ok); lg.setLineWidth(2)
    lg.rectangle("line", x, y - 100, 3 * bw, 62, 8, 8); lg.setLineWidth(1)
    lg.setFont(F.h2); lg.setColor(C.ok)
    local shown = w.buf .. string.rep("_", 4 - #w.buf)
    lg.printf((shown:gsub(".", "%1 ")), x, y - 94, 3 * bw, "center")
    -- клавиши: КРУПНЫЕ цифры, C/OK выделены цветом
    local keys = {"1","2","3","4","5","6","7","8","9","C","0","OK"}
    lg.setFont(F.h2)
    local fh = F.h2:getHeight()
    for i, k in ipairs(keys) do
      local kx = x + ((i - 1) % 3) * (bw + 10)
      local ky = y + math.floor((i - 1) / 3) * (bh + 10)
      local spec = (k == "C" or k == "OK")
      lg.setColor(spec and 0.22 or 0.17, spec and 0.19 or 0.18, 0.24)
      lg.rectangle("fill", kx, ky, bw, bh, 10, 10)
      lg.setColor(C.panel_line); lg.setLineWidth(2)
      lg.rectangle("line", kx, ky, bw, bh, 10, 10); lg.setLineWidth(1)
      lg.setColor(k == "OK" and C.ok or (k == "C" and C.bad or C.text))
      lg.printf(k, kx, ky + (bh - fh) / 2, bw, "center")
    end
    lg.setColor(1, 1, 1)
  elseif w.kind == "pc" then
    -- после разблокировки: рабочий стол
    lg.setColor(0.07, 0.10, 0.16)
    lg.rectangle("fill", 392, 112, 641, 551)
    lg.setColor(C.panel_line); lg.rectangle("line", 392, 112, 641, 551)
    lg.setFont(F.badge); lg.setColor(C.brass)
    lg.print("ВАЛТЕК · рабочий стол Иры", 412, 126)
    lg.setFont(F.dlg)
    local items = {}
    for _, did in ipairs(w.hs.pc_docs) do items[#items + 1] = {d = did} end
    items[#items + 1] = {form = true}
    w.pc_items = items
    for i, it in ipairs(items) do
      local iy = 170 + (i - 1) * 62
      lg.setColor(0.13, 0.17, 0.25)
      lg.rectangle("fill", 420, iy, 585, 52, 8, 8)
      lg.setColor(C.panel_line); lg.rectangle("line", 420, iy, 585, 52, 8, 8)
      lg.setColor(C.text)
      local label = it.form and ("⚿  " .. T.docs.doc_skud_blank.title:gsub(" %(экран%)", "") .. " — ЗАПОЛНИТЬ")
        or ("🗎  " .. T.docs[it.d].title:gsub(" %(экран%)", ""))
      lg.print(label, 436, iy + 12)
    end
    lg.setColor(1, 1, 1)
  elseif w.kind == "form" then
    local x, y = 660, 280
    lg.setColor(C.panel); lg.rectangle("fill", x, y, 600, 440, 14, 14)
    lg.setColor(C.panel_line); lg.rectangle("line", x, y, 600, 440, 14, 14)
    lg.setFont(F.h2); lg.setColor(C.brass)
    lg.printf("ФОРМА СКУД-2", x, y + 16, 600, "center")
    -- поле «№ карты» (кликабельно; активное поле — яркая рамка)
    local f1 = (w.field == 1)
    lg.setFont(F.small); lg.setColor(C.text)
    lg.print(T.ui.form_card_no .. ":", x + 40, y + 96)
    lg.setColor(0.10, 0.12, 0.16); lg.rectangle("fill", x + 210, y + 84, 330, 52, 8, 8)
    lg.setColor(f1 and C.ok or C.panel_line); lg.setLineWidth(f1 and 3 or 1)
    lg.rectangle("line", x + 210, y + 84, 330, 52, 8, 8); lg.setLineWidth(1)
    lg.setFont(F.dlg); lg.setColor(C.text)
    lg.print(w.no .. string.rep("_", 6 - #w.no), x + 228, y + 90)
    -- поле «Отдел» (◀ ▶, клик по половинам меняет)
    local f2 = (w.field == 2)
    lg.setFont(F.small); lg.setColor(C.text)
    lg.print(T.ui.form_dept .. ":", x + 40, y + 172)
    lg.setColor(0.10, 0.12, 0.16); lg.rectangle("fill", x + 210, y + 160, 330, 52, 8, 8)
    lg.setColor(f2 and C.ok or C.panel_line); lg.setLineWidth(f2 and 3 or 1)
    lg.rectangle("line", x + 210, y + 160, 330, 52, 8, 8); lg.setLineWidth(1)
    lg.setFont(F.dlg); lg.setColor(C.text)
    lg.printf(P.tokens.depts[w.dept_i], x + 210, y + 166, 330, "center")
    -- стрелки ◀ ▶ — векторные (глифов треугольников нет в шрифте)
    lg.setColor(C.brass)
    lg.polygon("fill", x + 234, y + 186, x + 252, y + 172, x + 252, y + 200)
    lg.polygon("fill", x + 516, y + 186, x + 498, y + 172, x + 498, y + 200)
    -- подсказка ввода
    lg.setFont(F.small); lg.setColor(C.dim)
    lg.printf("Клик по полю — выбрать.  Цифры — с клавиатуры.  Tab — след. поле.",
      x + 40, y + 234, 520, "left")
    -- кнопка ОТПРАВИТЬ: ширина под текст (getWidth) + центрирование
    lg.setFont(F.h2)
    local label = T.ui.form_send
    local bw = F.h2:getWidth(label) + 90
    local bx, by = x + (600 - bw) / 2, y + 322
    w._send = {bx, by, bw, 68}
    lg.setColor(0.16, 0.4, 0.2); lg.rectangle("fill", bx, by, bw, 68, 10, 10)
    lg.setColor(C.ok); lg.setLineWidth(2)
    lg.rectangle("line", bx, by, bw, 68, 10, 10); lg.setLineWidth(1)
    lg.setColor(C.text); lg.printf(label, bx, by + 13, bw, "center")
    lg.setColor(1, 1, 1)
  end
end

local function keypad_click(x, y)
  local kx0, ky0, bw, bh = keypad_geom()
  local keys = {"1","2","3","4","5","6","7","8","9","C","0","OK"}
  for i, k in ipairs(keys) do
    local kx = kx0 + ((i - 1) % 3) * (bw + 10)
    local ky = ky0 + math.floor((i - 1) / 3) * (bh + 10)
    if x >= kx and x < kx + bw and y >= ky and y < ky + bh then
      if k == "C" then widget.buf = ""; snd("ui_click")
      elseif k == "OK" then
        local ok, why = ST:try_code(widget.node, widget.buf)
        if ok then
          snd("beep_ok"); sting("sting_solved"); say_node(widget.node, "do")
          ui.after_fire(widget.node); ui.close_widget()
        else
          snd("beep_err"); widget.buf = ""
          say_node(widget.node, "fail_code")
        end
      else
        if #widget.buf < 4 then widget.buf = widget.buf .. k; snd("ui_click") end
      end
      return true
    end
  end
  return false
end

local function pc_click(x, y)
  local w = widget
  for i, it in ipairs(w.pc_items or {}) do
    local iy = 170 + (i - 1) * 62
    if x >= 420 and x < 1005 and y >= iy and y < iy + 52 then
      if it.form then
        local ok, why = ST:can_fire("skud_form")
        if not ok and why == "needs" then
          say_node("skud_form", "fail")
        elseif ST.done.skud_form then
          say_node("skud_form", "already")
        else
          ui.open_widget("form", "skud_form", w.hs)
          push_lines(T.nodes.skud_form.open)
        end
      else
        ui.open_doc(it.d)
      end
      return true
    end
  end
  return false
end

local function form_click(x, y)
  local wx, wy = 660, 280
  local b = widget._send
  if b and x >= b[1] and x < b[1] + b[3] and y >= b[2] and y < b[2] + b[4] then
    local ok, why = ST:try_form(widget.no, P.tokens.depts[widget.dept_i])
    if ok then
      snd("beep_ok"); sting("sting_solved"); say_node("skud_form", "do")
      ui.after_fire("skud_form"); ui.close_widget()
    else
      snd("beep_err"); say_node("skud_form", "fail_code")
      widget.no = ""; widget.dept_i = 1; widget.field = 1
    end
    return true
  end
  -- клик по полю «№ карты» активирует его (цифры вводятся с клавиатуры)
  if x >= wx + 210 and x < wx + 540 and y >= wy + 84 and y < wy + 136 then
    widget.field = 1; snd("ui_click")
  -- клик по полю «Отдел»: левая/правая половина = меняет ◀ / ▶
  elseif x >= wx + 210 and x < wx + 540 and y >= wy + 160 and y < wy + 212 then
    widget.field = 2
    local depts = P.tokens.depts
    if x < wx + 375 then widget.dept_i = (widget.dept_i - 2) % #depts + 1
    else widget.dept_i = widget.dept_i % #depts + 1 end
    snd("ui_click")
  end
  return true
end

function ui.widget_key(key)
  if not widget then return false end
  if widget.kind == "keypad" then
    if key:match("^[0-9]$") and #widget.buf < 4 then
      widget.buf = widget.buf .. key; snd("ui_click")
    elseif key == "backspace" then widget.buf = widget.buf:sub(1, -2)
    elseif key == "return" then
      local kx, ky, bw, bh = keypad_geom()
      keypad_click(kx + 2 * (bw + 10) + bw / 2, ky + 3 * (bh + 10) + bh / 2)
    end
    return true
  elseif widget.kind == "form" then
    if key == "tab" then widget.field = 3 - widget.field
    elseif widget.field == 1 and key:match("^[0-9]$") and #widget.no < 6 then
      widget.no = widget.no .. key; snd("ui_click")
    elseif widget.field == 1 and key == "backspace" then
      widget.no = widget.no:sub(1, -2)
    elseif widget.field == 2 and (key == "left" or key == "right") then
      local depts = P.tokens.depts
      widget.dept_i = (key == "left")
        and ((widget.dept_i - 2) % #depts + 1)
        or (widget.dept_i % #depts + 1)
      snd("ui_click")
    end
    return true
  end
  return false
end

-- бенч-операции (клики по хотспотам зума транслируются сюда)
function ui.bench_node(id, btn)
  local op = id:match("^bench_move_(%w+)$")
  if op then op = op .. ((btn == 2) and "-" or "+") end
  if id == "bench_pump" then op = "PUMP"
  elseif id == "bench_reset" then op = "RESET" end
  local res, a, b = ST:bench_op(op)
  if res == "no_wheel" then
    say_node("install_wheel", "fail")
  elseif res == "reset" then
    snd("hiss")
    push_lines({{s = "lap", e = "neutral",
      t = "СБРОС. Пшшш — система выдохнула. Начинаем с чистого листа."}})
  elseif res == "pump" then
    snd("pump"); SC.mark_pump()
    push_lines({{s = "lap", e = "neutral",
      t = ("Кач. Стрелка ползёт (%d/%d)."):format(a, b)}})
  elseif res == "pump_futile" then
    snd("pump"); SC.mark_pump()
    push_lines({{s = "lap", e = "worried",
      t = "Качаю, а стрелка падает. Без верного порядка вентилей это мартышкин труд."}})
  elseif res == "seq_ok" then
    snd("valve")
  elseif res == "seq_done" then
    snd("valve")
    push_lines({{s = "anc", e = "calm",
      t = "Порядок соблюдён. Теперь — давление. Качай, потомок."}})
  elseif res == "seq_bad" then
    snd("creak")
    push_lines({{s = "anc", e = "stern",
      t = "НЕ ТОТ вентиль. Система обиделась и всё стравила. Сначала."}})
  elseif res == "solved" then
    snd("psh"); sting("sting_solved"); say_node("bench_solve", "do"); ui.after_fire("bench_solve")
  elseif res == "already" then
    say_node("bench_solve", "already")
  end
end

-- ================= МЕНЮ/ТИТУЛ =================
local function draw_title_logo()
  -- арт-логотип 2.0.1 (перегенерация по MIGRATION §5.1);
  -- движковый вариант v2.0.0 — в git-истории (санация бракованного лого)
  lg.setColor(1, 1, 1)
  lg.draw(IMG["ui/logo_title.png"], 360, 84)
end

local title_btns
local function menu_draw()
  if menu == nil then return end
  if menu == "title" then
    lg.draw(IMG["ui/bg_title.png"], 0, 0)
    draw_title_logo()
    title_btns = {}
    local labels = {{"start", T.ui.title_start}}
    if ui.has_save() then labels[#labels + 1] = {"cont", T.ui.title_continue} end
    labels[#labels + 1] = {"settings", T.ui.title_settings}
    labels[#labels + 1] = {"quit", T.ui.title_quit}
    lg.setFont(F.h2)
    for i, lb in ipairs(labels) do
      local bx, by, bw2, bh2 = 760, 560 + (i - 1) * 92, 400, 72
      title_btns[#title_btns + 1] = {id = lb[1], x = bx, y = by, w = bw2, h = bh2}
      lg.setColor(C.panel); lg.rectangle("fill", bx, by, bw2, bh2, 12, 12)
      lg.setColor(C.brass); lg.rectangle("line", bx, by, bw2, bh2, 12, 12)
      lg.setColor(C.text); lg.printf(lb[2], bx, by + 16, bw2, "center")
    end
  elseif menu == "pause" or menu == "settings" then
    lg.setColor(0, 0, 0, 0.6); lg.rectangle("fill", 0, 0, 1920, 1080)
    lg.setColor(C.panel); lg.rectangle("fill", 660, 240, 600, 560, 14, 14)
    lg.setColor(C.panel_line); lg.rectangle("line", 660, 240, 600, 560, 14, 14)
    lg.setFont(F.h2); lg.setColor(C.brass)
    lg.printf(menu == "pause" and T.ui.pause or T.ui.settings,
      660, 268, 600, "center")
    title_btns = {}
    lg.setFont(F.dlg)
    if menu == "pause" then
      local items = {{"resume", T.ui.resume}, {"settings", T.ui.settings},
                     {"savequit", T.ui.save_quit}}
      for i, it in ipairs(items) do
        local by = 360 + (i - 1) * 96
        title_btns[#title_btns + 1] = {id = it[1], x = 720, y = by, w = 480, h = 72}
        lg.setColor(0.15, 0.16, 0.2); lg.rectangle("fill", 720, by, 480, 72, 10, 10)
        lg.setColor(C.panel_line); lg.rectangle("line", 720, by, 480, 72, 10, 10)
        lg.setColor(C.text); lg.printf(it[2], 720, by + 18, 480, "center")
      end
    else
      local opts = {{"music", T.ui.music}, {"sound", T.ui.sound},
                    {"fullscreen", T.ui.fullscreen}, {"noshake", T.ui.noshake}}
      for i, o in ipairs(opts) do
        local by = 350 + (i - 1) * 80
        title_btns[#title_btns + 1] = {id = "opt_" .. o[1], x = 720, y = by,
                                        w = 480, h = 60}
        lg.setColor(C.text)
        lg.print(o[2], 740, by + 12)
        lg.setColor(settings[o[1]] and C.ok or C.dim)
        lg.rectangle(settings[o[1]] and "fill" or "line", 1120, by + 12, 36, 36, 6, 6)
      end
      title_btns[#title_btns + 1] = {id = "back", x = 720, y = 690, w = 480, h = 64}
      lg.setColor(0.15, 0.16, 0.2); lg.rectangle("fill", 720, 690, 480, 64, 10, 10)
      lg.setColor(C.panel_line); lg.rectangle("line", 720, 690, 480, 64, 10, 10)
      lg.setColor(C.text); lg.printf(T.ui.back, 720, 704, 480, "center")
    end
    lg.setColor(1, 1, 1)
  end
end

local settings_from = "title"
local function menu_click(x, y)
  for _, b in ipairs(title_btns or {}) do
    if x >= b.x and x < b.x + b.w and y >= b.y and y < b.y + b.h then
      snd("ui_click")
      if b.id == "start" then
        menu = nil; ui.new_game()
      elseif b.id == "cont" then
        menu = nil; ui.load_save(); mus_boot()
      elseif b.id == "settings" then
        settings_from = menu; menu = "settings"
      elseif b.id == "quit" then love.event.quit()
      elseif b.id == "resume" then menu = nil
      elseif b.id == "savequit" then ui.save(); menu = "title"
      elseif b.id == "back" then
        menu = settings_from
        if settings_from == nil then menu = "pause" end
        if settings_from == "title" then menu = "title" end
      elseif b.id:sub(1, 4) == "opt_" then
        local k = b.id:sub(5)
        settings[k] = not settings[k]
        if k == "fullscreen" then love.window.setFullscreen(settings.fullscreen) end
      end
      return true
    end
  end
  return false
end

function ui.new_game()
  ST:deserialize({})
  SC.goto_room("A")
  hint.topic_idx = {}
  hint_intro_done = false
  victory_stage = nil
  push_lines(T.opening)
  mus_boot()
end

-- ================= кнопка подсказки/паузы на экране =================
local function hud_buttons()
  return {
    {id = "hint", x = 1640, y = 12, w = 250, h = 48, t = T.ui.hint_btn},
    {id = "pause", x = 1560, y = 12, w = 64, h = 48, t = "II"},
    {id = "zones", x = 1414, y = 12, w = 130, h = 48, t = "ЗОНЫ"},
  }
end
local function hud_draw()
  local ox, oy = shk(4)
  lg.setFont(F.badge)
  for _, b in ipairs(hud_buttons()) do
    lg.setColor(C.panel)
    lg.rectangle("fill", b.x + ox, b.y + oy, b.w, b.h, 10, 10)
    lg.setColor(C.panel_line)
    lg.rectangle("line", b.x + ox, b.y + oy, b.w, b.h, 10, 10)
    lg.setColor(b.id == "hint" and C.steel or C.text)
    lg.printf(b.t, b.x + ox, b.y + 10 + oy, b.w, "center")
  end
  lg.setColor(1, 1, 1)
end

-- ================= idle =================
local idle_i = 0
local function idle_update(dt)
  if ui.in_menu() or ui.dialog_active() or widget or reader or victory_stage then
    idle_timer = 0; return
  end
  idle_timer = idle_timer + dt
  if idle_timer >= 75 then
    idle_timer = 0
    idle_i = idle_i + 1
    local pool = ST.flags.calm_down and T.idle_calm or T.idle
    push_lines({pool[(idle_i - 1) % #pool + 1]})
  end
end

-- ================= ГЛАВНЫЕ обработчики =================
function ui.update(dt)
  dlg_update(dt)
  idle_update(dt)
  mus_update(dt)
end

-- «предмет в руке»: иконка выбранного предмета у курсора (курсор-предмет)
local function held_item_draw()
  if not inv.selected then return end
  if widget or reader or menu or ui.dialog_active() then return end
  local ic = IMG["icons/ic_" .. inv.selected:gsub("^relic_", "") .. ".png"]
  if not ic then return end
  local mx, my = SC.mouse_world()
  local s = 48 / ic:getWidth()
  lg.setColor(0, 0, 0, 0.35)
  lg.draw(ic, mx + 20, my + 10, 0, s, s)
  lg.setColor(1, 1, 1, 0.95)
  lg.draw(ic, mx + 18, my + 8, 0, s, s)
  lg.setColor(1, 1, 1, 1)
end

function ui.draw_overlays()
  if not (victory_stage and not ui.dialog_active()) then
    goals_draw()
    inv_draw()
    hud_draw()
    held_item_draw()
  end
  widget_draw()
  reader_draw()
  dlg_draw()
  toast_draw()
  victory_draw()
  menu_draw()
end

local function fire_herring(node)
  local nt = T.nodes[node]
  if node == "h_intercom" and ST.flags.power_on and nt.powered then
    push_lines(nt.powered); return
  end
  if not ST.done[node] then
    ST:fire(node)
    push_lines(nt["do"])
    ui.after_fire(node)
  else
    if ST.flags.calm_down and nt.calm then push_lines(nt.calm)
    else
      local pool = nt.again or nt["do"]
      push_lines({pool[love.math.random(#pool)]})
    end
  end
end

-- === механика «использовать выбранный предмет на объект» (раунд 4) ===
-- Применяет предмет item к хотспоту h. Узел срабатывает ТОЛЬКО если предмет
-- входит в его требования и остальные условия выполнены; иначе — «не подходит»
-- или намёк-fail (если предмет верный, но чего-то ещё не хватает).
function ui.use_item_on(item, h)
  idle_timer = 0
  local node = h.node
  local n = node and ST.nodes[node]
  if n and not n.herring then
    local matches = false
    for _, it in ipairs(ST:item_needs(node)) do
      if it == item then matches = true; break end
    end
    if matches and not ST.done[node] then
      if select(1, ST:can_fire(node)) then
        if select(1, ST:fire(node)) then
          say_node(node, "do"); ui.after_fire(node)
          inv.selected = nil
        end
      else
        -- предмет верный, но не хватает другого предмета/флага — намёк
        say_node(node, "fail")
        if not (T.nodes[node] and T.nodes[node].fail) then
          push_lines({{s = "lap", e = "neutral",
            t = "Верно мыслю, но чего-то ещё не хватает."}})
        end
      end
      return
    end
    if ST.done[node] then say_node(node, "already"); return end
  end
  -- предмет к этому объекту не подходит
  push_lines({T.item_wrong[love.math.random(#T.item_wrong)]})
end

-- Клик мира: хотспот → действие
local function world_click(x, y, btn)
  local h = SC.hit(x, y)
  if not h then
    if btn == 1 and inv.selected then inv.selected = nil end
    return
  end
  idle_timer = 0
  if btn == 2 then
    if h.bench then ui.bench_node(h.node, 2); return end
    if h.doc_rmb then ui.open_doc(h.doc_rmb); return end
    if h.look and T.looks[h.id] then
      push_lines(T.looks[h.id].look); maybe_nervous(); return
    end
    return
  end
  -- ЛКМ
  -- если выбран предмет — клик по объекту ПРИМЕНЯЕТ его (не навигация/осмотр)
  if inv.selected then ui.use_item_on(inv.selected, h); return end
  if h.goto_room then
    snd("transition"); SC.goto_room(h.goto_room); ui.save_auto(); return
  end
  if h.goto then snd("zoom_in"); SC.goto_zoom(h.goto); return end
  if h.doc then ui.open_doc(h.doc); return end
  if h.widget == "pc" then
    if ST.flags.pc_on then ui.open_widget("pc", "pc_unlock", h)
    else
      ui.open_widget("keypad", "pc_unlock", h)
      if not ST.done.pc_unlock then push_lines(T.nodes.pc_unlock.open) end
    end
    return
  end
  if h.widget == "keypad" then
    if ST.done[h.node] then say_node(h.node, "already"); return end
    ui.open_widget("keypad", h.node, h)
    push_lines(T.nodes[h.node].open)
    return
  end
  if h.widget == "breakers" then
    local idx = math.floor((x - h.breaker_x0) / h.breaker_step) + 1
    idx = math.max(1, math.min(#h.breaker_map, idx))
    local node = h.breaker_map[idx]
    if node == nil then push_lines(T.breaker_dead); snd("ui_click"); return end
    if ST.nodes[node].herring then fire_herring(node); return end
    if ST.done[node] then say_node(node, "already"); return end
    local ok = select(1, ST:fire(node))
    if ok then say_node(node, "do"); ui.after_fire(node) end
    return
  end
  if h.widget == "bolt" then
    -- засову нужен предмет (литол + разводник): обычный клик — только намёк,
    -- само применение идёт через выбранный предмет (ui.use_item_on)
    if ST.done.bolt_free then say_node("bolt_free", "already")
    else say_node("bolt_free", "fail") end
    return
  end
  if h.bench then ui.bench_node(h.node, btn); return end
  if h.node then
    local n = ST.nodes[h.node]
    if n.herring then
      fire_herring(h.node)
      maybe_nervous()
      return
    end
    -- узел-ДЕЙСТВИЕ, требующий предмет, НЕ срабатывает от простого клика:
    -- нужен выбранный в карманах предмет (ui.use_item_on). Клик — намёк.
    if n.type == "action" and #ST:item_needs(h.node) > 0
       and not ST.done[h.node] then
      say_node(h.node, "fail")
      if not (T.nodes[h.node] and T.nodes[h.node].fail) then
        push_lines({{s = "lap", e = "neutral",
          t = "Тут нужен подходящий предмет. Возьми его в карманах и примени."}})
      end
      maybe_nervous()
      return
    end
    local ok, why = ST:can_fire(h.node)
    if why == "already" then say_node(h.node, "already"); return end
    if not ok then
      say_node(h.node, "fail")
      if not T.nodes[h.node].fail then
        push_lines({{s = "lap", e = "neutral", t = "Пока не выходит."}})
      end
      return
    end
    local fired = select(1, ST:fire(h.node))
    if fired then say_node(h.node, "do"); ui.after_fire(h.node) end
    return
  end
  if h.look then
    push_lines(T.looks[h.id] and T.looks[h.id].look or
      {{s = "lap", e = "neutral", t = h.name .. ". Ну, " .. h.name:lower() .. "."}})
    maybe_nervous()
  end
end

function ui.save_auto() ui.save() end

function ui.mousepressed(x, y, btn)
  if menu then menu_click(x, y); return end
  if victory_stage and not ui.dialog_active() then return end
  if reader then
    if btn == 2 then reader = nil; snd("paper")
    else
      local d = T.docs[reader.doc]
      if reader.page < #d.pages then reader.page = reader.page + 1
      else reader = nil; snd("paper") end
    end
    return
  end
  if ui.dialog_active() then
    if btn == 1 then dlg_click() end
    return
  end
  if btn == 1 and not widget and ui.goals_click(x, y) then
    snd("ui_click"); return       -- тоггл плашки целей, клик не сквозит в сцену
  end
  if widget then
    if btn == 2 then ui.close_widget(); snd("zoom_out"); return end
    if widget.kind == "keypad" then keypad_click(x, y)
    elseif widget.kind == "pc" then pc_click(x, y)
    elseif widget.kind == "form" then form_click(x, y) end
    return
  end
  -- HUD
  for _, b in ipairs(hud_buttons()) do
    if x >= b.x and x < b.x + b.w and y >= b.y and y < b.y + b.h then
      if b.id == "hint" then ui.hint()
      elseif b.id == "zones" then ui.zones_toggle()
      else menu = "pause" end
      snd("ui_click")
      return
    end
  end
  if inv_click(x, y, btn) then return end
  if btn == 1 then
    -- выбор предмета НЕ сбрасывается до клика по миру: world_click применит
    -- его к объекту (механика «использовать предмет на объект», раунд 4)
    world_click(x, y, 1)
    return
  end
  if btn == 2 then
    -- ПКМ снимает выбор предмета
    if inv.selected then inv.selected = nil; snd("ui_click"); return end
    local h = SC.hit(x, y)
    if h and (h.bench or h.doc_rmb or (h.look and T.looks[h.id])) then
      world_click(x, y, 2)
      return
    end
    if SC.view().kind == "zoom" then snd("zoom_out"); SC.leave_zoom() end
  end
end

function ui.keypressed(key)
  if menu == "title" then
    if key == "return" then menu = nil; ui.new_game() end
    return
  end
  if victory_stage and not ui.dialog_active() then
    if key == "escape" then ui.save(); ui.reset_to_title() end
    return
  end
  if key == "escape" then
    if reader then reader = nil
    elseif widget then ui.close_widget(); snd("zoom_out")
    elseif ui.dialog_active() then dlg_click()
    elseif inv.selected then inv.selected = nil; snd("ui_click")
    elseif SC.view().kind == "zoom" then snd("zoom_out"); SC.leave_zoom()
    elseif menu == "pause" then menu = nil
    elseif menu == "settings" then menu = settings_from or "pause"
    else menu = "pause" end
    return
  end
  if key == "space" then
    if ui.dialog_active() then dlg_click() end
    return
  end
  if ui.widget_key(key) then return end
end

local zones_on = false
function ui.zones_toggle() zones_on = not zones_on end
function ui.space_down()
  return (love.keyboard.isDown("space") or zones_on) and not ui.dialog_active()
    and not widget and not reader and not menu
end

function ui.settings_table() return settings end
ui.C = C

return ui
