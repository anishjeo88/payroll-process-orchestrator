"""Task Status API tool: retrieves live task completion data, deadlines, and
owner assignments from the simulated payroll environment.

Owner: Cycle Monitor Agent (agents/cycle_monitor.py) - polls this on a
schedule to detect run book step changes. No other agent calls it directly
(guardrails/static_constraints.py scopes tool access per agent role).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_steps() -> list[dict[str, Any]]:
    """Every run book step in the current cycle, joined with owner name/role."""
    conn = _connect()
    rows = conn.execute(
        """SELECT rs.*, u.name AS owner_name, u.role AS owner_role
           FROM runbook_steps rs JOIN users u ON u.id = rs.owner_user_id
           ORDER BY rs.sequence"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_step(step_id: int) -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute(
        """SELECT rs.*, u.name AS owner_name, u.role AS owner_role
           FROM runbook_steps rs JOIN users u ON u.id = rs.owner_user_id
           WHERE rs.id = ?""",
        (step_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_completed(step_id: int) -> None:
    """Marks a step done - this is the step owner's own action (e.g. Priya
    finishing Benefits Data Feed Validation), not an agent decision, so it
    lives here as a plain write against the environment rather than in any
    agent module. Cycle Monitor picks the change up on its next poll like
    any other live state change - it doesn't need to be told separately."""
    conn = _connect()
    conn.execute("UPDATE runbook_steps SET status = 'completed' WHERE id = ?", (step_id,))
    conn.commit()
    conn.close()
