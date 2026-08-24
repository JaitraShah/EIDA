# Task 1 — Gap Validation Results

**Source:** QMSum, `data/Product/jsonl/test.jsonl` (AMI-derived remote-control design meetings)
**Method note (read first):** QMSum doesn't ship a literal "final decision document" — it ships
the raw multi-speaker transcript plus two levels of human-written summary: a **general summary**
(one paragraph covering the whole ~40-min meeting) and **specific-query answers** (a few sentences
per sub-topic, closer to a detailed meeting note). For this validation we treated the **specific-query
answers** (cross-checked against the raw transcript spans they're sourced from) as ground truth for
"what reasoning was in the discussion," and the **general summary** as the "final document" —
because that one-paragraph artifact is structurally the closest analogue in this dataset to the
one-line project doc in our problem story (§1 of the team understanding doc). This is a deliberate
substitution, not the literal QMSum "summary vs. source transcript" setup — flagging it because it's
exactly the kind of detail a faculty reviewer will ask about.

Two of the five pairs below were additionally spot-checked against the **raw transcript** (not just
the specific-query answer) to confirm the annotator summary wasn't itself smoothing over things —
see the note under Meetings 5 and 10.

---

## Pair 1 — Meeting 5 (remote control casing style + display)

**Decision:** Casing shape and display technology for the remote.

| Reasoning element | In discussion? | In document? |
|---|---|---|
| Alternatives considered (uncurved / single-curved / double-curved) | Yes | Partial — all three are *named*, but the general summary never states which one won |
| Rationale for choice (uncurved too dull; double-curved blocks scroll-wheel use) | Yes | No |
| Condition/rejected option (LCD display rejected — team already had scroll-wheel, speech recognition, rubber, fancy colours; PM actually leaned toward LCD for budget/flash reasons and was talked out of it) | Yes | No — LCD isn't mentioned at all |
| Owner / approver | N/A — team consensus, no individual sign-off recorded in this dataset (see limitation note below) | N/A |

*Raw-transcript spot check:* the LCD discussion in the actual transcript is a real back-and-forth
disagreement (PM: *"if we do have enough space in our finance, I would say do integrate it... it adds
extra high-tech feeling"* vs. Industrial Designer: *"it's too much"*) — the specific-query answer
compresses this fairly but the general summary drops the topic entirely, including the fact that it
was a live disagreement, not a unanimous call.

---

## Pair 2 — Meeting 7 (energy source selection)

**Decision:** "Kryptonite" chosen as the preferred energy source.

| Reasoning element | In discussion? | In document? |
|---|---|---|
| Alternatives considered (battery, solar, dynamo also on the table) | Yes | No — general summary states only the winner |
| Dissent (Industrial Designer actually preferred battery, was skeptical of dynamo) | Yes | No |
| Rationale (chip is the most expensive part regardless, so Kryptonite's own cost is a secondary concern) | Yes | No |
| Open risk/condition (exact price for Kryptonite was never found — "the website did not give an actual cost") | Yes | No — document states the choice with more confidence than the discussion actually had |
| Owner / approver | N/A | N/A |

---

## Pair 3 — Meeting 9 (menu display vs. more buttons)

**Decision:** Menu display adopted; basic buttons kept; case material temporarily set as lightweight plastic.

| Reasoning element | In discussion? | In document? |
|---|---|---|
| Rejected alternative (flip-top design, rejected specifically for cost) | Yes | No — not mentioned at all |
| Rationale (market wants convenient browsing, not many buttons to tamper with; symbol simplification) | Yes | Partial — document states the outcome ("user-friendly... basic buttons with self-intuitive screen menu") but not the market-based reasoning behind it |
| Provisional/conditional status of material decision | Yes ("temporarily decided") | **Yes** — the general summary actually preserves the word "temporarily" |
| Owner / approver | N/A | N/A |

*Note: this is the one row across all five pairs where the document faithfully kept a qualifier —
worth keeping in view so the write-up doesn't read as "the document always drops everything."*

---

## Pair 4 — Meeting 10 (intelligent controller; material & alimentation)

**Decision:** Pure "intelligent controller" (voice+gesture) concept rejected; hybrid of Google-style
and fancy controller with limited vocal commands adopted instead. Separately: wood over plastic;
both battery and solar alimentation.

| Reasoning element | In discussion? | In document? |
|---|---|---|
| Alternatives considered (Google controller / fancy controller / intelligent controller) | Yes | Yes — this is the one case where alternatives *do* survive into the general summary |
| Rationale for rejecting the intelligent controller (simultaneous multi-user interference, cost increase, language/localization burden, unresolved mic/camera hardware issues) | Yes — four distinct objections in the raw transcript | No — document only says it was "seriously questioned" |
| Condition/risk on the alimentation choice ("although the design would increase the production cost, it would be added value that can be compensated") | Yes | No — document states the decision as unconditional |
| Owner / approver | Project Manager acts as de facto approver in-meeting, but no named individual is recorded as formal owner | Not distinguished |

*Raw-transcript spot check:* confirms the specific-query answer isn't cherry-picking — the real
exchange has PM raising cost, interference, and language objections one at a time, each answered
provisionally by User Interface. None of that negotiation survives into the general summary.

---

## Pair 5 — Meeting 12 (chip tier for speech recognition)

**Decision:** Advanced chip approved to support speech recognition (over a regular chip).

| Reasoning element | In discussion? | In document? |
|---|---|---|
| Alternative considered (regular vs. advanced chip; separately, LCD ruled out earlier specifically because it would force the *most expensive* chip) | Yes | No — document lists "speech recognition" as a feature but never mentions the chip-tier decision or the LCD tradeoff |
| Rationale (Marketing's push for technological-innovation positioning) | Yes | No |
| Cost-mitigating condition (Industrial Designer's note that a newly available low-cost sensor component meant the advanced chip wouldn't be expensive — this directly enabled the group's agreement) | Yes | No |
| Owner / approver | PM proposed, group agreed informally | Not distinguished |

---

## Assessment

**Do gaps exist in most pairs?** Yes — 5/5. Every pair lost at least the rationale and at least one
rejected alternative or condition between the detailed discussion and the compressed document.

**Are the gaps decision-specific rather than generic filler?** Yes. What's dropped is consistently
the *reasoning infrastructure* around a decision — rejected alternatives (Meetings 2, 3, 5), the
specific objections behind a rejection (Meeting 4), and risk/cost conditions attached to an
otherwise-settled choice (Meetings 2, 4, 5). What's *kept* is almost always just the outcome itself
("they chose X"), and in one case (Meeting 1) even the outcome identity is left ambiguous. This
matches the project's core claim directly: documents record WHAT, not WHY.

**Could someone reading only the document recover the missing reasoning?** No, in 4 of 5 cases the
rationale is not recoverable from the document text at all — a reader would have no way to know
LCD was debated (Meeting 1), that battery/solar/dynamo were rejected in favor of Kryptonite
(Meeting 2), why the intelligent controller was rejected beyond "questioned" (Meeting 4), or that
the advanced-chip decision even happened (Meeting 5).

**Honest caveats for the team / faculty:**
1. This dataset (AMI-style product design meetings) doesn't model formal enterprise approval
   chains — there's no "owner" or "approver" field the way a real Confluence decision doc would
   have one. The owner/approver row is included per the task template but is genuinely N/A here;
   this is a dataset limitation, not a finding. Note it explicitly if this table goes in front of
   faculty, since PPT slide claims about "owner/approver" evidence should not point to this dataset.
2. One pair (Meeting 9, material provisionality) shows the document *correctly* preserving a
   qualifier — include this so the pitch doesn't overstate "documents always drop everything."
3. Sample size is 5 pairs from one domain (Product/AMI) — consistent with what Task 1 asked for,
   but not yet enough to claim a generalizable rate. That's what the 50-pair benchmark (Task 5) is for.

**Verdict: the core assumption holds.** Meaningful, decision-specific reasoning gaps exist between
discussion and document in this sample, and they are not generic omissions — they cluster
specifically around rejected alternatives, objection chains, and risk/conditions. Proceed to
Task 2 (test whether a pretrained NLI model can actually detect this automatically).
