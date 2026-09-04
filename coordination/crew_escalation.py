"""Iterative, feedback-driven coordination for escalation decisions -
Checkpoints 4 & 5.

    Cycle Monitor -> Orchestrator -> Escalation Decision Agent
        (ToT: Strategy Proposer generates -> Critic scores
         -> Controller prunes -> next depth)
        -> Knowledge Retrieval Agent (called mid-ToT for policy grounding)
        -> Orchestrator (human-in-the-loop gate)
        -> Notification & Action Agent

A real CrewAI crew: a Strategy Proposer agent generates 3 candidate
escalation strategies (Tier 1/2/3), then an Escalation Critic agent scores
each against the weighted rubric (Constraint Satisfaction 40%, Stakeholder
Appropriateness 25%, Prior Escalation History 20%, Downstream Impact 15%),
grounded in whatever agents.knowledge_retrieval already pulled from Chroma.
CrewAI manages the role separation between the two sub-roles; the Critic's
task runs after and consumes the Proposer's task output (`context=`).

Requires ANTHROPIC_API_KEY - agents/escalation_decision.py checks for one
and falls back to its deterministic heuristic scorer when it's absent,
so the demo keeps working before a key is added.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from coordination.llm import get_crewai_llm

RUBRIC = (
    "Constraint Satisfaction (40%) - does the strategy respect SLA and escalation "
    "policy; Stakeholder Appropriateness (25%) - is the tier and contact correct for "
    "this situation; Prior Escalation History (20%) - does it avoid repeating an "
    "already-ineffective tier; Downstream Impact (15%) - does it avoid over- or "
    "under-escalating given what else depends on this step."
)


class EscalationBranch(BaseModel):
    tier: int = Field(description="1, 2, or 3")
    strategy_text: str = Field(description="One sentence describing the concrete action")
    score: float = Field(description="0.0-1.0 against the weighted rubric")


class EscalationAssessment(BaseModel):
    branches: list[EscalationBranch] = Field(
        description="Exactly three branches, one each for tier 1, 2, and 3"
    )


def _build_crew():
    from crewai import Agent, Crew, Process, Task

    llm = get_crewai_llm()

    proposer = Agent(
        role="Escalation Strategy Proposer",
        goal="Generate three genuinely distinct candidate escalation strategies - "
             "one at each tier - for an overdue payroll run book step.",
        backstory=(
            "You coordinate payroll run books. You know that jumping straight to "
            "senior management for every delay causes alert fatigue and erodes "
            "trust, but that under-escalating a genuinely stuck task risks a missed "
            "SLA. You always produce all three tiers as live options, never just "
            "your favorite."
        ),
        llm=llm,
        verbose=False,
    )

    critic = Agent(
        role="Escalation Critic",
        goal="Score each proposed strategy against the weighted rubric and return "
             "a structured assessment.",
        backstory=(
            "You are skeptical of premature commitment to a single escalation path. "
            "You weigh prior escalation history heavily - a tier that already failed "
            "to get a response scores low - and you ground your scoring in the "
            "retrieved policy context you're given, not general instinct."
        ),
        llm=llm,
        verbose=False,
    )

    propose_task = Task(
        description=(
            "Payroll step '{step_name}' (owner: {owner_name}) is overdue by "
            "{hours_overdue} hours, with {prior_alerts} prior alert(s) already "
            "sent and unanswered. Propose three candidate escalation strategies: "
            "Tier 1 (direct owner reminder), Tier 2 (escalate to team lead), and "
            "Tier 3 (escalate to senior management). One sentence each, naming the "
            "concrete action."
        ),
        expected_output="Three short strategy sentences, one per tier.",
        agent=proposer,
    )

    critique_task = Task(
        description=(
            "Score each of the three proposed strategies against this rubric: "
            f"{RUBRIC}\n\nRelevant retrieved policy/history context:\n{{grounding}}\n\n"
            "Return exactly one branch per tier (1, 2, 3) with a score from 0.0 to 1.0."
        ),
        expected_output="A structured assessment with exactly three branches.",
        agent=critic,
        context=[propose_task],
        output_pydantic=EscalationAssessment,
    )

    return Crew(
        agents=[proposer, critic],
        tasks=[propose_task, critique_task],
        process=Process.sequential,
        verbose=False,
    )


_CREW = None


def run_crew_escalation(step: dict, grounding_text: str) -> EscalationAssessment:
    """Builds the crew once (lazily - so importing this module never requires
    an API key) and kicks it off for one step. Raises on any failure; the
    caller (agents/escalation_decision.py) catches that and falls back."""
    global _CREW
    if _CREW is None:
        _CREW = _build_crew()

    result = _CREW.kickoff(inputs={
        "step_name": step["step_name"],
        "owner_name": step["owner_name"],
        # Pre-formatted here, not with a {var:.1f} spec in the task template -
        # CrewAI's placeholder substitution is a plain string replace, not
        # Python's str.format(), so a format spec in the template is never
        # recognised as a placeholder and leaks into the prompt verbatim.
        "hours_overdue": f"{step.get('hours_overdue', 0.0):.1f}",
        "prior_alerts": step.get("prior_alerts_sent", 0),
        "grounding": grounding_text or "(no matching policy context retrieved)",
    })
    return result.pydantic
