#!/usr/bin/env python3
"""Render the overlay image and write the app's data file.

  python3 build_plan.py plan.pdf georef.json symbols.json OUT_DIR \
      [--extra extra.json] [--dpi 220] [--source "drawing name"]

Writes OUT_DIR/data/plan.webp (white made transparent so the base map shows
through) and OUT_DIR/data/plan.js (window.PLAN = {image, poles, relocated}).
extra.json (optional) is a list of {"id", "px", "py"} for secondary points
(e.g. existing poles moved to a new location); they appear as black diamonds.
DPI 220 keeps 3-pt labels legible at street zoom while the file stays ~4 MB.
"""
import argparse, json, os, math
import numpy as np, pymupdf
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("pdf"); ap.add_argument("georef"); ap.add_argument("symbols"); ap.add_argument("out")
ap.add_argument("--extra"); ap.add_argument("--dpi", type=int, default=220); ap.add_argument("--source", default="")
a = ap.parse_args()
g = json.load(open(a.georef)); M = np.array(g["M"])
def geo(x, y):
    E, N = np.array([x, y, 1]) @ M
    return [round(g["lat0"] + N / g["ky"], 8), round(g["lon0"] + E / g["kx"], 8)]

page = pymupdf.open(a.pdf)[0]
lo = page.get_pixmap(dpi=36); px = np.frombuffer(lo.samples, np.uint8).reshape(lo.height, lo.width, lo.n)[:, :, :3]
ys, xs = np.where(px.min(axis=2) < 240); f = 72 / 36
clip = pymupdf.Rect(xs.min() * f - 4, ys.min() * f - 4, xs.max() * f + 4, ys.max() * f + 4) & page.rect
pix = page.get_pixmap(clip=clip, dpi=a.dpi)
im = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(np.int16)
mn = im.min(axis=2); alpha = np.clip((255 - mn) * 255 // 60, 0, 255).astype(np.uint8); alpha[mn < 200] = 255
os.makedirs(os.path.join(a.out, "data"), exist_ok=True)
Image.fromarray(np.dstack([im.astype(np.uint8), alpha]), "RGBA").save(os.path.join(a.out, "data/plan.webp"), quality=88, method=5)

sym = json.load(open(a.symbols))
poles = sorted(({"id": s["id"] or f"?{i}", "code": s.get("code"), **dict(zip(("lat", "lon"), geo(s["px"], s["py"])))} for i, s in enumerate(sym)), key=lambda p: p["id"])
extra = [{"id": e["id"], **dict(zip(("lat", "lon"), geo(e["px"], e["py"])))} for e in json.load(open(a.extra))] if a.extra else []
data = {"source": a.source, "image": {"url": "data/plan.webp", "width": pix.width, "height": pix.height,
        "corners": {"tl": geo(clip.x0, clip.y0), "tr": geo(clip.x1, clip.y0), "bl": geo(clip.x0, clip.y1)}},
        "poles": poles, "relocated": extra}
open(os.path.join(a.out, "data/plan.js"), "w").write("window.PLAN = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
print(f"image {pix.width}x{pix.height}, {os.path.getsize(os.path.join(a.out, 'data/plan.webp'))/1e6:.1f} MB; {len(poles)} points, {len(extra)} extra -> {a.out}/data/")
