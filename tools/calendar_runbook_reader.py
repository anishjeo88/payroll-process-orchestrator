"""Calendar & Run book Reader tool: reads the structured payroll schedule and
run book to determine expected step sequencing and deadlines.

Owner: Cycle Monitor Agent (agents/cycle_monitor.py), alongside the Task
Status API. Grounds event classification in the authoritative schedule
rather than parametric knowledge.
"""

from __future__ import annotations

from tools.task_status_api import get_all_steps


def get_sequence() -> list[str]:
    """The run book's step names in expected order, for context on where a
    given step sits in the cycle (used to judge "is this on the critical
    path" without hardcoding it in the agent)."""
    return [s["step_name"] for s in get_all_steps()]
