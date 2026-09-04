"""Short-term memory: session-scoped working context for the active payroll
cycle (completed tasks, sent alerts, open exceptions, per-stakeholder action
queues). Owned by the Orchestrator Agent, which connects it to long-term
memory at cycle boundaries (agents/orchestrator.py). Reset at the start of
each new cycle.

Distinct from MCP (coordination/mcp_state.py): short-term memory is this
process's working context, while MCP is the cross-agent shared-state hub all
five agents read/write during the cycle (branch tracking, action history,
runtime-monitoring log).

Implemented in a later phase."""
