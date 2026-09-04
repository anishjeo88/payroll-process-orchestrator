"""The Payroll Manager's human-intervention queue - reads pending escalations
(Tier 2/3, or a compliance-bypass item) and presents each with the proposed
action for confirm/reject - the human-in-the-loop gate in practice.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from agents.notification_action import dispatch_approved_escalation
from interface.theme import render_banner
from interface.utils import ensure_cycle_ran, role_selector
from tools.escalation_workflow import decide_escalation, get_pending_escalations

st.set_page_config(page_title="Approvals · Payroll Process Orchestrator", page_icon="✅", layout="wide")
role_selector()
ensure_cycle_ran()

render_banner("✅ Approval Queue", [
    "Items for your review and approval",
])

pending = get_pending_escalations()

if not pending:
    st.success("Nothing pending. All caught up.")
else:
    for e in pending:
        with st.container(border=True):
            tier_label = {2: "Tier 2 — Team Lead", 3: "Tier 3 — Senior Management / Compliance"}.get(
                e["tier"], f"Tier {e['tier']}"
            )
            st.markdown(f"### {e['step_name']}")
            st.caption(f"Owner: {e['owner_name']} · {tier_label}")
            st.write(e["strategy_text"])
            st.caption(f"Why this needs a human: {e['reason']}")

            c1, c2 = st.columns(2)
            if c1.button("✅ Approve & dispatch", key=f"approve_{e['id']}"):
                decide_escalation(e["id"], approve=True)
                dispatch_approved_escalation(e)
                st.rerun()
            if c2.button("❌ Reject", key=f"reject_{e['id']}"):
                decide_escalation(e["id"], approve=False)
                st.rerun()
