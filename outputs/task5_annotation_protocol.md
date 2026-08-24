# Task 5 — annotation protocol

This is the document the two annotators read before starting. It exists because the
Jaccard > 0.6 target is only meaningful if both people are answering the same question;
most disagreement in this kind of labelling comes from an unstated definition, not from
genuine ambiguity in the text.

## What you are being asked

For each reasoning element, with the **document** in front of you:

> Does this document contain this piece of reasoning?

You are **not** being asked whether the document is good, whether the decision was
right, or what else is missing. One element at a time, four possible answers:

| Key | Label | Means |
|---|---|---|
| `o` | omitted | the document does not contain this at all |
| `v` | verbatim | present, in near-identical wording |
| `p` | paraphrased | present, but reworded |
| `y` | present | present, and you cannot cleanly call it verbatim or reworded |
| `?` | flag | you genuinely cannot decide — records a flag for adjudication |

Run it with:

```bash
python -m edia.benchmark.annotate --annotator <your-name>
```

The second annotator on a pair works **blind** — no visible labels from the generator or
from the first annotator. Do not compare notes on a pair before both passes are recorded;
that is the whole basis of the agreement number.

## Decision rules (read these — they are where the disagreements come from)

**1. Judge content, not wording.** "The board approved it" and "sign-off came from the
board" are the same element. If the meaning survives, it is present.

**2. A topic mention is not the element.** A document that says "the team discussed the
chip" does not contain the element "an advanced chip was approved to support speech
recognition". Naming the subject is not recording the reasoning. This is the single most
common source of split judgements, and Task 1 hit it directly: QSUM_001's document names
all three casing shapes but never says which one won — the alternatives are present, the
decision is **omitted**.

**3. Hedged presence still counts as present.** "Some concerns were raised about cost"
does contain a cost condition, even weakly. Mark it present (`p`) and put a note on the
pair. Do not mark it omitted because it is vague.

**4. Vague gestures at reasoning are omitted.** "After weighing the options, the team
decided X" contains no alternatives and no rationale. It gestures at reasoning without
recording any. That is exactly the failure the project is about — mark `o`.

**5. Rationale vs. condition.** Rationale is why the chosen option won. A condition is
something unresolved or depended-upon. If the document keeps one and not the other, label
each on its own — they are separate elements and often have different answers.

**6. Partial presence goes to the element that is actually there.** If an element is
"rejected because of cost and localisation burden" and the document mentions only cost,
mark it present (`p`) and flag it. The adjudication pass decides whether the element
should be split.

**7. When you truly cannot tell, flag it.** `?` is a legitimate answer and is better than
a coin flip. Flags are reviewed; guesses silently corrupt the agreement number.

## What to do with a bad pair

Synthetic pairs are model-generated and some will be poor. Press `x` to reject the whole
pair and say why. Reject when:

- the transcript does not actually contain a decision;
- the document contradicts the transcript rather than compressing it;
- the meeting is incoherent enough that you cannot follow what was decided.

Do **not** reject a pair merely for reading a bit stiffly. Cleanness is a known limitation
of the synthetic half and is why the five QMSum pairs are in the same dataset.

Pairs whose notes begin `AUTOMATIC LEAK FLAG` were caught by the generator mentioning
something in the document that was supposed to be omitted. Those need your labels most:
label what the document actually says, not what the generator intended.

## Volume and pacing

- 50 synthetic pairs, roughly 8–12 elements each ≈ 450–550 judgements for the full pass.
- 10 of those pairs get a second, blind pass for agreement (Task 5 step 3).
- The five QMSum pairs (QSUM_001–005) already carry Task 1 labels and are **not**
  re-annotated. If you disagree with one while reading it, raise it — do not silently
  relabel, because Tasks 1 and 2 are already reported against those labels.
- Expect 5–10 minutes per pair. Do not do all 50 in one sitting; label drift after an hour
  is real and shows up as a worse agreement score.

## After annotation

```bash
python -m edia.benchmark.agreement
```

Reports pooled Jaccard on the gap sets (the stated target), Cohen's kappa, and the
per-element disagreements. Read the kappa: our documents drop most reasoning, so the gap
class is large, and two annotators marking nearly everything a gap can clear Jaccard 0.6
on chance alone. The tool prints an explicit warning when that pattern appears —
if it does, the target is met on paper only and should be reported that way.
