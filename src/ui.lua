-- src/ui.lua — интерфейс: диалоги, инвентарь, цели, читалка, виджеты, меню
local ui = {}
local lg = love.graphics
local json = require("src.json")
local utf8 = require("utf8")

local T, P, ST, SC, IMG, AUD, F
local settings = {music = true, sound = true, fullscreen = false, noshake = false, fasttext = false}
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
local last_autosave = -1e9   -- (аудит F06) троттлинг автосейва
local victory_stage = nil   -- объявлен выше менеджера музыки/стингеров

ui.autoplay_hooks = {}    -- заполняет autoplay

function ui.init(texts, puzzles, state, scenes_mod, images, audio, fonts)
  T, P, ST, SC, IMG, AUD, F = texts, puzzles, state, scenes_mod, images, audio, fonts
  SC.set_fonts(fonts)
  ui.load_settings()                                    -- (аудит F09) отдельный settings-файл
  love.window.setFullscreen(settings.fullscreen or false)
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

  -- «Саундтрек тряски» (слой nervous) и обычный фон ВЗАИМОИСКЛЮЧЕНЫ.
  -- Правило (запрос автора): nervous звучит ⟺ тряска РЕАЛЬНО идёт — включена
  -- в настройках (not noshake) И не унята внутриигрово (not calm_down), в самой
  -- игре (не титул/не победа). Как только тряску унял (валидол+кофе → calm_down)
  -- или выключил в настройках — звучит обычный фон. То есть аудио точно повторяет
  -- визуальную тряску (см. shake_amp: тоже 0 при noshake или calm_down).
  -- Две дорожки одновременно НИКОГДА: входящая поднимается только когда исходящая
  -- полностью стихла (порог 0.03) — наложения нет даже на переходе («вдох» тишины).
  local nervous = (not settings.noshake) and not ST.flags.calm_down
                  and menu ~= "title" and not victory_stage

  -- выбор слота фона идёт всегда, даже когда фон приглушён из-за nervous —
  -- чтобы при возврате сразу звучала музыка текущей комнаты
  local want = mus_target_bgm()
  local cs = mus.slots[mus.cur]
  if mus.cur == 0 or (cs and cs.name ~= want) then
    local ni = (mus.cur == 1) and 2 or 1
    local ns = mus.slots[ni]
    if ns.src and ns.src:isPlaying() then ns.src:stop() end
    ns.name, ns.vol, ns.src = want, 0, AUD[want]
    mus.cur = ni
  end

  -- взаимный гейт: уровни исходящих дорожек (порог тишины 0.03)
  local bgm_v = math.max(mus.slots[1].vol, mus.slots[2].vol)
  local ln_q = mus.ln_vol < 0.03                    -- nervous уже стих?
  local bgm_q = bgm_v < 0.03 and mus.lg_vol < 0.03  -- фон и гирлянда стихли?

  -- обычный фон звучит, только если nervous не нужен И уже стих
  local bgm_on = (not nervous) and ln_q
  for i, s in ipairs(mus.slots) do
    s.vol = approach(s.vol, (i == mus.cur and bgm_on) and 1 or 0, dt, BGM_FADE)
    mus_apply(s.src, s.vol * mus.gain * MUS_MASTER)
  end

  -- слой «нервы» звучит, только если нужен И фон уже стих
  local ln_on = nervous and bgm_q
  mus.ln_vol = approach(mus.ln_vol, ln_on and 1 or 0, dt, LAYER_FADE)
  mus_apply(AUD.layer_nervous, mus.ln_vol * mus.gain * MUS_MASTER)

  -- слой «гирлянда»: festive-акцент только поверх обычного фона (не поверх nervous)
  local lg_on = ST.flags.garland_on and menu ~= "title" and not victory_stage
                and not nervous and ln_q
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
  if ST.inv.coffee or ST.inv.validol then return 2.5 end  -- унял чуть — дрожь спадает
  return 6.0                                               -- на нервах — заметно трясёт (плашки)
end
local function shk(k)
  local a = shake_amp()
  if a == 0 then return 0, 0 end
  -- нервная дрожь плашки: сумма двух частот (быстрая тремор-составляющая),
  -- фаза разнесена по k, чтобы плашки не «ехали» синхронно. Смещение — только
  -- в отрисовке плашек; хит-тесты плашек статичны, целимся в центр — клик не рвётся.
  local t = SC.time()
  local ox = (math.sin(t * 17 + k * 7.3) * 0.7 + math.sin(t * 31 + k * 2.1) * 0.3) * a
  local oy = (math.cos(t * 15 + k * 5.1) * 0.7 + math.cos(t * 27 + k * 1.7) * 0.3) * a * 0.85
  return ox, oy
end

-- ================= диалог =================
-- (аудит К3) Реплика без speaker/emotion роняла отрисовку на конкатенации
-- nil (порт, плашка имени) и на utf8.len(nil). Ловить это обязан GATE2 на
-- сборке (см. tools/validate_scene.py), но рантайм не имеет права падать в
-- Lua-ошибку у игрока: битая запись чинится дефолтом и пишется в stderr.
-- Здоровый путь не трогаем — копия создаётся только у битой записи.
local DEF_EMO = { lap = "neutral", anc = "calm" }
local function fix_line(r)
  if type(r) ~= "table" then
    io.stderr:write("UI WARN: реплика не таблица (" .. type(r) .. ")\n")
    return { s = "lap", e = DEF_EMO.lap, t = "…" }
  end
  if type(r.s) == "string" and type(r.e) == "string" and type(r.t) == "string"
     and DEF_EMO[r.s] then return r end
  local s = (type(r.s) == "string" and DEF_EMO[r.s]) and r.s or "lap"
  local fixed = { s = s,
                  e = (type(r.e) == "string") and r.e or DEF_EMO[s],
                  t = (type(r.t) == "string") and r.t or "…" }
  io.stderr:write(("UI WARN: битая реплика s=%s e=%s t=%s -> %s/%s\n"):format(
    tostring(r.s), tostring(r.e), type(r.t), fixed.s, fixed.e))
  return fixed
end

local function push_lines(lines)
  for _, r in ipairs(lines or {}) do dlg.queue[#dlg.queue + 1] = fix_line(r) end
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
-- (аудит В4) спикер берётся из активной реплики, а если кадр обновления ещё
-- не наступил — из головы очереди: утверждение не должно зависеть от того,
-- успел ли пройти dlg_update между кликом и проверкой
function ui.current_speaker()
  if dlg.cur then return dlg.cur.s end
  local q = dlg.queue[1]
  return q and q.s or nil
end
-- (аудит К1/В4) текст текущей реплики — для текстовых утверждений автоплея
function ui.current_text()
  if dlg.cur then return dlg.cur.t end
  local q = dlg.queue[1]
  return q and q.t or nil
end

local function dlg_update(dt)
  if not dlg.cur and #dlg.queue > 0 then dlg_next() end
  local cur = dlg.cur
  if not cur then return end
  local full = utf8.len(cur.t)
  if dlg.shown < full then
    if settings.fasttext then dlg.shown = full; dlg.t = full; return end   -- (аудит U03) мгновенный текст
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
  if port then lg.draw(port, px + 6, py + 6, 0, 0.5, 0.5) end   -- (аудит F11) не падать на отсутствующем портрете
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
  -- bench_printed_ru / bench_seq_ru приходят из gen_puzzles СПИСКАМИ шагов;
  -- склеиваем в строку-процедуру (иначе gsub-замена получает таблицу и
  -- читалка листка стенда падает). Разделитель « » », а не « → »: стрелки
  -- нет ни в одном шрифте сборки, и процедура на листке читалась как
  -- «П ☒ К1 ☒ …» — квадраты вместо стрелок (р.19, гейт tools/check_fonts.py).
  if k == "bench_printed_ru" then
    return table.concat(P.answers.bench_printed_ru, " » ")
  end
  if k == "bench_seq_ru" then
    return table.concat(P.answers.bench_seq_ru, " » ")
  end
  if k == "bench_fix_ru" then
    local i0 = P.answers.bench_fix_idx          -- 0-based индекс шага-опечатки
    local pr = P.answers.bench_printed_ru
    local rt = P.answers.bench_seq_ru
    return ("шаг %d: не «%s», а «%s»"):format(
      i0 + 1, pr[i0 + 1] or "?", rt[i0 + 1] or "?")
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
    -- (р.19) «▸» в PTSans нет — на плашке стоял квадрат-тофу. Рисуем треугольник.
    local head = T.ui.goals .. "  " .. dn .. "/" .. tot
    lg.print(head, x + 14, y + 6)
    local tx = x + 14 + F.badge:getWidth(head) + 14
    lg.polygon("fill", tx, y + 9, tx + 12, y + 17, tx, y + 25)
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
    local gy = y + 34 + (i - 1) * 30
    lg.setColor(done and C.ok or C.text)
    -- (р.19) «✓» в PTSans тоже нет: каждая закрытая цель показывала квадрат.
    -- Галочка и точка — вектором, текст цели от единой левой границы.
    if done then
      lg.setLineWidth(3)
      lg.line(x + 18, gy + 13, x + 23, gy + 19, x + 32, gy + 6)
      lg.setLineWidth(1)
    else
      lg.circle("fill", x + 24, gy + 13, 3.5)
    end
    lg.print(g.t, x + 40, gy)
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
  -- (р.19) цепочка карты разбита на три темы: раньше t_card держался до
  -- card_active и повторял «лови сачком», когда игрок уже стоял перед ПИНом.
  {"t_card", function() return not ST.inv.card end},
  {"t_pc", function() return not ST.flags.pc_on end},
  {"t_skud", function() return not ST.flags.card_active end},
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
-- (аудит F02) Атомарная запись: во временный файл -> подмена через ОС; прежний
-- сейв уходит в .bak. Прерванная запись (вылет/питание/диск) не оставит усечённый
-- рабочий сейв. os.rename в пределах save-каталога атомарен (один том).
local function atomic_write(path, data)
  if not love.filesystem.write(path .. ".tmp", data) then return false end
  local dir = love.filesystem.getSaveDirectory()
  os.remove(dir .. "/" .. path .. ".bak")
  os.rename(dir .. "/" .. path, dir .. "/" .. path .. ".bak")  -- прежний -> .bak (может отсутствовать)
  return os.rename(dir .. "/" .. path .. ".tmp", dir .. "/" .. path)
end

local SAVE_VERSION = 3

function ui.save()
  local blob = {version = SAVE_VERSION, state = ST:serialize(), view = SC.view(),
                settings = settings, hint_idx = hint.topic_idx}
  atomic_write(savefile, json.encode(blob))
end
function ui.has_save() return love.filesystem.getInfo(savefile) ~= nil end

-- (аудит F01/С1) Защищённое чтение. Битый JSON, отсутствие .state или ЧУЖАЯ
-- версия формата не роняют игру и не подсовывают состояние от другой сборки:
-- поля меняются между версиями, и «почти подходящий» сейв хуже отсутствующего.
-- Возвращает blob либо nil и причину — причина нужна вызывающему, чтобы внятное
-- «версия» не подменилось невнятным «нет файла» от резервной копии.
local function read_save(path)
  local s = love.filesystem.read(path)
  if not s then return nil, "нет файла" end
  local ok, blob = pcall(json.decode, s)
  if not ok or type(blob) ~= "table" or type(blob.state) ~= "table" then
    return nil, "битый файл"
  end
  if blob.version ~= SAVE_VERSION then
    -- без «≠»: символа нет в Neucha, а строка может уйти в тост (гейт шрифтов)
    return nil, string.format("версия %s, нужна %d", tostring(blob.version), SAVE_VERSION)
  end
  return blob
end

-- (аудит С1) Чистка снимка по словарям сборки. Сейв — обычный JSON в
-- пользовательском каталоге: его правят руками, таскают между сборками и бьют
-- на полпути. Имя, которого в этой сборке нет, — это не «немного другой
-- прогресс», а предмет без картинки и узел без правил. Выбрасываем.
local function sanitize_state(s)
  local dropped = {}
  local function filter(list, known, label)
    local out, bad = {}, 0
    for _, k in ipairs(list or {}) do
      if type(k) == "string" and known[k] then out[#out + 1] = k
      else bad = bad + 1 end
    end
    if bad > 0 then dropped[#dropped + 1] = string.format("%s %d", label, bad) end
    return out
  end
  s.inv  = filter(s.inv,  ST.items_set, "предметов")
  s.done = filter(s.done, ST.nodes,     "узлов")
  s.read = filter(s.read, T.docs,       "документов")
  -- Флаги словаря не имеют: их порождают узлы, списка «всех возможных» нет.
  -- Чужой флаг безвреден — он просто никогда не совпадёт ни с одним needs,
  -- а вред от недостижимой победы ловит проба ниже.
  if type(s.flags) ~= "table" then s.flags = {} end
  local b = type(s.bench) == "table" and s.bench or {}
  if not ST:bench_seq_ok(b.seq) then
    b.seq, b.pumps = {}, 0
    dropped[#dropped + 1] = "стенд сброшен"
  end
  b.pumps = tonumber(b.pumps) or 0
  s.bench, s.steps = b, tonumber(s.steps) or 0
  return dropped
end

-- (аудит С1) Точка обзора тоже проверяется по словарю сцены: зум, которого в
-- сборке нет, оставлял игрока в пустом кадре без единого хотспота — выйти
-- можно было только через меню.
local function restore_view(v)
  local S = ui.scene_json or {}
  local rooms, zooms = S.rooms or {}, S.zooms or {}
  if type(v) ~= "table" then SC.goto_room("A"); return nil end
  if type(v.room) ~= "string" or not rooms[v.room] then
    SC.goto_room("A")
    if v.room ~= nil then
      return string.format("неизвестная комната %q — откат в комнату A",
                           tostring(v.room))
    end
    return nil
  end
  SC.goto_room(v.room)
  if v.kind == "zoom" then
    if type(v.zoom) == "string" and zooms[v.zoom] then
      SC.goto_zoom(v.zoom)
    else
      return string.format("неизвестный зум %q — показываю комнату %s целиком",
                           tostring(v.zoom), v.room)
    end
  end
  return nil
end

-- (аудит С1) Проба на проходимость: применённое состояние прогоняется солвером
-- на копии. Загрузку это не отменяет — решать игроку, — но про тупик он узнаёт
-- сразу, а не после получаса обшаривания углов.
local function probe_dead_end()
  if ST.flags.victory then return nil end
  local ok, won, why = pcall(function() return ST:clone():solve(400) end)
  if not ok then return "солвер не отработал" end
  if won then return nil end
  return why == "budget" and "не уложился в бюджет шагов" or "тупик"
end

function ui.load_save()
  local blob, why = read_save(savefile)
  if not blob then
    local bak, why_bak = read_save(savefile .. ".bak")
    -- причина от основного файла информативнее: .bak обычно просто нет
    if bak then blob, why = bak, nil
    elseif why == "нет файла" then why = why_bak end
  end
  if not blob then
    print("сейв: отвергнут — " .. tostring(why))
    ui.toast("Сейв не загрузился: " .. tostring(why))
    return false
  end
  local dropped = sanitize_state(blob.state)
  if #dropped > 0 then
    print("сейв: выброшено чужих имён — " .. table.concat(dropped, ", "))
    ui.toast("Сейв из другой сборки — лишнее выброшено")
  end
  ST:deserialize(blob.state)
  SC.reset_anims()                                          -- (аудит С2) метки не наследуются
  for k, v in pairs(blob.settings or {}) do settings[k] = v end
  love.window.setFullscreen(settings.fullscreen or false)   -- (аудит F04) применить оконный режим
  hint.topic_idx = type(blob.hint_idx) == "table" and blob.hint_idx or {}
  local note = restore_view(blob.view)
  if note then
    print("сейв: " .. note)
    ui.toast("Точка обзора из сейва не найдена")
  end
  local dead = probe_dead_end()
  if dead then
    print("сейв: из этой точки победа недостижима (" .. dead .. ")")
    ui.toast("Внимание: из этой точки победа недостижима")
  end
  return true
end

-- (аудит F09) настройки персистятся отдельно от прогресса (settings-файл)
local settings_file = "settings_bj2.json"
function ui.save_settings()
  atomic_write(settings_file, json.encode(settings))
end
function ui.load_settings()
  local s = love.filesystem.read(settings_file)
  if not s then return end
  local ok, t = pcall(json.decode, s)
  if ok and type(t) == "table" then
    for k, v in pairs(t) do if settings[k] ~= nil then settings[k] = v end end
  end
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
  -- (аудит F06) прогресс переживает вылет: автосейв после значимого узла (троттлинг 3с)
  if not ui.in_menu() and SC.time() - last_autosave > 3 then
    last_autosave = SC.time(); ui.save()
  end
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

-- Архив бумаг (р.19). Панель на 2 колонки по 9 строк — ровно под 17 бумаг
-- из scene.doc_list, с запасом на одну. Геометрия в одном месте: рисование
-- и клик обязаны читать её отсюда (docs/LESSONS.md — координаты не дублировать).
-- Только ПРОЧИТАННОЕ и в порядке scene.doc_list: архив не оглавление
-- ненайденного — иначе он сам стал бы спойлером (канон, AGENTS.md §1).
local function docs_list()
  local out = {}
  for _, did in ipairs((ui.scene_json and ui.scene_json.doc_list) or {}) do
    if ST.read[did] and T.docs[did] then out[#out + 1] = did end
  end
  return out
end
-- Панель растёт под содержимое: на четырёх бумагах фикс 1240x780 выглядел
-- как пустой ангар. До 9 бумаг — одна колонка, дальше вторая (всего 17).
-- Колонки уравнены (ceil(n/2)), а не «первая под завязку»: на десяти бумагах
-- заполненная девятка плюс одинокая строка справа читались как поломка.
-- Возвращает x, y, w, h, колонок, строк в колонке.
local function docs_geom()
  local n = #docs_list()
  local cols = (n > 9) and 2 or 1
  local per = (cols == 2) and math.ceil(n / 2) or n
  local rows = math.max(3, per)
  local pw = 80 + cols * 560 + (cols - 1) * 40
  local ph = 90 + rows * 62 + 74
  return (1920 - pw) / 2, (1080 - ph) / 2, pw, ph, cols, per
end
-- Прямоугольник i-й строки (1-based): сперва левая колонка сверху вниз.
local function docs_slot(i)
  local px, py, _, _, _, per = docs_geom()
  return px + 40 + math.floor((i - 1) / math.max(1, per)) * 600,
         py + 90 + ((i - 1) % math.max(1, per)) * 62, 560, 52
end
-- Значок бумаги/бланка вектором: в PTSans нет ни 🗎, ни ⚿ — с раунда 4 на
-- рабочем столе Иры вместо иконок стояли квадраты-тофу (видно на
-- work/shots/ap_06_pc_desktop.png). Заодно бланк СКУД теперь отличим от
-- своей же читаемой копии не только хвостом «— ЗАПОЛНИТЬ».
local function doc_icon(x, y, form)
  lg.setColor(0.86, 0.84, 0.78)
  lg.rectangle("fill", x, y, 21, 27, 3, 3)
  lg.setColor(0.32, 0.30, 0.27); lg.setLineWidth(2)
  lg.rectangle("line", x, y, 21, 27, 3, 3); lg.setLineWidth(1)
  lg.setColor(0.45, 0.43, 0.40)
  for k = 0, 3 do lg.line(x + 5, y + 7 + k * 5, x + 16, y + 7 + k * 5) end
  if form then                       -- карандаш поверх бланка
    lg.setColor(C.brass); lg.setLineWidth(4)
    lg.line(x + 6, y + 25, x + 22, y + 6); lg.setLineWidth(1)
    lg.setColor(0.20, 0.18, 0.16)
    lg.circle("fill", x + 6, y + 25, 2.5)
  end
end
-- Гаунтлету: где лежит строка бумаги (мир-координаты) — жать он будет сам,
-- через настоящий ui.mousepressed. Так тест не держит копию координат и не
-- ломается от порядка прочтения; nil — бумаги в архиве нет.
function ui.docs_slot_of(doc_id)
  for i, did in ipairs(docs_list()) do
    if did == doc_id then return docs_slot(i) end
  end
  return nil
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
      doc_icon(436, iy + 13, it.form)
      lg.setFont(F.dlg); lg.setColor(C.text)
      local label = it.form and (T.docs.doc_skud_blank.title:gsub(" %(экран%)", "") .. " — ЗАПОЛНИТЬ")
        or (T.docs[it.d].title:gsub(" %(экран%)", ""))
      lg.print(label, 474, iy + 12)
    end
    lg.setColor(1, 1, 1)
  elseif w.kind == "docs" then
    local px, py, pw, ph = docs_geom()
    lg.setColor(C.panel); lg.rectangle("fill", px, py, pw, ph, 16, 16)
    lg.setColor(C.panel_line); lg.setLineWidth(2)
    lg.rectangle("line", px, py, pw, ph, 16, 16); lg.setLineWidth(1)
    lg.setFont(F.h2); lg.setColor(C.brass)
    lg.printf(T.ui.docs_title, px, py + 20, pw, "center")
    local list = docs_list()
    w.docs_items = list
    if #list == 0 then
      lg.setFont(F.dlg); lg.setColor(C.dim)
      lg.printf(T.ui.docs_empty, px + 60, py + 130, pw - 120, "center")
    end
    for i, did in ipairs(list) do
      local ix, iy, iw, ih = docs_slot(i)
      lg.setColor(0.13, 0.17, 0.25)
      lg.rectangle("fill", ix, iy, iw, ih, 8, 8)
      lg.setColor(C.panel_line); lg.rectangle("line", ix, iy, iw, ih, 8, 8)
      doc_icon(ix + 16, iy + 13, false)
      local label = T.docs[did].title:gsub(" %(экран%)", "")
      -- длинные заголовки не режем, а мельчим: обрезка многоточием на
      -- кириллице требует utf8-смещений и всё равно съедает смысл строки
      local fnt = (F.dlg:getWidth(label) <= iw - 70) and F.dlg or F.small
      lg.setFont(fnt); lg.setColor(C.text)
      lg.print(label, ix + 54, iy + (ih - fnt:getHeight()) / 2)
    end
    lg.setFont(F.small); lg.setColor(C.dim)
    lg.printf(T.ui.docs_help, px, py + ph - 54, pw, "center")
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

-- Клик по строке архива открывает читалку ПОВЕРХ архива: порядок отрисовки
-- (widget_draw → reader_draw) и порядок ввода в ui.mousepressed совпадают,
-- поэтому закрытие бумаги возвращает игрока в список, а не в комнату.
local function docs_click(x, y)
  -- список берём заново, а не из кэша отрисовки: клик обязан работать и до
  -- первого draw (headless-прогоны гаунтлета кликают быстрее, чем рисуют)
  for i, did in ipairs(widget.docs_items or docs_list()) do
    local ix, iy, iw, ih = docs_slot(i)
    if x >= ix and x < ix + iw and y >= iy and y < iy + ih then
      ui.open_doc(did)
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
                    {"fullscreen", T.ui.fullscreen}, {"noshake", T.ui.noshake},
                    {"fasttext", T.ui.fasttext or "Быстрый текст"}}
      for i, o in ipairs(opts) do
        local by = 350 + (i - 1) * 68
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
        -- (аудит F01) на битом сейве остаёмся на титуле, а не в пустом состоянии
        if ui.load_save() then menu = nil; mus_boot() end
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
        ui.save_settings()                              -- (аудит F09) сохранить настройку сразу
      end
      return true
    end
  end
  return false
end

function ui.new_game()
  ST:deserialize({})
  SC.reset_anims()   -- (аудит С2) метки идл-анимаций не переживают новую игру
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
    -- (р.19) АРХИВ БУМАГ. Замечание автора: бирка Санты читается только пока
    -- коробка цела; забрал сотку — коробка исчезла, и подсказку не перечитать.
    -- Кнопка живёт в той же полосе HUD, слева от «ЗОНЫ» (зазор 16, как у прочих).
    {id = "docs", x = 1238, y = 12, w = 160, h = 48, t = T.ui.docs_btn},
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
    -- пустой архив помечен тусклой надписью: кнопка есть всегда (иначе она
    -- появлялась бы «из ниоткуда»), но врать о содержимом не должна
    if b.id == "hint" then lg.setColor(C.steel)
    elseif b.id == "docs" and not next(ST.read) then lg.setColor(C.dim)
    else lg.setColor(C.text) end
    lg.printf(b.t, b.x + ox, b.y + 10 + oy, b.w, "center")
  end
  lg.setColor(1, 1, 1)
end
-- (р.19) Прямоугольник кнопки HUD по id — гаунтлету, чтобы он жал ровно те
-- же пиксели, что и человек, и не хранил копию координат у себя.
function ui.hud_button_rect(id)
  for _, b in ipairs(hud_buttons()) do
    if b.id == id then return b.x, b.y, b.w, b.h end
  end
  return nil
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

-- (аудит U01) имя объекта под курсором (узнаваемость p&c)
local function hover_name_draw()
  if menu or reader or widget or victory_stage or ui.dialog_active() then return end
  local mx, my = SC.mouse_world()
  local h = SC.hit(mx, my)
  if not h or not h.name then return end
  lg.setFont(F.small)
  local w = F.small:getWidth(h.name) + 24
  local x = math.max(4, math.min(mx + 22, 1920 - w - 4))
  local y = math.max(4, my - 40)
  lg.setColor(C.panel)
  lg.rectangle("fill", x, y, w, 32, 6, 6)
  lg.setColor(C.panel_line)
  lg.rectangle("line", x, y, w, 32, 6, 6)
  lg.setColor(C.text)
  lg.print(h.name, x + 12, y + 4)
  lg.setColor(1, 1, 1)
end

function ui.draw_overlays()
  if not (victory_stage and not ui.dialog_active()) then
    goals_draw()
    inv_draw()
    hud_draw()
    held_item_draw()
    hover_name_draw()
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

-- (clarity р.16) Почему выходная дверь не открывается: перечисляем незакрытые
-- требования узла door_open живым языком Лапидуса. Спойлеров нет — только «что
-- ещё висит». reader_green раскрываем на под-причины: нет света / пропуск не
-- оживлён / осталось приложить пропуск к считывателю.
local DOOR_REASON = {
  surveyed  = {s = "lap", e = "neutral", t = "Я тут ещё толком не осмотрелся. Сперва — глаза разуть."},
  alarm_off = {s = "lap", e = "worried", t = "Сигналка ещё под током. С ней дверь злить не будем."},
  bolt_free = {s = "lap", e = "tired",   t = "Засов держит намертво. Сам себя он не отпустит."},
  calm_down = {s = "lap", e = "panic",   t = "Руки ходуном — какой тут замок. Сперва надо унять трясучку."},
}
local function door_reason_lines()
  local out = {}
  for _, need in ipairs(ST.nodes.door_open.needs) do
    if not ST:need_ok(need) then
      if need == "reader_green" then
        if not ST.flags.power_on then
          out[#out + 1] = {s = "lap", e = "tired", t = "Считыватель у двери мёртв — на нём нет питания. Света бы сюда."}
        elseif not ST.flags.card_active then
          out[#out + 1] = {s = "lap", e = "tired", t = "Считывателю нечего читать: пропуск ещё не оживлён."}
        else
          out[#out + 1] = {s = "lap", e = "neutral", t = "Пропуск готов, свет есть — осталось приложить его к считывателю у двери."}
        end
      elseif DOOR_REASON[need] then
        out[#out + 1] = DOOR_REASON[need]
      end
    end
  end
  return out
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
    -- (аудит К1) дырка в карте приходит из JSON как json.null: раньше она
    -- проваливалась при разборе, длина карты падала до 5, и клик по шестому
    -- рычагу зажимался клампом в пятый (герринг «РЕЗЕРВ»).
    if node == nil or node == json.null then
      push_lines(T.breaker_dead); snd("ui_click"); return
    end
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
      if h.node == "door_open" then   -- (clarity р.16) внятный список незакрытого
        local rs = door_reason_lines()
        if #rs > 0 then
          push_lines({{s = "lap", e = "tired", t = "Дверь не поддаётся. Гляну, что ещё висит:"}})
          push_lines(rs)
          return
        end
      end
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
  -- (аудит С3) Порядок разбора обязан совпадать с порядком отрисовки, иначе
  -- клик получает не тот слой, который человек видит сверху. Рисуем виджет →
  -- читалку → диалог (см. draw_overlays), значит и ввод идёт сверху вниз:
  -- диалог раньше читалки. Раньше было наоборот, и реплики поверх открытого
  -- документа приходилось «прокликивать» вслепую через страницы.
  if ui.dialog_active() then
    if btn == 1 then dlg_click() end
    return
  end
  if reader then
    if btn == 2 then reader = nil; snd("paper")
    else
      local d = T.docs[reader.doc]
      if reader.page < #d.pages then reader.page = reader.page + 1
      else reader = nil; snd("paper") end
    end
    return
  end
  if btn == 1 and not widget and ui.goals_click(x, y) then
    snd("ui_click"); return       -- тоггл плашки целей, клик не сквозит в сцену
  end
  if widget then
    if btn == 2 then ui.close_widget(); snd("zoom_out"); return end
    if widget.kind == "keypad" then keypad_click(x, y)
    elseif widget.kind == "pc" then pc_click(x, y)
    elseif widget.kind == "docs" then docs_click(x, y)
    elseif widget.kind == "form" then form_click(x, y) end
    return
  end
  -- HUD
  for _, b in ipairs(hud_buttons()) do
    if x >= b.x and x < b.x + b.w and y >= b.y and y < b.y + b.h then
      if b.id == "hint" then ui.hint()
      elseif b.id == "zones" then ui.zones_toggle()
      elseif b.id == "docs" then ui.open_widget("docs"); return  -- звук уже там
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
    -- (аудит С3) тот же порядок, что и у мыши: сперва верхний нарисованный слой
    if ui.dialog_active() then dlg_click()
    elseif reader then reader = nil
    elseif widget then ui.close_widget(); snd("zoom_out")
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
