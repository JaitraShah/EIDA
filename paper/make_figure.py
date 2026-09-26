"""Draw Fig. 1 (EDIA pipeline) as a 300-dpi grayscale PNG sized for one IEEE column.

    .venv\\Scripts\\python.exe paper/make_figure.py   ->  paper/fig_pipeline.png

Pillow only (no matplotlib in the offline environment). Used by both edia_ieee.tex
(\\includegraphics) and build_docx.py, so the two versions share one figure.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DPI = 300
W, H = int(3.45 * DPI), int(2.25 * DPI)        # one IEEE column (3.5 in) wide
OUT = Path(__file__).with_name("fig_pipeline.png")
FONT_DIR = Path(r"C:\Windows\Fonts")
TITLE = ImageFont.truetype(str(FONT_DIR / "arialbd.ttf"), 34)    # ~8.2 pt at 300 dpi
BODY = ImageFont.truetype(str(FONT_DIR / "arial.ttf"), 29)       # ~7 pt
GREY = (232, 232, 232)
BLACK = (0, 0, 0)

img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

BW, BH = 300, 190                      # box size
COLS = [8, (W - BW) // 2, W - BW - 8]  # three columns
ROWS = [8, 258, 490]                   # three rows (row 3 boxes are shorter)


def box(col, row, title, lines, fill="white", h=BH, dashed=False):
    x0, y0 = COLS[col], ROWS[row]
    x1, y1 = x0 + BW, y0 + h
    if dashed:
        d.rectangle([x0, y0, x1, y1], fill=fill)
        for x in range(x0, x1, 18):
            d.line([x, y0, min(x + 9, x1), y0], fill=BLACK, width=3)
            d.line([x, y1, min(x + 9, x1), y1], fill=BLACK, width=3)
        for y in range(y0, y1, 18):
            d.line([x0, y, x0, min(y + 9, y1)], fill=BLACK, width=3)
            d.line([x1, y, x1, min(y + 9, y1)], fill=BLACK, width=3)
    else:
        d.rectangle([x0, y0, x1, y1], fill=fill, outline=BLACK, width=3)
    rows = [(title, TITLE)] + [(t, BODY) for t in lines]
    heights = [f.getbbox("Ag")[3] + 6 for _, f in rows]
    y = y0 + (h - sum(heights)) // 2
    for (text, font), hh in zip(rows, heights):
        tw = d.textlength(text, font=font)
        assert tw <= BW - 16, f"text too wide for box: {text!r} ({tw:.0f}px)"
        d.text((x0 + (BW - tw) / 2, y), text, font=font, fill=BLACK)
        y += hh
    return x0, y0, x1, y1


def arrow(p, q, dashed=False):
    (x0, y0), (x1, y1) = p, q
    if dashed:
        n = max(abs(x1 - x0), abs(y1 - y0)) // 16
        for i in range(0, n, 2):
            a, b = i / n, min((i + 1) / n, 1)
            d.line([x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, x0 + (x1 - x0) * b, y0 + (y1 - y0) * b],
                   fill=BLACK, width=4)
    else:
        d.line([x0, y0, x1, y1], fill=BLACK, width=4)
    import math
    ang = math.atan2(y1 - y0, x1 - x0)
    L, S = 22, 12
    pts = [(x1, y1),
           (x1 - L * math.cos(ang) + S * math.sin(ang), y1 - L * math.sin(ang) - S * math.cos(ang)),
           (x1 - L * math.cos(ang) - S * math.sin(ang), y1 - L * math.sin(ang) + S * math.cos(ang))]
    d.polygon(pts, fill=BLACK)


# row 1: extraction stage (grey)
t = box(0, 0, "Transcript", ["multi-speaker", "meeting"], fill=GREY)
c = box(1, 0, "Chunking", ["\u22641,200 tokens,", "2-turn overlap"], fill=GREY)
e = box(2, 0, "Extraction", ["Mistral 7B, temp 0,", "JSON schema"], fill=GREY)
# row 2: records -> detection -> report
r = box(2, 1, "Decision records", ["rationale, alternatives,", "dissent, quotes"])
g = box(1, 1, "Gap detection", ["lexical / NLI /", "LLM / ensemble"])
o = box(0, 1, "Gap report", ["reasoning missing", "from the document"])
# row 3: inputs / evaluation
doc = box(1, 2, "Filed document", ["minutes / summary"], h=150)
ev = box(2, 2, "Evaluation", ["completeness,", "unsupported quotes"], h=150, dashed=True)

mid = lambda b: (b[1] + b[3]) // 2
cx = lambda b: (b[0] + b[2]) // 2
arrow((t[2], mid(t)), (c[0], mid(c)))
arrow((c[2], mid(c)), (e[0], mid(e)))
arrow((cx(e), e[3]), (cx(r), r[1]))
arrow((r[0], mid(r)), (g[2], mid(g)))
arrow((g[0], mid(g)), (o[2], mid(o)))
arrow((cx(doc), doc[1]), (cx(g), g[3]))
arrow((cx(r), r[3]), (cx(ev), ev[1]), dashed=True)

img.save(OUT, dpi=(DPI, DPI))
print(f"wrote {OUT} ({W}x{H} px, {W / DPI:.2f}x{H / DPI:.2f} in)")
