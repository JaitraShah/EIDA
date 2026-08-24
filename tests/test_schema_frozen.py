"""Freeze test for edia.extraction.schema.

Task 4 step 2: the schema is frozen before anything downstream is built. If this
test fails, someone changed the wire format. That is allowed ONLY as a deliberate
act: bump SCHEMA_VERSION, update EXPECTED_SCHEMA_FINGERPRINT here, and tell the
team -- do not "fix" the test by pasting the new hash silently.
"""
from edia.extraction.schema import (
    SCHEMA_VERSION,
    DecisionRecord,
    DecisionStatus,
    ElementType,
    schema_fingerprint,
)

EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_SCHEMA_FINGERPRINT = (
    "463d9d8446c4a0076779067ced99977bd1eb824f3a74aaf849f93bb806c08f2c"
)


def test_schema_version_pinned():
    assert SCHEMA_VERSION == EXPECTED_SCHEMA_VERSION


def test_schema_fingerprint_pinned():
    assert schema_fingerprint() == EXPECTED_SCHEMA_FINGERPRINT, (
        "DecisionRecord/ExtractionResult wire format changed. Bump SCHEMA_VERSION "
        "and update EXPECTED_SCHEMA_FINGERPRINT deliberately."
    )


def test_required_fields_present():
    fields = set(DecisionRecord.model_fields)
    for required in (
        "decision_id", "source_id", "chunk_id", "decision", "status",
        "alternatives", "rationale", "conditions", "dissent",
        "owner", "approver", "evidence",
    ):
        assert required in fields, f"schema lost field {required!r}"


def test_extra_fields_rejected():
    import pytest
    with pytest.raises(Exception):
        DecisionRecord(
            decision_id="x", source_id="s", chunk_id="c", decision="d",
            invented_field="nope",
        )


def test_owner_approver_nullable():
    """Task 1 caveat 1: AMI-style data records no formal sign-off. Null must be legal."""
    rec = DecisionRecord(decision_id="x", source_id="s", chunk_id="c", decision="d")
    assert rec.owner is None and rec.approver is None
    assert rec.status is DecisionStatus.DECIDED


def test_provisional_status_exists():
    """Task 1 pair 3 kept the word 'temporarily' -- the schema must be able to hold that."""
    assert DecisionStatus.PROVISIONAL.value == "provisional"


def test_reasoning_elements_flatten():
    rec = DecisionRecord(
        decision_id="x", source_id="s", chunk_id="c",
        decision="Kryptonite chosen as energy source",
        alternatives=[{"option": "battery", "rejected": True, "reason": "ID preferred it but lost"}],
        rationale=["chip dominates cost anyway"],
        conditions=["exact kryptonite price never found"],
        dissent=["Industrial Designer preferred battery"],
    )
    kinds = [k for k, _ in rec.reasoning_elements()]
    assert kinds.count(ElementType.DECISION) == 1
    assert ElementType.ALTERNATIVE in kinds
    assert ElementType.CONDITION in kinds
    assert ElementType.DISSENT in kinds
    assert len(rec.reasoning_elements()) == 5
