"""Shared Streamlit helpers: session-state access and small formatting utils
used across pages."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"

ROLES = [
    "Payroll Administrator", "Payroll Engineer",
    "Benefits and Compensation Analyst", "Finance Reviewer", "Leadership",
]

RISK_BADGE = {
    "completed": "🟢 Completed",
    "on_track": "🔵 On track",
    "at_risk": "🟠 At risk",
    "overdue": "🔴 Overdue",
    "blocked": "🟣 Blocked (upstream)",
}


def _get_persisted_role() -> str | None:
    """Reads the last-chosen role from the same SQLite DB every other agent
    tool uses - not session_state, and not st.query_params either. Both were
    tried and both turned out unreliable across a sidebar page navigation
    here: st.session_state doesn't survive it in this deployment (confirmed
    directly - picking a role on Dashboard and clicking straight to History
    resets it, not just a Home-specific gap), and st.query_params is cleared
    on page navigation by Streamlit's own design, not a bug. A plain SQLite
    row is the one thing every page can actually read consistently."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'current_role'").fetchone()
    conn.close()
    return row[0] if row else None


def _set_persisted_role(role: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES ('current_role', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (role,),
    )
    conn.commit()
    conn.close()


def current_role() -> str:
    """Always reads the durable DB value directly - deliberately not
    session_state (see role_selector's docstring for why)."""
    role = _get_persisted_role()
    return role if role in ROLES else ROLES[0]


def role_selector() -> None:
    """The "Viewing as" role switcher. Call this on every page, not just one.

    Explicitly computes the widget's initial `index` from the DB-persisted
    value on every render, rather than trusting a `key not in
    st.session_state` check to know whether this is this widget's first
    appearance: Streamlit's frontend re-seeds a *newly-mounted* widget
    (i.e. the first time this page's own selectbox instance renders) to its
    own default - ROLES[0] here - as part of the very rerun request that
    triggers this script, before any of this function's Python even runs.
    So by the time we'd check "is 'role' already in session_state", it
    already is - just wrongly, with the frontend's default instead of the
    real persisted choice. Comparing the widget's returned value against
    the persisted one (rather than reading session_state at all) is what
    actually detects a genuine user-driven change reliably."""
    persisted = current_role()
    choice = st.sidebar.selectbox("Viewing as", ROLES, index=ROLES.index(persisted), key="role")
    if choice != persisted:
        _set_persisted_role(choice)


def ensure_cycle_ran() -> None:
    """Runs the orchestrator's cycle pass exactly once for a freshly-seeded
    cycle - not once per browser session. A new Streamlit session (a page
    reload, a second tab, reconnecting after a server restart) would
    otherwise re-trigger a full pass every time session_state resets, and
    since Cycle Monitor legitimately re-observes "still blocked" or
    "still deduped" on every pass, that repeatedly buries genuine new
    entries (like an escalation you just approved) under re-run noise in
    the MCP action log. Checking the log itself - not session_state - for
    whether *any* pass has ever run against this database is what actually
    makes this idempotent across sessions; session_state still short-circuits
    repeat page loads within one browser session so this stays cheap."""
    if st.session_state.get("_cycle_ran"):
        return

    from guardrails.runtime_enforcement import get_action_log
    if not get_action_log(limit=1):
        from agents.orchestrator import run_cycle_pass
        st.session_state["_last_pass"] = run_cycle_pass()

    st.session_state["_cycle_ran"] = True


def rerun_cycle_pass() -> None:
    from agents.orchestrator import run_cycle_pass
    st.session_state["_last_pass"] = run_cycle_pass()
