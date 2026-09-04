"""Scenario tests for the Checkpoint 6 safety guardrails - static
constraints and human-intervention conditions. Pure-function tests, no DB
required except is_duplicate_alert (which takes a connection directly).
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from guardrails.static_constraints import (
    requires_human_approval, is_duplicate_alert, filter_superseded,
)
from guardrails.human_intervention import (
    compliance_bypass, escalation_needs_review, escalation_rate_spike,
)


def test_tier_1_is_autonomous():
    assert requires_human_approval(1) is False


def test_tier_2_and_3_require_approval():
    assert requires_human_approval(2) is True
    assert requires_human_approval(3) is True


def test_filter_superseded_drops_superseded_sources():
    chunks = [
        {"text": "old", "status": "superseded"},
        {"text": "new", "status": "current"},
    ]
    result = filter_superseded(chunks)
    assert result == [{"text": "new", "status": "current"}]


def test_is_duplicate_alert_within_window():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE mcp_alert_log (
        id INTEGER PRIMARY KEY, step_id INTEGER, alert_type TEXT,
        recipient_user_id INTEGER, sent_at TEXT)""")
    now = datetime(2026, 9, 10, 15, 0, 0)
    conn.execute(
        "INSERT INTO mcp_alert_log (step_id, alert_type, recipient_user_id, sent_at) VALUES (1, 'tier1_reminder', 2, ?)",
        ((now - timedelta(hours=1)).isoformat(),),
    )
    conn.commit()

    assert is_duplicate_alert(conn, 1, "tier1_reminder", 2, now=now) is True
    # Different recipient, different type, or outside the window: not a duplicate
    assert is_duplicate_alert(conn, 1, "tier1_reminder", 99, now=now) is False
    assert is_duplicate_alert(conn, 1, "unblocked_notice", 2, now=now) is False
    assert is_duplicate_alert(conn, 1, "tier1_reminder", 2, now=now + timedelta(hours=5)) is False


def test_compliance_bypass_requires_prior_alert():
    step = {"is_compliance_step": True, "prior_alerts_sent": 0}
    assert compliance_bypass(step) is False
    step["prior_alerts_sent"] = 1
    assert compliance_bypass(step) is True


def test_compliance_bypass_false_for_non_compliance_step():
    step = {"is_compliance_step": False, "prior_alerts_sent": 5}
    assert compliance_bypass(step) is False


def test_escalation_needs_review_for_tier_2_regardless_of_confidence():
    needs_review, reason = escalation_needs_review(tier=2, confidence=0.99)
    assert needs_review is True
    assert "Tier 2" in reason


def test_escalation_needs_review_for_low_confidence_tier_1():
    needs_review, reason = escalation_needs_review(tier=1, confidence=0.4)
    assert needs_review is True
    assert "confidence" in reason.lower()


def test_tier_1_high_confidence_does_not_need_review():
    needs_review, reason = escalation_needs_review(tier=1, confidence=0.95)
    assert needs_review is False


def test_escalation_rate_spike_detection():
    now = datetime(2026, 9, 10, 15, 0, 0)
    recent = [now - timedelta(minutes=m) for m in (10, 20, 30, 40)]  # 4 within 2h
    assert escalation_rate_spike(recent, now) is True

    sparse = [now - timedelta(hours=h) for h in (1, 5, 10)]  # only 1 within 2h
    assert escalation_rate_spike(sparse, now) is False
