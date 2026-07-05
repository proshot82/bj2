#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_puzzles.py — GATE1 «Латунный янычар 2.0».
Проверки (все обязаны PASS):
  1. Граф ацикличен; победа достижима; все обязательные узлы достижимы.
  2. Never-blind: для каждого замка все clue_sources доступны в фикспойнте
     графа БЕЗ срабатывания самого замка; у каждого замка >=2 источника.
  3. Глубина главной цепи (длиннейший путь по обязательным узлам) >= 9.
  4. Одновременно открытых обязательных нитей: доля шагов с count>=3
     >= 60% прохождения; медиана в [3,4].
  5. Cross-room: каждая ветка D1-D5 содержит ребро A<->B (need или
     clue_source через комнаты) либо узел-стык с потребностями из A и B.
  6. Реликвии: 3 шт. + корона, все достижимы (опционально).
  7. Герринги >= 6.
  8. Узлов (без доков) в коридоре 48-52; обязательных 30-34.
Ответы замков в отчёт НЕ выводятся.
"""
import json, sys, os
from collections import deque, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PUZ = json.load(open(os.path.join(HERE, "..", "design", "puzzles.json"),
                     encoding="utf-8"))
NODES = {n["id"]: n for n in PUZ["nodes"]}
DOCS = {d["id"]: d for d in PUZ["docs"]}
FAIL = []
INFO = []

def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    line = f"[{tag}] {name}" + (f" — {detail}" if detail else "")
    (INFO if cond else FAIL).append(line)
    print(line)

# --- карта: флаг/предмет -> кто его даёт
giver = defaultdict(list)
for n in PUZ["nodes"]:
    for g in n["gives"]:
        giver[g].append(n["id"])

def deps_of(n):
    """need-флаги узла -> id узлов-источников."""
    out = set()
    for need in n["needs"]:
        for src in giver.get(need, []):
            out.add(src)
    return out

# --- 1. ацикличность + достижимость (фикспойнт наивного солвера)
def fixpoint(banned=frozenset()):
    flags, fired = set(), set()
    changed = True
    while changed:
        changed = False
        for n in PUZ["nodes"]:
            if n["id"] in fired or n["id"] in banned:
                continue
            if all(x in flags for x in n["needs"]):
                fired.add(n["id"])
                flags |= set(n["gives"])
                changed = True
    return fired, flags

fired_all, flags_all = fixpoint()
ok("Победа достижима", "door_open" in fired_all)
mand = [n for n in PUZ["nodes"] if n["mand"]]
unreach = [n["id"] for n in mand if n["id"] not in fired_all]
ok("Все обязательные узлы достижимы", not unreach, str(unreach) if unreach else "")

# циклы: Кан по need-рёбрам
indeg = {i: 0 for i in NODES}
adj = defaultdict(set)
for n in PUZ["nodes"]:
    for s in deps_of(n):
        if n["id"] not in adj[s]:
            adj[s].add(n["id"]); indeg[n["id"]] += 1
q = deque([i for i, d in indeg.items() if d == 0]); seen = 0
while q:
    u = q.popleft(); seen += 1
    for v in adj[u]:
        indeg[v] -= 1
        if indeg[v] == 0: q.append(v)
ok("Граф ацикличен", seen == len(NODES), f"обойдено {seen}/{len(NODES)}")

# --- 2. never-blind
doc_access_fired = fixpoint()  # доки доступны, если их needs-узлы отработали
def doc_available(doc, fired):
    return all(nd in fired for nd in doc["needs"])
nb_pass = True
for n in PUZ["nodes"]:
    if not n["lock"]:
        continue
    srcs = n["lock"].get("clue_sources", [])
    if len(srcs) < 2:
        nb_pass = False
        FAIL.append(f"[FAIL] never-blind: {n['id']} источников {len(srcs)} < 2")
        print(FAIL[-1]); continue
    fired_wo, _ = fixpoint(banned=frozenset([n["id"]]))
    for s in srcs:
        d = DOCS.get(s)
        if d is None or not doc_available(d, fired_wo):
            nb_pass = False
            FAIL.append(f"[FAIL] never-blind: {n['id']} — источник {s} "
                        f"недоступен до замка")
            print(FAIL[-1])
ok("Never-blind: замки, >=2 источника, доступность до замка", nb_pass)
locks = [n["id"] for n in PUZ["nodes"] if n["lock"]]
INFO.append(f"[i] замков: {len(locks)}: {', '.join(locks)}")

# --- 3. глубина главной цепи (длиннейший путь по обязательным узлам)
memo = {}
def depth(i):
    if i in memo: return memo[i]
    n = NODES[i]
    ds = [depth(s) for s in deps_of(n) if NODES[s]["mand"]]
    memo[i] = 1 + (max(ds) if ds else 0)
    return memo[i]
main_depth = max(depth(n["id"]) for n in mand)
chain_end = max(mand, key=lambda n: depth(n["id"]))["id"]
ok("Глубина главной цепи >= 9", main_depth >= 9,
   f"глубина {main_depth}, финал цепи: {chain_end}")

# --- 4. параллельные обязательные нити (симуляция солвера)
def simulate():
    flags, fired, timeline = set(), set(), []
    def workable(n):
        """Узел «открыт»: needs выполнены; для замка вдобавок досягаемы
        все clue-доки (иначе нить не рабочая, а декоративная)."""
        if any(x not in flags for x in n["needs"]):
            return False
        if n["lock"]:
            for s in n["lock"]["clue_sources"]:
                if any(nd not in fired for nd in DOCS[s]["needs"]):
                    return False
        return True
    while True:
        avail = [n for n in PUZ["nodes"]
                 if n["id"] not in fired and workable(n)]
        m_avail = [n for n in avail if n["mand"]]
        if not m_avail:
            break
        branches = {n["branch"] for n in m_avail}
        timeline.append(len(branches))
        # канонический deepest-first солвер: двигаем критический путь,
        # прочие нити остаются «открытыми» — метрика GDD именно о них
        n = max(m_avail, key=lambda x: (depth(x["id"]), x["id"]))
        fired.add(n["id"]); flags |= set(n["gives"])
    return timeline, fired

timeline, sim_fired = simulate()
share3 = sum(1 for c in timeline if c >= 3) / max(1, len(timeline))
med = sorted(timeline)[len(timeline)//2]
ok("Нити: доля шагов с >=3 ветками >= 60%", share3 >= 0.60,
   f"{share3*100:.0f}% ({len(timeline)} шагов), медиана {med}, "
   f"распределение {sorted(set(timeline))}")
ok("Нити: медиана одновременных веток в [3,4]", 3 <= med <= 4, f"медиана {med}")
ok("Солвер добивает победу", "door_open" in sim_fired,
   f"{len(sim_fired)} узлов")

# --- 5. cross-room по веткам D1-D5
def node_room(i):
    return NODES[i]["room"]
cr_pass = True
for br in ["D1", "D2", "D3", "D4", "D5"]:
    hit = None
    for n in PUZ["nodes"]:
        if n["branch"] != br:
            continue
        rooms_in = {node_room(s) for s in deps_of(n) if node_room(s) in "AB"}
        r = n["room"]
        if r in "AB" and any(x != r for x in rooms_in):
            hit = f"{n['id']}: need из {rooms_in} при комнате {r}"; break
        if r == "inv" and rooms_in >= {"A", "B"}:
            hit = f"{n['id']}: inv-стык потребностей A и B"; break
        if n["lock"]:
            crooms = {DOCS[s]["room"] for s in n["lock"]["clue_sources"]}
            if r in "AB" and any(x != r for x in crooms if x in "AB"):
                hit = f"{n['id']}: clue из {crooms} при комнате {r}"; break
    okb = hit is not None
    cr_pass &= okb
    print(f"[{'PASS' if okb else 'FAIL'}] cross-room {br}"
          + (f" — {hit}" if hit else ""))
    (INFO if okb else FAIL).append(f"cross-room {br}: {hit}")
ok("Cross-room гейт (D1-D5)", cr_pass)

# --- 6. реликвии + корона
relics = PUZ["relics"]
r_ok = all(any(r in n["gives"] and n["id"] in fired_all for n in PUZ["nodes"])
           for r in relics)
crown_ok = any("crown" in n["gives"] and n["id"] in fired_all
               for n in PUZ["nodes"])
ok("Реликвии 3 шт. достижимы", r_ok and len(relics) == 3, ", ".join(relics))
ok("Корона достижима", crown_ok)
mand_ids = {n["id"] for n in mand}
sec_mand = [n["id"] for n in PUZ["nodes"]
            if (n["secret"] or "crown" in n["gives"]) and n["id"] in mand_ids]
ok("Секретный слой опционален", not sec_mand, str(sec_mand) if sec_mand else "")

# --- 7. герринги
herr = [n["id"] for n in PUZ["nodes"] if n["herring"]]
ok("Герринги >= 6", len(herr) >= 6, f"{len(herr)}: {', '.join(herr)}")

# --- 8. численные коридоры
total = len(PUZ["nodes"]); mand_n = len(mand)
ok("Узлов 48-52 (без доков)", 48 <= total <= 52, f"{total}")
ok("Обязательных 30-34", 30 <= mand_n <= 34, f"{mand_n}")
ok("Документов = 17", len(DOCS) == 17, f"{len(DOCS)}")

# --- итог
report = {"gate": "GATE1", "pass": not FAIL,
          "checks": INFO + FAIL,
          "metrics": {"nodes": total, "mandatory": mand_n,
                      "locks": len(locks), "docs": len(DOCS),
                      "main_depth": main_depth,
                      "threads_share3": round(share3, 3),
                      "threads_median": med,
                      "herrings": len(herr)}}
os.makedirs(os.path.join(HERE, "..", "work"), exist_ok=True)
with open(os.path.join(HERE, "..", "work", "gate1_report.json"), "w",
          encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("\n" + ("=== GATE1 PASS ===" if not FAIL else "=== GATE1 FAIL ==="))
sys.exit(0 if not FAIL else 1)
