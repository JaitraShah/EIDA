"""
QSUM_001-005: the five QMSum pairs hand-validated in Task 1, re-expressed in the
frozen DecisionRecord schema.

Source of truth: outputs/gap_validation_results.md. Every element below traces to a
row in one of those five tables -- nothing here was added by reading the raw
transcripts afresh, because the point of this file is to make the Task 1 human
judgement machine-checkable, not to quietly extend it.

Two columns from the Task 1 tables are preserved separately:

  * `decisions` -- DecisionRecords holding what the DISCUSSION contained. This is
    what the Task 4 extractor is scored against (completeness = how much of this it
    recovers from the transcript).
  * `present_in_document` -- the element texts that survived into the general
    summary ("document" proxy). This is the Task 2 / gap-detection ground truth,
    carried here so the two tasks cannot drift apart.

Honest limitations, carried forward from Task 1 so they travel with the data:
  * owner/approver is genuinely N/A in AMI-style data -- absent here means "the
    dataset has no such field", NOT "the extractor missed it". Scoring must not
    count these as recall misses (see score.py::IGNORED_ELEMENT_TYPES).
  * n=5, one domain. This is a regression fixture, not an accuracy estimate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..extraction.schema import DecisionRecord, DecisionStatus


@dataclass
class GroundTruthPair:
    pair_id: str                       # QSUM_001 ...
    qmsum_meeting: str                 # meeting id as used in Task 1
    title: str
    decisions: list[DecisionRecord]
    present_in_document: list[str] = field(default_factory=list)
    notes: str = ""

    def all_elements(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for d in self.decisions:
            out += [(t.value, text) for t, text in d.reasoning_elements()]
        return out


def _rec(pair_id: str, n: int, **kw) -> DecisionRecord:
    """Ground-truth records have no chunk of origin -- they are the human column."""
    return DecisionRecord(
        decision_id=f"{pair_id}_gt{n}",
        source_id=pair_id,
        chunk_id="GROUND_TRUTH",
        **kw,
    )


# --------------------------------------------------------------------------- #
# QSUM_001 -- Task 1 Pair 1, Meeting 5: casing style + display
# --------------------------------------------------------------------------- #
QSUM_001 = GroundTruthPair(
    pair_id="QSUM_001",
    qmsum_meeting="M5",
    title="Remote control casing style and display technology",
    decisions=[
        _rec(
            "QSUM_001", 1,
            decision="A single-curved casing was chosen for the remote control.",
            topic="casing style",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "uncurved (flat) casing", "rejected": True, "reason": "too dull"},
                {"option": "single-curved casing", "rejected": False, "reason": None},
                {"option": "double-curved casing", "rejected": True,
                 "reason": "would block use of the scroll wheel"},
            ],
            rationale=[
                "The uncurved option was considered too dull.",
                "The double-curved option would interfere with using the scroll wheel.",
            ],
        ),
        _rec(
            "QSUM_001", 2,
            decision="An LCD display was rejected for the remote control.",
            topic="display technology",
            status=DecisionStatus.REJECTED,
            alternatives=[
                {"option": "LCD display", "rejected": True,
                 "reason": "the design already had a scroll wheel, speech recognition, rubber and fancy colours"},
            ],
            rationale=[
                "The team already had a scroll wheel, speech recognition, rubber and fancy colours, so an LCD was not needed.",
            ],
            dissent=[
                "The Project Manager leaned towards including the LCD for budget and high-tech-feel reasons and was talked out of it.",
                "The Industrial Designer argued the LCD was too much.",
            ],
        ),
    ],
    present_in_document=[
        "uncurved (flat) casing",
        "single-curved casing",
        "double-curved casing",
    ],
    notes=(
        "Task 1: the general summary names all three casing shapes but never states which "
        "won, and drops the LCD topic entirely including the fact that it was a live "
        "disagreement. Raw-transcript spot check confirmed the PM/ID exchange is real."
    ),
)

# --------------------------------------------------------------------------- #
# QSUM_002 -- Task 1 Pair 2, Meeting 7: energy source
# --------------------------------------------------------------------------- #
QSUM_002 = GroundTruthPair(
    pair_id="QSUM_002",
    qmsum_meeting="M7",
    title="Energy source selection",
    decisions=[
        _rec(
            "QSUM_002", 1,
            decision="Kryptonite was chosen as the preferred energy source.",
            topic="energy source",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "battery", "rejected": True, "reason": None},
                {"option": "solar power", "rejected": True, "reason": None},
                {"option": "dynamo", "rejected": True, "reason": None},
                {"option": "kryptonite", "rejected": False, "reason": None},
            ],
            rationale=[
                "The chip is the most expensive part regardless, so the energy source's own cost is a secondary concern.",
            ],
            conditions=[
                "The exact price of kryptonite was never established -- the website did not give an actual cost.",
            ],
            dissent=[
                "The Industrial Designer preferred a battery and was skeptical of the dynamo.",
            ],
        ),
    ],
    present_in_document=[
        "Kryptonite was chosen as the preferred energy source.",
    ],
    notes=(
        "Task 1: the general summary states only the winner. Alternatives, dissent, "
        "rationale and the unresolved price all drop out, and the document states the "
        "choice with more confidence than the discussion had."
    ),
)

# --------------------------------------------------------------------------- #
# QSUM_003 -- Task 1 Pair 3, Meeting 9: menu display vs more buttons
# --------------------------------------------------------------------------- #
QSUM_003 = GroundTruthPair(
    pair_id="QSUM_003",
    qmsum_meeting="M9",
    title="Menu display vs more buttons; case material",
    decisions=[
        _rec(
            "QSUM_003", 1,
            decision="A screen menu display was adopted and only basic buttons were kept.",
            topic="interface controls",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "more physical buttons", "rejected": True,
                 "reason": "users would tamper with them; the market wants convenient browsing"},
                {"option": "flip-top design", "rejected": True, "reason": "cost"},
                {"option": "screen menu with basic buttons", "rejected": False, "reason": None},
            ],
            rationale=[
                "The market wants convenient browsing rather than many buttons to tamper with.",
                "Symbols on the interface were to be simplified.",
            ],
        ),
        _rec(
            "QSUM_003", 2,
            decision="Lightweight plastic was temporarily set as the case material.",
            topic="case material",
            status=DecisionStatus.PROVISIONAL,
            alternatives=[
                {"option": "lightweight plastic", "rejected": False, "reason": None},
            ],
            conditions=[
                "The material choice was explicitly temporary and open to revision.",
            ],
        ),
    ],
    present_in_document=[
        "A screen menu display was adopted and only basic buttons were kept.",
        "Lightweight plastic was temporarily set as the case material.",
        "The material choice was explicitly temporary and open to revision.",
    ],
    notes=(
        "Task 1: the only row across all five pairs where the document faithfully keeps a "
        "qualifier -- the general summary preserves 'temporarily'. Keep this pair in any "
        "write-up so the claim does not read as 'documents always drop everything'. The "
        "flip-top rejection and the market reasoning are still lost."
    ),
)

# --------------------------------------------------------------------------- #
# QSUM_004 -- Task 1 Pair 4, Meeting 10: intelligent controller; material; alimentation
# --------------------------------------------------------------------------- #
QSUM_004 = GroundTruthPair(
    pair_id="QSUM_004",
    qmsum_meeting="M10",
    title="Intelligent controller concept; material and alimentation",
    decisions=[
        _rec(
            "QSUM_004", 1,
            decision=("The pure intelligent controller concept was rejected in favour of a hybrid of "
                      "the Google-style and fancy controllers with limited vocal commands."),
            topic="controller concept",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "Google-style controller", "rejected": False, "reason": None},
                {"option": "fancy controller", "rejected": False, "reason": None},
                {"option": "intelligent controller (voice and gesture)", "rejected": True,
                 "reason": "interference, cost, language burden and unresolved hardware"},
            ],
            rationale=[
                "Simultaneous use by several people would cause interference.",
                "It would increase the cost.",
                "It would add a language and localisation burden.",
                "The microphone and camera hardware questions were unresolved.",
            ],
            approver="Project Manager",
        ),
        _rec(
            "QSUM_004", 2,
            decision="Wood was chosen over plastic as the casing material.",
            topic="case material",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "wood", "rejected": False, "reason": None},
                {"option": "plastic", "rejected": True, "reason": None},
            ],
        ),
        _rec(
            "QSUM_004", 3,
            decision="Both battery and solar alimentation were adopted.",
            topic="alimentation",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "battery and solar together", "rejected": False, "reason": None},
            ],
            conditions=[
                "The design would increase the production cost, but this was treated as added value that can be compensated.",
            ],
        ),
    ],
    present_in_document=[
        "Google-style controller",
        "fancy controller",
        "intelligent controller (voice and gesture)",
        "Wood was chosen over plastic as the casing material.",
        "Both battery and solar alimentation were adopted.",
    ],
    notes=(
        "Task 1: the one case where alternatives survive into the general summary. The four "
        "distinct objections behind the rejection collapse to 'seriously questioned', and the "
        "cost condition on alimentation is dropped so the decision reads as unconditional. "
        "The PM is a de facto in-meeting approver but no formal owner is recorded. "
        "This pair also contains the single Task 2 NLI false positive: the wood/plastic "
        "element is present in the document but phrased as 'suggested... agreed by the group'."
    ),
)

# --------------------------------------------------------------------------- #
# QSUM_005 -- Task 1 Pair 5, Meeting 12: chip tier
# --------------------------------------------------------------------------- #
QSUM_005 = GroundTruthPair(
    pair_id="QSUM_005",
    qmsum_meeting="M12",
    title="Chip tier for speech recognition",
    decisions=[
        _rec(
            "QSUM_005", 1,
            decision="An advanced chip was approved in order to support speech recognition.",
            topic="chip tier",
            status=DecisionStatus.DECIDED,
            alternatives=[
                {"option": "regular chip", "rejected": True,
                 "reason": "would not support speech recognition"},
                {"option": "advanced chip", "rejected": False, "reason": None},
                {"option": "LCD display", "rejected": True,
                 "reason": "would have forced the most expensive chip"},
            ],
            rationale=[
                "Marketing pushed for positioning the product on technological innovation.",
            ],
            conditions=[
                "A newly available low-cost sensor component meant the advanced chip would not be expensive, which is what enabled the group to agree.",
            ],
            approver="Project Manager",
        ),
    ],
    present_in_document=[
        "speech recognition",
    ],
    notes=(
        "Task 1: the document lists speech recognition as a feature but never mentions the "
        "chip-tier decision or the LCD tradeoff at all -- a reader could not tell the "
        "decision happened. The PM proposed and the group agreed informally; approver is "
        "recorded as the PM as de facto in-meeting approver, not a formal sign-off."
    ),
)

GROUND_TRUTH: list[GroundTruthPair] = [QSUM_001, QSUM_002, QSUM_003, QSUM_004, QSUM_005]
BY_ID = {p.pair_id: p for p in GROUND_TRUTH}
BY_MEETING = {p.qmsum_meeting: p for p in GROUND_TRUTH}


def to_json(path: str | Path | None = None) -> str:
    payload = {
        "source": "outputs/gap_validation_results.md (Task 1)",
        "pairs": [
            {
                "pair_id": p.pair_id,
                "qmsum_meeting": p.qmsum_meeting,
                "title": p.title,
                "notes": p.notes,
                "present_in_document": p.present_in_document,
                "decisions": [d.model_dump(mode="json") for d in p.decisions],
            }
            for p in GROUND_TRUTH
        ],
    }
    blob = json.dumps(payload, indent=2, ensure_ascii=False)
    if path:
        Path(path).write_text(blob, encoding="utf-8")
    return blob


if __name__ == "__main__":
    total = 0
    for p in GROUND_TRUTH:
        elems = p.all_elements()
        total += len(elems)
        print(f"{p.pair_id} ({p.qmsum_meeting}): {len(p.decisions)} decision(s), "
              f"{len(elems)} reasoning element(s), "
              f"{len(p.present_in_document)} present in document")
    print(f"total reasoning elements: {total}")
