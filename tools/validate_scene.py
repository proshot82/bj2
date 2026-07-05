#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE2: согласованность design/scene.json + design/texts.json с
design/puzzles.json и файлами ассетов. rc=0 — PASS."""
import json, os, re, sys

ERR = []
def err(m): ERR.append(m)

P = json.load(open("design/puzzles.json"))
S = json.load(open("design/scene.json"))
T = json.load(open("design/texts.json"))

node_ids = {n["id"] for n in P["nodes"]}
doc_ids = {d["id"] for d in P["docs"]}
gives = {g for n in P["nodes"] for g in n["gives"]}
item_like = set(T["item_names"].keys())
VIRTUAL = {"bench_move_P", "bench_move_K1", "bench_move_K2", "bench_move_S",
           "bench_pump", "bench_reset"}
ENGINE_FLAGS = {"victory"}
LEGAL_FLAG = re.compile(r"^(done:[a-z_]+|item:[a-z_]+|read:doc_[a-z_]+|[a-z_]+)$")

def flag_ok(f):
    if f.startswith("done:"): return f[5:] in node_ids
    if f.startswith("item:"): return f[5:] in item_like
    if f.startswith("read:"): return f[5:] in doc_ids
    return f in gives or f in ENGINE_FLAGS

# ---------- обход хотспотов/катаутов ----------
spots = []          # (where, hs)
cutouts = []        # (where, co)
for rid, room in S["rooms"].items():
    for h in room["hotspots"]: spots.append((rid, h))
    for c in room["cutouts"]: cutouts.append((rid, c))
    for a in room.get("arrows", []):
        if "needs_flag" in a and not flag_ok(a["needs_flag"]):
            err(f"arrow {rid}: bad flag {a['needs_flag']}")
for zid, z in S["zooms"].items():
    for h in z["hotspots"]: spots.append((zid, h))
    for c in z["cutouts"]: cutouts.append((zid, c))
    if "needs_flag" in z and not flag_ok(z["needs_flag"]):
        err(f"zoom {zid}: bad flag {z['needs_flag']}")

# 1) геометрия ≥44px
for w, h in spots:
    for key in ("rect", "rect_day"):
        r = h.get(key)
        if r and min(r[2], r[3]) < 44:
            err(f"{w}/{h['id']}: {key} min side {min(r[2],r[3])} < 44")

# 2) файлы существуют
def need_file(rel, ctx):
    if not os.path.exists("assets/gfx/" + rel):
        err(f"{ctx}: файла нет assets/gfx/{rel}")
for rid, room in S["rooms"].items():
    for k in ("night", "day"): need_file(room["bg"][k], f"bg {rid}")
for zid, z in S["zooms"].items(): need_file(z["bg"], f"bg {zid}")
for w, c in cutouts:
    need_file(c["img"], f"cutout {w}")
    for fr in c.get("frames", []): need_file(fr, f"frames {w}")
need_file(S["fx"]["util_handle"], "fx")

# 3) покрытие узлов
covered = {h.get("node") for _, h in spots if h.get("node")}
for _, h in spots:
    covered |= set(h.get("also_nodes", []))
    covered |= {x for x in h.get("breaker_map", []) if x}
missing_nodes = (node_ids - covered) - {"combine_longnet", "combine_trikey",
                                        "combine_calm", "bench_solve"}
if missing_nodes: err(f"узлы без точки: {sorted(missing_nodes)}")
bench_virtual_missing = VIRTUAL - covered
if bench_virtual_missing: err(f"нет bench-виртуалов: {sorted(bench_virtual_missing)}")
unknown = covered - node_ids - VIRTUAL
if unknown: err(f"хотспоты ссылаются на неизвестные узлы: {sorted(unknown)}")

# 4) покрытие доков
doc_pts = {h.get("doc") for _, h in spots if h.get("doc")}
doc_pts |= {h.get("doc_rmb") for _, h in spots if h.get("doc_rmb")}
doc_pts |= set(S.get("doc_items", {}).keys())
doc_pts |= set(S.get("doc_auto", {}).values())
for _, h in spots: doc_pts |= set(h.get("pc_docs", []))
missing_docs = doc_ids - doc_pts
if missing_docs: err(f"доки без точки: {sorted(missing_docs)}")
if len(P["docs"]) != 17: err(f"доков в puzzles {len(P['docs'])} != 17")
if set(T["docs"].keys()) != doc_ids:
    err(f"texts.docs != puzzles.docs: {set(T['docs'])^doc_ids}")

# 5) reachability зумов
reach = set()
for rid, room in S["rooms"].items():
    for h in room["hotspots"]:
        if h.get("goto"): reach.add(h["goto"])
for zid, z in S["zooms"].items():
    for h in z["hotspots"]:
        if h.get("goto"): reach.add(h["goto"])
unreach = set(S["zooms"].keys()) - reach
if unreach: err(f"недостижимые зумы: {sorted(unreach)}")

# 6) флаги show/hide/needs
for w, obj in spots + cutouts:
    for key in ("show_on", "hide_on"):
        for f in obj.get(key, []):
            if not LEGAL_FLAG.match(f) or not flag_ok(f):
                err(f"{w}/{obj.get('id', obj.get('img'))}: bad flag '{f}' in {key}")
    nf = obj.get("needs_flag")
    if nf and not flag_ok(nf):
        err(f"{w}/{obj.get('id','?')}: bad needs_flag {nf}")

# 7) реплики: спикер-линт + мат-линт
reps = []
def walk(x):
    if isinstance(x, dict):
        if {"s", "e", "t"} <= set(x.keys()): reps.append(x)
        else:
            for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
walk(T)
EMO = {"lap": {"neutral","tired","panic","inspired","smug","triumphant",
               "worried","angry"},
       "anc": {"calm","proud","stern","smug"}}
for r in reps:
    if r["s"] not in EMO: err(f"спикер? {r}")
    elif r["e"] not in EMO[r["s"]]: err(f"эмоция {r['s']}/{r['e']}: {r['t'][:30]}")
    if not r["t"].strip(): err(f"пустая реплика {r}")
    port = f"assets/gfx/portraits/port_{r['s']}_{r['e']}.png"
    if not os.path.exists(port): err(f"нет портрета {port}")
if len(reps) < 300: err(f"реплик {len(reps)} < 300")
MAT = re.compile(r"(хуй|хуе|хуё|хул|пизд|бляд|бля\b|еба|ебал|ебан|ёб|заеб|наеб|"
                 r"съеб|проеб|сука|суки|мудак|мудач|мудил|говн|жоп|хер\b|"
                 r"долбо|дроч|ссык|падл|ирод|нахуй|похуй|ёпт|ёпта|хуежд)", re.I)
nm = sum(1 for r in reps if MAT.search(r["t"]))
share = 100.0 * nm / len(reps)
if not (15 <= share <= 35): err(f"мат-доля {share:.0f}% вне [15;35]")

# 8) токены доков
TOKS = set(P["tokens"].keys())
ANS_OK = {"bench_printed_ru", "bench_seq_ru", "bench_fix_ru"}
SPECIAL = {"PIN_GLYPHS", "LEGEND", "CAL"}
pat = re.compile(r"\{(TOK|ANS):([a-z_]+)\}|\{([A-Z_]+)\}")
for did, d in T["docs"].items():
    if not d.get("title"): err(f"{did}: нет title")
    for pg in d["pages"]:
        for line in pg:
            for m in pat.finditer(line):
                kind, key, spec = m.group(1), m.group(2), m.group(3)
                if kind == "TOK" and key not in TOKS:
                    err(f"{did}: неизвестный TOK {key}")
                if kind == "ANS" and key not in ANS_OK:
                    err(f"{did}: недопустимый ANS {key}")
                if spec and spec not in SPECIAL:
                    err(f"{did}: неизвестный спец-токен {spec}")
    hw = d.get("handwritten", [])
    flat = max(len(pg) for pg in d["pages"])
    if any(i >= flat for i in hw): err(f"{did}: handwritten index вне страницы")

# {TOK:} в item_desc
for iid, r in T["item_desc"].items():
    for m in pat.finditer(r["t"]):
        if m.group(1) == "TOK" and m.group(2) not in TOKS:
            err(f"item_desc {iid}: TOK {m.group(2)}")

# 9) подсказки: 3 тира на тему
for tid, tier in T["hints"]["topics"].items():
    if len(tier) != 3: err(f"hint {tid}: тиров {len(tier)} != 3")

# 10) looks ссылаются на существующие хотспоты
hs_ids = {h["id"] for _, h in spots}
for lid in T["looks"]:
    if lid not in hs_ids: err(f"looks: нет хотспота {lid}")
look_flagged = {h["id"] for _, h in spots if h.get("look")}
no_look_text = look_flagged - set(T["looks"].keys())
if no_look_text: err(f"look-хотспоты без текста: {sorted(no_look_text)}")

# 11) клюи замков достижимы (клю-док имеет точку) — маскированно
for n in P["nodes"]:
    lk = n.get("lock")
    if lk:
        for c in lk["clue_sources"]:
            if c not in doc_ids: err(f"{n['id']}: клю не док: {c}")

print(f"хотспотов={len(spots)} катаутов={len(cutouts)} реплик={len(reps)} "
      f"мат={share:.0f}% доков={len(T['docs'])}")
if ERR:
    print("GATE2 FAIL:"); [print(" -", e) for e in ERR]; sys.exit(1)
print("GATE2 PASS")
