-- Simulated payroll environment + MCP shared state schema.
-- This file is the source of truth; environment/seed_data.py executes it
-- and then inserts the demo cycle's rows.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN (
        'Payroll Administrator', 'Payroll Engineer',
        'Benefits and Compensation Analyst', 'Finance Reviewer', 'Leadership'
    ))
);

CREATE TABLE IF NOT EXISTS runbook_steps (
    id INTEGER PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    owner_user_id INTEGER NOT NULL REFERENCES users(id),
    deadline TEXT NOT NULL,              -- ISO datetime, relative to the demo's fixed "now"
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed')),
    -- risk (on_track / at_risk / overdue / blocked) is NOT stored here - the
    -- Cycle Monitor derives it from `deadline` vs. the simulated "now", and
    -- from `depends_on_step_id` below, at query time
    -- (environment/simulator.py), so the agent is grounded in a live
    -- comparison rather than a pre-baked label.
    is_compliance_step INTEGER NOT NULL DEFAULT 0,
    prior_alerts_sent INTEGER NOT NULL DEFAULT 0,
    -- If set, this step cannot be genuinely underway until the referenced
    -- step is completed - risk_level() reports 'blocked' rather than
    -- independently scoring this step's own deadline, so a downstream step
    -- never shows as on-track/completed while its prerequisite is still open.
    depends_on_step_id INTEGER REFERENCES runbook_steps(id)
);

-- Long-term structured memory (read via the Historical Cycle Store tool)
CREATE TABLE IF NOT EXISTS delay_patterns (
    id INTEGER PRIMARY KEY,
    step_name TEXT NOT NULL,
    typical_delay_days REAL NOT NULL,
    note TEXT
);

-- Closed-out past cycles (read via the Historical Cycle Store tool) - the
-- demo's live cycle (environment/seed_data.py's CYCLE_ID) never appears
-- here, only prior ones seeded purely for cycle-over-cycle history on the
-- History page. Deliberately a standalone summary table rather than more
-- runbook_steps rows under a different cycle_id, so past cycles can't
-- leak into get_all_steps()/Cycle Monitor and get treated as live work.
CREATE TABLE IF NOT EXISTS cycle_history (
    id INTEGER PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    period_label TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    steps_total INTEGER NOT NULL,
    steps_on_time INTEGER NOT NULL,
    tier2_escalations INTEGER NOT NULL DEFAULT 0,
    tier3_escalations INTEGER NOT NULL DEFAULT 0,
    compliance_status TEXT NOT NULL,
    note TEXT
);

-- MCP shared state (coordination/mcp_state.py) - what the 5 agents actually
-- read/write hub-and-spoke during the cycle.
CREATE TABLE IF NOT EXISTS mcp_alert_log (
    id INTEGER PRIMARY KEY,
    step_id INTEGER NOT NULL REFERENCES runbook_steps(id),
    alert_type TEXT NOT NULL,
    recipient_user_id INTEGER NOT NULL REFERENCES users(id),
    sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_escalations (
    id INTEGER PRIMARY KEY,
    step_id INTEGER NOT NULL REFERENCES runbook_steps(id),
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    strategy_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_approval'
        CHECK (status IN ('pending_approval', 'approved', 'rejected', 'auto_dispatched')),
    reason TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT
);

-- Enforces "at most one active (non-rejected) escalation per step" at the
-- database level, not just via an application-side check-then-insert (which
-- can race: two near-simultaneous cycle passes - e.g. two browser sessions
-- hitting a freshly-seeded DB at once - can each see "none active yet" and
-- both insert before either commits, exactly what produced 3 pending
-- escalations for one step in testing). A partial UNIQUE index makes the
-- second insert fail atomically instead; tools/escalation_workflow.py's
-- create_escalation() catches that and returns the row that won.
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_escalation_per_step
    ON mcp_escalations(step_id) WHERE status != 'rejected';

CREATE TABLE IF NOT EXISTS mcp_action_log (
    id INTEGER PRIMARY KEY,
    agent TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- Tiny durable key/value store for UI preferences that must survive a
-- sidebar page navigation (interface/utils.py's role_selector) - also
-- created lazily on first read/write, so it doesn't force a re-seed.
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
