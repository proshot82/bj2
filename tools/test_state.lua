-- headless-тест ядра: солвер до победы, round-trip сериализации
package.path = "src/?.lua;src/core/?.lua;" .. package.path
local json = require("json")
local State = require("state")

local function readfile(p)
  local f = assert(io.open(p, "rb")); local s = f:read("*a"); f:close(); return s
end
local P = json.decode(readfile("design/puzzles.json"))
local T = json.decode(readfile("design/texts.json"))
local items = {}
for k in pairs(T.item_names) do items[#items+1] = k end

-- 1) солвер
local st = State.new(P, items)
local ok, steps = st:solve(300)
assert(ok, "solver failed: " .. tostring(steps))
print("solver: victory in " .. steps .. " steps")
assert(st.flags.victory, "no victory flag")

-- 2) негативы на свежем состоянии
local s2 = State.new(P, items)
assert(select(2, s2:fire("take_handle")) == "needs", "neg needs")
assert(select(2, s2:try_code("pc_unlock", "0000")) == "badcode" or
       tostring(P.answers.pc_pin) == "0000", "neg badcode")
do
  s2.flags.wheel_on = true
  local first
  for _, m in ipairs(P.answers.bench_seq) do
    if not m:match("^PUMP") then first = m; break end
  end
  local flipped = first:gsub("[+%-]$", function(c)
    return c == "+" and "-" or "+"
  end)
  assert(s2:bench_op(flipped) == "seq_bad", "bench wrong direction -> reset")
  assert(#s2.bench.seq == 0, "bench seq cleared")
end
print("negatives: ok")

-- 3) round-trip
local mid = State.new(P, items)
mid:fire("survey_door"); mid:fire("take_ruler"); mid:fire("pry_drawer")
mid:fire("take_handle")
local blob = json.encode(mid:serialize())
local re = State.new(P, items)
re:deserialize(json.decode(blob))
assert(json.encode(re:serialize()) == blob, "roundtrip mismatch")
local ok2 = re:solve(300)
assert(ok2, "resume solve failed")
print("roundtrip+resume: ok")
print("STATE CORE PASS")
