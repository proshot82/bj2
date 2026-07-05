-- tools/fuzz_state.lua — фаззер ядра (luajit, headless)
-- 3 прогона × 25 000 случайных операций. Инварианты:
--   (а) ни одного исключения;
--   (б) serialize→deserialize→serialize идентичен;
--   (в) из любой достигнутой точки solve(400) добивает победу
--       (анти-софтлок), либо победа уже достигнута;
--   (г) фронтир не пуст до победы.
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

local node_ids = {}
for _, n in ipairs(P.nodes) do node_ids[#node_ids + 1] = n.id end
table.sort(node_ids)

local codes = {"0000", "1111", "9999", "1234", "0007", "2018", "2019"}
local depts = P.tokens.depts
local bench_ops = {"P+", "P-", "K1+", "K1-", "K2+", "K2-", "S+", "S-",
                   "PUMP", "RESET"}

local SEEDS = {20260101, 31337, 8675309}
local N = 25000

for run, seed in ipairs(SEEDS) do
  math.randomseed(seed)
  local st = State.new(P, items)
  local solve_checks, max_steps = 0, 0
  for i = 1, N do
    local r = math.random(100)
    local ok, e = pcall(function()
      if r <= 55 then
        st:fire(node_ids[math.random(#node_ids)])
      elseif r <= 70 then
        local nid = node_ids[math.random(#node_ids)]
        local n
        for _, x in ipairs(P.nodes) do if x.id == nid then n = x end end
        if n and n.lock and n.lock.kind == "code" then
          if math.random(4) == 1 then
            st:try_code(nid, tostring(P.answers[n.lock.id]))
          else
            st:try_code(nid, codes[math.random(#codes)])
          end
        end
      elseif r <= 80 then
        if math.random(5) == 1 then
          st:try_form(tostring(P.answers.skud.card_number),
                      P.answers.skud.dept)
        else
          st:try_form(tostring(math.random(0, 999999)),
                      depts[math.random(#depts)])
        end
      elseif r <= 92 then
        st:bench_op(bench_ops[math.random(#bench_ops)])
      else
        -- round-trip (канонизированное сравнение)
        local s1 = json.encode(st:serialize())
        local st2 = State.new(P, items)
        st2:deserialize(json.decode(s1))
        local s2 = json.encode(st2:serialize())
        assert(s1 == s2, "round-trip mismatch")
      end
    end)
    if not ok then
      io.stderr:write(("FUZZ FAIL run=%d i=%d: %s\n"):format(run, i, e))
      os.exit(1)
    end
    if st.steps > max_steps then max_steps = st.steps end
    if i % 500 == 0 and not st.flags.victory then
      local snap = json.decode(json.encode(st:serialize()))
      local probe = State.new(P, items)
      probe:deserialize(snap)
      local sok, res = probe:solve(400)
      if not sok then
        io.stderr:write(("FUZZ SOFTLOCK run=%d i=%d: %s\n")
          :format(run, i, tostring(res)))
        io.stderr:write(snap:sub(1, 400) .. "\n")
        os.exit(1)
      end
      solve_checks = solve_checks + 1
      local avail = probe:available()
      assert(#avail > 0 or probe.flags.victory, "пустой фронтир без победы")
    end
  end
  print(("run %d: %d ops, victory=%s, solve-checks=%d, steps=%d")
    :format(run, N, tostring(st.flags.victory ~= nil and
            (st.flags.victory and true or false)), solve_checks, st.steps))
end
print("FUZZ PASS")
