#!/usr/bin/env python3
"""Visual check: draw register addresses (magenta) and extracted points (green)
on the overlay image. Addresses should sit inside the right buildings and green
rings on the drawn symbols. Iceland only (needs iceaddr.db); for other places
open the app on a satellite base map instead.
Usage: python3 check_alignment.py OUT_DIR/data iceaddr.db check.png [x0 y0 x1 y1 crop in image px]"""
import sys, json, sqlite3
import numpy as np
from PIL import Image, ImageDraw
d, dbp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
P = json.loads(open(d + "/plan.js").read()[len("window.PLAN = "):].rstrip().rstrip(";"))
c = P["image"]["corners"]; W, H = P["image"]["width"], P["image"]["height"]
tl, tr, bl = map(np.array, (c["tl"], c["tr"], c["bl"]))
Ai = np.linalg.inv(np.array([(tr - tl) / W, (bl - tl) / H]).T)
im = Image.open(d + "/plan.webp").convert("RGB"); dr = ImageDraw.Draw(im)
lats = [q[0] for q in (c["tl"], c["tr"], c["bl"])]; lons = [q[1] for q in (c["tl"], c["tr"], c["bl"])]
for la, lo in sqlite3.connect(dbp).execute("select lat_wgs84,long_wgs84 from stadfong where lat_wgs84 between ? and ? and long_wgs84 between ? and ?",
                                           (min(lats) - .01, max(lats) + .01, min(lons) - .02, max(lons) + .02)):
    x, y = Ai @ (np.array([la, lo]) - tl); dr.ellipse((x - 9, y - 9, x + 9, y + 9), outline=(255, 0, 255), width=4)
for p in P["poles"]:
    x, y = Ai @ (np.array([p["lat"], p["lon"]]) - tl); dr.ellipse((x - 12, y - 12, x + 12, y + 12), outline=(0, 200, 0), width=4)
if len(sys.argv) > 7: im = im.crop(tuple(int(v) for v in sys.argv[4:8]))
im.save(outp); print("->", outp)
