import pymupdf  # modern import name; `fitz` alias is deprecated upstream


def parse_pdf(file_path: str) -> tuple[str, dict]:
    """Returns (raw_text, extra_metadata). Scanned/no-text-layer PDFs return empty text
    on purpose -- OCR is explicitly out of scope for this module (see Task 3 notes)."""
    doc = pymupdf.open(file_path)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    page_count = doc.page_count
    doc.close()
    return "\n".join(text_parts).strip(), {"pages": page_count}
