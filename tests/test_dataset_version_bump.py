"""The 1.1.0 dataset-side additions -- provenance, the new source, and that the
frozen extraction schema was NOT touched."""
import pytest

from edia.benchmark.dataset import (
    DATASET_VERSION,
    BenchmarkPair,
    PairSource,
    dataset_stats,
)
from edia.extraction.schema import SCHEMA_VERSION, schema_fingerprint


def test_dataset_version_is_1_1_0():
    assert DATASET_VERSION == "1.1.0"


def test_pair_source_values():
    assert {s.value for s in PairSource} == {"synthetic", "qmsum", "qmsum_auto"}


def test_frozen_extraction_schema_untouched():
    """This work must not have changed the SHA-pinned wire format."""
    assert SCHEMA_VERSION == "1.0.0"
    assert schema_fingerprint() == (
        "463d9d8446c4a0076779067ced99977bd1eb824f3a74aaf849f93bb806c08f2c"
    )


def _pair(**kw):
    base = dict(
        pair_id="X_001", source=PairSource.QMSUM_AUTO, topic="qmsum_academic",
        transcript="A: hi\nB: yo", document="We decided X.", elements=[],
    )
    base.update(kw)
    return BenchmarkPair(**base)


def test_qmsum_auto_roundtrips():
    p = _pair(label_provenance="nli:roberta-large-mnli / thr=0.5")
    reloaded = BenchmarkPair.model_validate_json(p.model_dump_json())
    assert reloaded.source is PairSource.QMSUM_AUTO
    assert reloaded.label_provenance.startswith("nli:")
    assert reloaded.dataset_version == "1.1.0"


def test_has_reasoning_ground_truth():
    assert _pair().has_reasoning_ground_truth is False  # decisions == []


def test_label_provenance_defaults_none_and_stats_bucket():
    p = _pair()
    assert p.label_provenance is None
    stats = dataset_stats([p])
    assert stats["by_label_provenance"] == {"unspecified": 1}
    assert stats["pairs_with_reasoning_gt"] == 0
    assert stats["by_source"] == {"qmsum_auto": 1}
