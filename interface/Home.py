"""Streamlit entry point: role selector + a landing summary. Navigation to
Dashboard / Agent Chat / Approvals / History is Streamlit's auto-discovered
multipage nav (interface/pages/*.py), shown in the sidebar.

Run from the project root:
    streamlit run interface/Home.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `import agents.*`, `import tools.*`, etc. when Streamlit runs this
# file directly (its cwd/sys.path default doesn't include the project root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from interface.theme import render_banner
from interface.utils import ensure_cycle_ran, current_role, role_selector
from tools.task_status_api import get_all_steps

st.set_page_config(page_title="Payroll Process Orchestrator", page_icon="🧾", layout="wide")

role_selector()

render_banner("Payroll Process Orchestrator", [
    "Orchestrator, Cycle Monitor, Knowledge Retrieval,",
    "Escalation Decision, Notification & Action with Safety Guardrails.",
])

ensure_cycle_ran()
steps = get_all_steps()

col1, col2, col3 = st.columns(3)
col1.metric("Total Run Book Steps", len(steps))
col2.metric("Your Role", current_role())
col3.metric("Current Cycle", steps[0]["cycle_id"] if steps else "—")

st.info(
    "The Payroll Process Orchestrator represents a complete, end-to-end "
    "agentic AI system design from initial problem scoping through "
    "multi-agent coordination, retrieval-augmented reasoning, Tree-of-"
    "Thought escalation logic, and production-grade safety guardrails."
)

st.caption(
    "An Autonomous Multi-Agent System for Real-Time Payroll Cycle Coordination."
)
