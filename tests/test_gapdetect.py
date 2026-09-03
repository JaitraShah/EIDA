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
