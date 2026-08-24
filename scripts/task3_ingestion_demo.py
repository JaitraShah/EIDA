"""Task 3 ingestion demo, carried over unchanged in substance from the Task 3
handover. Kept as a runnable script (it prints a human-readable report) rather
than a pytest module; tests/test_ingestion_samples.py covers the same paths as
assertions for CI.

Run from the repo root: python scripts/task3_ingestion_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.ingestion.ingest import ingest_file

SAMPLES_DIR = str(Path(__file__).resolve().parents[1] / "data" / "ingestion_test_samples")

test_files = [
    (f"{SAMPLES_DIR}/meeting.pdf", "transcript"),
    (f"{SAMPLES_DIR}/decision_doc.docx", "document"),
    (f"{SAMPLES_DIR}/notes.txt", "document"),
    (f"{SAMPLES_DIR}/transcript.json", "transcript"),
    (f"{SAMPLES_DIR}/decisions.csv", "document"),
    (f"{SAMPLES_DIR}/config_not_a_transcript.json", "document"),  # non-transcript JSON fallback path
]

print("=== HAPPY PATH: all 6 file types ===\n")
for path, dtype in test_files:
    doc = ingest_file(path, doc_type=dtype)
    print(f"{doc.file_name} | type={doc.file_type} | doc_type={doc.doc_type} | metadata={doc.metadata}")
    print(f"  text preview: {doc.raw_text[:100]!r}")
    print()

print("=== ERROR HANDLING ===\n")

try:
    ingest_file(f"{SAMPLES_DIR}/does_not_exist.pdf")
except FileNotFoundError as e:
    print(f"[OK] FileNotFoundError raised as expected: {e}")

try:
    with open(f"{SAMPLES_DIR}/bad.xyz", "w") as f:
        f.write("data")
    ingest_file(f"{SAMPLES_DIR}/bad.xyz")
except ValueError as e:
    print(f"[OK] ValueError raised for unsupported type: {e}")

try:
    with open(f"{SAMPLES_DIR}/empty.txt", "w") as f:
        f.write("   ")
    ingest_file(f"{SAMPLES_DIR}/empty.txt")
except ValueError as e:
    print(f"[OK] ValueError raised for empty file: {e}")

print("\nAll checks completed.")
