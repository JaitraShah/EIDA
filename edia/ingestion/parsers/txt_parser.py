def parse_txt(file_path: str) -> tuple[str, dict]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    return text.strip(), {}
