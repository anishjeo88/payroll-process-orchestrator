"""Scenario tests for the escalation-dedup guarantee (tools/escalation_
workflow.py + the uq_active_escalation_per_step partial unique index in
environment/db_schema.sql). Regression tests for a real bug found in the
live demo: two near-simultaneous cycle passes each saw "no active
escalation yet" before either had committed, producing 3 duplicate pending
escalations for one step. Runs against a temp, isolated SQLite DB - never
the real data/payroll.db.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "environment" / "db_schema.sql"


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """A fresh, schema-initialized SQLite DB isolated to this test, with
    tools.escalation_workflow (and get_active_escalation/get_pending_
    escalations) pointed at it instead of the real demo database."""
    db_path = tmp_path / "test_payroll.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute("INSERT INTO users (id, name, role) VALUES (1, 'Test Owner', 'Payroll Administrator')")
    conn.execute(
        """INSERT INTO runbook_steps
           (id, cycle_id, step_name, sequence, owner_user_id, deadline, status)
           VALUES (1, 'TEST-CYCLE', 'Test Step', 1, 1, '2026-01-01T00:00:00', 'pending')"""
    )
    conn.commit()
    conn.close()

    import tools.escalation_workflow as ew
    monkeypatch.setattr(ew, "DB_PATH", db_path)
    return db_path


def test_second_concurrent_escalation_returns_the_first_row(temp_db):
    """Simulates the exact race: two calls for the same step, back to
    back, as if two cycle passes both decided to escalate it."""
    from tools.escalation_workflow import create_escalation, get_pending_escalations

    first_id = create_escalation(1, 2, "First strategy", 0.9, "test")
    second_id = create_escalation(1, 2, "A different strategy text", 0.7, "test")

    assert second_id == first_id, "a duplicate attempt must resolve to the existing row, not a new one"
    pending = [e for e in get_pending_escalations() if e["step_id"] == 1]
    assert len(pending) == 1


def test_rejected_escalation_allows_a_fresh_one(temp_db):
    """A rejected escalation must NOT count as "active" - the Orchestrator
    is allowed to propose a fresh strategy after a human turns one down."""
    from tools.escalation_workflow import create_escalation, decide_escalation, get_active_escalation

    first_id = create_escalation(1, 2, "First strategy", 0.9, "test")
    decide_escalation(first_id, approve=False)

    assert get_active_escalation(1) is None, "a rejected escalation must not block a new one"

    second_id = create_escalation(1, 2, "Second strategy after rejection", 0.85, "test")
    assert second_id != first_id
    assert get_active_escalation(1)["id"] == second_id


def test_approved_escalation_still_blocks_a_new_one(temp_db):
    from tools.escalation_workflow import create_escalation, decide_escalation, get_active_escalation

    first_id = create_escalation(1, 2, "First strategy", 0.9, "test")
    decide_escalation(first_id, approve=True)

    second_id = create_escalation(1, 2, "Attempted second strategy", 0.8, "test")
    assert second_id == first_id
    assert get_active_escalation(1)["status"] == "approved"
