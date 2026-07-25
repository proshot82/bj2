#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Маскированный clue-аудит (Фаза 5). Значения ответов не печатаются.

1) У каждого замка (code/form/bench) ≥ 2 независимых clue-источника.
2) По трассе золотого пути: каждый док-улика становится ДОСТУПЕН строго
   раньше шага, на котором солвер проходит соответствующий замок.
   Доступность дока в состоянии: видима точка чтения (hs.doc / doc_rmb /
   reader_note / pc_docs / doc_items / doc_auto) с учётом show/hide-флагов
   точки, флага зума и открытости пути в комнату B.
"""
import json, sys

P = json.load(open("design/puzzles.json", encoding="utf-8"))
S = json.load(open("design/scene.json", encoding="utf-8"))
ERR = []
def err(m): ERR.append(m)

# ---------- 1) ≥2 источника ----------
locks = [(n["id"], n["lock"]) for n in P["nodes"] if n.get("lock")]
for nid, lk in locks:
    srcs = lk.get("clue_sources", [])
    if len(srcs) < 2:
        err(f"{nid}: {len(srcs)} clue-источник(ов) < 2")
print(f"[1] замков: {len(locks)}, все с ≥2 источниками: "
      f"{'да' if not ERR else 'НЕТ'}")

# ---------- 2) доступность по трассе ----------
# (аудит С4) Внятная диагностика вместо питоновской трассировки: трассу пишет
# tools/trace_solver.lua, и «файла нет» здесь означает ровно одно — солвер не
# отработал. Сообщать об этом надо словами, а не стеком вызовов json.
TRACE = "work/solver_trace.json"
try:
    with open(TRACE, encoding="utf-8") as fh:
        trace = json.load(fh)
except FileNotFoundError:
    sys.exit(f"CLUE FAIL: нет {TRACE} — сперва прогнать трассу солвера "
             f"(love/luajit tools/trace_solver.lua) из корня репозитория")
except json.JSONDecodeError as e:
    sys.exit(f"CLUE FAIL: {TRACE} не разбирается как JSON ({e}) — "
             f"трасса оборвана, перегенерировать")
if not isinstance(trace, list) or not trace:
    sys.exit(f"CLUE FAIL: {TRACE} пуст или не список — мерить доступность не по чему")

def state_of(step):
    s = trace[step]
    return set(s.get("flags", [])), set(s.get("inv", [])), \
           set(s.get("done", [])), set(s.get("read", []))

def flag_ok(f, flags, inv, done):
    if f.startswith("done:"): return f[5:] in done
    if f.startswith("item:"): return f[5:] in inv
    if f.startswith("read:"): return False  # чтение вне ядра: консервативно
    return f in flags

def spot_visible(h, flags, inv, done):
    for f in h.get("show_on", []) or []:
        if not flag_ok(f, flags, inv, done): return False
    for f in h.get("hide_on", []) or []:
        if flag_ok(f, flags, inv, done): return False
    return True

def room_reachable(rid, flags):
    return True if rid == "A" else ("utility_open" in flags)

def zoom_reachable(zid, flags, inv, done):
    z = S["zooms"][zid]
    if not room_reachable(z["room"], flags): return False
    nf = z.get("needs_flag")
    if nf and not flag_ok(nf, flags, inv, done): return False
    return True

doc_items = S.get("doc_items", {})          # doc -> item
doc_auto = S.get("doc_auto", {})            # node -> doc

def doc_accessible(doc, step):
    flags, inv, done, read = state_of(step)
    if doc in read: return True
    # авто-доки: узел сделан
    for node, d in doc_auto.items():
        if d == doc and node in done: return True
    # предметные доки: предмет в инвентаре
    for d, item in doc_items.items():
        if d == doc and item in inv: return True
    # точки чтения в комнатах/зумах
    for rid, room in S["rooms"].items():
        if not room_reachable(rid, flags): continue
        for h in room["hotspots"]:
            if doc in (h.get("doc"), h.get("doc_rmb"), h.get("reader_note")):
                if spot_visible(h, flags, inv, done): return True
    for zid, z in S["zooms"].items():
        if not zoom_reachable(zid, flags, inv, done): continue
        for h in z["hotspots"]:
            if doc in (h.get("doc"), h.get("doc_rmb"), h.get("reader_note")):
                if spot_visible(h, flags, inv, done): return True
            if doc in (h.get("pc_docs") or []):
                if "pc_on" in flags: return True
    return False

order = [t["node"] for t in trace]
for nid, lk in locks:
    if nid not in order:
        err(f"{nid}: замок не встретился в золотом пути"); continue
    k = order.index(nid)  # снапшот ПОСЛЕ прохождения; доступ нужен до k
    for doc in lk.get("clue_sources", []):
        first = None
        for j in range(0, k):
            if doc_accessible(doc, j):
                first = j; break
        if first is None:
            err(f"{nid}: улика «{doc}» недоступна до шага {k}")
        else:
            print(f"[2] {nid}: улика «{doc}» доступна с шага {first} "
                  f"(замок на шаге {k})")

if ERR:
    print("CLUE AUDIT FAIL:")
    for e in ERR: print(" -", e)
    sys.exit(1)
print("CLUE AUDIT PASS")
