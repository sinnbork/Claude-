#!/usr/bin/env python3
"""Inventory a CAD/plan PDF so you can decide how to extract its symbols.

Writes to OUT_DIR:
  overview.png   whole page, low resolution (look at it first)
  words.json     every text span: [x0, y0, x1, y1, text, color_hex, rotated]
  shapes.txt     the most common vector-path "signatures"
                 (fill colour, stroke colour, bbox w x h, item count) with a
                 sample position, to spot repeated symbols such as pole markers
Use crop.py to zoom into a sample position before choosing a signature.

Usage: python3 pdf_inventory.py plan.pdf OUT_DIR
"""
import sys, os, json, collections
import pymupdf

pdf, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
page = pymupdf.open(pdf)[0]
print("page size (pt):", page.rect.width, "x", page.rect.height, "rotation", page.rotation)
page.get_pixmap(dpi=40).save(os.path.join(out, "overview.png"))

words = []
for b in page.get_text("dict")["blocks"]:
    for ln in b.get("lines", []):
        rot = ln["dir"] != (1.0, 0.0)
        for sp in ln["spans"]:
            t = sp["text"].strip()
            if t:
                words.append([*[round(v, 2) for v in sp["bbox"]], t, "%06x" % sp["color"], rot])
json.dump(words, open(os.path.join(out, "words.json"), "w"), ensure_ascii=False)
print(len(words), "text spans -> words.json")

def col(c):
    return ",".join("%.2f" % v for v in c) if c else "-"

sig = collections.Counter(); sample = {}
for d in page.get_drawings():
    r = d["rect"]
    k = (col(d.get("fill")), col(d.get("color")), round(r.width, 1), round(r.height, 1), len(d["items"]))
    sig[k] += 1; sample.setdefault(k, (round((r.x0 + r.x1) / 2, 1), round((r.y0 + r.y1) / 2, 1)))
with open(os.path.join(out, "shapes.txt"), "w") as f:
    f.write("count\tfill\tstroke\tw\th\titems\tsample_x,y\n")
    for k, n in sig.most_common(80):
        f.write(f"{n}\t{k[0]}\t{k[1]}\t{k[2]}\t{k[3]}\t{k[4]}\t{sample[k]}\n")
print("top shape signatures -> shapes.txt")
