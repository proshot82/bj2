-- tools/fuzz_state.lua — фаззер ядра (luajit, headless)
-- 3 прогона × 25 000 случайных операций.
--
-- Инварианты прогона:
--   (а) ни одного исключения;
--   (б) serialize→deserialize→serialize идентичен;
--   (в) из любой достигнутой точки solve(400) добивает победу (анти-софтлок);
--   (г) фронтир не пуст до победы;
--   (д) [р.17] ПОКРЫТИЕ: каждая ветка из REQUIRED реально отработала
--       из самого фаззера, а не из солвера внутри probe-копий.
--
-- Зачем (д) — находка К2. До р.17 ветка замков сравнивала n.lock.kind со
-- строкой "code", тогда как и в данных, и в ядре вид зовётся "keypad".
-- Условие не было истинным ни разу: try_code из фаззера не вызывался,
-- фаззируемое состояние не открыло ни одного замка за всю историю проекта,
-- и вся «запертая» половина графа не фаззировалась. Прогон при этом честно
-- печатал FUZZ PASS. Мёртвая ветка неотличима от рабочей, пока никто не
-- считает исходы, — поэтому счётчики и список REQUIRED теперь часть гейта,
-- а не отладочная роскошь.
--
-- Провенанс исходов разделён на два ведра. Солвер (state.lua:solve) сам
-- дёргает try_code/try_form/bench_op с ПРАВИЛЬНЫМИ ответами на probe-копиях
-- каждые 500 операций. Если считать всё в одну кучу, вызовы солвера
-- маскируют мёртвую ветку фаззера — именно так К2 и выглядела: try_code
-- вызывался 450 раз, все вызовы из солвера, все с исходом fired.
--
-- Спойлер-гигиена: наружу не печатается ни одно значение ответа — в таблице
-- покрытия только имена исходов, в дампе состояния при софтлоке bench.seq
-- заменяется на длину.
package.path = package.path .. ";./?.lua;./src/?.lua;./src/core/?.lua"
local json = require("src.json")
local State = require("src.core.state")

local function readfile(p)
  local f = assert(io.open(p, "rb")); local d = f:read("*a"); f:close(); return d
end

local P = json.decode(readfile("design/puzzles.json"))
local T = json.decode(readfile("design/texts.json"))
local items = {}
for k in pairs(T.item_names) do items[#items + 1] = k end
table.sort(items)

local node_ids, plain_ids = {}, {}
for _, n in ipairs(P.nodes) do
  node_ids[#node_ids + 1] = n.id
  if not n.lock then plain_ids[#plain_ids + 1] = n.id end
end
table.sort(node_ids)
table.sort(plain_ids)

-- ---------------------------------------------------------------- замки ----
-- Вид замка больше нигде не написан литералом в теле цикла: таблица ниже —
-- единственное место, где фаззер утверждает, что знает вид замка. Оба
-- рассогласования с данными ловятся до первой операции.
local KIND_METHOD = {keypad = "try_code", form = "try_form", bench = "bench_op"}

local LOCKS = {}
for k in pairs(KIND_METHOD) do LOCKS[k] = {} end
local seen_kind = {}
for _, n in ipairs(P.nodes) do
  if n.lock then
    local k = tostring(n.lock.kind)
    seen_kind[k] = true
    if not KIND_METHOD[k] then
      io.stderr:write(("FUZZ FAIL: вид замка %q есть в design/puzzles.json, " ..
        "но фаззер не умеет его дёргать — добавьте ветку\n"):format(k))
      os.exit(1)
    end
    LOCKS[k][#LOCKS[k] + 1] = n.id
  end
end
for k, meth in pairs(KIND_METHOD) do
  if not seen_kind[k] then
    io.stderr:write(("FUZZ FAIL: фаззер знает вид замка %q (метод %s), но " ..
      "узлов с таким lock.kind в данных нет — ветка мертва (находка К2)\n")
      :format(k, meth))
    os.exit(1)
  end
end

-- ------------------------------------------------------------- материал ----
local codes = {"0000", "1111", "9999", "1234", "0007", "2018", "2019"}
local depts = P.tokens.depts
local bench_ops = {"P+", "P-", "K1+", "K1-", "K2+", "K2-", "S+", "S-",
                   "PUMP", "RESET"}
local bench_junk = {"", "P", "P++", "PUMPP", "reset", "К1+", "ЖМИ", "S", "-"}
local degenerate = {"", " ", "-1", "0", "00000000000000000000", "абв", "1e3"}
local ghosts = {"нет_такого_узла", "", "pc_unlock ", "PC_UNLOCK", "0"}

-- Ответ на один символ мимо: максимально злой вход для строкового сравнения.
-- Значение живёт только внутри процесса и никуда не печатается.
local function near_miss(ans)
  ans = tostring(ans)
  if #ans == 0 then return "x" end
  local i = math.random(#ans)
  local c = ans:sub(i, i)
  local d = tonumber(c)
  local rep
  if d then rep = tostring((d + math.random(1, 9)) % 10)
  else rep = (c == "?") and "!" or "?" end
  return ans:sub(1, i - 1) .. rep .. ans:sub(i + 1)
end

-- Заведомо чужой отдел: если тянуть из общего списка, можно случайно попасть
-- в правильный и закрыть форму раньше, чем накопится статистика badcode.
local function other_dept(right)
  if #depts < 2 then return tostring(right) .. "?" end
  for _ = 1, 8 do
    local x = depts[math.random(#depts)]
    if x ~= right then return x end
  end
  return tostring(right) .. "?"
end

local function wrong_code(n)
  local r = math.random(10)
  if r <= 2 then return degenerate[math.random(#degenerate)] end
  if r <= 5 then return codes[math.random(#codes)] end
  if r <= 8 and n and n.lock then return near_miss(P.answers[n.lock.id]) end
  local len = (n and n.lock and tonumber(n.lock.len)) or 4
  if len < 1 or len > 24 then len = 4 end
  local s = {}
  for i = 1, len do s[i] = tostring(math.random(0, 9)) end
  return table.concat(s)
end

local node_by_id = {}
for _, n in ipairs(P.nodes) do node_by_id[n.id] = n end

-- Замки, которые ещё не открыты, предпочтительнее: иначе после первого же
-- удачного кода ветка вырождается в бесконечный «already».
local function pick_lock(st, kind)
  local pool = LOCKS[kind]
  if #pool == 0 then return nil end
  if math.random(4) > 1 then
    local fresh = {}
    for _, id in ipairs(pool) do
      if not st.done[id] then fresh[#fresh + 1] = id end
    end
    if #fresh > 0 then return fresh[math.random(#fresh)] end
    return nil          -- всё открыто: бросок уходит в негативную ветку
  end
  return pool[math.random(#pool)]
end

-- Стенд случайными вентилями не собирается никогда: шанс угадать порядок
-- из десяти операций — (1/10)^len. Без «умного» броска весь граф за
-- bench_solve остаётся не фаззированным, ровно как запертая половина при К2.
local function bench_smart(st)
  local need = st:_vent_seq()
  local idx = #st.bench.seq + 1
  if idx <= #need then return need[idx] end
  return "PUMP"
end

-- Даже «умного» хода мало: между двумя правильными нажатиями успевает
-- влезть случайный вентиль и сбросить прогресс, поэтому до р.17 стенд в
-- фаззируемом состоянии не собирался НИ РАЗУ (bench_op/solved жил только в
-- ведре солвера — на probe-копиях). Ветка-«игрок, знающий решение» проводит
-- всю последовательность подряд и открывает граф за стендом для фаззинга.
local function bench_burst(st)
  for _, op in ipairs(st:_vent_seq()) do st:bench_op(op) end
  for _ = 1, P.answers.bench_pumps do st:bench_op("PUMP") end
end

-- ------------------------------------------------------------ покрытие -----
local COV = {F = {}, S = {}}
local in_fuzz = false

local function hook(name, label)
  local orig = State[name]
  State[name] = function(self, ...)
    local r1, r2, r3 = orig(self, ...)
    local t = in_fuzz and COV.F or COV.S
    local key = name .. "/" .. tostring(label(r1, r2))
    t[key] = (t[key] or 0) + 1
    return r1, r2, r3
  end
end

local function second(_, b) return b end
local function first(a) return a end
hook("fire", second)
hook("try_code", second)
hook("try_form", second)
hook("bench_op", first)

-- Ветки, которые обязаны отработать ИЗ ФАЗЗЕРА в каждом прогоне.
-- Список закрыт: добавили ветку в цикл — добавьте сюда её исходы, иначе
-- мёртвый код снова проедет как PASS.
local REQUIRED = {
  "fire/fired", "fire/needs", "fire/already", "fire/locked", "fire/unknown",
  "try_code/fired", "try_code/badcode", "try_code/notlock",
  "try_code/already",
  "try_form/fired", "try_form/badcode", "try_form/already",
  "bench_op/seq_ok", "bench_op/seq_bad", "bench_op/seq_done",
  "bench_op/reset", "bench_op/pump", "bench_op/pump_futile",
  "bench_op/solved", "bench_op/already", "bench_op/no_wheel",
}

-- Исход "needs" у замка достижим только если у узла вообще есть needs.
-- Сейчас у клавиатурных их нет (код можно набирать сразу, брутфорс держит
-- размер кода), у формы СКУД — есть. Требование включается само, как только
-- дизайнер добавит needs: иначе новая ветка молча осталась бы не покрытой.
local function kind_has_needs(kind)
  for _, id in ipairs(LOCKS[kind]) do
    local n = node_by_id[id]
    if n and n.needs and #n.needs > 0 then return true end
  end
  return false
end
if kind_has_needs("keypad") then REQUIRED[#REQUIRED + 1] = "try_code/needs" end
if kind_has_needs("form") then REQUIRED[#REQUIRED + 1] = "try_form/needs" end

local function dump_cov(tag, t)
  local keys = {}
  for k in pairs(t) do keys[#keys + 1] = k end
  table.sort(keys)
  local parts = {}
  for _, k in ipairs(keys) do parts[#parts + 1] = ("%s=%d"):format(k, t[k]) end
  print(("  покрытие[%s]: %s"):format(tag, table.concat(parts, ", ")))
end

-- --------------------------------------------------------------- прогон ----
local SEEDS = {20260101, 31337, 8675309}
local N = 25000
local FAILED = false

for run, seed in ipairs(SEEDS) do
  math.randomseed(seed)
  COV.F, COV.S = {}, {}
  local st = State.new(P, items)
  local solve_checks, victories, total_steps = 0, 0, 0
  for i = 1, N do
    local r = math.random(100)
    in_fuzz = true
    local ok, e = pcall(function()
      if r <= 52 then
        if math.random(50) == 1 then
          st:fire(ghosts[math.random(#ghosts)])
        else
          st:fire(node_ids[math.random(#node_ids)])
        end
      elseif r <= 67 then
        local id = pick_lock(st, "keypad")
        if id then
          local n = node_by_id[id]
          -- правильный код редко: сравнение строк фаззируется только пока
          -- замок закрыт (после — can_fire отвечает already, не доходя до
          -- сравнения), так что открывать его сразу значит выбросить ветку
          if math.random(30) == 1 then
            st:try_code(id, tostring(P.answers[n.lock.id]))
          else
            st:try_code(id, wrong_code(n))
          end
        elseif math.random(4) == 1 then
          -- все клавиатурные открыты: четверть бросков — на идемпотентность
          local pool = LOCKS.keypad
          st:try_code(pool[math.random(#pool)], wrong_code(nil))
        else
          -- остальное не жжём на повторный already, а гоняем граф
          st:fire(node_ids[math.random(#node_ids)])
        end
      elseif r <= 70 then
        -- негатив: код в узел без замка и в несуществующий узел
        if math.random(2) == 1 and #plain_ids > 0 then
          st:try_code(plain_ids[math.random(#plain_ids)], "0000")
        else
          st:try_code(ghosts[math.random(#ghosts)], wrong_code(nil))
        end
      elseif r <= 80 then
        local a = P.answers.skud
        if math.random(30) == 1 then
          st:try_form(tostring(a.card_number), a.dept)
        else
          -- обе половины условия «номер И отдел» проверяются порознь
          local d = math.random(4)
          if d == 1 then
            st:try_form(tostring(a.card_number), other_dept(a.dept))
          elseif d == 2 then
            st:try_form(near_miss(a.card_number), a.dept)
          elseif d == 3 then
            st:try_form(degenerate[math.random(#degenerate)], a.dept)
          else
            st:try_form(tostring(math.random(0, 999999)), other_dept(a.dept))
          end
        end
      elseif r <= 92 then
        local d = math.random(12)
        if d == 1 and i > N / 4 then
          -- не раньше четверти прогона: иначе стенд собирается на первых
          -- операциях и частичные исходы (seq_bad, reset, pump_futile,
          -- no_wheel) не успевают отработать — их съедает ранний already
          bench_burst(st)
        elseif d <= 5 then
          st:bench_op(bench_smart(st))
        elseif d <= 7 then
          st:bench_op(bench_junk[math.random(#bench_junk)])
        else
          st:bench_op(bench_ops[math.random(#bench_ops)])
        end
      else
        -- round-trip (канонизированное сравнение)
        local s1 = json.encode(st:serialize())
        local st2 = State.new(P, items)
        st2:deserialize(json.decode(s1))
        local s2 = json.encode(st2:serialize())
        assert(s1 == s2, "round-trip mismatch")
      end
    end)
    in_fuzz = false
    if not ok then
      io.stderr:write(("FUZZ FAIL run=%d i=%d: %s\n"):format(run, i, e))
      os.exit(1)
    end
    if i % 500 == 0 and not st.flags.victory then
      local s1 = json.encode(st:serialize())
      local probe = State.new(P, items)
      probe:deserialize(json.decode(s1))
      local sok, res = probe:solve(400)
      if not sok then
        io.stderr:write(("FUZZ SOFTLOCK run=%d i=%d: %s\n")
          :format(run, i, tostring(res)))
        -- спойлер-гигиена: bench.seq — часть ответа, наружу идёт только длина
        local dump = st:serialize()
        dump.bench = {seq_len = #dump.bench.seq, pumps = dump.bench.pumps}
        io.stderr:write(json.encode(dump):sub(1, 600) .. "\n")
        os.exit(1)
      end
      solve_checks = solve_checks + 1
      local avail = probe:available()
      assert(#avail > 0 or probe.flags.victory, "пустой фронтир без победы")
    end
    -- После К2 фаззируемое состояние действительно доходит до победы (раньше
    -- оно застревало перед замками). Победившее состояние дальше неподвижно:
    -- can_fire отвечает already на всё, и остаток бюджета уходит в пустоту,
    -- а анти-софтлок-проверка перестаёт срабатывать. Поэтому — новая партия.
    if st.flags.victory then
      victories = victories + 1
      total_steps = total_steps + st.steps
      st = State.new(P, items)
    end
  end
  total_steps = total_steps + st.steps

  print(("run %d: %d ops, побед=%d, solve-checks=%d, шагов=%d")
    :format(run, N, victories, solve_checks, total_steps))
  dump_cov("фаззер", COV.F)
  dump_cov("солвер", COV.S)

  local missing = {}
  for _, k in ipairs(REQUIRED) do
    if not COV.F[k] then missing[#missing + 1] = k end
  end
  if #missing > 0 then
    table.sort(missing)
    io.stderr:write(("FUZZ COVERAGE FAIL run=%d: ветки фаззера не " ..
      "отработали: %s\n"):format(run, table.concat(missing, ", ")))
    FAILED = true
  end
  if victories < 1 then
    io.stderr:write(("FUZZ COVERAGE FAIL run=%d: фаззируемое состояние ни " ..
      "разу не дошло до победы — значит, кусок графа за замками не " ..
      "фаззируется вовсе (ровно симптом К2)\n"):format(run))
    FAILED = true
  end
end

if FAILED then os.exit(1) end
print("FUZZ PASS")
