"""
EDIA extraction schema -- FROZEN as of SCHEMA_VERSION below.

    ####################################################################
    #  DO NOT MODIFY THIS FILE without bumping SCHEMA_VERSION and       #
    #  updating tests/test_schema_frozen.py::EXPECTED_SCHEMA_FINGERPRINT #
    #  Every downstream component (chunker, extractor, benchmark,        #
    #  annotation tooling, gap detector) reads this and must not         #
    #  redefine, subclass-with-extra-fields, or locally patch it.        #
    ####################################################################

Field design traces directly to the reasoning-element taxonomy validated in Task 1
(outputs/gap_validation_results.md). Every row that appeared in those five
hand-built tables has exactly one home here:

    "Alternatives considered"      -> DecisionRecord.alternatives
    "Rationale for choice"         -> DecisionRecord.rationale
    "Condition / rejected option"  -> DecisionRecord.conditions  (+ Alternative.rejected)
    "Dissent"                      -> DecisionRecord.dissent
    "Owner / approver"             -> DecisionRecord.owner / .approver  (nullable on purpose --
                                      QMSum/AMI records no formal sign-off; see Task 1 caveat 1)
    "temporarily decided"          -> DecisionRecord.status == PROVISIONAL

`evidence` exists so hallucination scoring (Task 4 step 6) is mechanical rather than
subjective: every non-empty reasoning field should be traceable to a verbatim span
that actually occurs in the source chunk.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class DecisionStatus(str, Enum):
    """How settled the decision was at the end of the discussion."""

    DECIDED = "decided"          # agreed, unqualified
    PROVISIONAL = "provisional"  # agreed but explicitly temporary//conditional ("temporarily decided")
    DEFERRED = "deferred"        # explicitly postponed to a later meeting
    REJECTED = "rejected"        # the proposal under discussion was turned down
    UNCLEAR = "unclear"          # discussed, no resolution recoverable from the text


class ElementType(str, Enum):
    """Which reasoning slot a piece of evidence supports. Mirrors the Task 1 table rows."""

    DECISION = "decision"
    ALTERNATIVE = "alternative"
    RATIONALE = "rationale"
    CONDITION = "condition"
    DISSENT = "dissent"
    OWNER = "owner"
    APPROVER = "approver"
    STATUS = "status"


class EvidenceSpan(BaseModel):
    """A verbatim quote from the source chunk backing one extracted element.

    `quote` MUST be copied character-for-character from the chunk text. The
    hallucination check in edia.benchmark.score is a literal substring test
    against the chunk, so paraphrasing here scores as a hallucination.
    """

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(..., min_length=1, description="Verbatim span from the chunk text.")
    speaker: Optional[str] = Field(None, description="Speaker label if the chunk carried one.")
    supports: ElementType = Field(..., description="Which reasoning slot this span backs.")


class Alternative(BaseModel):
    """An option that was on the table -- chosen or not."""

    model_config = ConfigDict(extra="forbid")

    option: str = Field(..., min_length=1, description="The alternative, in the discussion's own terms.")
    rejected: Optional[bool] = Field(
        None, description="True if turned down, False if selected, None if left open."
    )
    reason: Optional[str] = Field(
        None, description="Stated reason it was rejected or selected. None if never stated."
    )


class DecisionRecord(BaseModel):
    """One decision, plus the reasoning infrastructure around it.

    Populated per-chunk by the extractor. Records from different chunks are NOT
    merged at this stage (Task 4 constraint) -- cross-chunk consolidation is a
    separate, later step and must not be smuggled in here.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    # --- identity / provenance -------------------------------------------------
    decision_id: str = Field(..., description="Stable id, e.g. 'M5_c02_d1'.")
    source_id: str = Field(..., description="Document/meeting id the chunk came from.")
    chunk_id: str = Field(..., description="Id of the single chunk this was extracted from.")
    schema_version: str = Field(default=SCHEMA_VERSION)

    # --- the decision itself ---------------------------------------------------
    decision: str = Field(..., min_length=1, description="What was decided, one sentence.")
    topic: Optional[str] = Field(None, description="Short subject label, e.g. 'energy source'.")
    status: DecisionStatus = Field(default=DecisionStatus.DECIDED)

    # --- the reasoning around it (this is the part documents drop) -------------
    alternatives: list[Alternative] = Field(default_factory=list)
    rationale: list[str] = Field(
        default_factory=list, description="Why the chosen option won. One claim per item."
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Caveats, open risks, unresolved costs, things the decision depends on.",
    )
    dissent: list[str] = Field(
        default_factory=list,
        description="Recorded disagreement or objection, even if overruled.",
    )

    # --- accountability (nullable by design: absent in AMI-style data) ---------
    owner: Optional[str] = Field(None, description="Who carries the decision forward.")
    approver: Optional[str] = Field(None, description="Who signed off, if anyone did explicitly.")

    # --- traceability ----------------------------------------------------------
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    extraction_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Model's own confidence. Advisory only, never a filter."
    )

    def reasoning_elements(self) -> list[tuple[ElementType, str]]:
        """Flatten every reasoning claim to (type, text) -- the unit the Task 1
        tables scored, and the unit completeness scoring counts against."""
        out: list[tuple[ElementType, str]] = [(ElementType.DECISION, self.decision)]
        for alt in self.alternatives:
            text = alt.option if not alt.reason else f"{alt.option} -- {alt.reason}"
            out.append((ElementType.ALTERNATIVE, text))
        out += [(ElementType.RATIONALE, r) for r in self.rationale]
        out += [(ElementType.CONDITION, c) for c in self.conditions]
        out += [(ElementType.DISSENT, d) for d in self.dissent]
        if self.owner:
            out.append((ElementType.OWNER, self.owner))
        if self.approver:
            out.append((ElementType.APPROVER, self.approver))
        return out


class ExtractionResult(BaseModel):
    """Everything the extractor produced for one source document.

    Deliberately a flat list: `records` may contain two records about the same
    real-world decision if it was discussed in two chunks. That duplication is
    expected and must be preserved for now (Task 4 constraint: no cross-chunk merging).
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    schema_version: str = Field(default=SCHEMA_VERSION)
    records: list[DecisionRecord] = Field(default_factory=list)
    chunks_processed: int = 0
    chunks_failed: list[str] = Field(default_factory=list)
    model_name: str = ""
    merged_across_chunks: bool = Field(
        default=False,
        description="Always False in Task 4. A downstream merge step may set it True.",
    )


def schema_fingerprint() -> str:
    """Stable hash of the wire format. The freeze test pins this."""
    payload = {
        "version": SCHEMA_VERSION,
        "DecisionRecord": DecisionRecord.model_json_schema(),
        "ExtractionResult": ExtractionResult.model_json_schema(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(f"SCHEMA_VERSION = {SCHEMA_VERSION}")
    print(f"fingerprint    = {schema_fingerprint()}")
