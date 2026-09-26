# EDIA paper (IEEE conference format)

- `edia_ieee.tex` -- the paper, `IEEEtran` conference class (two-column, IEEE numbered citations).
- `refs.bib` -- bibliography (BibTeX, `IEEEtran` style).
- `NUMBERS.md` -- source file for every number in the paper.
- `edia_ieee.docx` -- the same paper as a Word document in IEEE conference layout, **generated
  from the .tex** by `build_docx.py` (edit the .tex, then rebuild; never edit the .docx by hand).
- `fig_pipeline.png` -- Fig. 1, drawn by `make_figure.py`; used by both the .tex and the .docx.

## Rebuild the Word version

    .venv\Scripts\python.exe paper/make_figure.py
    .venv\Scripts\python.exe paper/build_docx.py

## Compile

No TeX distribution is installed on the lab PC. Easiest: upload `edia_ieee.tex` and
`refs.bib` to Overleaf (New Project -> Upload Project); `IEEEtran` is built in. Locally
with any TeX distribution:

    pdflatex edia_ieee
    bibtex   edia_ieee
    pdflatex edia_ieee
    pdflatex edia_ieee

## Before submission

- [ ] Resolve every red `[TODO: ...]` (author block, spot-check result, limitations, acknowledgment).
- [ ] Human spot-check done -> `scripts/spotcheck_report.py --dir data/benchmark/spotcheck_mini`,
      numbers into Sec. IV and Sec. VIII.
- [ ] Check each reference's venue/pages against the official proceedings.
- [ ] Check the target venue's page limit and whether it wants the IEEE conference template.
- [ ] Optional: add a pipeline figure (Sec. III).
- [ ] `python -m pytest -q` passes; README reproduce commands work.
