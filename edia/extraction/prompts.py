"""
Extraction prompts.

Design notes worth keeping (these are the choices a reviewer will ask about):

1. The instruction set names the five Task 1 reasoning slots explicitly rather than
   asking for "the decision and its context". The Task 1 tables show the gap is
   always in the same places -- alternatives, rationale, conditions, dissent -- so
   the prompt makes each of those a slot the model must either fill or leave empty.

2. Every filled slot needs a verbatim quote. This is the anti-hallucination lever:
   a 7B model asked for free-text rationale will invent plausible business reasoning,
   but a 7B model asked to also paste the exact words has a much harder time doing so
   silently, and when it does, the substring check in benchmark/score.py catches it.

3. "Return an empty list" is stated repeatedly and shown in the few-shot example,
   because the dominant 7B failure on this task is filling every field for the sake
   of filling it. The negative example is the important half of the prompt.

4. No cross-chunk merging: the prompt tells the model it is seeing one excerpt and
   must not speculate about what came before or after.
"""

SYSTEM_PROMPT = """\
You are a precise information extractor for meeting transcripts. You do not \
summarise, interpret, or add business context. You only report what is literally \
present in the excerpt you are given.

You return a single JSON object and nothing else.

Absolute rules:
- Extract ONLY what is stated in the excerpt. Never infer, never fill gaps with \
plausible reasoning, never use world knowledge about how such decisions usually go.
- Every quote you output must be copied CHARACTER-FOR-CHARACTER from the excerpt. \
Do not fix grammar, do not shorten, do not paraphrase inside quotes.
- If something is not in the excerpt, return an empty list or null for it. An empty \
field is a correct answer. A guessed field is a wrong answer.
- You are seeing one excerpt from a longer meeting. Do not speculate about what was \
said before or after it.
- If the excerpt contains no decision at all -- only chit-chat, agenda reading, or \
open discussion with nothing settled or proposed for settling -- return an empty \
decisions list.\
"""

# The JSON contract handed to the model. Mirrors edia.extraction.schema but is
# written in the model's terms (flat, no enums-by-name, no ids -- the code fills ids).
OUTPUT_CONTRACT = """\
Return exactly this shape:

{
  "decisions": [
    {
      "decision": "one sentence: what was decided",
      "topic": "two or three word subject label",
      "status": "decided | provisional | deferred | rejected | unclear",
      "alternatives": [
        {"option": "the other option named", "rejected": true, "reason": "stated reason, or null"}
      ],
      "rationale": ["a stated reason the chosen option won"],
      "conditions": ["a caveat, unresolved cost, risk, or dependency stated in the excerpt"],
      "dissent": ["a disagreement or objection someone actually voiced"],
      "owner": "person or role who will carry it out, or null",
      "approver": "person or role who explicitly signed off, or null",
      "evidence": [
        {"quote": "verbatim span from the excerpt", "speaker": "speaker label or null",
         "supports": "decision | alternative | rationale | condition | dissent | owner | approver | status"}
      ],
      "extraction_confidence": 0.0
    }
  ]
}

Field meanings:
- status: use "provisional" when the excerpt marks the decision as temporary or \
conditional (e.g. "for now", "temporarily", "unless we find something better"). \
Use "deferred" when it is explicitly pushed to later. Use "rejected" when the \
proposal being discussed was turned down. Use "unclear" when it was discussed but \
not resolved in this excerpt.
- alternatives: options that were genuinely on the table. rejected=true if turned \
down, false if this is the option chosen, null if left open.
- rationale: WHY the choice was made. Only reasons someone actually stated.
- conditions: things the decision depends on, unresolved costs, open risks, caveats.
- dissent: objections voiced by someone, even if they were overruled or later agreed.
- owner/approver: null unless a specific person or role is named as responsible or \
as signing off. Group agreement is NOT an approver -- leave it null.
- evidence: at least one quote per decision. Add quotes for rationale, conditions, \
and dissent where you filled them.
- extraction_confidence: 0.0-1.0, your own confidence this decision is real and \
correctly characterised.\
"""

# One positive and one negative example. The negative example carries most of the
# weight -- it is the case a 7B model gets wrong by default.
FEW_SHOT = """\
Example A -- excerpt:
---
Project Manager: So for the power, what are we thinking?
Industrial Designer: I'd say a standard battery, it's cheap and people get it.
Marketing: Solar's an option but indoors it just won't charge reliably.
Industrial Designer: Honestly I'm not sold on the dynamo either, too much cranking.
Project Manager: The chip dominates our cost anyway, so power source cost is \
secondary. Let's go with kryptonite for the innovation angle.
User Interface: Just so it's on record, the website did not give an actual cost for it.
---
Correct output:
{
  "decisions": [
    {
      "decision": "Kryptonite was chosen as the energy source for the remote.",
      "topic": "energy source",
      "status": "decided",
      "alternatives": [
        {"option": "standard battery", "rejected": true, "reason": "cheap and familiar, but not chosen"},
        {"option": "solar", "rejected": true, "reason": "will not charge reliably indoors"},
        {"option": "dynamo", "rejected": true, "reason": "too much cranking"},
        {"option": "kryptonite", "rejected": false, "reason": "innovation angle"}
      ],
      "rationale": ["The chip dominates the cost, so the power source's own cost is secondary."],
      "conditions": ["No actual cost for kryptonite was ever found."],
      "dissent": ["The Industrial Designer preferred a standard battery and was not sold on the dynamo."],
      "owner": null,
      "approver": null,
      "evidence": [
        {"quote": "Let's go with kryptonite for the innovation angle.", "speaker": "Project Manager", "supports": "decision"},
        {"quote": "The chip dominates our cost anyway, so power source cost is secondary.", "speaker": "Project Manager", "supports": "rationale"},
        {"quote": "the website did not give an actual cost for it", "speaker": "User Interface", "supports": "condition"},
        {"quote": "I'd say a standard battery, it's cheap and people get it.", "speaker": "Industrial Designer", "supports": "dissent"}
      ],
      "extraction_confidence": 0.9
    }
  ]
}

Example B -- excerpt with NO decision:
---
Project Manager: Alright, is everyone on the call? Let me share my screen.
Marketing: Can you make it bigger, I can't read the third bullet.
Project Manager: Better? Okay, so the agenda today is the interface concept, \
then the evaluation criteria.
Marketing: Sounds good.
---
Correct output:
{"decisions": []}

Note what Example B does NOT do: it does not invent "the team decided to discuss \
the interface concept" as a decision. An agenda is not a decision.\
"""


# Phase 3.1 ablation (EDIA_Project_Plan_v2.md): does asking the model to reason
# before extracting help? The plan's hypothesis is that CoT improves reasoning at
# answer time but does not help find facts scattered across a chunk, so any gain
# should be small.
#
# This has to be a SEPARATE unconstrained call, not an instruction bolted onto the
# extraction prompt. OllamaClient.chat_json sends format="json", which
# grammar-constrains decoding to a JSON object -- under that constraint the model
# physically cannot emit reasoning tokens first, so a "think step by step" line in
# the extraction prompt is a silent no-op and the ablation would measure prompt
# wording noise rather than chain-of-thought. Pass 1 (chat_text) reasons; pass 2
# (chat_json) extracts with that reasoning in context.
COT_SYSTEM_PROMPT = """\
You are analysing an excerpt from a meeting transcript. Think step by step about \
what was decided and what reasoning was given. Do not produce JSON. Write short \
plain-text notes only.\
"""


def build_cot_prompt(chunk_text: str, speakers: list[str] | None = None) -> str:
    speaker_line = (
        f"Speakers present in this excerpt: {', '.join(speakers)}\n" if speakers else ""
    )
    return f"""Let's think step by step about what decisions and reasoning appear in \
this excerpt.

Work through it and note, in a few short lines each:
- any decision that was settled, proposed, rejected, or deferred
- any alternative option that was named
- any stated reason why an option was chosen or rejected
- any condition, caveat, unresolved cost, or dependency
- any objection or disagreement someone voiced

Only note things actually stated in the excerpt. If there is no decision at all, \
say so in one line.

{speaker_line}Excerpt:
---
{chunk_text}
---

Your notes:"""


COT_PREFIX = """\
You previously analysed this excerpt and made these notes:

{notes}

Use those notes to help you, but extract ONLY what the excerpt itself states. If a \
note is not supported by the excerpt, ignore it.

"""


def build_user_prompt(
    chunk_text: str, speakers: list[str] | None = None, cot_notes: str | None = None
) -> str:
    speaker_line = (
        f"Speakers present in this excerpt: {', '.join(speakers)}\n" if speakers else ""
    )
    cot_block = COT_PREFIX.format(notes=cot_notes.strip()) if cot_notes else ""
    return f"""{OUTPUT_CONTRACT}

{FEW_SHOT}

Now do the same for this excerpt.

{cot_block}{speaker_line}Excerpt:
---
{chunk_text}
---

Return the JSON object only."""


REPAIR_PROMPT = """\
Your previous response was not valid against the required schema.

Error: {error}

Your response was:
{previous}

Return the SAME information, corrected to match the schema exactly. Do not add new \
decisions, do not invent content to fill fields -- only fix the structure. If a field \
cannot be filled from the excerpt, use an empty list or null.

Return the JSON object only."""
