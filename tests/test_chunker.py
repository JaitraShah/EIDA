from edia.extraction.chunker import (
    Chunk, chunk_text, estimate_tokens, parse_turns,
)

TRANSCRIPT = """Project Manager: Okay so let's talk about the energy source.
Industrial Designer: I would say battery. It's cheap and everyone understands it.
Marketing: But kryptonite gives us the innovation angle we need.
Industrial Designer: I'm skeptical of the dynamo though, it's a lot of hand cranking.
Project Manager: The chip is the most expensive part regardless, so let's go kryptonite.
User Interface: The website did not give an actual cost for kryptonite.
"""


def test_parse_turns_basic():
    turns = parse_turns(TRANSCRIPT)
    assert len(turns) == 6
    assert turns[0].speaker == "Project Manager"
    assert turns[1].speaker == "Industrial Designer"
    assert "battery" in turns[1].text


def test_continuation_lines_join_previous_turn():
    txt = "PM: first part\nof the same sentence\nID: next speaker"
    turns = parse_turns(txt)
    assert len(turns) == 2
    assert turns[0].text == "first part of the same sentence"


def test_prose_without_speakers_becomes_paragraph_turns():
    txt = "The team chose kryptonite.\n\nThe casing will be single curved.\n"
    turns = parse_turns(txt)
    assert len(turns) == 2
    assert all(t.speaker is None for t in turns)


def test_colon_in_prose_not_treated_as_speaker():
    txt = "The real problem is this: the chip dominates the cost of the unit entirely."
    turns = parse_turns(txt)
    assert turns[0].speaker is None


def test_turns_are_never_split_when_they_fit():
    chunks = chunk_text(TRANSCRIPT, "M7", max_tokens=40, overlap_turns=1)
    assert len(chunks) > 1
    for c in chunks:
        for line in c.text.splitlines():
            assert line.strip(), "no blank/fragment lines"
        assert not c.split_turn


def test_all_turns_covered():
    turns = parse_turns(TRANSCRIPT)
    chunks = chunk_text(TRANSCRIPT, "M7", max_tokens=40, overlap_turns=1)
    covered = set()
    for c in chunks:
        covered.update(range(c.turn_start, c.turn_end + 1))
    assert covered == set(range(len(turns)))


def test_overlap_repeats_turns():
    chunks = chunk_text(TRANSCRIPT, "M7", max_tokens=45, overlap_turns=2)
    assert len(chunks) >= 2
    assert any(c.overlap_turns > 0 for c in chunks[1:])
    # the overlapped turn range must actually back up
    assert chunks[1].turn_start < chunks[0].turn_end + 1


def test_no_overlap_when_zero():
    chunks = chunk_text(TRANSCRIPT, "M7", max_tokens=45, overlap_turns=0)
    for a, b in zip(chunks, chunks[1:]):
        assert b.turn_start == a.turn_end + 1


def test_token_budget_respected():
    budget = 50
    chunks = chunk_text(TRANSCRIPT * 4, "M7", max_tokens=budget, overlap_turns=1)
    for c in chunks:
        assert c.est_tokens <= budget * 1.05, (c.chunk_id, c.est_tokens)


def test_oversized_single_turn_is_split_and_marked():
    long_turn = "PM: " + "This is a sentence about cost. " * 200
    chunks = chunk_text(long_turn, "BIG", max_tokens=60)
    assert len(chunks) > 1
    assert all(c.split_turn for c in chunks)
    assert all(c.est_tokens <= 66 for c in chunks)


def test_single_unsplittable_sentence_hard_cut_terminates():
    chunks = chunk_text("PM: " + "word" * 2000, "HARD", max_tokens=50)
    assert len(chunks) > 1
    assert all(c.est_tokens <= 55 for c in chunks)


def test_chunk_ids_unique_and_ordered():
    chunks = chunk_text(TRANSCRIPT * 3, "M7", max_tokens=45)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_tiny_tail_is_folded_into_previous_chunk():
    txt = TRANSCRIPT + "PM: Ok.\n"
    chunks = chunk_text(txt, "M7", max_tokens=200, overlap_turns=0, min_tokens=40)
    assert chunks[-1].est_tokens >= 40 or len(chunks) == 1


def test_empty_input():
    assert chunk_text("", "X") == []
    assert chunk_text("   \n\n  ", "X") == []


def test_speakers_recorded():
    chunks = chunk_text(TRANSCRIPT, "M7", max_tokens=500)
    assert "Project Manager" in chunks[0].speakers
    assert "Marketing" in chunks[0].speakers


def test_invalid_params():
    import pytest
    with pytest.raises(ValueError):
        chunk_text(TRANSCRIPT, "X", max_tokens=0)
    with pytest.raises(ValueError):
        chunk_text(TRANSCRIPT, "X", overlap_turns=-1)
