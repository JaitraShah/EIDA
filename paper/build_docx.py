"""Build paper/edia_ieee.docx from paper/edia_ieee.tex + paper/refs.bib (IEEE conference layout).

    .venv\\Scripts\\python.exe paper/make_figure.py     # Fig. 1 PNG (shared with the LaTeX build)
    .venv\\Scripts\\python.exe paper/build_docx.py      # -> paper/edia_ieee.docx

The .tex is the single source: edit it, then re-run this script. This is a converter
for the constructs edia_ieee.tex actually uses (sections, subsections, paragraphs,
itemize, table/table*, figure, \\textbf/\\emph/\\textit/\\texttt/\\url/\\footnote/\\TODO,
\\cite, \\ref, simple inline math) -- not a general LaTeX engine.

Layout follows the IEEE conference template: US Letter, margins 0.75/1/0.625/0.625 in,
two 3.5 in columns with 0.25 in gutter, Times New Roman 10 pt, small-caps Roman-numbered
section heads, lettered italic subsections, table captions above ("TABLE I"), figure
captions below ("Fig. 1."), 8 pt numbered references in citation order.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
TEX = HERE / "edia_ieee.tex"
BIB = HERE / "refs.bib"
OUT = HERE / "edia_ieee.docx"
FONT = "Times New Roman"
COL_W = 3.45      # usable single-column width (in)
FULL_W = 7.1      # usable full-page width (in)
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
ACCENTS = {r"{\'s}": "ś", r"{\'n}": "ń", r"\'e": "é", r"\'a": "á", r'\"o': "ö", r'\"u': "ü"}


# ----------------------------------------------------------------------------- tex helpers
def strip_comments(tex: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.splitlines())


def braced(s: str, i: int) -> tuple[str, int]:
    """s[i] == '{'. Return (content, index after the closing brace)."""
    assert s[i] == "{", s[i:i + 30]
    depth, j = 0, i
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces near: " + s[i:i + 60])


def command_arg(s: str, name: str) -> str | None:
    """First mandatory {argument} of \\name, skipping an optional [..] argument."""
    m = re.search(r"\\" + re.escape(name) + r"\s*(?:\[[^\]]*\])?\s*\{", s)
    return braced(s, m.end() - 1)[0] if m else None


def env(s: str, name: str) -> str | None:
    m = re.search(r"\\begin\{" + re.escape(name) + r"\}(.*?)\\end\{" + re.escape(name) + r"\}", s, re.S)
    return m.group(1) if m else None


# ----------------------------------------------------------------------------- inline -> runs
def typography(t: str) -> str:
    t = t.replace("---", "\u2014").replace("--", "\u2013")
    t = t.replace("``", "\u201c").replace("''", "\u201d").replace("`", "\u2018").replace("'", "\u2019")
    return t


def math_runs(m: str, fmt: dict) -> list:
    for a, b in ((r"\geq", "≥"), (r"\leq", "≤"), (r"\times", "×"), (r"\dagger", "†"), ("-", "−")):
        m = m.replace(a, b)
    runs, i = [], 0
    while i < len(m):
        ch = m[i]
        if ch == "^":
            nxt = m[i + 1] if i + 1 < len(m) else ""
            if nxt == "{":
                sup, i = braced(m, i + 1)
            else:
                sup, i = nxt, i + 2
            runs.append((sup, {**fmt, "sup": True}))
            continue
        j = i
        if ch.isalpha():
            while j < len(m) and m[j].isalpha():
                j += 1
            runs.append((m[i:j], {**fmt, "i": True}))
        else:
            while j < len(m) and not m[j].isalpha() and m[j] != "^":
                j += 1
            runs.append((m[i:j], dict(fmt)))
        i = j
    return runs


SYMBOLS = {"%": "%", "&": "&", "_": "_", "#": "#", ",": "\u2009", " ": " ", "$": "$", "{": "{", "}": "}"}
STYLE_CMDS = {"textbf": {"b": True}, "emph": {"i": True}, "textit": {"i": True},
              "texttt": {"mono": True}, "textsc": {"sc": True}, "url": {}}


def inline(s: str, fmt: dict | None = None) -> list:
    """LaTeX inline text -> list of (text, fmt) runs."""
    fmt = fmt or {}
    runs, buf, i = [], [], 0

    def flush():
        if buf:
            runs.append((typography("".join(buf)), dict(fmt)))
            buf.clear()

    while i < len(s):
        ch = s[i]
        if ch == "\\":
            m = re.match(r"\\([A-Za-z]+)\*?", s[i:])
            if not m:                                   # \%, \&, \_, \,, "\ ", \\ ...
                sym = s[i + 1] if i + 1 < len(s) else ""
                if sym == "\\" or sym.isspace():
                    buf.append(" ")
                else:
                    buf.append(SYMBOLS.get(sym, sym))
                i += 2
                continue
            name, i = m.group(1), i + m.end()
            while i < len(s) and s[i] == " " and name not in STYLE_CMDS and name not in ("TODO", "footnote"):
                i += 1  # control words eat following spaces
            if name in STYLE_CMDS or name in ("TODO", "footnote"):
                arg, i = braced(s, i)
                flush()
                if name == "TODO":
                    red = {**fmt, "color": "C00000"}
                    runs += [("[TODO: ", red)] + inline(arg, red) + [("]", red)]
                elif name == "footnote":
                    runs += [(", ", dict(fmt))] + inline(arg, fmt)
                elif name == "url":
                    runs.append((arg, dict(fmt)))
                else:
                    runs += inline(arg, {**fmt, **STYLE_CMDS[name]})
            elif name == "ldots":
                buf.append("\u2026")
            # any other control word is layout-only here (\centering, \small, ...) and dropped
            continue
        if ch == "$":
            j = s.index("$", i + 1)
            flush()
            runs += math_runs(s[i + 1:j], fmt)
            i = j + 1
            continue
        if ch in "{}":
            i += 1
            continue
        if ch == "~":
            buf.append("\u00a0")
        elif ch in "\n\t":
            buf.append(" ")
        else:
            buf.append(ch)
        i += 1
    flush()
    # collapse whitespace across run boundaries
    out, prev_space = [], True
    for text, f in runs:
        text = re.sub(r"[ ]{2,}", " ", text)
        if prev_space:
            text = text.lstrip(" ")
        if text:
            out.append((text, f))
            prev_space = text.endswith(" ")
    if out:
        out[-1] = (out[-1][0].rstrip(" "), out[-1][1])
    return out


# ----------------------------------------------------------------------------- docx helpers
def set_run(run, fmt: dict, size: float):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.bold = fmt.get("b") or None
    run.italic = fmt.get("i") or None
    if fmt.get("sc"):
        run.font.small_caps = True
    if fmt.get("sup"):
        run.font.superscript = True
    if fmt.get("mono"):
        run.font.name = "Courier New"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Courier New")
    if fmt.get("color"):
        run.font.color.rgb = RGBColor.from_string(fmt["color"])


def add_runs(par, runs, size=10.0, base: dict | None = None):
    for text, fmt in runs:
        set_run(par.add_run(text), {**(base or {}), **fmt}, size)


def para(doc, runs=None, size=10.0, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=True,
         before=0.0, after=0.0, base=None, keep_next=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = align
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.first_line_indent = Pt(10) if indent else None
    pf.line_spacing = 1.0
    pf.keep_with_next = keep_next or None
    if runs:
        add_runs(p, runs, size, base)
    return p


def set_columns(section, n: int, space_in: float = 0.25):
    cols = section._sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        section._sectPr.append(cols)
    cols.set(qn("w:num"), str(n))
    cols.set(qn("w:space"), str(int(space_in * 1440)))


def page_setup(section):
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin, section.bottom_margin = Inches(0.75), Inches(1.0)
    section.left_margin = section.right_margin = Inches(0.625)


# WordprocessingML fixes the child order of these property blocks; Word treats an
# out-of-order child as corruption (it opens a hidden "repair?" prompt under automation).
TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
               "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders",
               "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"]
TCPR_ORDER = ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap",
              "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"]


def insert_ordered(parent, child, order):
    """Insert child at its schema position, replacing any existing element of the same name."""
    name = child.tag.split("}")[1]
    for old in parent.findall(qn("w:" + name)):
        parent.remove(old)
    rank = order.index(name)
    for sib in parent:
        sname = sib.tag.split("}")[1]
        if sname in order and order.index(sname) > rank:
            sib.addprevious(child)
            return
    parent.append(child)


def cell_borders(cell, **edges):
    """edges: top/bottom=<size in eighths of a point>. Idempotent (merged cells repeat)."""
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    insert_ordered(tcPr, borders, TCPR_ORDER)
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        if edge in edges:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(edges[edge]))
            el.set(qn("w:color"), "000000")
        else:
            el.set(qn("w:val"), "nil")
        borders.append(el)


def no_table_borders(table):
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        b.append(el)
    insert_ordered(table._tbl.tblPr, b, TBLPR_ORDER)


def cell_margins(table, left=0.05, right=0.05):
    mar = OxmlElement("w:tblCellMar")
    for edge, v in (("top", 0.0), ("left", left), ("bottom", 0.0), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(int(v * 1440)))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    insert_ordered(table._tbl.tblPr, mar, TBLPR_ORDER)


# ----------------------------------------------------------------------------- bibliography
def parse_bib(text: str) -> dict:
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        kind, key = m.group(1).lower(), m.group(2)
        i, fields = m.end(), {}
        while True:
            fm = re.compile(r"\s*(\w+)\s*=\s*").match(text, i)
            if not fm:
                break
            name, j = fm.group(1).lower(), fm.end()
            if text[j] == "{":
                val, j = braced(text, j)
            else:
                vm = re.compile(r"[^,}\n]+").match(text, j)
                val, j = vm.group(0).strip(), vm.end()
            fields[name] = val
            cm = re.compile(r"\s*,?").match(text, j)
            i = cm.end()
            if i < len(text) and text[i] == "}":
                break
        entries[key] = {"kind": kind, **fields}
    return entries


def bib_text(s: str) -> str:
    for a, b in ACCENTS.items():
        s = s.replace(a, b)
    return typography(re.sub(r"[{}]", "", s).replace("\\&", "&"))


def ieee_authors(raw: str) -> str:
    names = [n.strip() for n in bib_text(raw).split(" and ")]
    others = "others" in names
    names = [n for n in names if n != "others"]

    def initials(n):
        parts = n.split()
        return " ".join(p[0] + "." for p in parts[:-1]) + " " + parts[-1] if len(parts) > 1 else n

    names = [initials(n) for n in names]
    if others or len(names) > 6:
        return names[0] + " et al."
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def ieee_reference(e: dict) -> list:
    """-> runs for one reference entry."""
    runs = [(ieee_authors(e["author"]) + ", \u201c" + bib_text(e["title"]) + ",\u201d ", {})]
    pages = f", pp. {bib_text(e['pages'])}" if "pages" in e else ""
    if e["kind"] == "inproceedings":
        runs += [("in ", {}), (bib_text(e["booktitle"]), {"i": True})]
        if "publisher" in e:
            runs.append((", " + bib_text(e["publisher"]), {}))
        runs.append((f", {e['year']}{pages}.", {}))
    else:
        runs.append((bib_text(e["journal"]), {"i": True}))
        vol = f", vol. {e['volume']}" if "volume" in e else ""
        runs.append((f"{vol}{pages}, {e['year']}.", {}))
    return runs


# ----------------------------------------------------------------------------- tables / figure
def parse_tabular(body: str):
    m = re.search(r"\\begin\{tabular\}\{(.*?)\}\s*\n(.*?)\\end\{tabular\}", body, re.S)
    spec = re.sub(r"@\{\}", "", m.group(1))
    aligns = [c for c in spec if c in "lrc"]
    rows, rules_after, pending_rule = [], set(), False
    for raw in re.split(r"\\\\", m.group(2)):
        lines = [l.strip() for l in raw.strip().splitlines()]
        for l in lines:
            if l in ("\\midrule", "\\toprule", "\\bottomrule"):
                if l == "\\midrule" and rows:
                    rules_after.add(len(rows) - 1)
        content = " ".join(l for l in lines if l not in ("\\midrule", "\\toprule", "\\bottomrule")).strip()
        if not content:
            continue
        if content.startswith("\\multicolumn"):
            i = len("\\multicolumn")
            _, i = braced(content, i)          # column count
            _, i = braced(content, i)          # alignment spec, may nest braces: {@{}l}
            text, _ = braced(content, i)
            rows.append(("span", text))
        else:
            rows.append(("cells", [c.strip() for c in re.split(r"(?<!\\)&", content)]))
    return aligns, rows, rules_after


def render_table(doc, block: str, labels: dict, width_in: float):
    caption = command_arg(block, "caption")
    label = command_arg(block, "label")
    aligns, rows, rules_after = parse_tabular(block)
    ncol = len(aligns)
    # caption above: "TABLE I" + caption text, small caps, centred, 8 pt
    para(doc, [(f"TABLE {labels[label]}", {"sc": True})], size=8,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=8, keep_next=True)
    para(doc, inline(caption, {"sc": True}), size=8, align=WD_ALIGN_PARAGRAPH.CENTER,
         indent=False, after=4, keep_next=True)
    # column widths proportional to longest cell text
    plain = lambda t: "".join(x for x, _ in inline(t))
    longest = [max((len(plain(r[1][c])) for r in rows if r[0] == "cells"), default=4) for c in range(ncol)]
    weights = [min(max(L, 3), 60) + 3 for L in longest]      # +3 chars: cell margins
    widths = [width_in * w / sum(weights) for w in weights]
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    no_table_borders(table)
    cell_margins(table)
    for ri, (kind, content) in enumerate(rows):
        row = table.rows[ri]
        if kind == "span":
            merged = row.cells[0].merge(row.cells[-1])
            cells_content = [(merged, content, "l")]
        else:
            cells_content = [(row.cells[c], content[c], aligns[c]) for c in range(ncol)]
        for cell, text, al in cells_content:
            p = cell.paragraphs[0]
            p.style = doc.styles["IEEE Table Text"]
            p.paragraph_format.alignment = {"l": WD_ALIGN_PARAGRAPH.LEFT, "r": WD_ALIGN_PARAGRAPH.RIGHT,
                                            "c": WD_ALIGN_PARAGRAPH.CENTER}[al]
            p.paragraph_format.keep_with_next = ri < len(rows) - 1 or None   # never split a table
            add_runs(p, inline(text), size=8)
        for c, cell in enumerate(row.cells):
            cell.width = Inches(widths[c])
            edges = {}
            if ri == 0:
                edges["top"] = 8                     # \toprule
            if ri in rules_after:
                edges["bottom"] = 4                  # \midrule
            if ri == len(rows) - 1:
                edges["bottom"] = 8                  # \bottomrule
            cell_borders(cell, **edges)
    para(doc, after=6, indent=False, size=4)         # small gap after the table


def render_figure(doc, block: str, labels: dict):
    img = command_arg(block, "includegraphics")
    caption = command_arg(block, "caption")
    label = command_arg(block, "label")
    p = para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=6, keep_next=True)
    p.add_run().add_picture(str(HERE / img), width=Inches(COL_W))
    para(doc, [(f"Fig. {labels[label]}. ", {})] + inline(caption), size=8,
         align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=False, after=8)


# ----------------------------------------------------------------------------- main
def main() -> int:
    tex = strip_comments(TEX.read_text(encoding="utf-8"))
    # expand argument-less \newcommand macros (e.g. \EDIAfull) as LaTeX would
    for name, val in re.findall(r"\\newcommand\{\\(\w+)\}\{([^{}]*)\}", tex):
        tex = re.sub(r"\\" + name + r"(?![A-Za-z])(\{\})?", lambda _m, v=val: v, tex)
    bib = parse_bib(BIB.read_text(encoding="utf-8"))
    body = tex.split("\\maketitle", 1)[1].split("\\bibliographystyle", 1)[0]
    for front in ("abstract", "IEEEkeywords"):
        body = re.sub(r"\\begin\{" + front + r"\}.*?\\end\{" + front + r"\}", "", body, flags=re.S)

    # numbering: citations in order of first appearance; tables Roman, figures Arabic
    order = []
    for grp in re.findall(r"\\cite\{([^}]+)\}", body):
        for k in grp.split(","):
            if k.strip() not in order:
                order.append(k.strip())
    missing = [k for k in order if k not in bib]
    assert not missing, f"cite keys missing from refs.bib: {missing}"
    cite_no = {k: i + 1 for i, k in enumerate(order)}
    labels, nt, nf = {}, 0, 0
    for m in re.finditer(r"\\begin\{(table\*?|figure)\}(.*?)\\end\{\1\}", body, re.S):
        lab = command_arg(m.group(2), "label")
        if m.group(1).startswith("table"):
            labels[lab] = ROMAN[nt]; nt += 1
        else:
            nf += 1; labels[lab] = str(nf)

    # section labels: a \label directly after a numbered \section gets its Roman number
    n_sec = 0
    for m in re.finditer(r"\\section(\*?)\s*\{[^}]*\}(\s*\\label\{([^}]+)\})?", body):
        if m.group(1):
            continue
        if m.group(3):
            labels[m.group(3)] = ROMAN[n_sec]
        n_sec += 1
    body = re.sub(r"(\\section\s*\{[^}]*\})\s*\\label\{[^}]+\}", r"\1", body)

    def resolve(s: str) -> str:
        s = re.sub(r"\\cite\{([^}]+)\}",
                   lambda m: ", ".join(f"[{cite_no[k.strip()]}]" for k in m.group(1).split(",")), s)
        return re.sub(r"\\ref\{([^}]+)\}", lambda m: labels[m.group(1)], s)

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.space_after = Pt(0)       # template default is 10 pt + 1.15 lines
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.line_spacing = 1.0
    tstyle = doc.styles.add_style("IEEE Table Text", WD_STYLE_TYPE.PARAGRAPH)
    tstyle.base_style = normal
    tstyle.font.size = Pt(8)
    tstyle.paragraph_format.space_before = tstyle.paragraph_format.space_after = Pt(1)
    page_setup(doc.sections[0])
    set_columns(doc.sections[0], 1)

    # --- title + authors (single column)
    title = command_arg(tex, "title")
    p = para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=10)
    add_runs(p, inline(re.sub(r"\\\\", " ", title)), size=24)   # Word wraps; no forced break
    author_src = command_arg(tex, "author")
    names = re.findall(r"\\IEEEauthorblockN\{", author_src)
    blocks = []
    for m in re.finditer(r"\\IEEEauthorblockN\{", author_src):
        name, j = braced(author_src, m.end() - 1)
        k = author_src.index("\\IEEEauthorblockA{", j)
        aff, _ = braced(author_src, k + len("\\IEEEauthorblockA"))
        blocks.append((name, [l for l in re.split(r"\\\\", aff) if l.strip()]))
    at = doc.add_table(rows=1, cols=len(blocks))
    no_table_borders(at)
    for cell, (name, aff) in zip(at.rows[0].cells, blocks):
        cp = cell.paragraphs[0]
        cp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_runs(cp, inline(name), size=11)
        for line in aff:
            q = cell.add_paragraph()
            q.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_runs(q, inline(line), size=10, base={"i": True})
    para(doc, after=6, indent=False, size=6)

    # --- two-column body
    body_sec = doc.add_section(WD_SECTION.CONTINUOUS)
    set_columns(body_sec, 2)

    abstract = env(tex, "abstract")
    p = para(doc, size=9, after=6, indent=True)
    add_runs(p, [("Abstract", {"b": True, "i": True}), ("\u2014", {"b": True})], size=9)
    add_runs(p, inline(resolve(abstract)), size=9, base={"b": True})
    kw = env(tex, "IEEEkeywords")
    p = para(doc, size=9, after=8, indent=True)
    add_runs(p, [("Index Terms", {"b": True, "i": True}), ("\u2014", {"b": True})], size=9)
    add_runs(p, inline(kw), size=9, base={"b": True})

    sec_no, sub_no = 0, 0
    for chunk in re.split(r"\n\s*\n", body):
        chunk = chunk.strip()
        while chunk.startswith("\\section") or chunk.startswith("\\subsection"):
            m = re.match(r"\\(sub)?section(\*?)\s*\{", chunk)
            head, end = braced(chunk, m.end() - 1)
            if m.group(1):                                   # subsection
                label = f"{chr(ord('A') + sub_no)}. "
                sub_no += 1
                para(doc, [(label, {"i": True})] + inline(resolve(head), {"i": True}),
                     align=WD_ALIGN_PARAGRAPH.LEFT, indent=False, before=6, after=3, keep_next=True)
            else:
                if m.group(2):                               # unnumbered (\section*)
                    runs = inline(head, {"sc": True})
                else:
                    runs = [(ROMAN[sec_no] + ". ", {"sc": True})] + inline(resolve(head), {"sc": True})
                    sec_no += 1
                    sub_no = 0
                para(doc, runs, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=10, after=4,
                     keep_next=True)
            chunk = chunk[end:].strip()
        # a chunk may mix paragraph text and environments (e.g. "...:" directly followed by itemize)
        while chunk:
            m_env = re.search(r"\\begin\{(table\*?|figure|itemize)\}", chunk)
            if not m_env:
                para(doc, inline(resolve(chunk)))
                break
            if m_env.start() > 0:
                para(doc, inline(resolve(chunk[:m_env.start()].strip())))
            kind = m_env.group(1)
            end_tag = "\\end{" + kind + "}"
            stop = chunk.index(end_tag, m_env.start()) + len(end_tag)
            block, chunk = chunk[m_env.start():stop], chunk[stop:].strip()
            if kind == "itemize":
                for item in re.split(r"\\item\s+", env(block, "itemize"))[1:]:
                    p = doc.add_paragraph(style="List Bullet")
                    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    add_runs(p, inline(resolve(item.strip())))
            elif kind == "figure":
                render_figure(doc, resolve(block), labels)
            elif kind == "table":
                render_table(doc, resolve(block), labels, COL_W)
            else:                                            # table*: full width
                one = doc.add_section(WD_SECTION.CONTINUOUS)
                set_columns(one, 1)
                render_table(doc, resolve(block), labels, FULL_W)
                two = doc.add_section(WD_SECTION.CONTINUOUS)
                set_columns(two, 2)

    # --- references
    para(doc, [("References", {"sc": True})], align=WD_ALIGN_PARAGRAPH.CENTER, indent=False,
         before=10, after=4, keep_next=True)
    for key in order:
        p = para(doc, size=8, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=False)
        pf = p.paragraph_format
        pf.left_indent, pf.first_line_indent = Inches(0.3), Inches(-0.3)
        pf.tab_stops.add_tab_stop(Inches(0.3))
        add_runs(p, [(f"[{cite_no[key]}]\t", {})] + ieee_reference(bib[key]), size=8)

    doc.core_properties.title = "".join(t for t, _ in inline(title.replace("\\\\", " ")))
    doc.core_properties.author = "; ".join("".join(t for t, _ in inline(n)) for n, _ in blocks)
    doc.save(OUT)
    unused = sorted(set(bib) - set(order))
    print(f"wrote {OUT}: {sec_no} sections, {nt} tables, {nf} figure(s), {len(order)} references"
          + (f" (unused bib keys: {unused})" if unused else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
