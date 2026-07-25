-- Выгрузка трассы солвера: снапшот (flags/inv/done/read) после каждого узла.
package.path = package.path .. ";./?.lua"
local json = require("src.json")
local State = require("src.core.state")
-- (аудит С4) внятный отказ вместо «attempt to index a nil value»
local function die(msg)
  io.stderr:write("TRACE FAIL: " .. msg .. "\n")
  os.exit(1)
end
local function rf(p)
  local f = io.open(p, "rb")
  if not f then die("не читается " .. p .. " — запускать из корня репозитория") end
  local d = f:read("*a"); f:close(); return d
end
local P = json.decode(rf("design/puzzles.json"))
local T = json.decode(rf("design/texts.json"))
local items = {}
for k in pairs(T.item_names) do items[#items+1]=k end
local st = State.new(P, items)
local trace = {}
local function snap(nid)
  local s = st:serialize(); s.node = nid
  trace[#trace+1] = s
end
snap("<start>")
local guard = 0
while not st.flags.victory do
  guard = guard + 1
  if guard > 300 then io.stderr:write("stuck\n"); os.exit(1) end
  local av = st:available()
  if #av == 0 then io.stderr:write("no frontier\n"); os.exit(1) end
  local id = av[1]
  local n = st.nodes[id]
  if n.lock then
    if n.lock.kind == "keypad" then st:try_code(id, st.answers[n.lock.id])
    elseif n.lock.kind == "form" then
      st:try_form(st.answers.skud.card_number, st.answers.skud.dept)
    elseif n.lock.kind == "bench" then
      for _, op in ipairs(st:_vent_seq()) do st:bench_op(op) end
      for _ = 1, st.answers.bench_pumps do st:bench_op("PUMP") end
    end
  else
    st:fire(id)
  end
  snap(id)
end
-- (аудит С4) Каталог создаём сами и проверяем результат открытия. Раньше при
-- отсутствии work/ скрипт падал на «attempt to index a nil value (local 'f')»,
-- а следующий за ним clue_audit.py — питоновской трассировкой про ненайденный
-- файл. Два невнятных падения подряд вместо одной понятной строки.
local OUT = "work/solver_trace.json"
os.execute("mkdir -p work")
local f = io.open(OUT, "wb")
if not f then
  die("не открывается на запись " .. OUT ..
      " — нет каталога work/ или нет прав; запускать из корня репозитория")
end
local ok, werr = f:write(json.encode(trace))
if not ok then f:close(); die("не записался " .. OUT .. ": " .. tostring(werr)) end
f:close()
print("trace nodes:", #trace)
