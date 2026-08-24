"""
Turn-aware chunking for meeting transcripts and decision documents.

Why not a naive character window: the reasoning elements Task 1 found (rejected
alternatives, objection chains, cost conditions) live inside multi-turn exchanges.
Cutting mid-turn strands a speaker's objection from the answer to it, which is
exactly the content the extractor exists to recover. So:

  * a speaker turn is atomic -- never split, unless one turn alone exceeds the
    budget, in which case it is split on sentence boundaries and marked;
  * consecutive chunks overlap by whole turns, so an exchange straddling a
    boundary is seen intact by at least one chunk;
  * every chunk carries its turn range, so a DecisionRecord can be traced back
    to specific lines of the transcript.

Chunks are deliberately independent: nothing here tries to reconcile the same
decision appearing in two overlapping chunks. That is a later step (Task 4 says
do not merge across chunks yet).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# "SPEAKER: text" at line start. Tolerates "Project Manager:", "PM :", "Speaker 1:".
_SPEAKER_RE = re.compile(r"^\s*([A-Za-z][\w .'\-/]{0,59}?)\s*:\s+(.*)$")

# A colon alone is not enough -- "The real problem is this: cost" is prose, not a
# speaker turn. Require a short, capitalised label: 1-5 words, each starting with
# an uppercase letter or a digit.
_LABEL_WORD_RE = re.compile(r"^[A-Z0-9][\w.'\-/]*$")


def _looks_like_speaker(label: str) -> bool:
    words = label.split()
    if not (1 <= len(words) <= 5):
        return False
    return all(_LABEL_WORD_RE.match(w) for w in words)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Rough char-per-token ratio for English prose. Deliberately conservative (under-
# estimating tokens would overflow the model's window, which is the failure that
# actually hurts).
CHARS_PER_TOKEN = 3.6


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


@dataclass
class Turn:
    index: int
    speaker: str | None
    text: str

    def render(self) -> str:
        return f"{self.speaker}: {self.text}" if self.speaker else self.text

    @property
    def est_tokens(self) -> int:
        return estimate_tokens(self.render())


@dataclass
class Chunk:
    chunk_id: str
    source_id: str
    index: int
    text: str
    turn_start: int
    turn_end: int                       # inclusive
    speakers: list[str] = field(default_factory=list)
    est_tokens: int = 0
    overlap_turns: int = 0              # how many leading turns are repeated from the previous chunk
    split_turn: bool = False            # True if an oversized single turn had to be broken up

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "index": self.index,
            "text": self.text,
            "turn_start": self.turn_start,
            "turn_end": self.turn_end,
            "speakers": self.speakers,
            "est_tokens": self.est_tokens,
            "overlap_turns": self.overlap_turns,
            "split_turn": self.split_turn,
        }


def parse_turns(raw_text: str) -> list[Turn]:
    """Split transcript text into speaker turns.

    Continuation lines (no speaker prefix) are appended to the current turn.
    Text with no speaker labels at all comes back as paragraph-level turns with
    speaker=None, so decision documents chunk through the same code path.
    """
    turns: list[Turn] = []
    current: Turn | None = None

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            # blank line ends a speakerless paragraph, but not a speaker turn
            if current is not None and current.speaker is None:
                turns.append(current)
                current = None
            continue

        m = _SPEAKER_RE.match(stripped)
        if m and _looks_like_speaker(m.group(1).strip()):
            if current is not None:
                turns.append(current)
            speaker, text = m.group(1).strip(), m.group(2).strip()
            current = Turn(index=len(turns), speaker=speaker, text=text)
        elif current is not None:
            current.text = f"{current.text} {stripped}".strip()
        else:
            current = Turn(index=len(turns), speaker=None, text=stripped)

    if current is not None:
        turns.append(current)

    for i, t in enumerate(turns):
        t.index = i
    return turns


def _split_oversized_turn(turn: Turn, max_tokens: int) -> list[str]:
    """Break one very long turn into <=max_tokens pieces on sentence boundaries."""
    sentences = _SENTENCE_RE.split(turn.text) or [turn.text]
    prefix = f"{turn.speaker}: " if turn.speaker else ""
    pieces: list[str] = []
    buf: list[str] = []

    for sent in sentences:
        candidate = " ".join(buf + [sent])
        if buf and estimate_tokens(prefix + candidate) > max_tokens:
            pieces.append(prefix + " ".join(buf))
            buf = [sent]
        else:
            buf.append(sent)
    if buf:
        pieces.append(prefix + " ".join(buf))

    # A single sentence longer than the budget: hard-cut it rather than loop forever.
    out: list[str] = []
    limit = int(max_tokens * CHARS_PER_TOKEN)
    for piece in pieces:
        while estimate_tokens(piece) > max_tokens:
            out.append(piece[:limit])
            piece = piece[limit:]
        if piece:
            out.append(piece)
    return out


def chunk_text(
    raw_text: str,
    source_id: str,
    max_tokens: int = 1200,
    overlap_turns: int = 2,
    min_tokens: int = 40,
) -> list[Chunk]:
    """Chunk raw text into turn-aligned, overlapping windows.

    max_tokens    -- budget for the chunk body only; leave headroom for the prompt.
    overlap_turns -- whole turns repeated at the head of the next chunk.
    min_tokens    -- a trailing chunk smaller than this is folded into the previous
                     one instead of being sent to the model on its own (a 15-token
                     tail chunk produces noise, not decisions).
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_turns < 0:
        raise ValueError("overlap_turns must be >= 0")

    turns = parse_turns(raw_text)
    if not turns:
        return []

    chunks: list[Chunk] = []
    i = 0
    carried = 0  # how many of the turns starting at i are overlap from the previous chunk

    while i < len(turns):
        buf: list[Turn] = []
        used = 0
        split_turn = False
        j = i

        while j < len(turns):
            t = turns[j]
            if t.est_tokens > max_tokens and not buf:
                # One turn alone blows the budget -- emit it as its own split chunks.
                for k, piece in enumerate(_split_oversized_turn(t, max_tokens)):
                    chunks.append(
                        Chunk(
                            chunk_id=f"{source_id}_c{len(chunks):03d}",
                            source_id=source_id,
                            index=len(chunks),
                            text=piece,
                            turn_start=t.index,
                            turn_end=t.index,
                            speakers=[t.speaker] if t.speaker else [],
                            est_tokens=estimate_tokens(piece),
                            overlap_turns=0,
                            split_turn=True,
                        )
                    )
                split_turn = True
                j += 1
                break
            if used + t.est_tokens > max_tokens and buf:
                break
            buf.append(t)
            used += t.est_tokens
            j += 1

        if split_turn and not buf:
            i = j
            carried = 0
            continue

        text = "\n".join(t.render() for t in buf)
        speakers: list[str] = []
        for t in buf:
            if t.speaker and t.speaker not in speakers:
                speakers.append(t.speaker)

        chunk = Chunk(
            chunk_id=f"{source_id}_c{len(chunks):03d}",
            source_id=source_id,
            index=len(chunks),
            text=text,
            turn_start=buf[0].index,
            turn_end=buf[-1].index,
            speakers=speakers,
            est_tokens=used,
            overlap_turns=min(carried, len(buf)),
        )
        chunks.append(chunk)

        if j >= len(turns):
            break

        # Step back by overlap_turns, but always make forward progress.
        step_back = min(overlap_turns, max(len(buf) - 1, 0))
        next_i = j - step_back
        if next_i <= i:
            next_i = i + max(len(buf), 1)
        carried = j - next_i
        i = next_i

    # Fold a too-small tail chunk into its predecessor.
    if len(chunks) > 1 and chunks[-1].est_tokens < min_tokens and not chunks[-1].split_turn:
        tail = chunks.pop()
        prev = chunks[-1]
        # Only the non-overlapping part of the tail is new text.
        prev.text = f"{prev.text}\n{tail.text}"
        prev.turn_end = max(prev.turn_end, tail.turn_end)
        prev.est_tokens = estimate_tokens(prev.text)
        for s in tail.speakers:
            if s not in prev.speakers:
                prev.speakers.append(s)

    return chunks


def chunk_document(doc, max_tokens: int = 1200, overlap_turns: int = 2) -> list[Chunk]:
    """Chunk an ingestion.models.IngestedDocument.

    Decision documents are short and are chunked with the same code path; they
    usually come back as a single chunk, which is what we want -- a document
    should be judged whole.
    """
    source_id = getattr(doc, "file_name", "unknown").rsplit(".", 1)[0]
    return chunk_text(
        doc.raw_text,
        source_id=source_id,
        max_tokens=max_tokens,
        overlap_turns=overlap_turns,
    )
