"""Build paper/EDIA_explained.docx -- the whole project explained in plain language AND
technical detail (companion to the IEEE paper; for supervisors, reviewers, teammates).

    .venv\\Scripts\\python.exe paper/build_explainer.py

Every number here comes from the same sources as the paper (see paper/NUMBERS.md).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_docx import TBLPR_ORDER, TCPR_ORDER, insert_ordered  # noqa: E402  (shared XML helpers)

OUT = HERE / "EDIA_explained.docx"
FIG = HERE / "fig_pipeline.png"
BODY_FONT = "Calibri"
SIMPLE_FILL = "EAF2FB"       # light blue: "In simple terms" boxes
HEAD_FILL = "D9E2F3"         # table header rows
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)

doc = Document()


# ----------------------------------------------------------------------------- helpers
def setup():
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)        # A4
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = BODY_FONT, Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
        st = doc.styles[name]
        st.font.size = Pt(size)
        st.font.color.rgb = ACCENT
        st.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
        st.paragraph_format.space_after = Pt(4)
        st.paragraph_format.keep_with_next = True
    # page number in the footer: "Page N"
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run("Page ")
    run.font.size = Pt(9)
    for kind, text in (("begin", None), (None, " PAGE "), ("end", None)):
        r = fp.add_run()
        r.font.size = Pt(9)
        if kind:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = text
            r._r.append(it)


def rich(p, text: str):
    """**bold** and *italic* markup inside a string."""
    import re
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if not part:
            continue
        if part.startswith("**"):
            p.add_run(part[2:-2]).bold = True
        elif part.startswith("*"):
            p.add_run(part[1:-1]).italic = True
        else:
            p.add_run(part)
    return p


def para(text: str = "", style=None, after=None, align=None):
    p = doc.add_paragraph(style=style)
    rich(p, text)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    if align:
        p.alignment = align
    return p


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        rich(p, it)


def shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    insert_ordered(cell._tc.get_or_add_tcPr(), shd, TCPR_ORDER)


def simple_box(*paragraphs: str):
    """Shaded 'In simple terms' call-out (one-cell table)."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.rows[0].cells[0]
    cell.width = Cm(16.6)
    shade(cell, SIMPLE_FILL)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        if edge == "left":
            el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "24"); el.set(qn("w:color"), "2E75B6")
        else:
            el.set(qn("w:val"), "nil")
        borders.append(el)
    insert_ordered(t._tbl.tblPr, borders, TBLPR_ORDER)
    mar = OxmlElement("w:tblCellMar")
    for edge, v in (("top", 90), ("left", 170), ("bottom", 90), ("right", 170)):
        el = OxmlElement(f"w:{edge}"); el.set(qn("w:w"), str(v)); el.set(qn("w:type"), "dxa"); mar.append(el)
    insert_ordered(t._tbl.tblPr, mar, TBLPR_ORDER)
    head = cell.paragraphs[0]
    r = head.add_run("In simple terms")
    r.bold = True
    r.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)
    head.paragraph_format.space_after = Pt(3)
    head.paragraph_format.keep_with_next = True
    for txt in paragraphs:
        if txt.startswith("- "):
            p = cell.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            rich(p, txt[2:])
        else:
            p = cell.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            rich(p, txt)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def technical():
    p = doc.add_paragraph()
    r = p.add_run("Technical detail")
    r.bold = True
    r.font.color.rgb = ACCENT
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True


def table(header, rows, widths_cm, font=9.5, align=None):
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = doc.styles["Table Grid"]
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    align = align or ["l"] * len(header)
    amap = {"l": WD_ALIGN_PARAGRAPH.LEFT, "r": WD_ALIGN_PARAGRAPH.RIGHT, "c": WD_ALIGN_PARAGRAPH.CENTER}
    for ri, row in enumerate([header] + rows):
        for ci, val in enumerate(row):
            cell = t.rows[ri].cells[ci]
            cell.width = Cm(widths_cm[ci])
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.keep_with_next = ri < len(rows)
            p.alignment = amap[align[ci]] if ri else WD_ALIGN_PARAGRAPH.LEFT
            rich(p, str(val))
            for run in p.runs:
                run.font.size = Pt(font)
                if ri == 0:
                    run.bold = True
            if ri == 0:
                shade(cell, HEAD_FILL)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def caption(text):
    p = para(text, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
    for r in p.runs:
        r.font.size = Pt(9)
        r.italic = True


# ----------------------------------------------------------------------------- content
setup()

title = doc.add_paragraph(style="Title")
title.add_run("EDIA, explained")
sub = doc.add_paragraph(style="Subtitle")
sub.add_run("What we built, what we found, and why it matters \u2014 in plain language and in technical detail")
para(f"Project: EDIA (Extraction of Decision Information from Artifacts) \u00b7 Branch: Jaitra \u00b7 "
     f"Status as of {date(2026, 9, 26):%d %B %Y} \u00b7 Companion to the IEEE paper draft (paper/edia_ieee.tex / .docx)",
     after=10)

doc.add_heading("How to read this document", level=1)
para("Every section has two layers. The shaded **In simple terms** box explains the idea without jargon; "
     "anyone can read just those boxes and follow the whole story. The **Technical detail** that follows "
     "gives the exact methods, settings and numbers, as a reviewer or supervisor would need them. A glossary "
     "at the end defines every technical term. All numbers match the paper and are traced to their source "
     "files in paper/NUMBERS.md.")
para("**Contents.** 1 The problem \u00b7 2 The data \u00b7 3 How EDIA works \u00b7 4 How we measure \u00b7 "
     "5 Finding: detecting what is missing \u00b7 6 Finding: the human check \u00b7 7 Finding: the extraction "
     "ceiling \u00b7 8 Finding: does the AI make things up? \u00b7 9 Finding: do other methods do better? \u00b7 "
     "10 The machine change \u00b7 11 Problems found and fixed \u00b7 12 What the results do not show \u00b7 "
     "13 What would do better \u00b7 14 Where everything is \u00b7 15 Glossary")

doc.add_heading("The headline, in one paragraph", level=2)
simple_box(
    "Meetings produce decisions, but the *reasons* behind them (the options rejected, the worries raised, the "
    "conditions attached) mostly never reach the written minutes. We built a system that tries to find those "
    "reasons in a meeting transcript and to spot which ones the minutes left out. It works only partly: it "
    "finds roughly **a third to a half** of the reasons a person finds. The ones it misses are mostly "
    "reasons spread across distant parts of the meeting or never said outright, and three popular alternative "
    "methods do not fix that. So the limit seems to be a real, current gap in what AI can do, not a bug.")

# 1 -------------------------------------------------------------------------------------------
doc.add_heading("1. The problem", level=1)
simple_box(
    "Imagine a team spends an hour choosing a battery for a new remote control. They weigh two options, one "
    "person worries about cost, and they agree to revisit it if the price changes. The minutes say only: "
    "*\u201cBattery: kinetic.\u201d* Months later, nobody remembers why. Each reason that was said in the "
    "meeting but dropped from the minutes is what we call a **gap**.",
    "The question of this project: **can today\u2019s AI (1) pull those reasons out of a meeting and (2) tell "
    "which of them the minutes lost?** Rather than assume it can, we measured it carefully and asked where "
    "and why it breaks.")
technical()
para("A *decision-context gap* is a reasoning element voiced in the meeting transcript but absent from the "
     "filed document. Reasoning elements are typed: decision, alternative, rationale, condition, dissent, owner "
     "and approver. The task has two parts: **extraction** (transcript \u2192 structured decision records) and "
     "**gap detection** (given a document and an element, decide whether the document carries it). The project "
     "is framed as a feasibility study and comparative analysis. The aim is to measure the ceiling honestly and "
     "diagnose it, not to maximise a score.")

# 2 -------------------------------------------------------------------------------------------
doc.add_heading("2. The data: adhd_v1", level=1)
simple_box(
    "To test the system we need meetings where we already know the right answer. We have three kinds:",
    "- **5 real meetings checked by a person.** The most trustworthy answers, but very few.",
    "- **227 real meetings labelled automatically by an AI model.** Lots of data, but the labels are only "
    "as good as that model, and we later found they are quite biased (section 6).",
    "- **139 invented meetings** where we decided the answers *before* writing the meeting, so the answers "
    "are known by construction. Only these have a roughly even mix of \u201cmissing\u201d and "
    "\u201cpresent\u201d items, which makes them the fairest place to compare methods.")
technical()
table(["Tier", "Pairs", "Elements", "Gap rate", "How the labels were made"],
      [["Gold (QMSum)", "5", "50", "0.76", "Human, checked against transcript spans"],
       ["Corpus (QMSum)", "227", "4,930", "0.93", "NLI model (roberta-large-mnli) at threshold 0.55: \u201csilver\u201d"],
       ["Synthetic", "139", "1,667", "0.59", "Constructed: each element\u2019s fate fixed before the text is written"],
       ["**Total**", "**371**", "**6,647**", "0.84", ""]],
      [3.2, 1.4, 1.8, 1.8, 8.4], align=["l", "r", "r", "r", "l"])
bullets([
    "Source: QMSum, 232 meetings in three domains: Academic (ICSI research-group meetings, 59), Committee "
    "(parliamentary committees, 36) and Product (AMI product-design meetings, 137 = 132 corpus + 5 gold). "
    "QMSum\u2019s written summaries stand in for filed minutes.",
    "Corpus elements come from splitting 1,543 query-based summary answers into 4,930 sentences. The NLI "
    "threshold 0.55 was chosen on the gold pairs.",
    "**Circularity rule:** corpus labels were made by the NLI detector, so scoring NLI against them measures "
    "self-consistency, not accuracy. Those rows are never quoted.",
    "Synthetic pairs span 12 organisational domains \u00d7 10 decision archetypes, generated by Mistral 7B with an "
    "automated leak check. They are cleaner than real speech, which is a known limitation.",
    "The dataset is **locked**. No data was added or regenerated during this work.",
])

# 3 -------------------------------------------------------------------------------------------
doc.add_heading("3. How EDIA works", level=1)
simple_box(
    "EDIA works like a careful note-taker in three steps. **First**, it cuts a long meeting into bite-sized "
    "pieces. **Second**, an AI model reads each piece and fills in a form for every decision: what was decided, "
    "the alternatives, the reasons, the conditions, any disagreement, plus exact quotes as evidence. "
    "**Third**, a checker compares each reason with the minutes and flags the ones that are missing.")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(FIG), width=Inches(4.6))
caption("Figure 1. The EDIA pipeline (same figure as in the paper). Grey: extraction; dashed: evaluation.")
technical()
bullets([
    "**Chunking:** at most 1,200 tokens per chunk, with a two-turn overlap so a sentence cut at a boundary "
    "appears in both chunks.",
    "**Extraction model:** Mistral 7B served locally by Ollama, fully deterministic: temperature 0, top-k 1, "
    "top-p 1, seed 0, 8,192-token context, 2,048-token output cap. Output is constrained to JSON, and one repair "
    "call is made if the JSON is malformed. The prompt forbids inference beyond the excerpt and requires quotes "
    "to be copied character for character.",
    "**Record schema:** decision, topic, status (decided / provisional / deferred / rejected / unclear), "
    "alternatives (with rejected flag and reason), rationale, conditions, dissent, owner, approver, and evidence "
    "quotes with speaker and the field each quote supports.",
    "**Gap detectors** (element predicted \u201cgap\u201d if its present-score < 0.55): *lexical* (token-F1 "
    "overlap with the document); *NLI* (entailment probability under roberta-large-mnli); *LLM judge* "
    "(Mistral 7B asked whether the element\u2019s substance is present, returning a verdict and confidence); and "
    "*ensemble* (each member\u2019s score is shifted by that member\u2019s own threshold so 0.5 means "
    "\u201cpresent\u201d, then the maximum is taken: present if any member says present).",
])

# 4 -------------------------------------------------------------------------------------------
doc.add_heading("4. How we measure, and why some numbers lie", level=1)
simple_box(
    "Most reasons really are missing from minutes: in the automatically labelled meetings, 93% are. That creates "
    "a trap. A lazy checker that always answers \u201cmissing\u201d looks 96% good on the usual score (F1), "
    "without doing anything. So we use **balanced accuracy**, which averages how well a method does on "
    "\u201cmissing\u201d items and on \u201cpresent\u201d items separately. The lazy checker gets exactly 50%, "
    "which is what it deserves.",
    "A second trap: when we check whether the system found a reason, strict word-matching misses correct answers "
    "that are worded differently. So we always report **two** scores, a strict one (matching words) and a "
    "lenient one (matching meaning), and never pick the flattering one.")
technical()
bullets([
    "**Balanced accuracy** = (gap recall + present recall) / 2. Any constant detector scores 0.5 regardless of "
    "class skew. **Present-class F1** is reported alongside, because the present class is the hard half.",
    "**Completeness** = fraction of hand-labelled reasoning elements matched by some extracted element. "
    "*Lexical:* token-F1 \u2265 0.45. *Semantic:* cosine similarity of all-MiniLM-L6-v2 sentence embeddings "
    "\u2265 0.55. Totals are **pooled** (sum matched / sum ground truth), not averaged per meeting.",
    "**Unsupported-quote (hallucination) rate:** fraction of evidence quotes not found in their own source "
    "chunk after normalising case, punctuation and whitespace, and ignoring transcription markers "
    "(e.g. {disfmarker}) and filler words (um, uh, \u2026).",
])

# 5 -------------------------------------------------------------------------------------------
doc.add_heading("5. Finding: detecting what is missing \u2014 simple word overlap wins", level=1)
simple_box(
    "Surprisingly, the simplest checker, which just counts shared words, beat a model designed to understand "
    "whether one sentence follows from another (called NLI). The NLI model is good at noticing when something is "
    "missing, but bad at noticing when it is **there**: it failed to recognise reworded reasons about two times "
    "in three, and even reasons **copied word for word** most of the time.",
    "A general-purpose AI judge (Mistral 7B, asked \u201cis this in the minutes?\u201d) said \u201cyes\u201d to "
    "about 95% of everything, including obvious omissions, which makes it no better than a coin.")
technical()
table(["Detector", "Tier / sample", "n", "Gap F1", "Balanced acc.", "Present F1"],
      [["NLI", "gold", "50", "0.861", "0.656", "0.476"],
       ["NLI", "synthetic", "1,667", "0.771", "0.629", "0.468"],
       ["Lexical", "gold", "50", "0.884", "0.583", "0.286"],
       ["Lexical", "synthetic", "1,667", "0.857", "**0.775**", "**0.715**"],
       ["NLI", "same sample (gold + synthetic)", "200", "\u2013", "0.611", "0.432"],
       ["Lexical", "same sample", "200", "\u2013", "**0.728**", "**0.637**"],
       ["LLM judge", "same sample", "200", "\u2013", "0.492", "0.596"],
       ["Ensemble", "same sample", "200", "\u2013", "0.521", "0.624"]],
      [2.3, 5.0, 1.4, 1.6, 2.6, 2.3], align=["l", "l", "r", "r", "r", "r"])
bullets([
    "**Accuracy by label** (gold + synthetic only; the NLI-labelled corpus is excluded as circular): true gaps: "
    "NLI 0.916, lexical 0.974. Paraphrased-present: NLI **0.366**, lexical 0.640. Verbatim-present: NLI "
    "**0.292**, lexical 0.453. Against a compressed ~100-word summary, almost every source sentence reads as "
    "\u201cnot entailed\u201d.",
    "**LLM judge**, 296-element stratified sample: gap recall 0.047, balanced accuracy 0.495. The inputs were "
    "verified (short summaries, correct labels), so this is a genuine yes-bias under a fixed prompt, not a "
    "pipeline error. The ensemble (present if any member says present) inherits the bias: 0.516 at the "
    "common 0.55 threshold, and at its designed 0.5 operating point it labels every sampled element present.",
    "**Base-rate distortion example:** on Committee meetings the lexical detector has the highest gap F1 of any "
    "bucket (0.988) and the lowest balanced accuracy (0.532), because nearly everything there is a gap.",
    "Why the \u201csame sample\u201d rows: the LLM/ensemble were run on a 296-element stratified sample (the "
    "\u201c--llm-sample 400\u201d flag is a per-cell cap). Scoring all four detectors on the same 200 gold + "
    "synthetic elements makes the comparison like for like.",
])

# 6 -------------------------------------------------------------------------------------------
doc.add_heading("6. Finding: the human spot-check", level=1)
simple_box(
    "The 227 automatically labelled meetings were labelled by the same NLI model that, as section 5 shows, "
    "struggles to see reworded content. So a person checked a random sample of those labels by hand, without "
    "seeing what the model had said (\u201cblind\u201d).",
    "Result: whenever the person said an item was missing, the model agreed. But **about half of the items the "
    "model called missing were actually in the minutes, just reworded.** The automatic labels therefore "
    "exaggerate how much is missing.")
technical()
table(["Measure", "Value"],
      [["Annotator / blinding", "1 human annotator, blind to the silver labels (all 52 labels made by the human)"],
       ["Sample", "52 elements from 3 randomly drawn corpus pairs: QMS_ACA_TR_002, QMS_ACA_TR_009, QMS_CMT_TR_007"],
       ["Gap class", "precision 0.478, recall 1.0 (silver never missed a human-seen gap)"],
       ["Present class", "recall 0.20: silver called 24 of the 30 human-\u201cpresent\u201d items gaps"],
       ["Balanced accuracy", "0.60 (a constant labeller scores 0.5)"],
       ["Disagreements", "24 (23 paraphrased); same direction in all 3 pairs; 19 come from the Committee pair"]],
      [4.2, 12.4])
para("**Caveats:** small sample, one annotator (so no inter-annotator agreement / Cohen\u2019s kappa), and no "
     "Product pair (a fourth, Product, pair was drawn but not annotated). The earlier \u201cbalanced accuracy "
     "0.836 / ~7% false gaps\u201d figure came from a *model* review pass (llm-review), not a human, and is "
     "superseded. It must not be cited as validation.")

# 7 -------------------------------------------------------------------------------------------
doc.add_heading("7. Finding: the extraction ceiling", level=1)
simple_box(
    "On the 5 meetings a person labelled, EDIA found **between 33% and 58%** of the reasons the person found. "
    "The strict (word-matching) score gives the lower number; the meaning-based score gives the higher one. "
    "Many strict \u201cmisses\u201d were actually correct answers phrased differently.",
    "We then read every remaining miss by hand. **Over half (11 of 20)** were reasons scattered across far-apart "
    "parts of the meeting (in one case about 670 turns apart), or never stated outright and only implied. "
    "Importantly, **none** was caused by where we cut the meeting into pieces, so simply giving the AI a bigger "
    "window would not help.")
technical()
table(["Meeting", "Lexical", "Semantic"],
      [["QSUM_001", "0.455", "0.636"], ["QSUM_002", "0.500", "0.875"], ["QSUM_003", "0.111", "0.222"],
       ["QSUM_004", "0.286", "0.643"], ["QSUM_005", "0.333", "0.500"],
       ["**Pooled**", "**0.333** (16/48)", "**0.583** (28/48)"]],
      [4.0, 4.0, 4.0], align=["l", "r", "r"])
table(["Failure category (20 semantic-residual misses, read manually)", "n", "Share"],
      [["Multi-hop, implicit: connection never stated, must be inferred", "6", "30%"],
       ["Multi-hop, scattered: reasoning spread across turns far apart", "5", "25%"],
       ["Paraphrase miss: found, but the scorer did not match it", "5", "25%"],
       ["Out of scope: present and local, but not extracted", "4", "20%"],
       ["Chunk boundary", "0", "0%"], ["Hallucination (a fabricated quote caused the miss)", "0", "0%"]],
      [12.0, 1.5, 2.0], align=["l", "r", "r"])
bullets([
    "14 of the 32 lexical misses are correct extractions that token overlap under-credits. For example, the "
    "headline decision \u201cKryptonite was chosen as the preferred energy source\u201d scores only 0.36. So the "
    "lexical figure is a floor.",
    "The unsupported-quote rate on these 5 meetings is **16.4%**. \u201cZero hallucination misses\u201d means "
    "no *miss* was caused by fabrication. It does **not** mean the extractor never produces unsupported quotes.",
    "The retired \u201c~47% completeness\u201d figure averaged two meetings under lexical scoring before the "
    "others were scored. The honest figure is the 33.3\u201358.3% range.",
])

# 8 -------------------------------------------------------------------------------------------
doc.add_heading("8. Finding: across all 227 meetings \u2014 does the AI make things up?", level=1)
simple_box(
    "We can only measure \u201chow much did it find\u201d on the 5 person-labelled meetings. But on all 227 real "
    "meetings we *can* check something else: whether the quotes the AI gives as evidence really appear in the "
    "transcript. Overall, about **15%** could not be found, even after allowing for punctuation and "
    "\u201cum\u201d/\u201cuh\u201d.",
    "Academic meetings looked much worse (27%). But when we looked closer, most of those quotes were real "
    "sentences the AI had **tidied up**: dropping stutters, repeated words and false starts, which are very "
    "common in those research-group recordings. Counting only quotes that are more than just tidied, all three "
    "meeting types land between 3.6% and 7.6%. That suggests the extractor behaves similarly everywhere.")
technical()
table(["Domain", "Meetings", "Quotes", "Unsupported (official)", "Excluding near-verbatim tidying"],
      [["Academic", "59", "6,341", "26.7%", "7.6%"], ["Committee", "36", "5,441", "5.1%", "3.6%"],
       ["Product", "132", "10,167", "12.0%", "5.1%"], ["**All**", "**227**", "**21,949**", "**14.6%**", "**5.4%**"]],
      [2.6, 2.0, 2.2, 4.0, 5.8], align=["l", "r", "r", "r", "r"])
bullets([
    "*Near-verbatim* = every word of the quote appears, in order, in its own chunk, within a window of 1.5\u00d7 "
    "the quote length + 3 words (words dropped, none added or changed). 72% of Academic unsupported quotes are "
    "near-verbatim. The official figure is the strict one; the tidying split explains the domain gap and does "
    "not replace it (scripts/quote_fidelity_diagnostic.py).",
    "Run: 3,532 chunks in about 5.4 hours on an RTX 3090 (about 5 s per chunk; the old RTX 3050 needed about "
    "85 s). 36 chunks (1.0%) failed because Ollama aborted a generation stuck in a repetition loop (\u201ctoken "
    "repeat limit reached\u201d). This is deterministic at temperature 0 and at the same rate as the old machine. "
    "A fallback fix was prepared but not needed below the agreed 5% threshold.",
])

# 9 -------------------------------------------------------------------------------------------
doc.add_heading("9. Finding: do other methods do better?", level=1)
simple_box(
    "We tried three well-known alternatives on the same 5 meetings, using the same AI model wherever one is "
    "needed:",
    "- **\u201cThink step by step\u201d (chain-of-thought):** the AI first writes notes, then fills in the "
    "form. A tiny gain of 2\u20133 more reasons found out of 48, and it produced 50% more records, so part of the "
    "gain may just be more guesses. Precision confirms it: once the extra output is counted, its F1 "
    "actually drops (22.0% to 18.3%).",
    "- **GraphRAG** (Microsoft\u2019s knowledge-graph method): much worse, at 4\u201319%. It organises the "
    "meeting around people and things (\u201cthe Project Manager\u201d) rather than decisions and reasons.",
    "- **Multi-hop retrieval** (search for the reason, then use it to search for alternatives, and so on): "
    "about 13% (and 0% under strict word matching), even though it was *given* the decisions. The first search already goes wrong, and each step "
    "compounds the error.",
    "None breaks the ceiling. Each fails for an understandable reason, and it is the same underlying difficulty "
    "each time.")
technical()
table(["Approach", "Completeness (lex)", "Completeness (sem)", "Unsupported quotes", "Runtime"],
      [["EDIA pipeline (stored baseline)", "33.3%", "58.3%", "16.4%", "Ollama 0.32.1 / RTX 3050"],
       ["EDIA pipeline, re-run", "27.1%", "58.3%", "14.1%", "0.34.4 / RTX 3090"],
       ["EDIA + chain-of-thought", "33.3%", "62.5%", "13.9%", "0.34.4 / RTX 3090"],
       ["GraphRAG (local search)", "4.2%", "14.6\u201318.8%", "\u2013", "0.34.4 / RTX 3090"],
       ["Multi-hop retrieval", "0.0%", "12.8%", "0 (retrieves only)", "none (TF-IDF, no LLM)"]],
      [4.6, 2.6, 2.8, 2.8, 3.8], align=["l", "r", "r", "r", "l"])
bullets([
    "**Chain-of-thought** is implemented as two calls per chunk: an unconstrained call writes notes, then the "
    "normal JSON-constrained extraction is conditioned on them. (A single JSON-constrained call cannot emit "
    "reasoning tokens.) Against the *same-runtime* baseline: +6.2 points lexical, +4.2 semantic (3 and 2 of 48 "
    "elements). Hallucination is unchanged (13.9% vs 14.1%). Records: 114 vs 76.",
    "**GraphRAG 3.2.0**, default configuration and prompts, local search with the plan\u2019s query (\u201cWhat "
    "decisions were made and what reasoning was given?\u201d), mistral + nomic-embed-text through Ollama. The "
    "prose answer is restructured into our schema by one deterministic \u201crestate only\u201d call. Items "
    "whose content words are less than 80% present in the answer are dropped, because the converter was seen "
    "inventing an alternative. 14.6% is with that filter, 18.8% without it; both are reported.",
    "**Multi-hop retrieval:** TF-IDF over transcript turns, top-3 per hop, rationale \u2192 alternatives "
    "\u2192 objections, seeded with the true decisions. The fair column excludes the seeded decisions (5/41).",
])

# 10 ------------------------------------------------------------------------------------------
doc.add_heading("10. The machine change, and why the \u201csame model\u201d is not always the same", level=1)
simple_box(
    "Halfway through, the project moved from a laptop (RTX 3050) to a lab PC (RTX 3090) that also had a newer "
    "version of Ollama, the program that runs the AI model. Even with the identical model file and identical "
    "settings, some answers came out slightly different. When we re-ran the basic system on the new setup, its "
    "strict score moved from 33% to 27% with no change to the method at all.",
    "So we followed one rule: **compare methods only when they ran on the same setup.** That is why the table "
    "above has two EDIA rows.")
technical()
table(["Period", "Runtime", "What ran on it"],
      [["Before handoff", "Ollama 0.32.1 / RTX 3050", "5 gold extractions (Table 2), original QMS_ACA_TR_000"],
       ["24 Sep 2026", "Ollama 0.34.3 / RTX 3090", "Corpus extraction (all 227 meetings; ACA_TR_000 re-extracted), \u00a74.3"],
       ["26 Sep 2026", "Ollama 0.34.4 / RTX 3090", "LLM/ensemble ablation, CoT + same-runtime baseline, GraphRAG"]],
      [3.2, 4.4, 9.0])
bullets([
    "Replaying 3 already-extracted chunks on 0.34.3: 1 identical, 2 different. Whether the version or the GPU "
    "causes this was not isolated; the 0.32.1 installer was not tried (user decision).",
    "Ollama auto-updated to 0.34.4 after the corpus run had finished. Auto-update was then disabled, and the "
    "version was checked at the start and end of every phase.",
    "Even within one runtime and session, the LLM judge returned a different confidence on 7 of 296 repeated "
    "calls (3 verdicts flipped). The cause was not isolated, but temperature 0 fixes the *settings*, not "
    "bit-for-bit outputs.",
    "Recommendation carried into the paper: extraction studies should report the inference-engine version "
    "alongside the model, because \u201csame weights, temperature 0\u201d is not enough for reproducibility.",
])

# 11 ------------------------------------------------------------------------------------------
doc.add_heading("11. Problems found and fixed along the way", level=1)
simple_box(
    "While running everything, several things were found that would have made a number wrong or misleading. "
    "Each was fixed before it could reach the paper. This section is the audit trail, so a reviewer can see "
    "exactly what was checked.")
technical()
table(["Problem found", "What would have gone wrong", "Fix"],
      [["Pooled NLI accuracy on gaps (0.985) was 82% circular", "Overstated NLI on true gaps",
        "Recomputed on independent labels: 0.916 (scripts/paper_detector_checks.py)"],
       ["\u201cThe extractor invented nothing\u201d in the results notes", "False claim: 16.4% of quotes unsupported",
        "Rewritten: no *miss* was caused by hallucination"],
       ["CoT compared with an old-runtime baseline", "CoT effect mixed with the runtime change",
        "Same-runtime baseline added (--no-cot)"],
       ["CoT script averaged per meeting, not pooled", "Baseline 33.7 / 57.5 instead of 33.3 / 58.3",
        "Pooled everywhere"],
       ["CoT scorer never received chunk text", "Quotes 0/0: Table 4 would show CoT hallucination 0%",
        "Chunk text passed: 13.9%"],
       ["LLM-only gap run overwrote Table 1\u2019s results file", "NLI / lexical rows lost from Table 1",
        "All four detectors rendered together; NLI / lexical verified unchanged"],
       ["Comparison table mixed two runtimes", "CoT would look like +0.0 lexical",
        "Same-runtime EDIA row and a runtime note"],
       ["GraphRAG converter invented content", "Could inflate GraphRAG\u2019s score",
        "Support filter + reported sensitivity range (14.6\u201318.8%)"],
       ["GraphRAG: no output cap, 25 parallel requests vs 1-slot server", "Runaway generations, endless timeouts",
        "max_tokens 2048, concurrent_requests 1"],
       ["Network blocks the tokenizer and HuggingFace downloads (TLS interception)", "GraphRAG failed; 27-minute stalls",
        "Verified tokenizer file cached in data/; offline mode"],
       ["Spot-check sampler deletes its output folder; report overwrites a committed file", "Loss of the earlier annotations / report",
        "New folder used; original report restored; README warning"],
       ["Academic hallucination 26.7% looked alarming", "Misread as a domain failure",
        "Diagnosed as tidying of disfluent speech (72% near-verbatim)"],
       ["Retired numbers (~47%; 0.836 model-only spot-check)", "Would overstate results or validation",
        "Excluded from the paper; docs corrected"],
       ["Ollama stored models on D:\\; --limit 1 hit a cached meeting; re-runs skip failed chunks", "Setup failure; a timing of 0.4 s; silent non-retries",
        "Models copied to D:\\; timed with --limit 2; documented in the runbook"]],
      [5.4, 4.8, 6.4], font=8.5)

# 12 ------------------------------------------------------------------------------------------
doc.add_heading("12. What the results do not show", level=1)
simple_box(
    "Honest limits matter as much as results. These are the main things this study **cannot** claim.")
bullets([
    "**Completeness is measured on only 5 meetings, all Product design.** Across all three domains we measured "
    "grounding (hallucination), not completeness. So we cannot claim the 33\u201358% ceiling holds everywhere.",
    "**The automatic corpus labels overstate gaps.** The human check found that about half of their "
    "\u201cgaps\u201d are actually present in the minutes. Corpus-tier figures are upper bounds.",
    "**The human check is small:** 52 items, one person, no Product meeting, so no agreement statistic between "
    "two people is possible.",
    "**Synthetic meetings are AI-written** and cleaner than real speech.",
    "**QMSum summaries stand in for real filed minutes.**",
    "**Only 7B-scale open models were used**, run locally. Larger models may behave differently.",
    "**Runtime sensitivity:** results can shift slightly across inference-engine versions (section 10).",
])

# 13 ------------------------------------------------------------------------------------------
doc.add_heading("13. What would do better", level=1)
simple_box(
    "The missing reasons are scattered or implied. Longer context windows, step-by-step thinking, knowledge "
    "graphs and chained searches all fail to find them. A method that follows a decision **through the whole "
    "meeting** is more likely to work: linking later remarks back to the proposal they respond to, before trying "
    "to fill in the form.")
technical()
bullets([
    "Discourse- or thread-level modelling of a decision across the full transcript (reply structure, "
    "coreference to proposals) before extraction, rather than similarity-based retrieval.",
    "A larger, multi-annotator human validation of the corpus labels (with Cohen\u2019s kappa), including "
    "Product meetings.",
    "Completeness ground truth for Academic and Committee meetings.",
    "Replication with larger models and with the inference-engine version pinned.",
])

# 14 ------------------------------------------------------------------------------------------
doc.add_heading("14. Where everything is", level=1)
simple_box(
    "Everything lives in the project folder D:\\EIDA (backed up on the pendrive at E:\\EIDA) and is saved in git "
    "history. The paper is in paper/, the results are in outputs/, and SESSION_LOG.md says what was done and "
    "what comes next.")
technical()
table(["What", "Where"],
      [["Paper (LaTeX / Word / figure / sources)", "paper/edia_ieee.tex, edia_ieee.docx, fig_pipeline.png, refs.bib, NUMBERS.md"],
       ["This explainer", "paper/EDIA_explained.docx (built by paper/build_explainer.py)"],
       ["Gap detection (Table 1)", "outputs/gap_eval_results.md, outputs/paper_detector_checks.md"],
       ["Completeness (Table 2) and failure taxonomy (Table 3)", "outputs/task4_extraction_scores*.json, outputs/failure_taxonomy.md"],
       ["Corpus grounding by domain", "outputs/corpus_extraction_results.md, outputs/corpus_quote_fidelity.md"],
       ["CoT, GraphRAG, multi-hop, Table 4", "outputs/cot_ablation_results.md, graphrag_results.md, multihop_retrieval_results.md, comparative_analysis.md"],
       ["Human spot-check", "data/benchmark/spotcheck_mini/, outputs/qmsum_spotcheck_mini_report.json"],
       ["How every step was run; resume point", "CONTINUATION_RUNBOOK.md, SESSION_LOG.md"]],
      [5.6, 11.0], font=9)
para("**Reproduce (from D:\\EIDA, with the venv):** python -m pytest -q (159 passed, 2 skipped) \u00b7 "
     "scripts/run_gap_eval.py --detectors nli lexical llm ensemble --llm-sample 400 --threshold 0.55 \u00b7 "
     "scripts/run_corpus_extraction.py --rescore-only \u00b7 scripts/run_cot_ablation.py [--no-cot] \u00b7 "
     "scripts/run_graphrag_comparison.py \u00b7 scripts/multihop_retrieval.py \u00b7 "
     "scripts/build_comparison_table.py \u2026 (exact flags in SESSION_LOG.md). Cached results make most of these "
     "run in seconds. Set HF_HUB_OFFLINE=1 on the lab network.")

# 15 ------------------------------------------------------------------------------------------
doc.add_heading("15. Glossary", level=1)
table(["Term", "In simple terms", "Technically"],
      [["Gap", "A reason said in the meeting but left out of the minutes", "Reasoning element absent from the filed document (gold label \u201comitted\u201d)"],
       ["Reasoning element", "One piece of \u201cwhy\u201d: an option, a reason, a worry, a condition", "Typed unit: decision / alternative / rationale / condition / dissent / owner / approver"],
       ["Gold / silver / constructed labels", "Answers checked by a person / guessed by a model / known by design", "Human-annotated / NLI-produced / fixed before text generation"],
       ["NLI (entailment)", "A model that judges whether one text implies another", "roberta-large-mnli, P(entailment | document, element)"],
       ["LLM judge", "Asking a chatbot-style model \u201cis this in there?\u201d", "Mistral 7B with a JSON verdict + confidence prompt"],
       ["Base rate", "How common the \u201cmissing\u201d answer is", "Prior probability of the gap class (0.93 in the corpus)"],
       ["F1 / precision / recall", "How right and how complete the answers are", "Harmonic mean of precision (correct among flagged) and recall (found among true)"],
       ["Balanced accuracy", "A fair score where guessing the common answer gets 50%", "Mean of per-class recall"],
       ["Completeness", "Share of the person\u2019s reasons the system found", "Matched ground-truth elements / all ground-truth elements"],
       ["Lexical vs semantic matching", "Same words vs same meaning", "Token-F1 \u2265 0.45 vs MiniLM cosine \u2265 0.55"],
       ["Hallucination / unsupported quote", "Evidence the AI gave that is not in the transcript", "Quote not found in its own chunk after normalisation"],
       ["Chunk", "A bite-sized piece of the meeting", "\u2264 1,200 tokens, 2-turn overlap"],
       ["Temperature 0 / deterministic settings", "The AI is told to always pick its top answer (almost always the same)", "Greedy decoding (top-k 1, fixed seed); outputs can still vary slightly across runtimes and runs"],
       ["Chain-of-thought (CoT)", "Asking the AI to think step by step first", "Unconstrained notes pass + constrained extraction pass"],
       ["GraphRAG", "Microsoft\u2019s method that builds a map of people and things, then searches it", "Entity graph + community summaries; local search"],
       ["Multi-hop retrieval", "Search, then use the result to search again", "Chained TF-IDF retrieval: rationale \u2192 alternatives \u2192 objections"],
       ["Multi-hop reasoning", "Connecting clues spread far apart", "Evidence for one element spans distant, non-adjacent turns"],
       ["Ollama / runtime", "The program that runs the AI model on the PC", "Local inference server (llama.cpp-based); version affects outputs"]],
      [3.4, 6.2, 7.0], font=8.5)

doc.core_properties.title = "EDIA, explained"
doc.core_properties.author = "Jaitra Shah"
doc.save(OUT)
print(f"wrote {OUT}")
