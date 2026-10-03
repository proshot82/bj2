-- tools/test_touch.lua — юнит-тест распознавателя касаний (р.25), без движка.
--
-- src/touch.lua переводит жест пальца в клики игры: тап = ЛКМ на отпускании,
-- удержание = ПКМ сразу по порогу, сдвиг — отмена. Гаунтлеты проверяют это
-- на живой игре (шаги r25_* и сенсорный прогон work/ap_touch.json), а здесь —
-- края, до которых сценарий не дотянется: дрожь пальца, потерянное
-- отпускание, отпускание далеко без событий сдвига, кольцо прогресса.
-- Время идёт кадрами по 1/60 с, как в движке.
-- Запуск из корня репозитория:  luajit tools/test_touch.lua
package.path = "src/?.lua;" .. package.path
local touch = require("touch")

local log, n, fails = {}, 0, 0
touch.init(function(x, y, b) log[#log + 1] = {x = x, y = y, b = b} end)

local function reset() for i = #log, 1, -1 do log[i] = nil end end
local function check(ok, name)
  n = n + 1
  if not ok then fails = fails + 1 end
  print((ok and "[OK  ] " or "[FAIL] ") .. name)
end
local function run(sec)                       -- кадры по 1/60 с
  local t = 0
  while t < sec - 1e-9 do
    local d = math.min(1 / 60, sec - t)
    touch.update(d); t = t + d
  end
end
local function only(b, x, y)                  -- ровно один клик этой кнопкой (и в этой точке)
  return #log == 1 and log[1].b == b and (x == nil or (log[1].x == x and log[1].y == y))
end

-- 1. короткий тап: ЛКМ на отпускании, в точке касания
reset(); touch.pressed(100, 200); run(0.1)
check(#log == 0, "тап: пока палец на экране — кликов нет")
touch.released(103, 202)
check(only(1, 100, 200), "тап → одна ЛКМ в точке касания")

-- 2. медленный тап (дольше обычного, но короче порога) — всё ещё ЛКМ
reset(); touch.pressed(10, 10); run(0.3); touch.released(10, 10)
check(only(1), "медленный тап 0,3 с → ЛКМ")

-- 3. удержание: ПКМ по порогу, пока палец лежит; отпускание ничего не добавляет
reset(); touch.pressed(50, 60); run(touch.HOLD - 0.03)
check(#log == 0, "до порога удержания — тишина")
run(0.05)
check(only(2, 50, 60), "удержание → ПКМ сразу по порогу, палец ещё на экране")
run(1.0)
check(#log == 1, "держать дольше — второго ПКМ нет")
touch.released(50, 60)
check(#log == 1, "отпускание после ПКМ — без лишней ЛКМ")

-- 4. палец уехал дальше SLOP — жест отменён целиком
reset(); touch.pressed(0, 0); touch.moved(touch.SLOP + 5, 0); run(1.0)
touch.released(touch.SLOP + 5, 0)
check(#log == 0, "сдвиг дальше SLOP → ни ЛКМ, ни ПКМ")

-- 5. дрожь в пределах SLOP не мешает ни тапу, ни удержанию
reset(); touch.pressed(0, 0); touch.moved(touch.SLOP - 3, 0); touch.released(touch.SLOP - 3, 0)
check(only(1, 0, 0), "дрожь пальца → тап")
reset(); touch.pressed(0, 0); touch.moved(0, touch.SLOP - 3); run(touch.HOLD + 0.05)
check(only(2, 0, 0), "дрожь пальца → удержание")
touch.released(0, 0)

-- 6. уехал и вернулся — всё равно отмена: жест уже был сдвигом
reset(); touch.pressed(0, 0); touch.moved(60, 0); touch.moved(0, 0); touch.released(0, 0)
check(#log == 0, "уехал и вернулся → отмена")

-- 7. отпускание далеко, а событий сдвига не было — не тап
reset(); touch.pressed(0, 0); touch.released(200, 0)
check(#log == 0, "отпускание далеко без сдвигов → отмена")

-- 8. отпускание без касания и сдвиг без касания — тишина
reset(); touch.released(5, 5); touch.moved(9, 9); run(1.0)
check(#log == 0, "отпускание/сдвиг без касания → тишина")

-- 9. касание поверх потерянного отпускания — считается новый жест
reset(); touch.pressed(1, 1); run(0.1); touch.pressed(300, 300); touch.released(300, 300)
check(only(1, 300, 300), "новое касание вместо потерянного → ЛКМ по новому")

-- 10. кольцо прогресса: не мигает на тапе, растёт, после ПКМ замкнуто до
-- отпускания; у отменённого сдвигом жеста кольца нет
reset(); touch.pressed(5, 7)
check(touch.ring() == nil, "кольцо не появляется сразу")
run(touch.RING_DELAY + 0.05)
local rx, ry, p = touch.ring()
check(rx == 5 and ry == 7 and p > 0 and p < 1, "кольцо растёт вокруг точки касания")
run(touch.HOLD)
local _, _, p2 = touch.ring()
check(p2 == 1, "после ПКМ кольцо замкнуто, пока палец на экране")
touch.released(5, 7)
check(touch.ring() == nil, "после отпускания кольца нет")
reset(); touch.pressed(0, 0); run(touch.RING_DELAY + 0.05); touch.moved(80, 0)
check(touch.ring() == nil, "жест отменён сдвигом — кольца нет")
touch.released(80, 0)

-- 11. чем вводит игрок — для подписей «касание»/«ЛКМ»
touch.mouse(); check(not touch.used(), "мышь/клавиатура → подписи для мыши")
touch.pressed(1, 1); check(touch.used(), "палец → подписи для касания")
touch.released(1, 1)

-- 12. пороги в «человеческом» коридоре: удержание около 0,45 с, допуск дрожи
-- заметно меньше пальца и заметно больше нуля
check(touch.HOLD >= 0.35 and touch.HOLD <= 0.6, "порог удержания ~0,45 с")
check(touch.SLOP >= 8 and touch.SLOP <= 32, "допуск сдвига 8..32 px")
check(touch.RING_DELAY < touch.HOLD, "кольцо успевает показаться до ПКМ")

if fails > 0 then
  print(("TOUCH TEST FAIL (%d из %d)"):format(fails, n))
  os.exit(1)
end
print(("TOUCH TEST PASS (%d проверок)"):format(n))
