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
# автор отказался от мата (ред. 2.0.4): мат не обязателен, нижняя граница снята
if share > 35: err(f"мат-доля {share:.0f}% > 35")

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

# 11a) show/hide: голые токены — только флаги; предметы через item:
flags_set = set()
for n in P["nodes"]:
    for g in n["gives"]:
        if g not in set(T["item_names"]): flags_set.add(g)
for vid, h in spots:
    for k in ("show_on", "hide_on"):
        for f in h.get(k) or []:
            if ":" not in f:
                if f in set(T["item_names"]):
                    err(f"{vid}/{h['id']}: {k} «{f}» — предмет, нужен item:{f}")
                elif f not in flags_set:
                    err(f"{vid}/{h['id']}: {k} «{f}» — неизвестный флаг")

# 11b) consumes — только предметы; у каждого предмета есть иконка
items_set = set(T["item_names"].keys())
for n in P["nodes"]:
    for c in n.get("consumes", []):
        if c not in items_set:
            err(f"{n['id']}: consumes «{c}» вне item_names")
for iid in items_set:
    need_file("icons/ic_" + iid.replace("relic_", "") + ".png",
              "иконка " + iid)

# 12) hit-тени: центр интерактивного хотспота не перехватывается более
# приоритетным (модель движка: интерактивные < look, мельче < крупнее)
def interactive(h):
    return bool(h.get("node") or h.get("goto") or h.get("goto_room")
                or h.get("doc") or h.get("widget") or h.get("bench"))
def rect_mode(h, day):
    return (h.get("rect_day") or h["rect"]) if day else \
           (h.get("rect") or h["rect_day"])
def excl(a, b):
    sa, ha = set(a.get("show_on", [])), set(a.get("hide_on", []))
    sb, hb = set(b.get("show_on", [])), set(b.get("hide_on", []))
    return bool((sa & hb) or (sb & ha))
def prio(h, seq, day):
    r = rect_mode(h, day)
    if h.get("_arrow"): rank = 1
    elif interactive(h): rank = 0
    else: rank = 2
    return (rank, r[2] * r[3], seq)

by_view = {}
for vid, h in spots:
    by_view.setdefault(vid, []).append(h)
for rid, room in S["rooms"].items():
    for a in room.get("arrows", []):
        by_view[rid].append({"id": "arrow_" + a["dir"], "rect": a["rect"],
                             "goto_room": a["goto_room"], "_arrow": True})
for vid, hs in by_view.items():
    for day in (False, True):
        order = sorted(range(len(hs)), key=lambda i: prio(hs[i], i, day))
        for pos, i in enumerate(order):
            b = hs[i]
            if not interactive(b): continue
            rb = rect_mode(b, day)
            cx, cy = rb[0] + rb[2] / 2, rb[1] + rb[3] / 2
            for j in order[:pos]:
                a = hs[j]
                if excl(a, b): continue
                if a.get("goto_room") and a.get("goto_room") == b.get("goto_room"):
                    continue  # действие идентично — перехват безвреден
                ra = rect_mode(a, day)
                if ra[0] <= cx < ra[0] + ra[2] and ra[1] <= cy < ra[1] + ra[3]:
                    err(f"{vid}: центр {b['id']} перехвачен {a['id']}"
                        f" ({'день' if day else 'ночь'})")

print(f"хотспотов={len(spots)} катаутов={len(cutouts)} реплик={len(reps)} "
      f"мат={share:.0f}% доков={len(T['docs'])}")
if ERR:
    print("GATE2 FAIL:"); [print(" -", e) for e in ERR]; sys.exit(1)
print("GATE2 PASS")


# ---------- WARN: silhouette-отчёт по всем зонам (урок №1-2, LESSONS.md) ----------
def _warn_silhouettes():
    import numpy as _np
    from PIL import Image as _Im
    sc = json.load(open("design/scene.json", encoding="utf-8"))
    warns = []
    for room, arts in (("A", ("room_office_night.png", "room_office_day.png")),
                       ("B", ("room_utility_night.png", "room_utility_day.png"))):
        cuts = []
        for c in sc["rooms"][room]["cutouts"]:
            try:
                im = _Im.open("assets/gfx/" + c["img"]); s0 = c.get("scale", 1.0)
                cuts.append((c["pos"][0], c["pos"][1],
                             c["pos"][0] + im.width * s0, c["pos"][1] + im.height * s0))
            except Exception: pass
        for mode, art_name in (("night", arts[0]), ("day", arts[1])):
            a = _np.asarray(_Im.open("assets/gfx/rooms/" + art_name).convert("L"), float) / 255.0
            for h in sc["rooms"][room]["hotspots"]:
                r = h.get("rect_day") if (mode == "day" and h.get("rect_day")) else h["rect"]
                x0, y0, x1, y1 = r[0], r[1], min(r[0]+r[2],1920), min(r[1]+r[3],1080)
                if x1 <= x0 or y1 <= y0:
                    warns.append(f"{room}/{h['id']} ({mode}): зона вне канваса"); continue
                if any(not (x1 <= c0 or x0 >= c2 or y1 <= c1 or y0 >= c3)
                       for c0, c1, c2, c3 in cuts):
                    continue  # объект — катаут, на голом арте его нет
                z = a[y0:y1, x0:x1]
                p = 40
                rx0, ry0 = max(x0-p,0), max(y0-p,0)
                ring = a[ry0:min(y1+p,1080), rx0:min(x1+p,1920)].copy()
                ring[y0-ry0:y1-ry0, x0-rx0:x1-rx0] = _np.nan
                d = abs(float(_np.nanmean(ring)) - float(z.mean()))
                if d < 0.015 and float(z.std()) < 0.02:
                    warns.append(f"{room}/{h['id']} ({mode}): плоская зона (dL={d:.3f}, std={z.std():.3f})")
    if warns:
        print(f"[WARN] silhouette: подозрительных зон {len(warns)} (не гейт, глянуть verify-лист):")
        for w in warns[:12]: print("   -", w)
_warn_silhouettes()
