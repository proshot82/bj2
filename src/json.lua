-- src/json.lua — минимальный JSON decode/encode (чистый Lua, без love.*)
local json = {}

-- (аудит К1) JSON null внутри МАССИВА несёт позицию: если положить nil,
-- элемент исчезает и все последующие сдвигаются влево (шестой рубильник
-- становился пятым). Поэтому в массивах null материализуется часовым
-- json.null. Внутри ОБЪЕКТА позиции нет, там null == отсутствие ключа,
-- и естественное представление — nil (сохраняем прежнее поведение:
-- 47 значений "lock": null в design/puzzles.json обязаны остаться nil).
json.null = setmetatable({}, {
  __tostring = function() return "json.null" end,
  __newindex = function() error("json.null неизменяем") end,
})

local function skip(s, i)
  while true do
    local c = s:sub(i, i)
    if c == " " or c == "\t" or c == "\n" or c == "\r" then i = i + 1
    else return i end
  end
end

local decode_value

local esc = {['"']='"', ['\\']='\\', ['/']='/', b='\b', f='\f', n='\n', r='\r', t='\t'}

local function decode_string(s, i)
  i = i + 1
  local out = {}
  while true do
    local c = s:sub(i, i)
    if c == "" then error("json: unterminated string") end
    if c == '"' then return table.concat(out), i + 1 end
    if c == "\\" then
      local e = s:sub(i + 1, i + 1)
      if e == "u" then
        local hex = s:sub(i + 2, i + 5)
        local cp = tonumber(hex, 16) or error("json: bad \\u")
        -- utf8 encode (BMP достаточно; суррогаты склеиваем)
        if cp >= 0xD800 and cp <= 0xDBFF then
          local hex2 = s:sub(i + 8, i + 11)
          local lo = tonumber(hex2, 16)
          cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
          i = i + 12
        else i = i + 6 end
        if cp < 0x80 then out[#out+1] = string.char(cp)
        elseif cp < 0x800 then
          out[#out+1] = string.char(0xC0 + math.floor(cp/0x40), 0x80 + cp % 0x40)
        elseif cp < 0x10000 then
          out[#out+1] = string.char(0xE0 + math.floor(cp/0x1000),
            0x80 + math.floor(cp/0x40) % 0x40, 0x80 + cp % 0x40)
        else
          out[#out+1] = string.char(0xF0 + math.floor(cp/0x40000),
            0x80 + math.floor(cp/0x1000) % 0x40,
            0x80 + math.floor(cp/0x40) % 0x40, 0x80 + cp % 0x40)
        end
      else
        out[#out+1] = esc[e] or error("json: bad escape " .. tostring(e))
        i = i + 2
      end
    else
      out[#out+1] = c; i = i + 1
    end
  end
end

local function decode_number(s, i)
  local j = i
  while s:sub(j, j):match("[%d%+%-%.eE]") do j = j + 1 end
  local n = tonumber(s:sub(i, j - 1)) or error("json: bad number")
  return n, j
end

decode_value = function(s, i)
  i = skip(s, i)
  local c = s:sub(i, i)
  if c == "{" then
    local obj = {}
    i = skip(s, i + 1)
    if s:sub(i, i) == "}" then return obj, i + 1 end
    while true do
      local k; k, i = decode_string(s, skip(s, i))
      i = skip(s, i)
      assert(s:sub(i, i) == ":", "json: expected :")
      local v; v, i = decode_value(s, i + 1)
      obj[k] = v
      i = skip(s, i); c = s:sub(i, i)
      if c == "," then i = i + 1
      elseif c == "}" then return obj, i + 1
      else error("json: expected , or }") end
    end
  elseif c == "[" then
    local arr = {}
    i = skip(s, i + 1)
    if s:sub(i, i) == "]" then return arr, i + 1 end
    local n = 0
    while true do
      local v; v, i = decode_value(s, i)
      n = n + 1
      if v == nil then v = json.null end   -- (аудит К1) позиция важна
      arr[n] = v
      i = skip(s, i); c = s:sub(i, i)
      if c == "," then i = i + 1
      elseif c == "]" then return arr, i + 1
      else error("json: expected , or ]") end
    end
  elseif c == '"' then return decode_string(s, i)
  elseif s:sub(i, i + 3) == "true" then return true, i + 4
  elseif s:sub(i, i + 4) == "false" then return false, i + 5
  elseif s:sub(i, i + 3) == "null" then return nil, i + 4
  else return decode_number(s, i) end
end

function json.decode(s)
  local v = select(1, decode_value(s, 1))
  return v
end

local function enc(v, out)
  if v == json.null then out[#out+1] = "null"; return end   -- (аудит К1)
  local tv = type(v)
  if tv == "nil" then out[#out+1] = "null"
  elseif tv == "boolean" then out[#out+1] = tostring(v)
  elseif tv == "number" then
    if v == math.floor(v) and math.abs(v) < 2^52 then
      out[#out+1] = string.format("%d", v)
    else out[#out+1] = string.format("%.14g", v) end
  elseif tv == "string" then
    out[#out+1] = '"' .. v:gsub('[%z\1-\31\\"]', function(c)
      if c == '"' then return '\\"' elseif c == "\\" then return "\\\\"
      elseif c == "\n" then return "\\n" elseif c == "\r" then return "\\r"
      elseif c == "\t" then return "\\t"
      else return string.format("\\u%04x", c:byte()) end
    end) .. '"'
  elseif tv == "table" then
    local n = 0; local isarr = true
    for k in pairs(v) do
      n = n + 1
      if type(k) ~= "number" then isarr = false end
    end
    if isarr and n == #v then
      out[#out+1] = "["
      for i2 = 1, #v do
        if i2 > 1 then out[#out+1] = "," end
        enc(v[i2], out)
      end
      out[#out+1] = "]"
    else
      out[#out+1] = "{"
      local first = true
      local keys = {}
      for k in pairs(v) do keys[#keys+1] = tostring(k) end
      table.sort(keys)
      for _, k in ipairs(keys) do
        if not first then out[#out+1] = "," end
        first = false
        enc(k, out); out[#out+1] = ":"; enc(v[k], out)
      end
      out[#out+1] = "}"
    end
  else error("json: cannot encode " .. tv) end
end

function json.encode(v)
  local out = {}
  enc(v, out)
  return table.concat(out)
end

return json
