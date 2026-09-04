"""Advances/derives simulated payroll-cycle time.

This demo uses a single fixed reference "now" rather than wall-clock time,
so the seeded scenario (which steps are overdue, at-risk, on track) is
reproducible on every run. A later phase can replace DEMO_NOW with a real
clock or a scenario-advancing simulator (Phase 7 scenario tests).
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Fixed "now" for the demo cycle - mid-cycle through the current semi-monthly
# payroll cycle (Sep 1-15, 2026), so the seeded scenario shows a realistic mix
# of completed, overdue, at-risk, and upcoming steps. Change this (or make it
# wall-clock) once real scenario-advancing is implemented.
DEMO_NOW = datetime(2026, 9, 10, 15, 0, 0)


def offset(days: float = 0, hours: float = 0) -> str:
    """ISO datetime string at DEMO_NOW + the given offset. Used by
    environment/seed_data.py to place deadlines relative to "now"."""
    dt = DEMO_NOW + timedelta(days=days, hours=hours)
    return dt.isoformat()


def risk_level(step: dict, steps_by_id: dict | None = None) -> str:
    """Derives blocked / on_track / at_risk / overdue / completed for a
    runbook step - this is what Cycle Monitor calls instead of trusting a
    stored label, so its output is grounded in a live comparison
    (guardrails/runtime_enforcement.py's groundedness check).

    A step whose `depends_on_step_id` prerequisite isn't completed yet is
    reported as 'blocked' regardless of its own deadline - a downstream step
    can never show as completed, on-track, or independently overdue while
    the step it depends on is still open (pass `steps_by_id`, an id-> step
    dict from tools.task_status_api.get_all_steps, to enable this check)."""
    if step["status"] == "completed":
        return "completed"

    dep_id = step.get("depends_on_step_id")
    if dep_id and steps_by_id is not None:
        dependency = steps_by_id.get(dep_id)
        if dependency is not None and dependency["status"] != "completed":
            return "blocked"

    deadline = datetime.fromisoformat(step["deadline"])
    delta = deadline - DEMO_NOW
    if delta.total_seconds() < 0:
        return "overdue"
    if delta.total_seconds() < 6 * 3600:  # within 6 hours
        return "at_risk"
    return "on_track"


def hours_overdue(deadline_iso: str) -> float:
    """Positive number of hours past deadline (0 if not yet due)."""
    deadline = datetime.fromisoformat(deadline_iso)
    delta = DEMO_NOW - deadline
    return max(delta.total_seconds() / 3600, 0.0)
