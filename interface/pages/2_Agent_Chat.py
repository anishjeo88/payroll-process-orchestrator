"""Conversational pane where the Orchestrator's routing decisions surface -
which agent handled a given event, and for escalation events, the
Tree-of-Thought trace behind the Escalation Decision Agent's proposal.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from agents.orchestrator import answer_question, cycle_summary, why_this_delay
from agents.knowledge_retrieval import retrieve, synthesize
from coordination.llm import has_api_key
from environment.simulator import risk_level
from interface.theme import render_banner
from interface.utils import ensure_cycle_ran, role_selector
from tools.task_status_api import get_all_steps

st.set_page_config(page_title="Agent Chat · Payroll Process Orchestrator", page_icon="💬", layout="wide")
role_selector()
ensure_cycle_ran()

api_line = (
    "Powered by Claude"
)
render_banner("💬 Agent Chat", [
    "Get answers and updates on the current payroll cycle.",
    api_line,
])

steps = get_all_steps()
steps_by_id = {s["id"]: s for s in steps}
last_pass = st.session_state.get("_last_pass", [])

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

def handle(question: str) -> tuple[str, str]:
    """Very small rule-based router standing in for an LLM-driven
    Orchestrator (see agents/orchestrator.py's docstring). Returns
    (agent_label, answer)."""
    q = question.lower()

    if "compliance" in q:
        step = next((s for s in steps if s["is_compliance_step"]), None)
        if not step:
            return "Orchestrator", "No compliance sign-off step in this cycle."
        risk = risk_level(step, steps_by_id)
        return "Cycle Monitor → Orchestrator", (
            f"'{step['step_name']}' (owner: {step['owner_name']}) is **{risk}**. "
            f"Compliance steps bypass Tree-of-Thought entirely per policy — "
            f"an overdue one with an unanswered alert routes straight to the "
            f"Payroll Manager and Compliance Lead. Check **Approvals**."
        )

    if "overdue" in q or "at risk" in q or "at-risk" in q or "status" in q or "summary" in q:
        return "Cycle Monitor → Orchestrator", cycle_summary(steps)

    if "why" in q and "delay" in q or "why" in q and ("late" in q or "slip" in q):
        overdue = [s for s in steps if risk_level(s, steps_by_id) == "overdue"]
        if not overdue:
            return "Knowledge Retrieval", "Nothing is currently overdue."
        return "Escalation Decision → Knowledge Retrieval", why_this_delay(overdue[0])

    if "escalat" in q:
        rows = [r for r in last_pass if "tot" in r or "branch" in r]
        if not rows:
            return "Escalation Decision", "No escalation decisions in the last cycle pass."
        lines = []
        for r in rows:
            lines.append(f"**{r['step']['step_name']}** — path: _{r['path']}_")
            branches = r.get("tot", {}).get("branches") or ([r["branch"]] if "branch" in r else [])
            for b in branches:
                lines.append(f"   - Tier {b['tier']}, score {b['score']}: {b['strategy_text']}")
        return "Escalation Decision (ToT trace)", "\n".join(lines)

    # Fallback: Knowledge Retrieval over the policy/history corpus, synthesized
    # into a cited prose answer (falls back to raw chunks itself if no API
    # key is set or the call fails - see synthesize()'s own docstring).
    hits = retrieve(question)
    if hits:
        label = (
            "Knowledge Retrieval (RAG top-3 → LangChain LCEL → Claude)"
            if has_api_key() else "Knowledge Retrieval (RAG, top-3)"
        )
        return label, synthesize(question, hits)
    return "Orchestrator", (
        "I don't have a grounded answer for that yet — try asking about "
        "'overdue steps', 'compliance', 'escalations', or 'why is X delayed'."
    )


quick = st.columns(4)
quick_questions = ["What's overdue?", "Any compliance risk?", "Show escalation decisions", "Why is Benefits delayed?"]
for col, q in zip(quick, quick_questions):
    if col.button(q):
        st.session_state["_pending_question"] = q

question = st.chat_input("Ask the Agent...") or st.session_state.pop("_pending_question", None)

for role, text in st.session_state["chat_history"]:
    with st.chat_message("user" if role == "user" else "assistant"):
        st.markdown(text)

if question:
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state["chat_history"].append(("user", question))

    claude_answer = answer_question(question, steps, last_pass)
    if claude_answer is not None:
        agent_label, answer = "Orchestrator (Claude API · tool use)", claude_answer
    else:
        agent_label, answer = handle(question)

    with st.chat_message("assistant"):
        st.caption(f"Handled by: {agent_label}")
        st.markdown(answer)
    st.session_state["chat_history"].append(("assistant", f"**{agent_label}**\n\n{answer}"))
