"""
Ensemble gap detector.

The NLI detector alone over-flags: run against the ~100-word QMSum general
summaries it labelled 93% of corpus elements as gaps and marked *every* element
absent in 82 of 227 meetings -- implausible, since at minimum the headline
decision survives. Entailment against a heavily compressed abstractive summary
reads genuinely-present-but-reworded content as NEUTRAL.

The fix: only call an element a **gap when every available signal agrees it is
absent**. present_score = max over the member detectors' present-scores, each
normalised to "1.0 = that detector says present at its own operating point":

    member vote = clamp01( raw_present_score - member_threshold + 0.5 )

so a member exactly at its threshold contributes 0.5, well above contributes ~1,
well below ~0. The ensemble's own threshold stays 0.5. Lexical (recall 1.0 on the
gold gaps) and the mistral LLM judge are the recall backstops NLI needs.
"""

from __future__ import annotations

from .base import BaseGapDetector
from .lexical import DEFAULT_THRESHOLD as LEX_THR
from .lexical import LexicalGapDetector
from .nli import DEFAULT_THRESHOLD as NLI_THR


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


class EnsembleGapDetector(BaseGapDetector):
    name = "ensemble"

    def __init__(
        self,
        nli_model: str = "roberta-large-mnli",
        nli_threshold: float = NLI_THR,
        lexical_threshold: float = LEX_THR,
        with_llm: bool = True,
        llm_model: str | None = None,
    ):
        self.threshold = 0.5
        self._members: list[tuple[object, float]] = []

        from .nli import NliGapDetector
        self._members.append((NliGapDetector(nli_model, nli_threshold), nli_threshold))
        self._members.append((LexicalGapDetector(lexical_threshold), lexical_threshold))

        self.with_llm = with_llm
        if with_llm:
            try:
                from .entailment_llm import LlmEntailmentGapDetector
                self._members.append((LlmEntailmentGapDetector(model=llm_model), 0.5))
            except Exception:  # noqa: BLE001 -- Ollama not up: run NLI+lexical only
                self.with_llm = False

    @property
    def member_names(self) -> list[str]:
        return [m.name for m, _ in self._members]

    def present_score(self, document: str, element_text: str) -> float:
        best = 0.0
        for member, thr in self._members:
            raw = member.present_score(document, element_text)
            vote = _clamp01(raw - thr + 0.5)
            best = max(best, vote)
        return best

    def member_scores(self, document: str, element_text: str) -> dict[str, float]:
        """Raw per-member present-scores, for auditing which signal carried a call."""
        return {
            member.name: round(float(member.present_score(document, element_text)), 4)
            for member, _ in self._members
        }
