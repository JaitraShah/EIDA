import os

from .models import IngestedDocument
from .parsers.pdf_parser import parse_pdf
from .parsers.docx_parser import parse_docx
from .parsers.txt_parser import parse_txt
from .parsers.json_parser import parse_json_transcript
from .parsers.csv_parser import parse_csv

PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
    ".json": parse_json_transcript,
    ".csv": parse_csv,
}


def ingest_file(file_path: str, doc_type: str = "document") -> IngestedDocument:
    """
    doc_type: "transcript" or "document" -- caller specifies which, since the file
    extension alone can't tell us (e.g. a .txt could be either).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in PARSERS:
        raise ValueError(
            f"Unsupported file type: {ext!r}. Supported: {', '.join(sorted(PARSERS))}"
        )

    try:
        raw_text, extra_metadata = PARSERS[ext](file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse {file_path}: {e}") from e

    if not raw_text.strip():
        raise ValueError(
            f"File appears to be empty or unreadable: {file_path} "
            f"(if this is a scanned PDF with no text layer, OCR is not yet supported)"
        )

    metadata = {"word_count": len(raw_text.split()), **extra_metadata}

    return IngestedDocument(
        file_name=os.path.basename(file_path),
        file_type=ext.lstrip("."),
        doc_type=doc_type,
        raw_text=raw_text,
        metadata=metadata,
        source_path=file_path,
    )
