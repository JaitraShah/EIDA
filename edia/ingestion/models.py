from dataclasses import dataclass, field


@dataclass
class IngestedDocument:
    file_name: str          # original filename
    file_type: str          # "pdf", "docx", "txt", "json", "csv"
    doc_type: str           # "transcript" or "document"
    raw_text: str            # full extracted text
    metadata: dict = field(default_factory=dict)   # e.g. {"pages": 3, "word_count": 450}
    source_path: str = ""    # where the file came from
