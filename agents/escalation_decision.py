"""Escalation Decision Agent - Checkpoints 4 & 5.

An event-triggered CrewAI component running Tree-of-Thought via Beam Search -
a Strategy Proposer sub-role generates 3 candidate strategies, a Critic
sub-role scores each against a weighted rubric (Constraint Satisfaction 40%,
Stakeholder Appropriateness 25%, Prior Escalation History 20%, Downstream
Impact 15%), consulting the Knowledge Retrieval Agent's real Chroma search
for policy/SLA grounding (coordination/crew_escalation.py).

Requires ANTHROPIC_API_KEY. Without one (or if the crew call fails for any
reason - network, rate limit, malformed output), `evaluate()` falls back to
a small deterministic heuristic over the same 3 tiers, so the *shape* of the
decision (3 branches -> scored -> best selected -> confidence gate applied)
stays testable even before a key is configured. `engine` in the returned
dict says which path actually ran.
"""

from __future__ import annotations

from agents.knowledge_retrieval import retrieve
from coordination.llm import has_api_key
from guardrails.runtime_enforcement import log_action

TIER_LABELS = {
    1: "Tier 1 — direct owner reminder",
    2: "Tier 2 — escalate to team lead",
    3: "Tier 3 — escalate to senior management",
}


def _score_branch(tier: int, hours_overdue: float, prior_alerts: int) -> float:
    """Stand-in for the Critic's weighted rubric. Rewards Tier 1 when the
    step just became due with no prior alerts, Tier 2 once a Tier 1 alert
    has gone unanswered, and Tier 3 only once the situation is more severe -
    mirroring the "premature commitment" failure mode Checkpoint 4 calls out
    for plain chain-of-thought (never escalating on deadline proximity alone)."""
    if tier == 1:
        return max(0.9 - 0.15 * prior_alerts, 0.1)
    if tier == 2:
        if prior_alerts >= 1:
            return min(0.55 + 0.1 * prior_alerts + 0.02 * hours_overdue, 0.95)
        return 0.35
    # tier == 3
    if prior_alerts >= 2 or hours_overdue > 24:
        return min(0.6 + 0.05 * hours_overdue, 0.9)
    return 0.15


def _heuristic_branches(step: dict) -> list[dict]:
    hours_overdue = step.get("hours_overdue", 0.0)
    prior_alerts = step.get("prior_alerts_sent", 0)
    branches = []
    for tier in (1, 2, 3):
        score = round(_score_branch(tier, hours_overdue, prior_alerts), 2)
        branches.append({
            "tier": tier,
            "strategy_text": (
                f"{TIER_LABELS[tier]} for '{step['step_name']}' "
                f"(owner: {step['owner_name']})"
            ),
            "score": score,
        })
    return branches


def evaluate(step: dict) -> dict:
    """Runs the 3-branch ToT search (real CrewAI crew if a key is
    configured, the deterministic heuristic otherwise) and returns every
    branch plus the winner, so the UI can show the full trace - not just
    the final pick."""
    grounding = retrieve(f"escalation tier {step['step_name']}")
    grounding_text = "\n".join(f"({g['source']}) {g['text']}" for g in grounding)

    branches = None
    engine = "heuristic"

    if has_api_key():
        try:
            from coordination.crew_escalation import run_crew_escalation

            assessment = run_crew_escalation(step, grounding_text)
            branches = [b.model_dump() for b in assessment.branches]
            if len(branches) != 3 or {b["tier"] for b in branches} != {1, 2, 3}:
                raise ValueError(f"expected branches for tiers 1/2/3, got {branches}")
            engine = "crewai"
        except Exception as exc:
            log_action("Escalation Decision", "crew_fallback",
                       f"{step['step_name']}: CrewAI call failed ({exc}), using heuristic")

    if branches is None:
        branches = _heuristic_branches(step)

    branches = sorted(branches, key=lambda b: b["score"], reverse=True)
    best = branches[0]

    return {
        "branches": branches,
        "best": best,
        "confidence": best["score"],
        "grounding": grounding,
        "engine": engine,
    }
