-- «Латунный янычар 2.0» — Фаза 0: заглушка селфтеста окна.
-- Полный движок появится в Фазе 3; этот файл проверяет, что LÖVE 11.5
-- поднимает GL-контекст под xvfb и штатно завершается с кодом 0.
local args = love.arg.parseGameArguments(arg)
local SELFTEST = false
for _, a in ipairs(args) do if a == "--selftest" then SELFTEST = true end end

local frame = 0
function love.draw()
  love.graphics.clear(0.08, 0.09, 0.12)
  love.graphics.print("BJ2 Phase 0 stub :: " .. love.getVersion(), 40, 40)
  frame = frame + 1
  if SELFTEST and frame >= 3 then
    print("PHASE0_SELFTEST_OK")
    love.event.quit(0)
  end
end
