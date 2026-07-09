-- src/core/state.lua — логическое ядро (без love.*). LuaJIT-совместимо.
local M = {}
M.__index = M

local function set_from(list)
  local s = {}
  for _, v in ipairs(list or {}) do s[v] = true end
  return s
end

function M.new(puzzles, item_ids)
  local self = setmetatable({}, M)
  self.P = puzzles
  self.answers = puzzles.answers
  self.nodes = {}
  self.order = {}
  for _, n in ipairs(puzzles.nodes) do
    self.nodes[n.id] = n
    self.order[#self.order + 1] = n.id
  end
  self.items_set = set_from(item_ids)   -- какие gives — предметы
  self.flags = {}      -- flag -> true
  self.inv = {}        -- item -> true (уникальные)
  self.inv_order = {}  -- порядок для UI
  self.done = {}       -- node -> true
  self.read = {}       -- doc -> true
  self.bench = {seq = {}, pumps = 0}
  self.steps = 0
  return self
end

-- ---------- предикаты ----------
function M:has_flag(f)
  if f:sub(1, 5) == "done:" then return self.done[f:sub(6)] == true end
  if f:sub(1, 5) == "item:" then return self.inv[f:sub(6)] == true end
  if f:sub(1, 5) == "read:" then return self.read[f:sub(6)] == true end
  return self.flags[f] == true
end

function M:need_ok(need)
  -- need: item или flag (в puzzles needs без префиксов)
  if self.items_set[need] then return self.inv[need] == true end
  return self.flags[need] == true
end

-- список требований-ПРЕДМЕТОВ узла (механика «использовать предмет на объект»,
-- раунд 4): возвращает те needs, что являются предметами инвентаря.
function M:item_needs(id)
  local n = self.nodes[id]
  local out = {}
  if not n then return out end
  for _, need in ipairs(n.needs) do
    if self.items_set[need] then out[#out + 1] = need end
  end
  return out
end

function M:can_fire(id)
  local n = self.nodes[id]
  if not n then return false, "unknown" end
  if self.done[id] and n.type ~= "herring" and n.type ~= "win" then
    return false, "already"
  end
  if self.done[id] and n.type == "win" then return false, "already" end
  for _, need in ipairs(n.needs) do
    if not self:need_ok(need) then return false, "needs" end
  end
  return true, "ok"
end

function M:give(g)
  if self.items_set[g] then
    if not self.inv[g] then
      self.inv[g] = true
      self.inv_order[#self.inv_order + 1] = g
    end
  else
    self.flags[g] = true
  end
end

function M:consume(c)
  if self.inv[c] then
    self.inv[c] = nil
    for i, v in ipairs(self.inv_order) do
      if v == c then table.remove(self.inv_order, i); break end
    end
  else
    self.flags[c] = nil
  end
end

-- fire: выполняет узел (замки должны идти через try_code/try_form/bench_*)
function M:fire(id)
  local ok, why = self:can_fire(id)
  if not ok then return false, why end
  local n = self.nodes[id]
  if n.lock and not self._lock_bypass then return false, "locked" end
  for _, c in ipairs(n.consumes) do self:consume(c) end
  for _, g in ipairs(n.gives) do self:give(g) end
  self.done[id] = true
  self.steps = self.steps + 1
  return true, "fired"
end

-- ---------- замки ----------
function M:try_code(id, code)
  local n = self.nodes[id]
  if not (n and n.lock and n.lock.kind == "keypad") then return false, "notlock" end
  local ok, why = self:can_fire(id)
  if not ok then return false, why end
  if tostring(code) ~= tostring(self.answers[n.lock.id]) then
    self.steps = self.steps + 1
    return false, "badcode"
  end
  self._lock_bypass = true
  local r = select(1, self:fire(id))
  self._lock_bypass = nil
  return r, r and "fired" or "err"
end

function M:try_form(no, dept)
  local id = "skud_form"
  local ok, why = self:can_fire(id)
  if not ok then return false, why end
  local a = self.answers.skud
  if tostring(no) ~= tostring(a.card_number) or dept ~= a.dept then
    self.steps = self.steps + 1
    return false, "badcode"
  end
  self._lock_bypass = true
  local r = select(1, self:fire(id))
  self._lock_bypass = nil
  return r, r and "fired" or "err"
end

-- ---------- стенд ----------
-- ops: "P","K1","K2","S" (перекладка вентиля), "PUMP", "RESET"
function M:_vent_seq()
  if not self._vents then
    self._vents = {}
    for _, m in ipairs(self.answers.bench_seq) do
      if not m:match("^PUMP") then self._vents[#self._vents + 1] = m end
    end
  end
  return self._vents
end

-- Правило: вентили в порядке answers.bench_seq; ошибка -> сброс seq.
-- После полной последовательности PUMP x bench_pumps -> solved.
function M:bench_op(op)
  if self.done.bench_solve then return "already" end
  if not self.flags.wheel_on and op:match("^P[+%-]") then return "no_wheel" end
  if not self.flags.wheel_on then
    -- без маховика на П последовательность не собрать, но крутить можно
    if op == "RESET" then self.bench.seq = {}; self.bench.pumps = 0; return "reset" end
  end
  local need = self:_vent_seq()                  -- вентильные ходы
  local pumps_need = self.answers.bench_pumps
  self.steps = self.steps + 1
  if op == "RESET" then
    self.bench.seq = {}; self.bench.pumps = 0
    return "reset"
  end
  if op == "PUMP" then
    if #self.bench.seq == #need then
      self.bench.pumps = self.bench.pumps + 1
      if self.bench.pumps >= pumps_need then
        self._lock_bypass = true
        self:fire("bench_solve")
        self._lock_bypass = nil
        return "solved"
      end
      return "pump", self.bench.pumps, pumps_need
    else
      -- качать рано: давление уходит
      self.bench.pumps = 0
      return "pump_futile"
    end
  end
  -- вентиль
  local idx = #self.bench.seq + 1
  if need[idx] == op then
    self.bench.seq[idx] = op
    if #self.bench.seq == #need then return "seq_done" end
    return "seq_ok", idx, #need
  else
    self.bench.seq = {}; self.bench.pumps = 0
    return "seq_bad"
  end
end

function M:gauge_frac()
  local need = self:_vent_seq()
  local pn = self.answers.bench_pumps
  if self.done.bench_solve then return 1 end
  if #self.bench.seq < #need then return 0.06 * #self.bench.seq end
  return 0.25 + 0.75 * math.min(1, self.bench.pumps / pn)
end

-- ---------- сериализация ----------
local function keys_sorted(t)
  local ks = {}
  for k in pairs(t) do ks[#ks + 1] = k end
  table.sort(ks)
  return ks
end

function M:serialize()
  local s = {flags = {}, inv = {}, done = {}, read = {},
             bench = {seq = {}, pumps = self.bench.pumps},
             steps = self.steps}
  for _, k in ipairs(keys_sorted(self.flags)) do s.flags[#s.flags + 1] = k end
  for _, k in ipairs(self.inv_order) do s.inv[#s.inv + 1] = k end
  for _, k in ipairs(keys_sorted(self.done)) do s.done[#s.done + 1] = k end
  for _, k in ipairs(keys_sorted(self.read)) do s.read[#s.read + 1] = k end
  for i, v in ipairs(self.bench.seq) do s.bench.seq[i] = v end
  return s
end

function M:deserialize(s)
  self.flags, self.inv, self.inv_order, self.done, self.read =
    {}, {}, {}, {}, {}
  for _, k in ipairs(s.flags or {}) do self.flags[k] = true end
  for _, k in ipairs(s.inv or {}) do
    self.inv[k] = true; self.inv_order[#self.inv_order + 1] = k
  end
  for _, k in ipairs(s.done or {}) do self.done[k] = true end
  for _, k in ipairs(s.read or {}) do self.read[k] = true end
  self.bench = {seq = {}, pumps = (s.bench and s.bench.pumps) or 0}
  for i, v in ipairs((s.bench and s.bench.seq) or {}) do self.bench.seq[i] = v end
  self.steps = s.steps or 0
end

-- ---------- доступность и солвер ----------
function M:available()
  local out = {}
  for _, id in ipairs(self.order) do
    local n = self.nodes[id]
    if not n.herring and not self.done[id] then
      local ok = select(1, self:can_fire(id))
      if ok then out[#out + 1] = id end
    end
  end
  return out
end

function M:solve(max_steps)
  max_steps = max_steps or 300
  local guard = 0
  while not self.flags.victory do
    guard = guard + 1
    if guard > max_steps then return false, "budget" end
    local av = self:available()
    if #av == 0 then return false, "stuck" end
    local id = av[1]
    local n = self.nodes[id]
    if n.lock then
      if n.lock.kind == "keypad" then
        self:try_code(id, self.answers[n.lock.id])
      elseif n.lock.kind == "form" then
        self:try_form(self.answers.skud.card_number, self.answers.skud.dept)
      elseif n.lock.kind == "bench" then
        for _, op in ipairs(self:_vent_seq()) do self:bench_op(op) end
        for _ = 1, self.answers.bench_pumps do self:bench_op("PUMP") end
      end
    else
      self:fire(id)
    end
  end
  return true, self.steps
end

return M
