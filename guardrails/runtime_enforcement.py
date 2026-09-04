"""Dynamic runtime enforcement - Checkpoint 6. Context-sensitive checks that
run within each reasoning loop, not fixed rules.

- Groundedness check: `assert_grounded` - every cycle-state claim must trace
  to a tool-call result, not an unverified model assertion.
- ToT confidence gate: `confidence_gate` - if every branch scores below 0.6,
  the search is inconclusive and goes to human review instead of picking
  the best of a bad set.
- Hard latency timeout: `TOT_TIMEOUT_SECONDS` - the full implementation
  (Phase 4+) wraps the Escalation Decision Agent's search in this budget;
  this demo's simplified scorer is instant, so the timeout is defined but
  not yet exercised.
- Runtime monitoring: `log_action` - every agent action is timestamped into
  mcp_action_log for the Orchestrator dashboard's anomaly detection.

Addresses: hallucinated cycle state and autonomous action on high-impact
decisions (Checkpoint 6 risk register).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

TOT_CONFIDENCE_THRESHOLD = 0.6
TOT_TIMEOUT_SECONDS = 8

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"


class UngroundedAssertionError(Exception):
    """Raised when a response would reference cycle state without a
    verified tool-call result backing it."""


def assert_grounded(claim: str, backing_tool_call: dict | None) -> None:
    """Groundedness check. Every UI-facing statement about cycle state must
    pass a `backing_tool_call` result (e.g. the dict returned by
    tools.task_status_api.get_step) - if it's None, the claim is blocked."""
    if backing_tool_call is None:
        raise UngroundedAssertionError(
            f"Blocked ungrounded claim: {claim!r} has no backing tool-call result."
        )


def confidence_gate(best_score: float) -> bool:
    """True if the ToT search's best branch clears the confidence gate and
    may proceed; False means it's inconclusive and must route to human
    review (guardrails/human_intervention.py) instead of auto-selecting."""
    return best_score >= TOT_CONFIDENCE_THRESHOLD


def log_action(agent: str, action: str, detail: str = "") -> None:
    """Runtime monitoring: append to mcp_action_log."""
    from environment.simulator import DEMO_NOW

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO mcp_action_log (agent, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (agent, action, detail, DEMO_NOW.isoformat()),
    )
    conn.commit()
    conn.close()


def get_action_log(limit: int = 25) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM mcp_action_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
