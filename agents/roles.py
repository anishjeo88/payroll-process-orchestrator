"""Role definitions (User Catalog with Roles) and per-role view/permission
logic used by the Orchestrator and the interface layer. Also defines the
escalation tier ceiling referenced by guardrails/static_constraints.py:
Tier 1 (direct owner), Tier 2 (team lead), Tier 3 (senior management/
Payroll Manager). Implemented in a later phase."""
