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
docs/          architecture diagram (v8, Checkpoint 6) + sample evaluation
               report and agent-chat transcript (real recorded output)
environment/   simulated payroll "world" (DB schema, seed data, cycle simulator)
tools/         the 5 agent tools, each scoped to one owning agent
memory/        short-term context + long-term SQLite/Chroma stores
agents/        the 5 agents: orchestrator, cycle_monitor, knowledge_retrieval,
               escalation_decision, notification_action + prompts/roles
coordination/  LangGraph sequential flow, CrewAI escalation flow, MCP state hub
guardrails/    static constraints, dynamic runtime enforcement, human intervention
evaluation/    the 7 evaluation metrics, computed live (see Evaluation below)
interface/     Streamlit GUI (dashboard, agent chat, human-intervention queue, history)
data/          local SQLite db file + Chroma persistence directory (gitignored)
tests/         scenario-based pytest tests (dependency-aware risk, escalation
               dedup, guardrail conditions) - see Testing below
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

Opens at `http://localhost:8501`. No API key is required to run it — every
LLM-backed path degrades to a deterministic fallback (see the tech-stack
table above); add one to `.env` at any point and the same pages switch over
automatically, no restart-time flag needed.

## Usage

The app seeds one demo payroll cycle (`2026-09A`, Sep 1-15 2026) and runs
one full agent pass against it automatically on first load. A few things to
try, in order:

1. **Home** — pick a role from "Viewing as" (e.g. *Benefits and Compensation
   Analyst*) - it's remembered across every page, backed by the app's own
   `app_settings` table rather than browser session state (see
   `interface/utils.py::role_selector` for why that distinction matters).
2. **Dashboard** — see every run book step's live risk status (on track /
   at risk / overdue / **blocked**, e.g. Payroll Calculation Run waiting on
   Benefits Data Feed Validation), plus the MCP action log under "Recent
   Activities". Try **Mark a step complete** on an overdue step and watch
   its risk badge and any downstream "blocked" step update after the
   cycle pass re-runs.
3. **Agent Chat** — ask it things: *"What's overdue?"*, *"Any compliance
   risk?"*, *"Show escalation decisions"*, *"Why is Benefits delayed?"*, or
   free-form questions like *"what's the escalation policy for a compliance
   step?"*. The banner tells you whether you're in Smart mode (a real
   Claude tool-use loop) or Basic mode (deterministic rules) depending on
   whether `ANTHROPIC_API_KEY` is set. See
   [`docs/sample-agent-chat-transcript.md`](docs/sample-agent-chat-transcript.md)
   for real recorded example Q&A.
4. **Approvals** — the human-in-the-loop queue. Every item here is a Tier
   2/3 escalation or an at-risk compliance sign-off (never Tier 1, which
   auto-dispatches). Approve or reject one and check Dashboard/History
   afterward.
5. **History** — two seeded past cycles (`2026-08A`, `2026-08B`) plus the
   known delay patterns Escalation Decision and Knowledge Retrieval draw
   on — the cross-cycle memory the current cycle's decisions are actually
   grounded in.

## Evaluation

`evaluation/metrics.py` implements all 7 Checkpoint 6 metrics as real, live
computations over the SQLite DB (and a real Chroma query for retrieval
relevance) — not placeholders. Run it any time:

```bash
.venv/bin/python -m evaluation.metrics
```

A worked example, with honest interpretation of what each number means at
this demo's scale (including two real findings it surfaced — a retrieval
score below target on a small corpus, and a genuine historical delay), is
checked in at
[`docs/sample-evaluation-report.md`](docs/sample-evaluation-report.md).

## Testing

```bash
.venv/bin/python -m pytest tests/ -v
```

`tests/scenarios/` covers dependency-aware risk derivation (the exact
"downstream step shows completed while its prerequisite is still overdue"
bug found during manual testing), the escalation-dedup unique constraint
(a regression test for a real race-condition bug — two near-simultaneous
cycle passes each creating their own duplicate escalation — found and
fixed during development), and the Checkpoint 6 guardrail conditions. Runs
against a temp, isolated DB — never `data/payroll.db`.

## Reviewing without running it

If you're reviewing rather than running: start with
[`docs/architecture-diagram-v8.png`](docs/architecture-diagram-v8.png) for
the visual, then `agents/orchestrator.py` (routing + the Claude tool-use
loop), `agents/escalation_decision.py` (the CrewAI-backed Tree-of-Thought
search), and `guardrails/` (the three-layer safety design). The two sample
artifacts above (`docs/sample-agent-chat-transcript.md`,
`docs/sample-evaluation-report.md`) are real recorded output, not mockups,
if you want to see behavior without standing up the environment yourself.

## Status

Working demo, not just scaffolding — the environment/tools/agents/guardrails
layers all have real (if intentionally simplified where noted) implementations
you can run and click through today. Phase-by-phase hardening continues from here.
