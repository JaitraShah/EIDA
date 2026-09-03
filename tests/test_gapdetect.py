"""Gap-detector logic -- lexical + metrics run offline; NLI is guarded."""
import pytest

from edia.benchmark.dataset import InDocument
from edia.gapdetect.base import BaseGapDetector, label_from_present_score
from edia.gapdetect.lexical import LexicalGapDetector
from edia.gapdetect.metrics import GapMetrics, sweep_threshold


# --- the shared present/gap rule --------------------------------------------

def test_label_rule():
    assert label_from_present_score(0.9, 0.5) is InDocument.PRESENT_UNSPECIFIED
    assert label_from_present_score(0.5, 0.5) is InDocument.PRESENT_UNSPECIFIED  # >= is present
    assert label_from_present_score(0.49, 0.5) is InDocument.OMITTED


def test_base_detector_mixin():
    class Fake(BaseGapDetector):
        name = "fake"
        threshold = 0.6

        def present_score(self, document, element_text):
            return 0.8 if "yes" in element_text else 0.1

    d = Fake()
    assert d.label_element("doc", "yes here") == (InDocument.PRESENT_UNSPECIFIED, 0.8)
    assert d.is_gap("doc", "no") is True
    assert d.is_gap("doc", "yes") is False


# --- lexical detector -------------------------------------------------------

def test_lexical_present_vs_gap():
    d = LexicalGapDetector()
    doc = ("Kryptonite was chosen as the preferred energy source. "
           "Rollout starts in March.")
    present_lab, present_s = d.label_element(
        doc, "Kryptonite was chosen as the energy source."
    )
    gap_lab, gap_s = d.label_element(
        doc, "The industrial designer preferred a battery and was sceptical of the dynamo."
    )
    assert present_lab is InDocument.PRESENT_UNSPECIFIED
    assert gap_lab is InDocument.OMITTED
    assert present_s > gap_s


def test_lexical_cannot_see_paraphrase():
    """The weakness the NLI detector exists to fix: reworded content reads as a gap."""
    d = LexicalGapDetector()
    doc = "The board green-lit the platform move."
    lab, _ = d.label_element(doc, "Migration to the new platform was approved.")
    assert lab is InDocument.OMITTED


# --- ensemble vote maths (no models) --------------------------------------

def test_ensemble_present_if_any_member_says_present():
    from edia.gapdetect.ensemble import EnsembleGapDetector

    class Member:
        def __init__(self, name, score):
            self.name = name
            self._s = score

        def present_score(self, d, e):
            return self._s

    ens = EnsembleGapDetector.__new__(EnsembleGapDetector)
    ens.threshold = 0.5
    ens.with_llm = False
    # nli well-below its threshold (gap), lexical well-above its threshold (present)
    ens._members = [(Member("nli", 0.02), 0.55), (Member("lexical", 0.9), 0.45)]
    assert ens.present_score("d", "e") >= 0.5          # lexical rescues
    assert ens.is_gap("d", "e") is False

    # both members below their thresholds -> gap
    ens._members = [(Member("nli", 0.02), 0.55), (Member("lexical", 0.1), 0.45)]
    assert ens.is_gap("d", "e") is True


# --- metrics --------------------------------------------------------------

def test_gap_metrics_basic():
    m = GapMetrics()
    for pred, act in [(True, True), (True, True), (False, True), (False, False), (True, False)]:
        m.add(pred, act)
    assert (m.tp, m.fn, m.tn, m.fp) == (2, 1, 1, 1)
    assert m.precision == pytest.approx(2 / 3)
    assert m.recall == pytest.approx(2 / 3)
    assert m.f1 == pytest.approx(2 / 3)
    assert m.gap_base_rate == pytest.approx(3 / 5)


def test_present_class_and_balanced_accuracy():
    """The gap class is nearly free on skewed data; the present class is the hard
    half, and balanced accuracy is immune to the base rate."""
    m = GapMetrics()
    for _ in range(90):      # all-gap detector on 90% gap data
        m.add(True, True)
    for _ in range(10):
        m.add(True, False)

    assert m.gap_base_rate == pytest.approx(0.9)
    assert m.f1 > 0.94, "gap F1 looks great..."
    assert m.present_recall == 0.0, "...but it never once identified a present element"
    assert m.balanced_accuracy == pytest.approx(0.5), "which balanced accuracy exposes"

    perfect = GapMetrics()
    for _ in range(90):
        perfect.add(True, True)
    for _ in range(10):
        perfect.add(False, False)
    assert perfect.balanced_accuracy == pytest.approx(1.0)
    assert perfect.present_f1 == pytest.approx(1.0)


def test_present_metrics_are_the_mirror_of_gap_metrics():
    m = GapMetrics()
    m.tp, m.fp, m.fn, m.tn = 6, 2, 3, 9
    # present class: tn are true positives, fn are its false positives,
    # fp are its false negatives
    assert m.present_precision == pytest.approx(9 / 12)
    assert m.present_recall == pytest.approx(9 / 11)
    assert m.balanced_accuracy == pytest.approx((6 / 9 + 9 / 11) / 2)
    assert set(m.to_dict()) >= {"present_precision", "present_recall",
                                "present_f1", "balanced_accuracy"}


def test_sweep_threshold_monotone_recall():
    # low present-score => predicted gap. Lower threshold => fewer predicted gaps.
    scores = [0.1, 0.3, 0.6, 0.9]
    gaps = [True, True, False, False]
    rows = sweep_threshold(scores, gaps, grid=[0.2, 0.5, 0.8])
    recalls = [r["recall"] for r in rows]
    assert recalls == sorted(recalls), "recall rises as the present-threshold rises"
    # at threshold 0.5 the split is perfect
    mid = next(r for r in rows if r["threshold"] == 0.5)
    assert mid["f1"] == 1.0


# --- NLI (needs transformers + a downloaded model) -------------------------

def test_nli_windowing_fast_path():
    """Short documents take the char-length fast path -- no model load."""
    pytest.importorskip("transformers")
    from edia.gapdetect.nli import NliGapDetector

    d = NliGapDetector()
    assert d._windows("Short document.") == ["Short document."]
    assert d._loaded is None, "fast path must not have loaded the model"


@pytest.mark.nli
def test_nli_windows_long_document():
    pytest.importorskip("transformers")
    from edia.gapdetect.nli import NliGapDetector

    d = NliGapDetector()
    long_doc = " ".join(f"Sentence number {i} says something specific." for i in range(400))
    wins = d._windows(long_doc)
    assert len(wins) > 1
    assert all(w for w in wins)


@pytest.mark.nli
def test_nli_entailment_direction():
    pytest.importorskip("transformers")
    from edia.gapdetect.nli import NliGapDetector

    d = NliGapDetector()
    try:
        s_present = d.present_score(
            "The team chose Postgres for the primary datastore.",
            "Postgres was selected as the database.",
        )
        s_gap = d.present_score(
            "The team chose Postgres for the primary datastore.",
            "The DBA objected that CockroachDB would scale better.",
        )
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"NLI model unavailable: {e}")
    assert s_present > 0.5
    assert s_gap < s_present


# --- base-rate warning in the report ----------------------------------------

def test_report_warns_when_gap_base_rate_inflates_f1():
    """Same trap agreement.py guards for: at a 93% gap base rate a headline F1 of
    ~0.96 is what an all-gap detector already scores."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "rge", Path(__file__).resolve().parents[1] / "scripts" / "run_gap_eval.py"
    )
    rge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rge)

    m = GapMetrics()
    for _ in range(93):
        m.add(True, True)
    for _ in range(7):
        m.add(False, False)
    report = {
        "threshold": 0.45, "nli_model": "x", "pairs": 1, "elements": 100,
        "detectors": {"lexical": {"overall": m.to_dict(), "breakdowns": {}}},
    }
    md = rge._render_md(report)
    assert "Base-rate warning" in md
    assert "called *everything* a gap" in md
    assert "NLI model" not in md, "no NLI detector ran -> no model line"


def test_report_has_no_base_rate_warning_when_balanced():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "rge2", Path(__file__).resolve().parents[1] / "scripts" / "run_gap_eval.py"
    )
    rge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rge)

    m = GapMetrics()
    for _ in range(50):
        m.add(True, True)
    for _ in range(50):
        m.add(False, False)
    report = {
        "threshold": 0.5, "nli_model": "x", "pairs": 1, "elements": 100,
        "detectors": {"nli:x": {"overall": m.to_dict(), "breakdowns": {}}},
    }
    md = rge._render_md(report)
    assert "Base-rate warning" not in md
    assert "NLI model" in md
