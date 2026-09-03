"""
The topic space the synthetic benchmark is generated over.

Scaled up from the original 10 hand-written topics to a **domain x decision-
archetype matrix**: ~12 organisational settings crossed with ~10 kinds of decision,
= ~120 topics, x PAIRS_PER_TOPIC variants each ≈ 2000 pairs. That size is what
makes the per-domain / per-element-type / per-label breakdowns in the gap eval
statistically meaningful rather than anecdotal.

NOTE FOR THE TEAM (carried over from the original file): the task brief refers to
"the existing topic list", which was never in the Task 1-3 handover. This matrix is
a principled stand-in. If a canonical list turns up, replace `DOMAINS` /
`ARCHETYPES` -- `TOPICS` and every id/seed derives from them, so a swap before
generation changes nothing else.

Design constraints kept from the original:
  * every archetype is a decision type where rejected alternatives and conditions
    are normal (that is what the Task 1 taxonomy scores);
  * domains span engineering / commercial / people / policy, not five flavours of
    one, because Task 1's honest caveat 3 is single-domain n=5;
  * none of it is an AMI-style product-design meeting -- the QMSum pairs own that
    domain and duplicating it would wreck the fold-in comparison.

Id scheme: ``SYN_<topic index, 4 digits>_<variant, 3 digits>`` e.g. ``SYN_0007_012``.
Seeds are handed out by `pair_plan()` (unique per pair) -- nothing parses the id
for a seed any more.
"""

from __future__ import annotations

from dataclasses import dataclass

PAIRS_PER_TOPIC = 17
BASE_SEED = 1000


@dataclass(frozen=True)
class Domain:
    key: str
    label: str
    setting: str          # who is in the room


@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    axis: str             # the tradeoff decisions of this kind turn on


@dataclass(frozen=True)
class Topic:
    key: str              # "<domain>__<archetype>"
    label: str
    setting: str
    example_axis: str


# The original 10, preserved as domains (their settings were already good), plus
# two that mirror QMSum's non-Product domains so the synthetic set is not purely
# corporate.
DOMAINS: list[Domain] = [
    Domain("cloud_platform", "Cloud platform / infrastructure",
           "platform engineering lead, SRE, finance partner, CTO"),
    Domain("vendor_tooling", "Vendor & tooling",
           "procurement, engineering manager, security reviewer, budget owner"),
    Domain("hiring", "Headcount & hiring",
           "engineering director, recruiter, finance partner, team lead"),
    Domain("pricing_packaging", "Pricing & packaging",
           "head of product, sales lead, finance analyst, customer success"),
    Domain("security_incident", "Security incident & disclosure",
           "security lead, on-call engineer, legal counsel, comms lead"),
    Domain("release_scope", "Release scope & delivery",
           "product manager, tech lead, designer, QA lead"),
    Domain("data_governance", "Data retention & governance",
           "data protection officer, data engineer, analytics lead, legal counsel"),
    Domain("architecture", "Core architecture & frameworks",
           "principal engineer, backend lead, mobile lead, staff engineer"),
    Domain("workplace_policy", "Workplace & working arrangements",
           "COO, people partner, department head, employee representative"),
    Domain("marketing_spend", "Marketing spend & channels",
           "marketing director, performance marketer, brand lead, finance partner"),
    Domain("academic_lab", "Academic research group",
           "principal investigator, postdoc, PhD student, lab manager"),
    Domain("public_committee", "Public-body committee",
           "committee chair, permanent secretary, external adviser, member for the opposition"),
]

ARCHETYPES: list[Archetype] = [
    Archetype("vendor_selection", "Vendor / tool selection",
              "price vs feature fit vs support quality vs switching cost"),
    Archetype("build_vs_buy", "Build vs buy",
              "control and fit vs time-to-value vs long-run maintenance load"),
    Archetype("scope_cut", "Scope reduction",
              "ship date vs feature completeness vs accrued technical debt"),
    Archetype("budget_allocation", "Budget allocation",
              "measurable near-term return vs strategic bets vs concentration risk"),
    Archetype("policy_change", "Policy change",
              "consistency and control vs flexibility vs enforcement cost"),
    Archetype("headcount_plan", "Headcount plan",
              "speed of hiring vs seniority mix vs budget envelope"),
    Archetype("tech_choice", "Technical / framework choice",
              "team familiarity vs long-term maintainability vs performance"),
    Archetype("risk_response", "Risk / incident response",
              "speed of action vs completeness of investigation vs exposure"),
    Archetype("process_change", "Process / ways-of-working change",
              "predictability vs autonomy vs coordination overhead"),
    Archetype("deprecation", "Deprecation / sunset",
              "maintenance savings vs migration burden on users vs reputational cost"),
]


def _build_topics() -> list[Topic]:
    topics: list[Topic] = []
    for d in DOMAINS:
        for a in ARCHETYPES:
            topics.append(Topic(
                key=f"{d.key}__{a.key}",
                label=f"{a.label} — {d.label}",
                setting=d.setting,
                example_axis=a.axis,
            ))
    return topics


TOPICS: list[Topic] = _build_topics()
BY_KEY = {t.key: t for t in TOPICS}


def pair_plan() -> list[tuple[str, Topic, int, int]]:
    """The full plan: (pair_id, topic, variant_index, seed).

    pair_id encodes topic + variant position so a partial run resumes trivially
    and a regenerated pair keeps its identity. seed is unique per pair and is NOT
    recoverable from the id -- callers take it from here.
    """
    plan: list[tuple[str, Topic, int, int]] = []
    for ti, topic in enumerate(TOPICS):
        for vi in range(1, PAIRS_PER_TOPIC + 1):
            pair_id = f"SYN_{ti:04d}_{vi:03d}"
            seed = BASE_SEED + ti * PAIRS_PER_TOPIC + vi
            plan.append((pair_id, topic, vi, seed))
    return plan


if __name__ == "__main__":
    plan = pair_plan()
    print(f"{len(DOMAINS)} domains x {len(ARCHETYPES)} archetypes = {len(TOPICS)} topics")
    print(f"x {PAIRS_PER_TOPIC} variants = {len(plan)} pairs")
    print(f"unique ids: {len({p[0] for p in plan})}, unique seeds: {len({p[3] for p in plan})}")
    for pid, topic, vi, seed in plan[:4]:
        print(f"  {pid}  {topic.key}  v{vi}  seed={seed}")
    print("  ...")
    print(f"  {plan[-1][0]}  {plan[-1][1].key}  v{plan[-1][2]}  seed={plan[-1][3]}")
