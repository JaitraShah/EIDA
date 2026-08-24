"""
The 10 topics the synthetic benchmark is built over, 5 pairs each = 50 pairs.

NOTE FOR THE TEAM: the task brief refers to "the existing topic list", which was not
in the Task 1-3 handover (gap_validation_results.md, nli_transfer_test_results.md,
task3_ingestion_output_summary.md, edia_ingestion_module.zip). This list is a
stand-in built to the same shape. If the team's canonical list differs, replace
TOPICS here -- it is the single place topics are defined, and pair ids are derived
from list position, so swapping the list before generation changes nothing else.

Selection criteria, so the substitution is at least principled:
  * every topic is a decision type where rejected alternatives and conditions are
    normal, because that is what the Task 1 taxonomy scores;
  * they span domains (engineering, commercial, people, policy) rather than five
    flavours of one, since Task 1's honest caveat 3 is that its n=5 came from a
    single domain and cannot claim generality;
  * none of them is an AMI-style product design meeting -- the QMSum pairs already
    cover that domain, and duplicating it would make the fold-in comparison useless.
"""

from __future__ import annotations

from dataclasses import dataclass

PAIRS_PER_TOPIC = 5


@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    setting: str          # who is in the room
    example_axis: str     # the kind of tradeoff decisions here turn on


TOPICS: list[Topic] = [
    Topic("cloud_migration", "Cloud platform migration",
          "platform engineering lead, SRE, finance partner, CTO",
          "cost vs migration risk vs vendor lock-in"),
    Topic("vendor_selection", "Vendor / tooling selection",
          "procurement, engineering manager, security reviewer, budget owner",
          "price vs feature fit vs support quality vs switching cost"),
    Topic("hiring_plan", "Headcount and hiring plan",
          "engineering director, recruiter, finance partner, team lead",
          "speed of hiring vs seniority mix vs budget envelope"),
    Topic("pricing_change", "Pricing or packaging change",
          "head of product, sales lead, finance analyst, customer success",
          "revenue upside vs churn risk vs sales-cycle complexity"),
    Topic("incident_response", "Security incident response and disclosure",
          "security lead, on-call engineer, legal counsel, comms lead",
          "speed of disclosure vs completeness of investigation vs legal exposure"),
    Topic("scope_cut", "Release scope reduction",
          "product manager, tech lead, designer, QA lead",
          "ship date vs feature completeness vs technical debt"),
    Topic("data_retention", "Data retention and deletion policy",
          "data protection officer, data engineer, analytics lead, legal counsel",
          "regulatory exposure vs analytical value vs storage cost"),
    Topic("architecture_choice", "Core architecture or framework choice",
          "principal engineer, backend lead, mobile lead, staff engineer",
          "team familiarity vs long-term maintainability vs performance"),
    Topic("workplace_policy", "Return-to-office / working arrangement policy",
          "COO, people partner, department head, employee representative",
          "collaboration benefits vs retention risk vs facilities cost"),
    Topic("campaign_budget", "Marketing campaign budget allocation",
          "marketing director, performance marketer, brand lead, finance partner",
          "measurable acquisition vs brand building vs channel concentration risk"),
]

BY_KEY = {t.key: t for t in TOPICS}


def pair_plan() -> list[tuple[str, Topic, int]]:
    """The full 50-pair plan: (pair_id, topic, variant_index).

    pair_id encodes position so a partially generated run is trivially resumable and
    so a regenerated pair keeps its identity: SYN_<topic#><variant#>.
    """
    plan: list[tuple[str, Topic, int]] = []
    for ti, topic in enumerate(TOPICS, start=1):
        for vi in range(1, PAIRS_PER_TOPIC + 1):
            plan.append((f"SYN_{ti:02d}{vi}", topic, vi))
    return plan


if __name__ == "__main__":
    plan = pair_plan()
    print(f"{len(TOPICS)} topics x {PAIRS_PER_TOPIC} = {len(plan)} pairs")
    for pid, topic, vi in plan[:6]:
        print(f"  {pid}  {topic.key} variant {vi}")
    print("  ...")
    print(f"  {plan[-1][0]}  {plan[-1][1].key} variant {plan[-1][2]}")
