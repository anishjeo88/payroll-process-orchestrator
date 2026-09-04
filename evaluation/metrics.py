"""Evaluation metrics - Checkpoint 6. Each function below is a real,
runnable computation over the live SQLite DB (and, for retrieval relevance,
a live Chroma query) - not a placeholder. Run `python -m evaluation.metrics`
from the project root to print a full report; see generate_report()'s
docstring for how each number is derived and what it means when a metric
reports "no data yet" instead of a percentage.

Surfaced on the Orchestrator dashboard conceptually to detect drift and
calibration failures over time, not just to judge individual decisions:

- Escalation Accuracy (target >=90%) - % of decided escalations (approved or
  rejected) the Payroll Manager approved.
- Groundedness Rate (target 100%) - the guardrail is checked live: this run
  actually calls assert_grounded() with both a valid and a missing backing
  tool-call result and confirms the missing one is blocked.
- Retrieval Relevance Score (target >=0.80) - average top-1 similarity score
  from live Chroma queries against a fixed sample question set.
- Notification Duplicate Rate (target <1%) - % of *sent* alerts in
  mcp_alert_log that share (step, type, recipient) with another sent alert
  within 4 hours. Structurally low by design (guardrails/static_constraints
  blocks a duplicate before it's ever logged), so this measures what got
  through, not what was attempted.
- Fallback Rate (target <15%) - % of escalations that were NOT auto-
  dispatched (i.e. needed some form of human review: Tier 2/3, or a
  low-confidence Tier 1 that got escalated anyway).
- Human Override Rate (target <10%) - % of decided escalations the Payroll
  Manager rejected outright.
- Cycle Step On-Time Rate (target >=95%) - % of steps completed on schedule
  across the closed historical cycles on file (environment/seed_data.py's
  CYCLE_HISTORY) - the live cycle is still in progress, so it isn't counted
  here (a step "on track" isn't yet a verdict).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"

TARGETS = {
    "escalation_accuracy": (">=", 90.0),
    "groundedness_rate": (">=", 100.0),
    "retrieval_relevance_score": (">=", 0.80),
    "notification_duplicate_rate": ("<", 1.0),
    "fallback_rate": ("<", 15.0),
    "human_override_rate": ("<", 10.0),
    "cycle_step_on_time_rate": (">=", 95.0),
}


def _meets(name: str, value: float | None) -> bool | None:
    if value is None:
        return None
    op, target = TARGETS[name]
    return value >= target if op == ">=" else value < target


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def escalation_accuracy() -> dict[str, Any]:
    conn = _connect()
    rows = conn.execute(
        "SELECT status FROM mcp_escalations WHERE status IN ('approved', 'rejected')"
    ).fetchall()
    conn.close()
    decided = len(rows)
    if decided == 0:
        return {"value": None, "n_decided": 0, "note": "no escalations decided yet"}
    approved = sum(1 for r in rows if r["status"] == "approved")
    value = round(100 * approved / decided, 1)
    return {"value": value, "n_decided": decided, "n_approved": approved}


def human_override_rate() -> dict[str, Any]:
    conn = _connect()
    rows = conn.execute(
        "SELECT status FROM mcp_escalations WHERE status IN ('approved', 'rejected')"
    ).fetchall()
    conn.close()
    decided = len(rows)
    if decided == 0:
        return {"value": None, "n_decided": 0, "note": "no escalations decided yet"}
    rejected = sum(1 for r in rows if r["status"] == "rejected")
    value = round(100 * rejected / decided, 1)
    return {"value": value, "n_decided": decided, "n_rejected": rejected}


def fallback_rate() -> dict[str, Any]:
    conn = _connect()
    rows = conn.execute("SELECT status FROM mcp_escalations").fetchall()
    conn.close()
    total = len(rows)
    if total == 0:
        return {"value": None, "n_total": 0, "note": "no escalations raised yet"}
    not_auto = sum(1 for r in rows if r["status"] != "auto_dispatched")
    value = round(100 * not_auto / total, 1)
    return {"value": value, "n_total": total, "n_needed_review": not_auto}


def groundedness_rate() -> dict[str, Any]:
    """A live self-test, not a static claim: confirms assert_grounded()
    actually passes a real backing result and actually blocks a missing
    one. If either check fails, the guardrail itself is broken."""
    from guardrails.runtime_enforcement import assert_grounded, UngroundedAssertionError

    passed_with_backing = False
    try:
        assert_grounded("evaluation self-test", {"source": "self-test"})
        passed_with_backing = True
    except UngroundedAssertionError:
        pass

    blocked_without_backing = False
    try:
        assert_grounded("evaluation self-test (no backing)", None)
    except UngroundedAssertionError:
        blocked_without_backing = True

    ok = passed_with_backing and blocked_without_backing
    return {
        "value": 100.0 if ok else 0.0,
        "passed_with_backing": passed_with_backing,
        "blocked_without_backing": blocked_without_backing,
    }


def retrieval_relevance_score() -> dict[str, Any]:
    """Live top-1 similarity, averaged over a fixed sample question set
    drawn from the actual seeded corpus (Escalation Matrix, Compliance
    Handbook, Cycle History) - see agents/knowledge_retrieval.py."""
    from agents.knowledge_retrieval import retrieve

    sample_queries = [
        "escalation tier for a compliance sign-off",
        "what happens when Benefits Data Feed Validation is delayed",
        "SOX control review compliance requirements",
        "typical delay pattern for benefits validation",
    ]
    top1_scores = []
    for q in sample_queries:
        hits = retrieve(q, top_k=1)
        if hits:
            top1_scores.append(hits[0]["score"])

    if not top1_scores:
        return {"value": None, "n_queries": len(sample_queries), "note": "no retrieval results"}
    value = round(sum(top1_scores) / len(top1_scores), 2)
    return {"value": value, "n_queries": len(sample_queries), "scores": [round(s, 2) for s in top1_scores]}


def notification_duplicate_rate() -> dict[str, Any]:
    conn = _connect()
    rows = conn.execute(
        "SELECT step_id, alert_type, recipient_user_id, sent_at FROM mcp_alert_log ORDER BY sent_at"
    ).fetchall()
    conn.close()
    total = len(rows)
    if total == 0:
        return {"value": None, "n_sent": 0, "note": "no notifications sent yet"}

    duplicates = 0
    by_key: dict[tuple, list[datetime]] = {}
    for r in rows:
        key = (r["step_id"], r["alert_type"], r["recipient_user_id"])
        ts = datetime.fromisoformat(r["sent_at"])
        prior = by_key.setdefault(key, [])
        if any(abs((ts - p).total_seconds()) < 4 * 3600 for p in prior):
            duplicates += 1
        prior.append(ts)

    value = round(100 * duplicates / total, 1)
    return {"value": value, "n_sent": total, "n_duplicates": duplicates}


def cycle_step_on_time_rate() -> dict[str, Any]:
    """Only closed historical cycles count (environment/seed_data.py's
    CYCLE_HISTORY) - the live cycle is still in progress."""
    from tools.historical_cycle_store import get_cycle_history

    history = get_cycle_history()
    if not history:
        return {"value": None, "n_cycles": 0, "note": "no closed cycles on file"}
    total_steps = sum(c["steps_total"] for c in history)
    on_time = sum(c["steps_on_time"] for c in history)
    value = round(100 * on_time / total_steps, 1) if total_steps else None
    return {"value": value, "n_cycles": len(history), "n_steps_total": total_steps, "n_on_time": on_time}


def generate_report() -> dict[str, Any]:
    """Computes all 7 metrics live and returns a single dict, each entry
    carrying its value, supporting counts, its target, and whether it
    currently meets that target (None for both when there's not yet enough
    data - e.g. a fresh demo cycle with nothing decided in Approvals)."""
    metrics = {
        "escalation_accuracy": escalation_accuracy(),
        "groundedness_rate": groundedness_rate(),
        "retrieval_relevance_score": retrieval_relevance_score(),
        "notification_duplicate_rate": notification_duplicate_rate(),
        "fallback_rate": fallback_rate(),
        "human_override_rate": human_override_rate(),
        "cycle_step_on_time_rate": cycle_step_on_time_rate(),
    }
    for name, result in metrics.items():
        op, target = TARGETS[name]
        result["target"] = f"{op}{target}"
        result["meets_target"] = _meets(name, result["value"])
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "metrics": metrics}


def _format_report(report: dict[str, Any]) -> str:
    lines = [f"Evaluation report - generated {report['generated_at']}", "=" * 60]
    for name, r in report["metrics"].items():
        label = name.replace("_", " ").title()
        if r["value"] is None:
            lines.append(f"{label}: n/a - {r.get('note', 'insufficient data')} (target {r['target']})")
            continue
        verdict = "PASS" if r["meets_target"] else "FAIL"
        lines.append(f"{label}: {r['value']} (target {r['target']}) [{verdict}]")
        extras = {k: v for k, v in r.items() if k not in ("value", "target", "meets_target", "note")}
        if extras:
            lines.append(f"    {extras}")
    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    print(_format_report(report))
