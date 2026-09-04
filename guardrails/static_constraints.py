"""Static safety constraints - Checkpoint 6. Always-on; scope tool access and
escalation authority regardless of context.

- Tool access limits: enforced structurally (each agent module only imports
  the tools it owns - see the "Owner:" note in each tools/*.py docstring).
- Escalation tier ceiling: Tier 1 may dispatch autonomously; Tier 2/3 require
  Orchestrator confirmation. See `requires_human_approval`.
- Notification deduplication rule: see `is_duplicate_alert`.
- Source version filter: RAG retrieval excludes chunks with status =
  superseded at query time (agents/knowledge_retrieval.py).

Addresses: incorrect escalation routing, notification over-dispatch, and
stale/superseded policy retrieval (Checkpoint 6 risk register).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

DEDUP_WINDOW_HOURS = 4
AUTONOMOUS_TIER_CEILING = 1  # Tier 1 only; Tier 2/3 need human confirmation


def requires_human_approval(tier: int) -> bool:
    """Escalation tier ceiling: Tier 1 is autonomous, Tier 2/3 are not."""
    return tier > AUTONOMOUS_TIER_CEILING


def is_duplicate_alert(
    conn: sqlite3.Connection, step_id: int, alert_type: str, recipient_user_id: int,
    now: datetime | None = None,
) -> bool:
    """True if a same-type alert already went to this recipient for this
    step within the last `DEDUP_WINDOW_HOURS`."""
    from environment.simulator import DEMO_NOW

    now = now or DEMO_NOW
    window_start = (now - timedelta(hours=DEDUP_WINDOW_HOURS)).isoformat()
    row = conn.execute(
        """SELECT 1 FROM mcp_alert_log
           WHERE step_id = ? AND alert_type = ? AND recipient_user_id = ?
             AND sent_at >= ?
           LIMIT 1""",
        (step_id, alert_type, recipient_user_id, window_start),
    ).fetchone()
    return row is not None


def filter_superseded(chunks: list[dict]) -> list[dict]:
    """Source version filter: drops any retrieved chunk flagged superseded,
    regardless of its similarity score (agents/knowledge_retrieval.py)."""
    return [c for c in chunks if c.get("status") != "superseded"]
