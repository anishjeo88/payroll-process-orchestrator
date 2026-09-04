"""Scenario tests for environment/simulator.py's risk_level() - the function
Cycle Monitor calls instead of trusting a stored status label. These are
pure-function tests (no DB), built around the exact dependency-blocking bug
a user found in the live demo: a downstream step showing "completed" while
its upstream prerequisite was still overdue.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from environment.simulator import DEMO_NOW, risk_level, offset


def _step(**overrides) -> dict:
    base = {
        "id": 1, "status": "pending", "deadline": offset(days=1),
        "depends_on_step_id": None,
    }
    base.update(overrides)
    return base


def test_completed_step_is_completed_even_if_deadline_passed():
    step = _step(status="completed", deadline=offset(days=-5))
    assert risk_level(step) == "completed"


def test_future_deadline_is_on_track():
    step = _step(deadline=offset(days=2))
    assert risk_level(step) == "on_track"


def test_deadline_within_six_hours_is_at_risk():
    step = _step(deadline=offset(hours=3))
    assert risk_level(step) == "at_risk"


def test_past_deadline_is_overdue():
    step = _step(deadline=offset(hours=-1))
    assert risk_level(step) == "overdue"


def test_step_blocked_by_incomplete_dependency_even_with_future_deadline():
    """The exact bug a user reported: a downstream step must never show as
    on-track (or completed) while its upstream prerequisite is still open,
    regardless of its own deadline."""
    upstream = _step(id=1, status="in_progress", deadline=offset(hours=-10))
    downstream = _step(id=2, status="pending", deadline=offset(days=3), depends_on_step_id=1)
    steps_by_id = {1: upstream, 2: downstream}

    assert risk_level(downstream, steps_by_id) == "blocked"


def test_step_unblocked_once_dependency_completes():
    upstream = _step(id=1, status="completed", deadline=offset(hours=-10))
    downstream = _step(id=2, status="pending", deadline=offset(days=3), depends_on_step_id=1)
    steps_by_id = {1: upstream, 2: downstream}

    assert risk_level(downstream, steps_by_id) == "on_track"


def test_dependency_check_is_skipped_without_steps_by_id():
    """risk_level() falls back to scoring the step's own deadline if
    steps_by_id isn't passed - documented, not accidental behavior."""
    downstream = _step(id=2, deadline=offset(days=3), depends_on_step_id=1)
    assert risk_level(downstream) == "on_track"
