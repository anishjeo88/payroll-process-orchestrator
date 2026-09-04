"""Role-filtered cycle timeline, task status table, and open exceptions view."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from environment.simulator import risk_level, DEMO_NOW
from guardrails.runtime_enforcement import get_action_log
from interface.theme import render_banner
from interface.utils import RISK_BADGE, current_role, ensure_cycle_ran, rerun_cycle_pass, role_selector
from tools.escalation_workflow import get_latest_escalation
from tools.task_status_api import get_all_steps, mark_completed

ESCALATION_BADGE = {
    "pending_approval": "⏳ Pending your review",
    "approved": "✅ Approved & dispatched",
    "rejected": "❌ Rejected",
    "auto_dispatched": "🤖 Auto-dispatched (Tier 1)",
}

st.set_page_config(page_title="Dashboard · Payroll Process Orchestrator", page_icon="📊", layout="wide")
role_selector()
ensure_cycle_ran()

render_banner("📊 Dashboard", [f'Current Time: {DEMO_NOW.isoformat(sep=" ")}'])

role = current_role()
steps = get_all_steps()
steps_by_id = {s["id"]: s for s in steps}

col_a, col_b = st.columns([1, 2])
if col_a.button("🔁 Re-run cycle pass"):
    rerun_cycle_pass()
    st.rerun()

with col_b:
    incomplete = [s for s in steps if s["status"] != "completed"]
    with st.expander("✅ Mark a step complete"):
        chosen = st.selectbox(
            "Step", options=[s["step_name"] for s in incomplete],
            key="complete_step_choice",
        ) if incomplete else None
        if chosen and st.button("Mark complete & re-run cycle pass"):
            step_id = next(s["id"] for s in incomplete if s["step_name"] == chosen)
            mark_completed(step_id)
            rerun_cycle_pass()
            st.rerun()
        if not incomplete:
            st.caption("Every step in this cycle is already completed.")

rows = []
for s in steps:
    r = risk_level(s, steps_by_id)
    escalation = get_latest_escalation(s["id"])
    rows.append({
        "Step": s["step_name"],
        "Owner": s["owner_name"],
        "Role": s["owner_role"],
        "Deadline": s["deadline"][:16].replace("T", " "),
        "Risk": RISK_BADGE[r],
        "Escalation": (
            f"Tier {escalation['tier']} — {ESCALATION_BADGE.get(escalation['status'], escalation['status'])}"
            if escalation else "—"
        ),
        "Prior alerts": s["prior_alerts_sent"],
        "Compliance step": "✅" if s["is_compliance_step"] else "",
    })
df = pd.DataFrame(rows)

if role != "Leadership":
    st.subheader(f"My Tasks: {role}")
    mine = df[df["Role"] == role]
    if not mine.empty:
        st.dataframe(mine, use_container_width=True, hide_index=True)
    else:
        st.caption("Nothing owned by this role in the current cycle.")
    st.divider()

st.subheader("Payroll Run Book Steps" if role == "Leadership" else "Payroll Run Book Steps")
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Recent Activities")
log = get_action_log(limit=15)
if log:
    st.dataframe(pd.DataFrame(log)[["created_at", "agent", "action", "detail"]],
                 use_container_width=True, hide_index=True)
else:
    st.caption("No agent actions logged yet.")
