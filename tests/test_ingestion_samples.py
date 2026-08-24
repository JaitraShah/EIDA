"""Assertion version of the Task 3 ingestion demo, so ingestion stays covered by
the suite. The demo script (scripts/task3_ingestion_demo.py) is kept as-is for its
human-readable output; this file is what CI actually checks.

Also covers the one integration gap Task 3 explicitly left open: running a real
QMSum transcript through the module end-to-end rather than only a synthetic fixture.
"""
from pathlib import Path

import pytest

from edia.ingestion.ingest import ingest_file

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "ingestion_test_samples"
QMSUM = ROOT / "data" / "qmsum"

CASES = [
    ("meeting.pdf", "transcript", "pdf"),
    ("decision_doc.docx", "document", "docx"),
    ("notes.txt", "document", "txt"),
    ("transcript.json", "transcript", "json"),
    ("decisions.csv", "document", "csv"),
]


@pytest.mark.parametrize("name,doc_type,ext", CASES)
def test_each_file_type_ingests(name, doc_type, ext):
    doc = ingest_file(str(SAMPLES / name), doc_type=doc_type)
    assert doc.file_type == ext
    assert doc.doc_type == doc_type
    assert doc.raw_text.strip()
    assert doc.metadata["word_count"] > 0


def test_non_transcript_json_falls_back_instead_of_raising():
    doc = ingest_file(str(SAMPLES / "config_not_a_transcript.json"), doc_type="document")
    assert doc.metadata.get("fallback") == "raw_json"


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        ingest_file(str(SAMPLES / "nope.pdf"))


def test_unsupported_extension(tmp_path):
    bad = tmp_path / "x.xyz"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file type"):
        ingest_file(str(bad))


def test_empty_file(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        ingest_file(str(empty))


@pytest.mark.skipif(
    not (QMSUM / "QSUM_002_transcript.json").exists(),
    reason="run scripts/prepare_qmsum.py first",
)
def test_real_qmsum_transcript_end_to_end():
    """Task 3's open item: a real QMSum file, not the small synthetic fixture."""
    doc = ingest_file(str(QMSUM / "QSUM_002_transcript.json"), doc_type="transcript")
    assert doc.metadata["turn_count"] > 400
    assert doc.metadata["word_count"] > 5000
    assert "Project Manager:" in doc.raw_text
