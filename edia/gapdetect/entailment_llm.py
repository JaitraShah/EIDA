"""
LLM-entailment gap detector -- the ablation Task 2's decision tree names as the
fallback if NLI transfer had come in under 75% (it did not, but the comparison is
worth having at benchmark scale).

One deterministic yes/no call per (document, element): "is this reasoning stated,
even loosely, in the record?" Uses the same `OllamaClient` the extractor uses,
with sampling refused (temperature 0). GPU-box path -- ~7k elements at a few
seconds each.
"""

from __future__ import annotations

from ..extraction.llm_client import DEFAULT_MODEL, OllamaClient
from .base import BaseGapDetector

_SYSTEM = (
    "You judge whether a piece of reasoning from a meeting is recorded in the "
    "meeting's short written summary. You answer with a single JSON object."
)

_USER = """\
Written summary:
---
{document}
---

Reasoning element from the discussion:
"{element}"

Is the substance of this element present in the summary above -- even if reworded,
compressed, or hedged? A bare mention of the topic is NOT enough; the summary must
actually carry this specific point.

Return: {{"present": true|false, "confidence": 0.0-1.0}}"""


class LlmEntailmentGapDetector(BaseGapDetector):
    name = "llm_entailment"

    def __init__(self, client: OllamaClient | None = None, model: str | None = None,
                 threshold: float = 0.5):
        self.model = model or DEFAULT_MODEL
        self.client = client or OllamaClient(model=self.model)
        self.threshold = threshold

    def present_score(self, document: str, element_text: str) -> float:
        from ..extraction.extractor import extract_json_object

        resp = self.client.chat_json(
            _SYSTEM, _USER.format(document=document, element=element_text)
        )
        try:
            data = extract_json_object(resp.text)
        except Exception:  # noqa: BLE001
            return 0.0
        present = bool(data.get("present"))
        try:
            conf = float(data.get("confidence"))
            conf = min(max(conf, 0.0), 1.0)
        except (TypeError, ValueError):
            conf = 1.0
        # Map to a present-score: high when the model says present with confidence,
        # low when it says absent with confidence.
        return conf if present else 1.0 - conf
