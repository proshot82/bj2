-- src/touch.lua — сенсорный ввод (р.25): распознаватель жестов касания.
--
-- Касание SDL присылает в love.mousepressed / love.mousereleased как ЛКМ с
-- istouch=true, сдвиг пальца — в love.mousemoved (проверено на love.js и в
-- Chromium: так приходит и тап, и удержание). Правой кнопки, наведения и
-- клавиатуры у пальца нет, поэтому жест переводится в клики игры:
--   короткое касание                       → ЛКМ, на отпускании;
--   удержание HOLD секунд без сдвига       → ПКМ, сразу по истечении, пока
--                                            палец ещё на экране (как
--                                            контекстное меню на телефоне);
--   палец уехал дальше SLOP                → жест отменён, кликов нет.
-- Клик уходит в точку, где палец КОСНУЛСЯ экрана, — в экранных координатах;
-- в мир их переводит main.lua тем же путём, что и мышь (letterbox).
-- Мышь сюда не попадает вовсе: main.lua разбирает istouch, и у мыши всё по-
-- прежнему — клик на нажатии, без задержек.
--
-- Модуль — чистый Lua (love.* только в touch.draw): его гоняет юнит-тест
-- tools/test_touch.lua под luajit, без движка.
local touch = {
  HOLD = 0.45,        -- с: удержание, которое считается правым кликом
  SLOP = 18,          -- px окна: сдвиг дальше — уже не тап и не удержание
  RING_DELAY = 0.2,   -- с: кольцо прогресса не мигает на обычном тапе
  RING_R = 46,        -- px окна: радиус кольца — шире подушечки пальца
}

local gest = nil       -- текущий жест: {x, y, t, done, fired}
local used = false     -- последний ввод — палец: подписи «касание» вместо «ЛКМ»
local emit = function() end

-- fn(x, y, btn): экранная точка и кнопка игры (1 = ЛКМ, 2 = ПКМ)
function touch.init(fn) emit = fn end

function touch.used() return used end
-- мышь или клавиатура: подписи снова для них (жест, если он идёт, не трогаем)
function touch.mouse() used = false end

local function far(g, x, y)
  local dx, dy = x - g.x, y - g.y
  return dx * dx + dy * dy > touch.SLOP * touch.SLOP
end

function touch.pressed(x, y)
  used = true
  gest = {x = x, y = y, t = 0, done = false}
end

function touch.moved(x, y)
  local g = gest
  if g and not g.done and far(g, x, y) then g.done = true end
end

function touch.released(x, y)
  local g = gest
  gest = nil
  if not g or g.done then return end
  -- палец уехал, а событий сдвига не было (их может и не быть) — тоже не тап
  if far(g, x, y) then return end
  emit(g.x, g.y, 1)
end

function touch.update(dt)
  local g = gest
  if not g or g.done then return end
  g.t = g.t + dt
  if g.t >= touch.HOLD then
    g.done, g.fired = true, true
    emit(g.x, g.y, 2)
  end
end

-- Кольцо прогресса удержания: экранная точка и доля 0..1, либо nil. После
-- срабатывания ПКМ кольцо замкнуто, пока палец на экране, — игрок видит, что
-- удержание засчитано; отменённый сдвигом жест кольца не рисует.
function touch.ring()
  local g = gest
  if not g then return nil end
  if g.fired then return g.x, g.y, 1 end
  if g.done or g.t < touch.RING_DELAY then return nil end
  return g.x, g.y, math.min(1, (g.t - touch.RING_DELAY) / (touch.HOLD - touch.RING_DELAY))
end

-- Рисуется в ЭКРАННЫХ координатах поверх всего: палец закрывает точку
-- касания, поэтому кольцо шире подушечки и не масштабируется с миром.
function touch.draw()
  local x, y, p = touch.ring()
  if not x then return end
  local lg = love.graphics
  lg.setLineWidth(6)
  lg.setColor(0, 0, 0, 0.45)
  lg.circle("line", x, y, touch.RING_R)
  if p > 0 then
    lg.setColor(0.72, 0.58, 0.34, 0.95)          -- латунь интерфейса (C.brass)
    lg.arc("line", "open", x, y, touch.RING_R, -math.pi / 2, -math.pi / 2 + 2 * math.pi * p)
  end
  lg.setLineWidth(1)
  lg.setColor(1, 1, 1, 1)
end

return touch
