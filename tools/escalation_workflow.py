"""Escalation Workflow tool: creates a formal escalation record for the
strategy the Escalation Decision Agent's Tree-of-Thought search selected,
routing it to the appropriate tier with a pre-drafted summary.

Owner: Notification & Action Agent (agents/notification_action.py) - only
called after the Orchestrator's human-in-the-loop gate clears a Tier 2/3
strategy (guardrails/static_constraints.py: Tier 1 may dispatch
autonomously; Tier 2/3 cannot).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from environment.simulator import DEMO_NOW

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"


def create_escalation(
    step_id: int, tier: int, strategy_text: str, confidence: float,
    reason: str, status: str = "pending_approval",
) -> int:
    """Inserts an mcp_escalations row and returns its id. `status` is
    'pending_approval' for Tier 2/3 or low-confidence ToT outcomes, or
    'auto_dispatched' for a Tier 1 strategy that clears the guardrails
    without needing human review.

    The Orchestrator already checks get_active_escalation() before calling
    this, but that check-then-insert isn't atomic on its own - two cycle
    passes running at nearly the same instant (e.g. two browser sessions
    both hitting a freshly-seeded DB) can each see "nothing active yet" and
    both reach this call. The schema's partial unique index
    (uq_active_escalation_per_step) is what actually closes that race: it
    lets at most one non-rejected row exist per step_id, so the loser here
    gets a real IntegrityError instead of a silent duplicate - caught below
    by just returning whichever row actually won."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """INSERT INTO mcp_escalations
               (step_id, tier, strategy_text, confidence, status, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (step_id, tier, strategy_text, confidence, status, reason, DEMO_NOW.isoformat()),
        )
        conn.commit()
        escalation_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        existing = conn.execute(
            """SELECT id FROM mcp_escalations
               WHERE step_id = ? AND status != 'rejected'
               ORDER BY id DESC LIMIT 1""",
            (step_id,),
        ).fetchone()
        escalation_id = existing[0] if existing else None
    finally:
        conn.close()
    return escalation_id


def decide_escalation(escalation_id: int, approve: bool) -> None:
    """Records the Payroll Manager's confirm/reject decision from the
    Approvals page (interface/pages/approvals.py)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE mcp_escalations SET status = ?, decided_at = ? WHERE id = ?",
        ("approved" if approve else "rejected", DEMO_NOW.isoformat(), escalation_id),
    )
    conn.commit()
    conn.close()


def get_active_escalation(step_id: int) -> dict | None:
    """The most recent non-rejected escalation for this step (pending
    approval, approved, or auto-dispatched), if any. The Orchestrator checks
    this before creating a new one, so re-running the cycle pass doesn't
    pile up duplicate escalations for a step that's already been raised -
    a rejected escalation doesn't count, so the Orchestrator can propose a
    fresh strategy next pass if the Payroll Manager turned one down."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT * FROM mcp_escalations
           WHERE step_id = ? AND status != 'rejected'
           ORDER BY id DESC LIMIT 1""",
        (step_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_escalation(step_id: int) -> dict | None:
    """The most recent escalation for this step regardless of status - for
    display (e.g. the Dashboard showing a rejected item), where
    get_active_escalation's rejected-exclusion isn't what's wanted."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM mcp_escalations WHERE step_id = ? ORDER BY id DESC LIMIT 1",
        (step_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_escalations() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT e.*, rs.step_name, u.name AS owner_name
           FROM mcp_escalations e
           JOIN runbook_steps rs ON rs.id = e.step_id
           JOIN users u ON u.id = rs.owner_user_id
           WHERE e.status = 'pending_approval'
           ORDER BY e.created_at"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
