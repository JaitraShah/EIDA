"""
Scoring for extraction runs: completeness (recall against Task 1 ground truth) and
hallucination.

The important methodological point, because it is the thing a reviewer will push on:
**"unmatched" is not the same as "hallucinated", and this module never conflates them.**

Two independent measures are reported:

1. `unsupported_evidence_rate` -- the objective one. Every DecisionRecord carries
   verbatim evidence quotes; a quote whose words do not occur in the source chunk is
   a fabrication. No human judgement needed, no ground truth needed. This is the
   number to quote as "hallucination rate". One deliberate tolerance: dropped filler
   and QMSum transcription markers ({disfmarker}, uh) do not count as fabrication,
   because tidying them away invents nothing -- see normalize_lenient. Quoting
   fidelity is reported separately as `strict_verbatim_rate`, so the tolerance is
   visible rather than buried.

2. `unmatched_element_rate` -- extracted reasoning elements with no counterpart in
   the Task 1 ground truth. The Task 1 tables were built to answer "did the document
   drop this?", not "here is everything the discussion contained", so they are NOT
   exhaustive. An unmatched element may be a correct extraction Task 1 simply did not
   tabulate. These are emitted individually for human adjudication rather than
   silently counted as errors.

Matching is lexical by default (token-F1 over content words) so scores are
deterministic and reproducible offline. `--semantic` swaps in sentence-transformer
cosine similarity, which matters because Task 2 established paraphrase-sensitivity as
this project's dominant failure mode -- a lexical matcher will under-credit a
correct-but-reworded extraction exactly the way roberta-large-mnli did.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field

from ..extraction.schema import DecisionRecord, ElementType, ExtractionResult
from .qmsum_ground_truth import GroundTruthPair

# Owner/approver are N/A in AMI-style data (Task 1 caveat 1). Counting them as recall
# misses would penalise the extractor for a dataset limitation, so they are scored
# separately and kept out of the headline completeness number.
SOFT_ELEMENT_TYPES = {ElementType.OWNER, ElementType.APPROVER}

DEFAULT_MATCH_THRESHOLD = 0.45

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "was", "were", "is", "are", "be", "been", "it", "its", "this", "that", "as",
    "at", "by", "from", "would", "will", "not", "no", "so", "than", "then",
    "they", "their", "there", "which", "who", "we", "our", "he", "she", "them",
}

_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = _PUNCT_RE.sub(" ", (text or "").lower())
    return _WS_RE.sub(" ", text).strip()


# QMSum transcripts carry transcription artifacts ({disfmarker}, {vocalsound}) and
# heavy filler. Models quoting them reliably tidy that away -- "I have some points
# {disfmarker} uh" comes back as "I have some points". Counting that as fabrication
# would put the hallucination rate several points too high for a behaviour that
# invents nothing, so grounding is checked twice:
#   strict  -- exact after case/punctuation/whitespace normalisation
#   lenient -- also ignoring transcription markers and filler words
# The lenient rate is the one to quote as the hallucination rate; the gap between
# the two is a separate, reportable fact about quoting fidelity.
_MARKER_RE = re.compile(r"\{[^}]*\}")
_FILLERS = {
    "uh", "um", "mm", "hmm", "mm-hmm", "er", "ah", "eh", "oh", "yeah", "okay",
    "disfmarker", "vocalsound", "gap", "pause", "nonvocalsound", "unclear",
}


def normalize_lenient(text: str) -> str:
    """Normalisation that also drops transcription markers and filler words."""
    text = _MARKER_RE.sub(" ", text or "")
    words = [w for w in normalize(text).split() if w not in _FILLERS]
    return " ".join(words)


def content_tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if t and t not in _STOPWORDS}


def token_f1(a: str, b: str) -> float:
    """Symmetric token-overlap F1 over content words.

    F1 rather than Jaccard because ground-truth elements and extracted elements
    differ a lot in length; Jaccard punishes a correct short extraction against a
    long ground-truth phrasing much harder than F1 does.
    """
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb)
    if not overlap:
        return 0.0
    precision = overlap / len(ta)
    recall = overlap / len(tb)
    return 2 * precision * recall / (precision + recall)


class SemanticMatcher:
    """Optional sentence-transformer matcher. Loaded lazily so the default path
    stays offline and dependency-free."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

    def similarity(self, a: str, b: str) -> float:
        from sentence_transformers import util

        emb = self.model.encode([a, b], convert_to_tensor=True, show_progress_bar=False)
        return float(util.cos_sim(emb[0], emb[1]).item())


# --------------------------------------------------------------------------- #
# evidence grounding -- the objective hallucination measure
# --------------------------------------------------------------------------- #

@dataclass
class QuoteCheck:
    decision_id: str
    quote: str
    supports: str
    grounded: bool           # lenient: ignores transcription markers and filler
    strict_grounded: bool = False   # exact after case/punctuation normalisation only


def check_evidence_grounding(
    records: list[DecisionRecord], chunk_texts: dict[str, str]
) -> list[QuoteCheck]:
    """Verify every evidence quote occurs in its own source chunk.

    Substring match after normalisation: case, punctuation and whitespace differences
    are forgiven (models reflow whitespace constantly and that invents nothing), but
    changed or added words are not. See normalize_lenient for why filler and
    transcription markers are forgiven too.
    """
    checks: list[QuoteCheck] = []
    strict_chunks = {cid: normalize(t) for cid, t in chunk_texts.items()}
    lenient_chunks = {cid: normalize_lenient(t) for cid, t in chunk_texts.items()}
    for rec in records:
        strict_hay = strict_chunks.get(rec.chunk_id)
        lenient_hay = lenient_chunks.get(rec.chunk_id)
        for ev in rec.evidence:
            strict = bool(strict_hay) and normalize(ev.quote) in strict_hay
            lenient = bool(lenient_hay) and normalize_lenient(ev.quote) in lenient_hay
            checks.append(
                QuoteCheck(
                    decision_id=rec.decision_id,
                    quote=ev.quote,
                    supports=ev.supports.value,
                    grounded=strict or lenient,
                    strict_grounded=strict,
                )
            )
    return checks


# --------------------------------------------------------------------------- #
# element matching -- completeness
# --------------------------------------------------------------------------- #

@dataclass
class ElementMatch:
    gt_type: str
    gt_text: str
    matched: bool
    best_score: float = 0.0
    best_extracted: str = ""


@dataclass
class ScoreReport:
    pair_id: str
    model_name: str
    matcher: str
    threshold: float

    # completeness
    gt_total: int = 0
    gt_matched: int = 0
    gt_soft_total: int = 0
    gt_soft_matched: int = 0
    matches: list[ElementMatch] = field(default_factory=list)

    # hallucination
    quotes_total: int = 0
    quotes_grounded: int = 0
    quotes_strict_grounded: int = 0
    ungrounded_quotes: list[QuoteCheck] = field(default_factory=list)
    unmatched_extracted: list[tuple[str, str]] = field(default_factory=list)
    extracted_total: int = 0

    # run shape
    records: int = 0
    chunks_processed: int = 0
    chunks_failed: list[str] = field(default_factory=list)

    @property
    def completeness(self) -> float:
        return self.gt_matched / self.gt_total if self.gt_total else 0.0

    @property
    def evidence_grounding(self) -> float:
        return self.quotes_grounded / self.quotes_total if self.quotes_total else 0.0

    @property
    def strict_verbatim_rate(self) -> float:
        """Quotes reproduced exactly, filler and transcription markers included."""
        return self.quotes_strict_grounded / self.quotes_total if self.quotes_total else 0.0

    @property
    def unsupported_evidence_rate(self) -> float:
        """The headline hallucination number: fabricated quotes / all quotes.

        Lenient grounding -- a quote that differs only by dropped filler or
        transcription markers invents nothing and is not counted here. Quoting
        fidelity is reported separately as strict_verbatim_rate."""
        return 1.0 - self.evidence_grounding if self.quotes_total else 0.0

    @property
    def unmatched_element_rate(self) -> float:
        """NOT a hallucination rate -- ground truth is not exhaustive. Needs adjudication."""
        return (
            len(self.unmatched_extracted) / self.extracted_total
            if self.extracted_total
            else 0.0
        )

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "model_name": self.model_name,
            "matcher": self.matcher,
            "threshold": self.threshold,
            "completeness": round(self.completeness, 3),
            "gt_matched": self.gt_matched,
            "gt_total": self.gt_total,
            "soft_owner_approver_matched": f"{self.gt_soft_matched}/{self.gt_soft_total}",
            "evidence_grounding": round(self.evidence_grounding, 3),
            "unsupported_evidence_rate": round(self.unsupported_evidence_rate, 3),
            "quotes_grounded": f"{self.quotes_grounded}/{self.quotes_total}",
            "strict_verbatim_rate": round(self.strict_verbatim_rate, 3),
            "quotes_strict_verbatim": f"{self.quotes_strict_grounded}/{self.quotes_total}",
            "unmatched_element_rate": round(self.unmatched_element_rate, 3),
            "unmatched_extracted_count": len(self.unmatched_extracted),
            "records": self.records,
            "chunks_processed": self.chunks_processed,
            "chunks_failed": self.chunks_failed,
            "missed_elements": [
                {"type": m.gt_type, "text": m.gt_text, "best_score": round(m.best_score, 2),
                 "closest_extracted": m.best_extracted}
                for m in self.matches if not m.matched
            ],
            "unmatched_extracted": [
                {"type": t, "text": x} for t, x in self.unmatched_extracted
            ],
        }


def score_extraction(
    result: ExtractionResult,
    truth: GroundTruthPair,
    chunk_texts: dict[str, str] | None = None,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    semantic: SemanticMatcher | None = None,
) -> ScoreReport:
    """Score one extraction run against one Task 1 ground-truth pair."""
    sim = semantic.similarity if semantic else token_f1
    matcher_name = f"semantic:{semantic.model_name}" if semantic else "lexical:token_f1"

    report = ScoreReport(
        pair_id=truth.pair_id,
        model_name=result.model_name,
        matcher=matcher_name,
        threshold=threshold,
        records=len(result.records),
        chunks_processed=result.chunks_processed,
        chunks_failed=list(result.chunks_failed),
    )

    extracted: list[tuple[str, str]] = []
    for rec in result.records:
        extracted += [(t.value, text) for t, text in rec.reasoning_elements()]
    report.extracted_total = len(extracted)

    matched_extracted_idx: set[int] = set()

    for gt_type, gt_text in truth.all_elements():
        best_score, best_idx = 0.0, -1
        for i, (ex_type, ex_text) in enumerate(extracted):
            s = sim(ex_text, gt_text)
            if s > best_score:
                best_score, best_idx = s, i

        is_match = best_score >= threshold
        if is_match and best_idx >= 0:
            matched_extracted_idx.add(best_idx)

        match = ElementMatch(
            gt_type=gt_type,
            gt_text=gt_text,
            matched=is_match,
            best_score=best_score,
            best_extracted=extracted[best_idx][1] if best_idx >= 0 else "",
        )
        report.matches.append(match)

        if gt_type in {t.value for t in SOFT_ELEMENT_TYPES}:
            report.gt_soft_total += 1
            report.gt_soft_matched += int(is_match)
        else:
            report.gt_total += 1
            report.gt_matched += int(is_match)

    report.unmatched_extracted = [
        pair for i, pair in enumerate(extracted) if i not in matched_extracted_idx
    ]

    if chunk_texts:
        checks = check_evidence_grounding(result.records, chunk_texts)
        report.quotes_total = len(checks)
        report.quotes_grounded = sum(c.grounded for c in checks)
        report.quotes_strict_grounded = sum(c.strict_grounded for c in checks)
        report.ungrounded_quotes = [c for c in checks if not c.grounded]

    return report


def render_markdown(reports: list[ScoreReport]) -> str:
    """Team-readable summary table plus the per-pair detail a reviewer will ask for."""
    lines: list[str] = []
    lines.append("| Pair | Completeness | Evidence grounded | Unsupported (hallucination) | Strict verbatim | Unmatched extracted | Records |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in reports:
        lines.append(
            f"| {r.pair_id} | {r.gt_matched}/{r.gt_total} ({r.completeness:.0%}) "
            f"| {r.quotes_grounded}/{r.quotes_total} ({r.evidence_grounding:.0%}) "
            f"| {r.unsupported_evidence_rate:.0%} "
            f"| {r.strict_verbatim_rate:.0%} "
            f"| {len(r.unmatched_extracted)}/{r.extracted_total} "
            f"| {r.records} |"
        )

    gt_total = sum(r.gt_total for r in reports)
    gt_matched = sum(r.gt_matched for r in reports)
    q_total = sum(r.quotes_total for r in reports)
    q_ok = sum(r.quotes_grounded for r in reports)
    q_strict = sum(r.quotes_strict_grounded for r in reports)
    ex_total = sum(r.extracted_total for r in reports)
    ex_unmatched = sum(len(r.unmatched_extracted) for r in reports)

    lines.append(
        f"| **TOTAL** | **{gt_matched}/{gt_total} "
        f"({(gt_matched / gt_total if gt_total else 0):.0%})** "
        f"| **{q_ok}/{q_total} ({(q_ok / q_total if q_total else 0):.0%})** "
        f"| **{(1 - q_ok / q_total if q_total else 0):.0%}** "
        f"| **{(q_strict / q_total if q_total else 0):.0%}** "
        f"| **{ex_unmatched}/{ex_total}** | **{sum(r.records for r in reports)}** |"
    )

    for r in reports:
        lines.append(f"\n### {r.pair_id} — missed ground-truth elements\n")
        missed = [m for m in r.matches if not m.matched]
        if not missed:
            lines.append("_None — every Task 1 element was recovered._")
        for m in missed:
            soft = " _(soft: owner/approver, excluded from headline)_" if m.gt_type in {t.value for t in SOFT_ELEMENT_TYPES} else ""
            lines.append(f"- **{m.gt_type}**: {m.gt_text}{soft}")
            lines.append(f"  - closest extraction ({m.best_score:.2f}): {m.best_extracted or '—'}")
        if r.ungrounded_quotes:
            lines.append(f"\n**Ungrounded quotes (fabricated text) in {r.pair_id}:**\n")
            for c in r.ungrounded_quotes:
                lines.append(f"- `{c.decision_id}` ({c.supports}): {c.quote!r}")

    return "\n".join(lines)
