"""Human intervention criteria - Checkpoint 6. Five conditions where the
Orchestrator routes to a human reviewer (the Payroll Manager, and the
Compliance Lead where noted) instead of proceeding autonomously:

1. Tier 2 or Tier 3 escalation
2. ToT confidence below threshold (or the 8s timeout)
3. Compliance sign-off step at risk - bypasses ToT entirely
4. Unverified cycle-state assertion (the groundedness check failed)
5. Anomalous escalation-rate spike (>3 escalations in a 2h window)

Deliberately selective: routed only where human judgment adds genuine value,
preserving autonomy for the ~80-85% of cycle decisions that are routine.
"""

from __future__ import annotations

from datetime import timedelta

from guardrails.static_constraints import requires_human_approval
from guardrails.runtime_enforcement import confidence_gate

SPIKE_WINDOW_HOURS = 2
SPIKE_THRESHOLD = 3


def compliance_bypass(step: dict) -> bool:
    """Condition 3: a compliance sign-off step overdue with at least one
    unanswered Tier 1 alert routes straight to a human - never through the
    Escalation Decision Agent's ToT search."""
    return bool(step.get("is_compliance_step")) and step.get("prior_alerts_sent", 0) >= 1


def escalation_needs_review(tier: int, confidence: float) -> tuple[bool, str]:
    """Conditions 1 & 2, for a Tier-N strategy the Escalation Decision Agent
    proposed. Returns (needs_review, reason)."""
    if requires_human_approval(tier):
        return True, f"Tier {tier} escalation requires Orchestrator confirmation"
    if not confidence_gate(confidence):
        return True, f"ToT confidence {confidence:.2f} below the 0.6 gate - inconclusive"
    return False, ""


def escalation_rate_spike(recent_escalation_times: list, now) -> bool:
    """Condition 5: more than SPIKE_THRESHOLD escalations created within the
    last SPIKE_WINDOW_HOURS - signals a systemic cycle issue, not an
    individual step failure."""
    window_start = now - timedelta(hours=SPIKE_WINDOW_HOURS)
    recent = [t for t in recent_escalation_times if t >= window_start]
    return len(recent) > SPIKE_THRESHOLD
