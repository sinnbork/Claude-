#!/usr/bin/env python3
"""Render a zoomed crop of the PDF around a point (PDF points) to inspect symbols.
Usage: python3 crop.py plan.pdf X Y [HALF_SIZE_PT=30] [DPI=800] out.png"""
import sys, pymupdf
a = sys.argv
x, y = float(a[2]), float(a[3])
h = float(a[4]) if len(a) > 5 else 30
dpi = int(a[5]) if len(a) > 6 else 800
pymupdf.open(a[1])[0].get_pixmap(clip=pymupdf.Rect(x - h, y - h, x + h, y + h), dpi=dpi).save(a[-1])
