"""Sequential coordination for routine operations - Checkpoint 5.

A real LangGraph StateGraph, not just a plain function call:

    Cycle Monitor (classify) -> [at_risk?] -> Notification & Action -> END
                              -> [not at_risk] --------------------> END

Deadline reminders, status updates, and sign-off prompts follow this linear,
predictable, low-latency path. Chosen over looser coordination because each
node has a single defined input/output and LangGraph's graph-based execution
enforces the order explicitly, keeping the common case (the 80-85% of cycle
decisions that are routine, per Checkpoint 6) fast and auditable.

agents/orchestrator.py invokes this graph for every at_risk event instead of
calling agents.notification_action directly - the escalation path
(coordination/crew_escalation.py) is what CrewAI handles instead.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

import agents.notification_action as notification_action


class RoutineState(TypedDict):
    step: dict
    risk: str
    action: dict | None


def _notify_node(state: RoutineState) -> RoutineState:
    outcome = notification_action.send_tier1_reminder(state["step"])
    return {**state, "action": outcome}


def _route(state: RoutineState) -> str:
    return "notify" if state["risk"] == "at_risk" else "skip"


def _build_graph():
    graph = StateGraph(RoutineState)
    graph.add_node("notify", _notify_node)
    graph.set_conditional_entry_point(_route, {"notify": "notify", "skip": END})
    graph.add_edge("notify", END)
    return graph.compile()


_ROUTINE_GRAPH = _build_graph()


def run_routine(step: dict, risk: str) -> dict:
    """Runs the compiled LangGraph for one at_risk event. Returns the final
    state; `state["action"]` is the notification outcome, or None if the
    graph routed straight to END without notifying."""
    return _ROUTINE_GRAPH.invoke({"step": step, "risk": risk, "action": None})
