"""Notification Dispatcher tool: sends personalized in-app alerts and email
notifications to specific stakeholders.

Owner: Notification & Action Agent (agents/notification_action.py) - the
only agent permitted to call it. Every dispatch is checked first against
the notification-deduplication guardrail (guardrails/static_constraints.py):
a same-type alert to the same recipient within the last 4 hours blocks the
call and notifies the Orchestrator instead.

This demo "sends" by writing to mcp_alert_log rather than a real email/
in-app system.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from environment.simulator import DEMO_NOW
from guardrails.static_constraints import is_duplicate_alert

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"


def dispatch(step_id: int, alert_type: str, recipient_user_id: int) -> dict:
    """Attempts to send an alert. Returns {"sent": bool, "reason": str}."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if is_duplicate_alert(conn, step_id, alert_type, recipient_user_id):
        conn.close()
        return {"sent": False, "reason": "blocked by notification-dedup guardrail (< 4h)"}

    conn.execute(
        """INSERT INTO mcp_alert_log (step_id, alert_type, recipient_user_id, sent_at)
           VALUES (?, ?, ?, ?)""",
        (step_id, alert_type, recipient_user_id, DEMO_NOW.isoformat()),
    )
    conn.execute(
        "UPDATE runbook_steps SET prior_alerts_sent = prior_alerts_sent + 1 WHERE id = ?",
        (step_id,),
    )
    conn.commit()
    conn.close()
    return {"sent": True, "reason": "dispatched"}
