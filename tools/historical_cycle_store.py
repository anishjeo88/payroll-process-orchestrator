"""Historical Cycle Store tool: queries structured long-term memory (SQLite)
- past cycle records, delay patterns, and exception logs - to inform
proactive decisions. This is the structured counterpart to the Knowledge
Retrieval Agent's semantic (Chroma) search; the two are separate interfaces
over separate stores (see memory/long_term_sqlite.py vs. long_term_vector.py).

Callers: the Escalation Decision Agent's Critic (Prior Escalation History
criterion, 20% weight in the ToT rubric) and the Orchestrator (cycle-over-
cycle reporting).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"


def get_delay_pattern(step_name: str) -> dict[str, Any] | None:
    """The known historical delay pattern for a step, if any - this demo
    seeds a couple of illustrative rows (environment/seed_data.py)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM delay_patterns WHERE step_name = ?", (step_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_cycle_history() -> list[dict[str, Any]]:
    """Closed-out past cycles, oldest first - this demo seeds two
    (environment/seed_data.py's CYCLE_HISTORY) so the History page has a
    cycle-over-cycle comparison. Never includes the live cycle."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM cycle_history ORDER BY cycle_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
