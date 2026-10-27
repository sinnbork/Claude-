#!/usr/bin/env python3
"""Find repeated point symbols (e.g. light poles) in a plan PDF and pair each
with its ID label and (optionally) a nearby code letter.

A symbol is identified by a vector-path signature found with pdf_inventory.py:
stroke and/or fill colour, bbox size and item count. Duplicate paths at the
same spot are merged. Labels are matched one-to-one to the nearest symbol
(greedy by distance), so every ID is used at most once.

Usage:
  python3 extract_symbols.py plan.pdf words.json \
      --stroke 0,0.5,1 --size 1.92 --items 10 \
      --id-regex '\\d\\d\\.\\d-\\d\\d' --max-label-dist 14 \
      [--code-regex '[A-L]' --code-color ff0000 --max-code-dist 12] \
      --out symbols.json
Prints counts, unmatched symbols/labels and duplicate IDs: check them.
"""
import argparse, json, math, re, collections
import pymupdf

ap = argparse.ArgumentParser()
ap.add_argument("pdf"); ap.add_argument("words")
ap.add_argument("--stroke"); ap.add_argument("--fill")
ap.add_argument("--size", type=float, required=True, help="symbol bbox width (pt)")
ap.add_argument("--size-tol", type=float, default=0.2)
ap.add_argument("--items", type=int, help="number of path items in the signature")
ap.add_argument("--id-regex", required=True)
ap.add_argument("--max-label-dist", type=float, default=14)
ap.add_argument("--code-regex"); ap.add_argument("--code-color")
ap.add_argument("--max-code-dist", type=float, default=12)
ap.add_argument("--out", required=True)
a = ap.parse_args()

def parse(c): return tuple(float(v) for v in c.split(",")) if c else None
def same(c, want): return want is None or (c is not None and len(c) == len(want) and all(abs(x - y) < 0.02 for x, y in zip(c, want)))

page = pymupdf.open(a.pdf)[0]
pts = set()
for d in page.get_drawings():
    r = d["rect"]
    if not same(d.get("color"), parse(a.stroke)) or not same(d.get("fill"), parse(a.fill)): continue
    if a.stroke and not d.get("color"): continue
    if a.fill and not d.get("fill"): continue
    if abs(r.width - a.size) > a.size_tol or abs(r.height - a.size) > a.size_tol: continue
    if a.items and len(d["items"]) != a.items: continue
    pts.add((round((r.x0 + r.x1) / 2, 1), round((r.y0 + r.y1) / 2, 1)))
pts = sorted(pts)
print("symbols found:", len(pts))

words = json.load(open(a.words))
ctr = lambda w: ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
ids = [(w[4].replace(" ", ""), ctr(w)) for w in words if re.fullmatch(a.id_regex, w[4].replace(" ", ""))]
print("ID labels found:", len(ids))
dist = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1])
pairs = sorted((dist(lc, s), i, j) for i, (_, lc) in enumerate(ids) for j, s in enumerate(pts) if dist(lc, s) < a.max_label_dist)
ui, uj, lab = set(), set(), {}
for d, i, j in pairs:
    if i in ui or j in uj: continue
    ui.add(i); uj.add(j); lab[j] = ids[i][0]

codes = []
if a.code_regex:
    codes = [(w[4], ctr(w)) for w in words if re.fullmatch(a.code_regex, w[4]) and (not a.code_color or w[5] == a.code_color.lower())]
    print("code letters found:", len(codes))

out = []
for j, s in enumerate(pts):
    code = None
    if codes:
        c = min(codes, key=lambda c: dist(c[1], s))
        if dist(c[1], s) < a.max_code_dist: code = c[0]
    out.append({"id": lab.get(j), "code": code, "px": s[0], "py": s[1]})
json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=0)

print("symbols without ID:", [ (o["px"], o["py"]) for o in out if not o["id"] ][:20])
print("unused ID labels:", [ids[i][0] for i in range(len(ids)) if i not in ui][:40])
print("duplicate IDs:", [k for k, v in collections.Counter(o["id"] for o in out if o["id"]).items() if v > 1])
if codes: print("codes:", dict(collections.Counter(o["code"] for o in out)))
print("->", a.out)
