# EDIA paper (IEEE conference format)

- `edia_ieee.tex` -- the paper, `IEEEtran` conference class (two-column, IEEE numbered citations).
- `refs.bib` -- bibliography (BibTeX, `IEEEtran` style).
- `NUMBERS.md` -- source file for every number in the paper.
- `edia_ieee.docx` -- the same paper as a Word document in IEEE conference layout, **generated
  from the .tex** by `build_docx.py` (edit the .tex, then rebuild; never edit the .docx by hand).
- `fig_pipeline.png` -- Fig. 1, drawn by `make_figure.py`; used by both the .tex and the .docx.

- `EDIA_explained.docx` -- companion explainer for teammates: the paper section by section, each
  part in plain language ("In simple terms" boxes) and technical detail, plus likely questions
  with answers, a map of the paper's tables and a glossary. Built by `build_explainer.py`
  (numbers hand-copied from the paper; if a result changes, update both).

## Rebuild the Word versions

    .venv\Scripts\python.exe paper/make_figure.py
    .venv\Scripts\python.exe paper/build_docx.py
    .venv\Scripts\python.exe paper/build_explainer.py

## Compile

No TeX distribution is installed on the lab PC. Easiest: upload `edia_ieee.tex` and
`refs.bib` to Overleaf (New Project -> Upload Project); `IEEEtran` is built in. Locally
with any TeX distribution:

    pdflatex edia_ieee
    bibtex   edia_ieee
    pdflatex edia_ieee
    pdflatex edia_ieee

## Status

The paper is complete. Author e-mail addresses are intentionally left out of this draft.
Compile once on Overleaf and check the page count against the target venue's limit.
