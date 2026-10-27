#!/usr/bin/env python3
"""Georeference a plan PDF: fit an affine transform PDF points -> WGS84.

Plans rarely carry coordinates and are often rotated (this repo's first plan
was rotated ~45 deg), so we fit from matched points instead of assuming north-up.

Mode A, control points (anywhere in the world):
  python3 georef.py --control points.csv --out georef.json
  points.csv columns: pdf_x,pdf_y,lat,lon  (>= 3 rows, spread across the sheet;
  more is better. Get lat/lon from the user, Google Maps "copy coordinates",
  or a survey file.)

Mode B, Iceland, automatic from house numbers (iceaddr = Staðfangaskrá):
  python3 georef.py --iceaddr path/to/iceaddr.db --words words.json \
      --anchor "811.2,196.8,Sólarhvarf,30" --anchor "840,378,Skyggnishvarf,25" \
      --anchor "1795,473,Turnahvarf,4" --out georef.json
  Three anchors (house-number label position on the PDF + its street and
  number) give a rough fit; then every number label on the sheet is matched
  to the nearest register address with the same number and the fit is
  refined with shrinking thresholds. Expect a few hundred matches and a
  median residual of ~2-3 m on a good sheet.

Prints residuals. Median > 5 m or few matches means a wrong anchor or
non-affine distortion: re-check the anchors on a crop.
"""
import argparse, json, math, sqlite3, csv
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--control"); ap.add_argument("--iceaddr"); ap.add_argument("--words")
ap.add_argument("--anchor", action="append", default=[])
ap.add_argument("--out", required=True)
a = ap.parse_args()

def fit(P, G):
    M, *_ = np.linalg.lstsq(np.c_[P, np.ones(len(P))], G, rcond=None); return M

def report(P, G, M):
    r = np.hypot(*(np.c_[P, np.ones(len(P))] @ M - G).T)
    return float(np.sqrt(np.mean(r ** 2))), float(np.median(r)), float(r.max())

if a.control:
    rows = list(csv.DictReader(open(a.control)))
    lat0 = sum(float(r["lat"]) for r in rows) / len(rows); lon0 = sum(float(r["lon"]) for r in rows) / len(rows)
else:
    lat0 = lon0 = None

def setup(lat0_, lon0_):
    global LAT0, LON0, KX, KY
    LAT0, LON0 = lat0_, lon0_
    KX = 111320 * math.cos(math.radians(LAT0)); KY = 110950
def toxy(lat, lon): return ((lon - LON0) * KX, (lat - LAT0) * KY)

if a.control:
    setup(lat0, lon0)
    P = np.array([[float(r["pdf_x"]), float(r["pdf_y"])] for r in rows])
    G = np.array([toxy(float(r["lat"]), float(r["lon"])) for r in rows])
    M = fit(P, G); n = len(rows); rms, med, mx = report(P, G, M)
else:
    db = sqlite3.connect(a.iceaddr)
    anchors = []
    for s in a.anchor:
        x, y, street, num = s.split(",")
        r = db.execute("select lat_wgs84,long_wgs84 from stadfong where heiti_nf=? and husnr=? and (bokst='' or bokst is null)", (street, int(num))).fetchone()
        if not r: raise SystemExit(f"address not found in register: {street} {num}")
        anchors.append((float(x), float(y), r[0], r[1]))
    setup(sum(v[2] for v in anchors) / len(anchors), sum(v[3] for v in anchors) / len(anchors))
    words = json.load(open(a.words))
    # snap each anchor to the actual label position if it is close by
    P = []
    for x, y, *_ in anchors:
        near = [w for w in words if abs((w[0] + w[2]) / 2 - x) < 15 and abs((w[1] + w[3]) / 2 - y) < 15]
        P.append(min([((w[0] + w[2]) / 2, (w[1] + w[3]) / 2) for w in near] or [(x, y)], key=lambda c: math.hypot(c[0] - x, c[1] - y)))
    M = fit(np.array(P), np.array([toxy(v[2], v[3]) for v in anchors]))
    d = 0.02
    rows = db.execute("select husnr,bokst,lat_wgs84,long_wgs84 from stadfong where lat_wgs84 between ? and ? and long_wgs84 between ? and ?",
                      (LAT0 - d, LAT0 + d, LON0 - 2 * d, LON0 + 2 * d)).fetchall()
    addr = collections_addr = {}
    for num, b, la, lo in rows:
        addr.setdefault(str(num) + (b or "").lower(), []).append(toxy(la, lo))
    labels = [((w[0] + w[2]) / 2, (w[1] + w[3]) / 2, w[4].lower()) for w in words if w[4].lower() in addr]
    for thr in (40, 25, 15, 12, 10):
        pairs = []
        for x, y, t in labels:
            g = np.array([x, y, 1]) @ M
            best = min(addr[t], key=lambda q: math.hypot(q[0] - g[0], q[1] - g[1]))
            if math.hypot(best[0] - g[0], best[1] - g[1]) < thr: pairs.append(((x, y), best))
        P = np.array([p[0] for p in pairs]); G = np.array([p[1] for p in pairs])
        M = fit(P, G); n = len(pairs); rms, med, mx = report(P, G, M)
        print(f"threshold {thr} m: {n} matches, rms {rms:.1f} m, median {med:.1f} m")

sx, sy = np.hypot(*M[0]), np.hypot(*M[1])
print(f"matches {n}, rms {rms:.2f} m, median {med:.2f} m, max {mx:.2f} m; scale {sx:.3f}/{sy:.3f} m per pt, rotation {math.degrees(math.atan2(M[0][1], M[0][0])):.1f} deg")
json.dump({"lat0": LAT0, "lon0": LON0, "kx": KX, "ky": KY, "M": M.tolist(), "matches": n, "rms_m": rms, "median_m": med}, open(a.out, "w"), indent=1)
print("->", a.out)
