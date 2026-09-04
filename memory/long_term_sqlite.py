"""Long-term structured memory (SQLite): delay patterns and exception history
as queryable facts (cycle_id, step, expected_date, actual_date, reason),
read through the Historical Cycle Store tool. Distinct from MCP
(coordination/mcp_state.py), which holds only the *current* cycle's live
session state, ToT branch tracking, and the runtime-monitoring log - MCP is
not itself long-term storage.

Implemented in a later phase."""
