"""Core ReAct reasoning loop (Thought -> Action -> Observation) via Claude API
tool use. Registers the 5 agent tools, reads/writes short-term memory each
turn, and enforces the defined stopping conditions. Implemented in Phase 4."""
