"""
NLI gap detector -- the primary mechanism (Task 2).

premise = the filed document, hypothesis = one reasoning element.
ENTAILMENT  -> the document contains this element    (present)
NEUTRAL / CONTRADICTION -> the document dropped it    (gap)

present_score = P(ENTAILMENT). A CONTRADICTION still means "not in the document as
stated", so it is a gap, not a separate category -- matching how Task 2 scored it
(outputs/nli_results.json has CONTRADICTION rows with model_gap=true).

Premise windowing: roberta-large-mnli truncates at ~512 tokens. A long Committee
general summary would be silently cut, turning real content into false gaps. So a
document longer than the window is split into overlapping sentence windows, each
scored against the hypothesis, and the max P(ENTAILMENT) is taken -- if any part
of the document entails the element, it is present.

`transformers` + `torch` are optional (heavy). Import is lazy; tests that need a
model use `pytest.importorskip`.
"""

from __future__ import annotations

from functools import lru_cache

from ..benchmark.textutil import split_sentences
from .base import BaseGapDetector

DEFAULT_MODEL = "roberta-large-mnli"
# Operating point from scripts/calibrate_qmsum_labels.py on the 5 gold pairs:
# F1 is flat (~0.85-0.86) across 0.35-0.70, so the exact value barely matters;
# 0.55 sits at the top of that plateau with the fewest false negatives.
DEFAULT_THRESHOLD = 0.55
# Leave headroom under the 512-token limit for the hypothesis + specials.
PREMISE_WINDOW_TOKENS = 380
WINDOW_STRIDE_SENTENCES = 3


@lru_cache(maxsize=4)
def _load(model_name: str):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    # id2label -> index of the ENTAILMENT / CONTRADICTION classes (bart & roberta
    # mnli agree on {0:CONTRADICTION,1:NEUTRAL,2:ENTAILMENT} but read it, don't assume)
    label2id = {v.upper(): k for k, v in model.config.id2label.items()}
    return tok, model, device, label2id


class NliGapDetector(BaseGapDetector):
    name = "nli"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        entail_threshold: float = DEFAULT_THRESHOLD,
        batch_size: int = 16,
    ):
        self.model_name = model_name
        self.threshold = entail_threshold
        self.batch_size = batch_size
        self._loaded = None

    # -- lazy model -----------------------------------------------------------
    @property
    def _bits(self):
        if self._loaded is None:
            self._loaded = _load(self.model_name)
        return self._loaded

    # -- premise windows ----------------------------------------------------
    def _windows(self, document: str) -> list[str]:
        # Fast path: well under the window in characters => certainly under it in
        # tokens, so no tokenizer (and no model load) is needed.
        if len(document) <= PREMISE_WINDOW_TOKENS * 3:
            return [document]
        tok = self._bits[0]
        if len(tok.encode(document, add_special_tokens=False)) <= PREMISE_WINDOW_TOKENS:
            return [document]
        sents = split_sentences(document) or [document]
        windows: list[str] = []
        i = 0
        while i < len(sents):
            cur: list[str] = []
            j = i
            while j < len(sents):
                trial = " ".join(cur + [sents[j]])
                if cur and len(tok.encode(trial, add_special_tokens=False)) > PREMISE_WINDOW_TOKENS:
                    break
                cur.append(sents[j])
                j += 1
            windows.append(" ".join(cur))
            if j >= len(sents):
                break
            i = max(i + 1, j - WINDOW_STRIDE_SENTENCES)
        return windows

    # -- scoring ----------------------------------------------------------
    def _entail_probs(self, pairs: list[tuple[str, str]]) -> list[float]:
        import torch

        tok, model, device, label2id = self._bits
        ent = label2id["ENTAILMENT"]
        out: list[float] = []
        for k in range(0, len(pairs), self.batch_size):
            chunk = pairs[k:k + self.batch_size]
            enc = tok(
                [p for p, _ in chunk], [h for _, h in chunk],
                return_tensors="pt", truncation=True, max_length=512, padding=True,
            ).to(device)
            with torch.no_grad():
                logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1)[:, ent]
            out.extend(probs.detach().cpu().tolist())
        return out

    def present_score(self, document: str, element_text: str) -> float:
        wins = self._windows(document)
        return max(self._entail_probs([(w, element_text) for w in wins]), default=0.0)

    def present_scores(self, document: str, element_texts: list[str]) -> list[float]:
        """Batched: one set of premise windows, every hypothesis against it."""
        wins = self._windows(document)
        pairs = [(w, h) for h in element_texts for w in wins]
        flat = self._entail_probs(pairs)
        nw = len(wins)
        return [max(flat[i * nw:(i + 1) * nw], default=0.0) for i in range(len(element_texts))]
