"""MCP shared-state hub - Checkpoints 5 & 6.

Single source of truth for cycle state, escalation tracking, action
history, and the runtime-monitoring log (timestamped agent actions,
tool-call results, and reasoning steps) - all backed by the
`mcp_alert_log`, `mcp_escalations`, and `mcp_action_log` tables in the same
SQLite database as the simulated environment (environment/db_schema.sql).

All five agents read from and write to MCP rather than passing full state
objects directly - deliberately hub-and-spoke rather than a mesh of direct
agent-to-agent channels, so agents added in future phases integrate by
reading from MCP without changing any existing agent's interface.

This module is a facade, not a new store: each function below just
re-exports the real implementation from wherever it actually lives
(tools/escalation_workflow.py, tools/notification_dispatcher.py,
guardrails/runtime_enforcement.py), so every agent can do `from
coordination.mcp_state import ...` as the one place "the MCP hub" is
addressed, matching the architecture diagram, without duplicating logic.

Also backs two guardrails:
- guardrails/static_constraints.py's notification-deduplication check
  (same-type/recipient alert log, 4-hour window)
- guardrails/runtime_enforcement.py's groundedness check (every
  cycle-state claim must trace to a logged tool-call result)
"""

from __future__ import annotations

from guardrails.runtime_enforcement import get_action_log, log_action
from tools.escalation_workflow import (
    create_escalation,
    decide_escalation,
    get_active_escalation,
    get_latest_escalation,
    get_pending_escalations,
)
from tools.notification_dispatcher import dispatch as dispatch_notification

__all__ = [
    "log_action",
    "get_action_log",
    "create_escalation",
    "decide_escalation",
    "get_active_escalation",
    "get_latest_escalation",
    "get_pending_escalations",
    "dispatch_notification",
]
