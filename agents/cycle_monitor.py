"""Cycle Monitor Agent - Checkpoint 5.

In the full design this is an always-on LangGraph node. This demo's version
keeps the same contract (poll -> classify -> route, no action decisions) as
a plain function, since detection/classification here is deterministic and
doesn't need an LLM - LangGraph's role is orchestrating *when* this runs
continuously, not the classification logic itself.

Tool access (guardrails/static_constraints.py): Task Status API,
Calendar & Runbook Reader only.
"""

from __future__ import annotations

from environment.simulator import risk_level, hours_overdue
from tools.task_status_api import get_all_steps


def poll_events() -> list[dict]:
    """Returns one event per non-completed step: {step, risk, hours_overdue}.
    Routing (to Escalation Decision vs. straight to Notification) is the
    Orchestrator's job, not this agent's."""
    steps = get_all_steps()
    steps_by_id = {s["id"]: s for s in steps}

    events = []
    for step in steps:
        risk = risk_level(step, steps_by_id)
        if risk == "completed":
            continue
        events.append({
            "step": step,
            "risk": risk,
            "hours_overdue": hours_overdue(step["deadline"]) if risk == "overdue" else 0.0,
        })
    return events
