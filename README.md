# Payroll Process Orchestrator

An agentic AI coordinator for corporate payroll cycles, built for the CMU Agentic AI
Certification Capstone (Building Autonomous Systems for Real-World Applications).

## What it does

Coordinates a multi-team payroll cycle (Payroll Administrators, Payroll Engineers,
Benefits and Compensation Analysts, Finance Reviewers, Leadership) by continuously
observing cycle state, reasoning about the highest-priority next action, and taking
real actions — sending reminders, logging escalations, summarizing status per role —
instead of relying on manual tracking across email/chat/spreadsheets.

## Architecture

- **Reasoning:** ReAct loop (Thought → Action → Observation) via Claude API tool use
- **Memory:** short-term session context (current cycle) + long-term memory split
  across SQLite (structured facts: delay patterns, exception history) and Chroma
  (semantic: stakeholder preferences, free-text exception context)
- **Tools:** Task Status API, Notification Dispatcher, Calendar & Runbook Reader,
  Historical Cycle Store, Escalation Workflow Tool
- **Environment:** simulated payroll system (Payroll Calendar & Runbook, Task &
  Status DB, Inbound Data Feed Tracker, Outbound Processing Log, User Catalog)
- **Interface:** Streamlit app with role-based dashboards, agent chat, and an
  approvals view for human-in-the-loop confirmation of consequential actions

## Project layout

```
environment/   simulated payroll "world" (DB schema, seed data, cycle simulator)
tools/         the 5 agent tools, each reading/writing the environment
memory/        short-term context + long-term SQLite/Chroma stores
agent/         ReAct reasoning loop, prompts, role definitions
interface/     Streamlit GUI (dashboard, agent chat, approvals, history)
data/          local SQLite db file + Chroma persistence directory (gitignored)
tests/         scenario-based tests for the simulated payroll cycle
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then add your ANTHROPIC_API_KEY
```

## Status

Project scaffold only — implementation in progress, phase by phase.
