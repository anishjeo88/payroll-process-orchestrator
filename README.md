# Payroll Process Orchestrator

An agentic AI coordinator for corporate payroll cycles, built for the CMU Agentic AI
Certification Capstone (Building Autonomous Systems for Real-World Applications).

## What it does

Coordinates a multi-team payroll cycle (Payroll Administrators, Payroll Engineers,
Benefits and Compensation Analysts, Finance Reviewers, Leadership) by continuously
observing cycle state, reasoning about the highest-priority next action, and taking
real actions — sending reminders, routing escalations, summarizing status per role —
instead of relying on manual tracking across email/chat/spreadsheets.

## Architecture (Checkpoint 6)

A five-agent system, not a single agent:

- **Orchestrator Agent (Supervisor)** — Claude API. Routes events to the right
  agent, is the human-in-the-loop gate, connects short-term ↔ long-term memory,
  produces cycle-status and executive reports.
- **Cycle Monitor Agent** — LangGraph, always-on. Polls task/data-feed status,
  classifies events, routes them onward. Makes no action decisions.
- **Knowledge Retrieval Agent** — LangChain (LCEL), on-demand. RAG over Chroma
  (Runbook, Escalation Matrix, Policy Documents, Cycle History); returns top-3
  chunks with citations. Retrieves only — never generates.
- **Escalation Decision Agent** — CrewAI, event-triggered. Tree-of-Thought via
  Beam Search (Strategy Proposer ⇄ Critic sub-roles) for multi-constraint
  escalation routing, consulting Knowledge Retrieval mid-search.
- **Notification & Action Agent** — CrewAI, action executor. Sends alerts,
  creates escalation records, logs outcomes. Makes no contact decisions.

**Coordination:** sequential LangGraph flow for routine operations (low latency,
predictable); iterative CrewAI + LangGraph flow with feedback for escalation
decisions (higher latency, higher decision quality). All five agents read/write
a shared **MCP** state hub — hub-and-spoke, not a mesh.

**Memory:** short-term (active-cycle context, Orchestrator-owned) + long-term,
split across SQLite (structured: delay patterns, exception history, via the
Historical Cycle Store tool) and Chroma (semantic: Knowledge Retrieval Agent
only).

**Safety guardrails (Checkpoint 6):**
- *Static constraints* — per-agent tool-access scoping, the Tier 1/2/3 escalation
  ceiling, notification deduplication, and a source-version filter on RAG.
- *Dynamic runtime enforcement* — a groundedness check, a ToT confidence gate,
  an 8-second hard timeout, and runtime monitoring logged to MCP.
- *Human intervention* — five selective triggers (Tier 2/3 escalation,
  inconclusive ToT, compliance risk, a failed groundedness check, an anomalous
  escalation-rate spike) routed to the Payroll Manager.

**Tools:** Task Status API, Notification Dispatcher, Calendar & Runbook Reader,
Historical Cycle Store, Escalation Workflow Tool — each scoped to a specific
agent by the static-constraints guardrail.

**Interface:** Streamlit app with role-based dashboards, agent chat (with the
ToT trace for escalation events), and a human-intervention queue.

See [`docs/architecture-diagram-v8.png`](docs/architecture-diagram-v8.png) (Checkpoint 6 / v8)
for the full visual.

## Project layout

```
docs/          architecture diagram (current: v8, Checkpoint 6)
environment/   simulated payroll "world" (DB schema, seed data, cycle simulator)
tools/         the 5 agent tools, each scoped to one owning agent
memory/        short-term context + long-term SQLite/Chroma stores
agents/        the 5 agents: orchestrator, cycle_monitor, knowledge_retrieval,
               escalation_decision, notification_action + prompts/roles
coordination/  LangGraph sequential flow, CrewAI escalation flow, MCP state hub
guardrails/    static constraints, dynamic runtime enforcement, human intervention
evaluation/    the 7 evaluation metrics (escalation accuracy, groundedness, ...)
interface/     Streamlit GUI (dashboard, agent chat, human-intervention queue, history)
data/          local SQLite db file + Chroma persistence directory (gitignored)
tests/         scenario-based tests for the simulated payroll cycle
```

## Tech stack — what's actually running vs. declared

Every package below is genuinely imported and used, not just listed:

| Layer | Tech | Where |
|---|---|---|
| UI | Streamlit + pandas | `interface/` |
| Agent reasoning | **Claude API** (`anthropic`), tool-use loop | `agents/orchestrator.py::answer_question` |
| Routine flow | **LangGraph** `StateGraph` | `coordination/langgraph_flow.py` |
| Escalation flow | **CrewAI** (Strategy Proposer + Critic agents) | `coordination/crew_escalation.py` |
| RAG generation | **LangChain** LCEL (`RunnableLambda \| prompt \| ChatAnthropic \| parser`) | `agents/knowledge_retrieval.py::synthesize` |
| Vector store | **Chroma** (persistent, local embeddings) | `agents/knowledge_retrieval.py::retrieve` |
| Structured data | SQLite | `environment/`, `tools/` |

**Every LLM-backed path degrades gracefully without an `ANTHROPIC_API_KEY`:**
Escalation Decision falls back to a deterministic heuristic scorer, and the
Orchestrator's chat falls back to a rule-based router — so the app is fully
testable before you add a key, and switches over automatically the moment
one is present in `.env`. Chroma retrieval itself needs no key at all (its
embeddings run locally).

## Setup

CrewAI requires Python 3.10+; this project uses a dedicated Python 3.11 venv
so it doesn't touch your system Python:

```bash
brew install python@3.11                    # one-time, if not already installed
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                        # then add your ANTHROPIC_API_KEY (optional - see above)
python3 -m environment.seed_data             # any Python works for this - no heavy deps
.venv/bin/python -m streamlit run interface/Home.py
```

## Status

Working demo, not just scaffolding — the environment/tools/agents/guardrails
layers all have real (if intentionally simplified where noted) implementations
you can run and click through today. Phase-by-phase hardening continues from here.
