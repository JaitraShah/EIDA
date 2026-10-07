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

## Before submission

Done (2026-10-07): authors and affiliation filled in; EDIA expanded on first use
(`\EDIAfull` macro in the preamble -- change the name there only); draft TODOs,
acknowledgment placeholder and domain-expert note removed; human spot-check
reported (Sec. IV, VIII); references completed with pages/volumes; pipeline
figure in; static checks clean (braces, environments, every \ref and \cite
resolves); Word version is 5 pages.

Still yours to do:
- [ ] Add the four e-mail addresses -- the only remaining red `[TODO: email]`
      markers (author block at the top of `edia_ieee.tex`), then rebuild the .docx.
- [ ] Compile once on Overleaf and check the page count against the venue limit
      (the .docx is 5 pages; IEEE conferences are usually 6).
- [ ] If the venue is double-blind, remove the author block and the NMIMS
      affiliation before submitting.
- [ ] Confirm author order.
