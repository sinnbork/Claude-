#!/usr/bin/env python3
"""Electrical layer: split the drawing into base + electrical images and work out
which cable line (strengur) feeds which poles, for the app's "Strengir" view.

  python3 extract_lines.py plan.pdf symbols.json OUT_DIR/data words.json \
      --cable-stroke 0.72,0.54,0 --cabinet-color 0.25,1,0 \
      --cabinet-label '157\\d-\\d\\d' --cabinet-label-color ff0000 \
      --line-regex '^(\\d\\d\\.\\d)' --group-regex '^(\\d\\d)' \
      [--substation "1571,1468,371.8" --substation "1570,707.4,908"] [--clip x0,y0,x1,y1 --dpi 220]

How it decides (check the printout, and tell the user what it inferred):
- Cable paths (one stroke colour) are joined where endpoints touch. Pieces are cut
  at every pole ring, so a piece whose ends touch poles of ONE line id is that
  line's cable; pole-less pieces join the single line they touch. In the first
  project, pole ids encoded the line (03.3-05 = pole 5 on line 03.3), and the
  geometry confirmed it: no cable piece mixed two lines.
- Each group (03) is fed by the cabinet nearest its first poles, confirmed by
  cable pieces that touch the cabinet. Groups whose first pole is > 150 m from
  every cabinet are reported as "cabinet not on the drawing".
- Pixels with saturated colour (cables, red text, ducts, cabinets) go to the
  electrical image; everything else to the base image. Uses plan.js's clip/dpi
  so both images line up with the existing overlay.
Writes plan-base.webp, plan-elec.webp, elec.js (window.ELEC).
"""
import argparse, json, math, re, collections, os
import numpy as np, pymupdf
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("pdf"); ap.add_argument("symbols"); ap.add_argument("data"); ap.add_argument("words")
ap.add_argument("--cable-stroke", required=True); ap.add_argument("--cabinet-color", required=True)
ap.add_argument("--cabinet-label", required=True); ap.add_argument("--cabinet-label-color", default=None)
ap.add_argument("--line-regex", required=True); ap.add_argument("--group-regex", required=True)
ap.add_argument("--substation", action="append", default=[], help="name,pdf_x,pdf_y")
ap.add_argument("--clip"); ap.add_argument("--dpi", type=int)
ap.add_argument("--max-cabinet-m", type=float, default=150)
a = ap.parse_args()
col = lambda s: tuple(float(v) for v in s.split(","))
same = lambda c, w: c is not None and len(c) == 3 and all(abs(x - y) < 0.02 for x, y in zip(c, w))
CABLE, CABC = col(a.cable_stroke), col(a.cabinet_color)

P = json.loads(open(os.path.join(a.data, "plan.js")).read()[len("window.PLAN = "):].rstrip().rstrip(";"))
img = P["image"]
clip = pymupdf.Rect(*(col(a.clip) if a.clip else img["clip"])); dpi = a.dpi or img["dpi"]
page = pymupdf.open(a.pdf)[0]
segs, greens = [], []
for d in page.get_drawings():
    if same(d.get("color"), CABLE):
        for it in d["items"]:
            if it[0] == "l": segs.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
            elif it[0] == "c": segs.append(((it[1].x, it[1].y), (it[4].x, it[4].y)))
    if same(d.get("color"), CABC) or same(d.get("fill"), CABC): greens.append(tuple(d["rect"]))
sym = json.load(open(a.symbols)); words = json.load(open(a.words))
print(len(segs), "cable segments,", len(greens), "cabinet-colour shapes")

# --- join cable segments into pieces
pts = [q for s in segs for q in s]; par = list(range(len(pts)))
def f(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
def u(i, j): par[f(i)] = f(j)
for k in range(len(segs)): u(2 * k, 2 * k + 1)
grid = collections.defaultdict(list)
for i, (x, y) in enumerate(pts): grid[(int(x // 2), int(y // 2))].append(i)
near = lambda x, y: [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid[(int(x // 2) + dx, int(y // 2) + dy)]]
for i, (x, y) in enumerate(pts):
    for j in near(x, y):
        if j > i and math.hypot(pts[j][0] - x, pts[j][1] - y) < 0.3: u(i, j)
lineid = lambda pid: (re.match(a.line_regex, pid or "") or [None, None])[1]
groupid = lambda lid: (re.match(a.group_regex, lid or "") or [None, None])[1]

# cabinets = cabinet-colour shape nearest each cabinet label
cabs = []
for w in words:
    if re.fullmatch(a.cabinet_label, w[4]) and (not a.cabinet_label_color or w[5] == a.cabinet_label_color.lower()):
        lx, ly = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        r = min(greens, key=lambda r: math.hypot((r[0] + r[2]) / 2 - lx, (r[1] + r[3]) / 2 - ly))
        cabs.append({"id": w[4], "rect": r, "x": (r[0] + r[2]) / 2, "y": (r[1] + r[3]) / 2})
print("cabinets:", [c["id"] for c in cabs])

pieces = collections.defaultdict(lambda: {"segs": [], "lines": set(), "cabs": set(), "ends": []})
for k in range(len(segs)): pieces[f(2 * k)]["segs"].append(k)
for i, (x, y) in enumerate(pts):
    pc = pieces[f(i)]; pc["ends"].append((x, y))
    for s in sym:
        if abs(s["px"] - x) < 1.6 and abs(s["py"] - y) < 1.6 and math.hypot(s["px"] - x, s["py"] - y) < 1.5 and lineid(s["id"]): pc["lines"].add(lineid(s["id"]))
    for c in cabs:
        R = c["rect"]
        if R[0] - 1 <= x <= R[2] + 1 and R[1] - 1 <= y <= R[3] + 1: pc["cabs"].add(c["id"])
owner = {r: next(iter(v["lines"])) for r, v in pieces.items() if len(v["lines"]) == 1}
mixed = sum(1 for v in pieces.values() if len(v["lines"]) > 1)
egrid = collections.defaultdict(set)
for r, v in pieces.items():
    for x, y in v["ends"]: egrid[(int(x // 2), int(y // 2))].add(r)
def nbrs(r):
    out = set()
    for x, y in pieces[r]["ends"]:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for o in egrid[(int(x // 2) + dx, int(y // 2) + dy)]:
                    if o != r and any(math.hypot(x - p, y - q) < 1.5 for p, q in pieces[o]["ends"]): out.add(o)
    return out
NB = {r: nbrs(r) for r in pieces}
for _ in range(20):
    grew = False
    for r, v in pieces.items():
        if r in owner or v["lines"]: continue
        ls = {owner[o] for o in NB[r] if o in owner}
        if len(ls) == 1: owner[r] = ls.pop(); grew = True
    if not grew: break
print(f"{sum(len(pieces[r]['segs']) for r in owner)} of {len(segs)} cable segments assigned to a line; {mixed} pieces touched two lines (left unassigned)")

# group -> cabinet: nearest to the group's lowest-numbered poles, confirmed by touching pieces
mpp = 1.0  # metres per pt, from plan.js corners
c_ = img["corners"]; W, H = img["width"], img["height"]
tl, tr, bl = map(np.array, (c_["tl"], c_["tr"], c_["bl"]))
k = dpi / 72
def geo(x, y):
    ix, iy = (x - clip.x0) * k, (y - clip.y0) * k
    g = tl + (tr - tl) * ix / W + (bl - tl) * iy / H; return [round(g[0], 7), round(g[1], 7)]
def dist_m(p, q):
    a_, b_ = geo(*p), geo(*q); return math.hypot((a_[0] - b_[0]) * 111000, (a_[1] - b_[1]) * 111000 * math.cos(math.radians(a_[0])))
by_line = collections.defaultdict(list)
for s in sym:
    if lineid(s["id"]): by_line[lineid(s["id"])].append(s)
touch = collections.defaultdict(collections.Counter)
for r, v in pieces.items():
    if r in owner:
        for c in v["cabs"]: touch[groupid(owner[r])][c] += 1
cab_of = {}
for g in sorted({groupid(l) for l in by_line}):
    firsts = [min(ps, key=lambda s: s["id"]) for l, ps in by_line.items() if groupid(l) == g]
    best = min(cabs, key=lambda c: min(dist_m((c["x"], c["y"]), (s["px"], s["py"])) for s in firsts))
    d = min(dist_m((best["x"], best["y"]), (s["px"], s["py"])) for s in firsts)
    cab_of[g] = best["id"] if d <= a.max_cabinet_m else None
    print(f"group {g}: nearest cabinet {best['id']} ({d:.0f} m) -> {cab_of[g] or 'not on drawing'}; cable pieces touching cabinets: {dict(touch[g]) or '-'}")

# --- images
pix = page.get_pixmap(clip=clip, dpi=dpi)
assert (pix.width, pix.height) == (W, H), "clip/dpi do not reproduce plan.webp; pass --clip/--dpi"
im = np.frombuffer(pix.samples, np.uint8).reshape(H, W, pix.n)[:, :, :3].astype(np.int16)
sat = im.max(axis=2) - im.min(axis=2)
mask = np.array(Image.fromarray(((sat > 55) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
base = im.copy(); base[mask] = 255
mn = base.min(axis=2); al = np.clip((255 - mn) * 255 // 60, 0, 255).astype(np.uint8); al[mn < 200] = 255
Image.fromarray(np.dstack([base.astype(np.uint8), al]), "RGBA").save(os.path.join(a.data, "plan-base.webp"), quality=88, method=5)
ea = np.clip(sat * 255 // 120, 0, 255).astype(np.uint8); ea[~mask] = 0
Image.fromarray(np.dstack([im.astype(np.uint8), ea]), "RGBA").save(os.path.join(a.data, "plan-elec.webp"), quality=88, method=5)

tx = lambda x, y: (round((x - clip.x0) * k, 1), round((y - clip.y0) * k, 1))
paths = collections.defaultdict(list)
for r, l in owner.items():
    for s in pieces[r]["segs"]:
        p1, p2 = tx(*segs[s][0]), tx(*segs[s][1]); paths[l].append(f"M{p1[0]} {p1[1]}L{p2[0]} {p2[1]}")
lines = [{"id": l, "cabinet": cab_of.get(groupid(l)), "poles": sorted(s["id"] for s in ps), "path": "".join(paths.get(l, []))} for l, ps in sorted(by_line.items())]
subs = []
for sdef in a.substation:
    n, x, y = sdef.split(","); la, lo = geo(float(x), float(y)); subs.append({"id": n, "lat": la, "lon": lo})
out = {"base": "data/plan-base.webp", "elec": "data/plan-elec.webp",
       "cabinets": [{"id": c["id"], **dict(zip(("lat", "lon"), geo(c["x"], c["y"])))} for c in cabs], "substations": subs, "lines": lines}
open(os.path.join(a.data, "elec.js"), "w").write("window.ELEC = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
print(f"{len(lines)} lines -> {a.data}/elec.js, plan-base.webp, plan-elec.webp")
