"""Notification & Action Agent - Checkpoint 5.

Executes what the Orchestrator or a confirmed Escalation Decision strategy
tells it to - it makes no contact-tier decisions itself. Tool access limited
to the Notification Dispatcher and Escalation Workflow tools
(guardrails/static_constraints.py).
"""

from __future__ import annotations

from guardrails.runtime_enforcement import log_action
from tools.escalation_workflow import create_escalation
from tools.notification_dispatcher import dispatch

# Demo stand-ins for "the team lead" / "senior management" recipient a real
# directory lookup would resolve per-step.
TIER_RECIPIENT = {2: 6, 3: 5}  # user ids: Jordan Blake (lead), Elena Vance (leadership)


def send_tier1_reminder(step: dict) -> dict:
    """Sends a Tier 1 reminder, or is silently no-op'd by the notification-
    dedup guardrail if one already went out recently. Only logs when a
    reminder actually goes out - the dedup guardrail's whole point is to
    prevent repeat noise, so re-polling a step that's still within its
    4-hour window shouldn't itself produce a fresh MCP log entry every pass."""
    result = dispatch(step["id"], "tier1_reminder", step["owner_user_id"])
    if result["sent"]:
        log_action("Notification & Action", "tier1_reminder", f"{step['step_name']}: {result}")
    return result


def notify_unblocked(step: dict) -> dict:
    """Proactive notification: the step's upstream dependency has just
    completed, so tell its owner rather than leaving them to notice on
    their own - "proactively notify dependent teams when an upstream task
    completes" from the original design. Deduped the same way as any other
    alert (guardrails/static_constraints.py), so this fires once per
    unblocking event, not on every subsequent poll."""
    result = dispatch(step["id"], "unblocked_notice", step["owner_user_id"])
    if result["sent"]:
        log_action("Notification & Action", "unblocked_notice",
                   f"{step['step_name']} - upstream dependency complete, owner notified")
    return result


def record_pending_escalation(step: dict, branch: dict, reason: str) -> int:
    """Tier 2/3 or low-confidence outcome: create the record for the
    Approvals queue rather than dispatching immediately."""
    escalation_id = create_escalation(
        step_id=step["id"],
        tier=branch["tier"],
        strategy_text=branch["strategy_text"],
        confidence=branch["score"],
        reason=reason,
        status="pending_approval",
    )
    log_action("Notification & Action", "escalation_queued",
               f"{step['step_name']} -> {reason}")
    return escalation_id


def dispatch_approved_escalation(escalation: dict) -> dict:
    """After the Orchestrator's human-in-the-loop gate confirms a Tier 2/3
    escalation (interface/pages/approvals.py), actually send it."""
    recipient = TIER_RECIPIENT.get(escalation["tier"])
    result = dispatch(escalation["step_id"], f"tier{escalation['tier']}_escalation", recipient)
    log_action("Notification & Action", "escalation_dispatched",
               f"escalation #{escalation['id']}: {result}")
    return result
