import json


# Different transcript exports name things differently. Try known shapes before giving up.
_SPEAKER_KEYS = ("speaker", "speaker_name", "name", "role")
_CONTENT_KEYS = ("content", "text", "utterance", "message")
_TURN_LIST_KEYS = ("meeting_transcripts", "transcript", "turns", "messages")


def _find_turn_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in _TURN_LIST_KEYS:
            if key in data and isinstance(data[key], list):
                return data[key]
    return None


def _turn_to_line(turn: dict) -> str | None:
    if not isinstance(turn, dict):
        return None
    speaker = next((turn[k] for k in _SPEAKER_KEYS if k in turn), None)
    content = next((turn[k] for k in _CONTENT_KEYS if k in turn), None)
    if content is None:
        return None
    return f"{speaker}: {content}" if speaker else str(content)


def parse_json_transcript(file_path: str) -> tuple[str, dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    turns = _find_turn_list(data)
    if turns:
        lines = [ln for ln in (_turn_to_line(t) for t in turns) if ln]
        if lines:
            return "\n".join(lines), {"turn_count": len(lines)}

    # Not a recognizable transcript shape -- fall back to readable pretty-printed JSON
    # rather than raising, so non-transcript JSON documents still ingest.
    return json.dumps(data, indent=2, ensure_ascii=False), {"fallback": "raw_json"}
