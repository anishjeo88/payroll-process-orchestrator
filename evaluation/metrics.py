"""Evaluation metrics - Checkpoint 6. Computed from the MCP runtime-monitoring
log and surfaced on the Orchestrator dashboard; used to detect drift and
calibration failures over time, not just to judge individual decisions.

- Escalation Accuracy (target >=90%) - % of escalation decisions the
  Payroll Manager confirms as correct after review.
- Groundedness Rate (target 100%) - % of cycle-state responses backed by a
  verified tool-call result.
- Retrieval Relevance Score (target >=0.80) - average top-1 semantic
  similarity score for RAG queries.
- Notification Duplicate Rate (target <1%) - % of dispatches that were
  same-type/recipient duplicates within 4 hours.
- Fallback Rate (target <15%) - % of escalation decisions that fell back
  from ToT to human review (low confidence or timeout). A rising rate
  signals the ToT evaluation criteria need recalibration.
- Human Override Rate (target <10%) - % of agent-proposed actions a human
  reviewer modified or rejected. A rising rate signals the agent's
  reasoning is misaligned with Payroll-team judgment.
- Cycle Step On-Time Rate (target >=95%) - % of critical-path run book
  steps completed by their scheduled deadline across a full cycle.

Implemented in a later phase.
"""
