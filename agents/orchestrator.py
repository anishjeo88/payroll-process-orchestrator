"""Orchestrator Agent (Supervisor) - Checkpoint 5/6.

Claude API, central controller. Routine events go straight through
LangGraph, escalation events go through the Escalation Decision Agent's
CrewAI-run ToT, human-intervention conditions gate before any Tier 2/3 or
compliance action. `run_cycle_pass` itself stays rule-based routing (the
control flow is deterministic by design, per the architecture doc - the
*reasoning* inside each step is where the LLM calls live). `answer_question`
is where the Orchestrator actually reasons with Claude: a real tool-use loop
grounded in the same tools every other agent uses, falling back to
interface/pages/2_Agent_Chat.py's rule-based handler if no
ANTHROPIC_API_KEY is configured.
"""

from __future__ import annotations

import agents.notification_action as notification_action
from agents.cycle_monitor import poll_events
from agents.escalation_decision import evaluate as evaluate_escalation
from coordination.langgraph_flow import run_routine
from coordination.llm import has_api_key
from guardrails.human_intervention import compliance_bypass, escalation_needs_review
from guardrails.runtime_enforcement import assert_grounded, log_action
from tools.escalation_workflow import get_active_escalation, get_pending_escalations
from tools.historical_cycle_store import get_delay_pattern


def run_cycle_pass() -> list[dict]:
    """One pass of the routine LangGraph flow + escalation CrewAI flow,
    combined: Cycle Monitor -> Orchestrator -> (Notification, or Escalation
    Decision -> Orchestrator HITL gate -> Notification). Returns one result
    per non-on-track event, for the dashboard/chat to display."""
    results = []

    for event in poll_events():
        step = dict(event["step"])
        step["hours_overdue"] = event["hours_overdue"]
        risk = event["risk"]

        if risk != "blocked" and step.get("depends_on_step_id"):
            # This step has an upstream dependency and isn't (or is no
            # longer) blocked on it - the dependency must have just
            # completed. Proactively tell the owner instead of leaving the
            # step to sit at 'pending' until someone happens to notice;
            # deduped via the same alert log as any other notification, so
            # this only actually sends once, right when the block clears.
            notice = notification_action.notify_unblocked(step)
            if notice.get("sent"):
                results.append({
                    "step": step, "risk": risk,
                    "path": "proactive: upstream dependency completed",
                    "action": notice,
                })

        if risk == "on_track":
            continue

        if risk == "blocked":
            # Blocked on an upstream step that's already the subject of its
            # own escalation - deliberately does NOT run its own ToT search
            # or create a second escalation for what is really one root
            # cause (the Escalation Decision rubric's Downstream Impact
            # criterion exists precisely to avoid this kind of pile-on).
            # Not logged to MCP: "still blocked" is a passive classification,
            # already visible as the step's Risk badge on the Dashboard, not
            # an agent action - logging it on every pass would just bury
            # real actions under repeat-observation noise.
            results.append({
                "step": step, "risk": risk,
                "path": "blocked (waiting on upstream escalation)",
            })
            continue

        if risk == "at_risk":
            state = run_routine(step, risk)
            results.append({
                "step": step, "risk": risk, "path": "routine (LangGraph)",
                "action": state["action"],
            })
            continue

        # risk == "overdue"
        active = get_active_escalation(step["id"])
        if active is not None:
            # Already escalated (pending review, approved, or auto-dispatched)
            # and not yet rejected - re-running the cycle pass must not pile
            # up duplicate escalations for a step that's already in flight.
            results.append({
                "step": step, "risk": risk, "path": f"already escalated ({active['status']})",
                "escalation_id": active["id"],
            })
            continue

        if compliance_bypass(step):
            branch = {
                "tier": 3,
                "strategy_text": (
                    f"Compliance sign-off '{step['step_name']}' is overdue with no "
                    f"owner response - immediate Payroll Manager + Compliance Lead review."
                ),
                "score": 1.0,
            }
            eid = notification_action.record_pending_escalation(
                step, branch, "compliance sign-off at risk - bypasses ToT per policy"
            )
            results.append({
                "step": step, "risk": risk, "path": "compliance bypass (direct to human)",
                "escalation_id": eid, "branch": branch,
            })
            continue

        tot_result = evaluate_escalation(step)
        best = tot_result["best"]
        needs_review, reason = escalation_needs_review(best["tier"], tot_result["confidence"])
        log_action("Escalation Decision", "tot_evaluated",
                   f"{step['step_name']}: best={best['tier']} conf={tot_result['confidence']}")

        if needs_review:
            eid = notification_action.record_pending_escalation(step, best, reason)
            results.append({
                "step": step, "risk": risk, "path": "ToT -> human review",
                "escalation_id": eid, "tot": tot_result,
            })
        else:
            outcome = notification_action.send_tier1_reminder(step)
            results.append({
                "step": step, "risk": risk, "path": "ToT -> auto Tier 1",
                "action": outcome, "tot": tot_result,
            })

    return results


def cycle_summary(steps: list[dict]) -> str:
    """A grounded natural-language summary - every fact traces to a `steps`
    row from tools.task_status_api.get_all_steps (the groundedness check
    would block anything that didn't)."""
    from environment.simulator import risk_level

    steps_by_id = {s["id"]: s for s in steps}
    by_risk: dict[str, list[str]] = {}
    for s in steps:
        r = risk_level(s, steps_by_id)
        by_risk.setdefault(r, []).append(s["step_name"])

    assert_grounded("cycle summary", {"source": "tools.task_status_api.get_all_steps"})

    lines = [f"Cycle {steps[0]['cycle_id']} - {len(steps)} run book steps."]
    for label, key in (
        ("Completed", "completed"), ("On track", "on_track"),
        ("At risk (due within 6h)", "at_risk"), ("Overdue", "overdue"),
        ("Blocked (waiting on an upstream step)", "blocked"),
    ):
        names = by_risk.get(key, [])
        if names:
            lines.append(f"- {label} ({len(names)}): {', '.join(names)}")
    return "\n".join(lines)


def why_this_delay(step: dict) -> str:
    """Answers "why is X delayed" using the Historical Cycle Store, showing
    long-term memory actually shaping the response."""
    pattern = get_delay_pattern(step["step_name"])
    if not pattern:
        return f"No historical delay pattern on file for '{step['step_name']}'."
    return (
        f"'{step['step_name']}' has a known pattern: typically ~"
        f"{pattern['typical_delay_days']} day(s) late. {pattern['note']}"
    )


_ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator Agent for a payroll \
process orchestrator. You supervise five agents but do not act autonomously \
yourself - you answer stakeholder questions by calling tools to ground every \
claim in live data, exactly like the other agents do. Never state a fact about \
cycle state, an escalation, or a policy without having called a tool for it \
first. Keep answers to 2-4 sentences, and say plainly when a tool returned \
nothing relevant rather than guessing."""

_TOOLS = [
    {
        "name": "get_cycle_summary",
        "description": "Grounded summary of every run book step's status: "
                        "completed, on track, at risk, overdue, or blocked.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_pending_escalations",
        "description": "Every escalation currently awaiting Payroll Manager review.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_last_cycle_pass_trace",
        "description": "The Tree-of-Thought trace (candidate strategies and scores) "
                        "from the most recent cycle pass, for escalation events.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "retrieve_policy",
        "description": "Semantic search over the Runbook/Escalation Matrix/Policy/"
                        "Cycle History knowledge base (Chroma).",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


def _execute_tool(name: str, tool_input: dict, steps: list[dict], last_pass: list[dict]) -> str:
    if name == "get_cycle_summary":
        return cycle_summary(steps)
    if name == "get_pending_escalations":
        pending = get_pending_escalations()
        if not pending:
            return "No escalations are currently pending review."
        return "\n".join(
            f"- {e['step_name']}: Tier {e['tier']}, confidence {e['confidence']:.2f} - {e['reason']}"
            for e in pending
        )
    if name == "get_last_cycle_pass_trace":
        rows = [r for r in last_pass if "tot" in r or "branch" in r]
        if not rows:
            return "No escalation decisions in the last cycle pass."
        lines = []
        for r in rows:
            lines.append(f"{r['step']['step_name']} (path: {r['path']}):")
            branches = r.get("tot", {}).get("branches") or ([r["branch"]] if "branch" in r else [])
            for b in branches:
                lines.append(f"  Tier {b['tier']}, score {b['score']}: {b['strategy_text']}")
        return "\n".join(lines)
    if name == "retrieve_policy":
        from agents.knowledge_retrieval import retrieve

        hits = retrieve(tool_input["query"])
        if not hits:
            return "Nothing relevant found."
        return "\n".join(f"({h['source']}) {h['text']}" for h in hits)
    return f"Unknown tool: {name}"


def answer_question(question: str, steps: list[dict], last_pass: list[dict]) -> str | None:
    """A real Claude API tool-use loop grounding every answer in the same
    tools the other agents use. Returns None (rather than raising) if no
    ANTHROPIC_API_KEY is configured, so interface/pages/2_Agent_Chat.py can
    fall back to its rule-based handler without a try/except around every
    call site."""
    if not has_api_key():
        return None

    from coordination.llm import CLAUDE_MODEL, get_anthropic_client

    client = get_anthropic_client()
    messages = [{"role": "user", "content": question}]

    for _ in range(4):  # hard cap - this is a bounded grounding loop, not open-ended agency
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=_ORCHESTRATOR_SYSTEM_PROMPT,
            tools=_TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text").strip()

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _execute_tool(block.name, block.input, steps, last_pass)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id, "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    return "I wasn't able to ground a complete answer to that within the tool-call budget."
