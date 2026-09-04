"""Creates data/payroll.db from environment/db_schema.sql and seeds one demo
payroll cycle: a realistic mix of completed, in-progress, overdue, and
at-risk run book steps (including one compliance sign-off) so the interface
and agents have something real to react to.

Cycle: 2026-09A, the semi-monthly period from Sep 1 through Sep 15, 2026.
Deadlines are explicit calendar dates within that window rather than
offsets, so the cycle stays legible on its own; environment/simulator.py's
DEMO_NOW (Sep 10, 15:00) sits roughly two-thirds through it.

Run directly to (re)build the demo database:
    python3 -m environment.seed_data
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payroll.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "db_schema.sql"

CYCLE_ID = "2026-09A"  # semi-monthly: "A" = 1st-15th, "B" would be 16th-EOM


def d(day: int, hour: int = 9) -> str:
    """ISO datetime for September `day`, 2026 - keeps the cycle's own
    deadlines readable as plain calendar dates."""
    return datetime(2026, 9, day, hour, 0, 0).isoformat()


USERS = [
    # (id, name, role)
    (1, "Dana Ruiz", "Payroll Administrator"),
    (2, "Sam Okafor", "Payroll Engineer"),
    (3, "Priya Nair", "Benefits and Compensation Analyst"),
    (4, "Marcus Lee", "Finance Reviewer"),
    (5, "Elena Vance", "Leadership"),
    (6, "Jordan Blake", "Finance Reviewer"),  # team lead tier for escalations
]

# (step_name, sequence, owner_user_id, deadline, status, is_compliance_step,
#  prior_alerts_sent, depends_on_sequence)
#
# `depends_on_sequence` refers to another row's `sequence` number, not a raw
# database id - seed() below resolves it to that row's actual id after
# insertion. A dependency that isn't completed makes this step 'blocked'
# (environment/simulator.py's risk_level), regardless of its own deadline -
# so Payroll Calculation Run can never show as completed, on-track, or
# independently overdue while Benefits Data Feed Validation is still open.
STEPS = [
    ("Period Open", 1, 1, d(1, 9), "completed", 0, 0, None),
    ("Inbound Data Feed: HR Roster", 2, 2, d(2, 17), "completed", 0, 0, None),
    ("Benefits Data Feed Validation", 3, 3, d(8, 17), "in_progress", 0, 2, None),
    ("Payroll Calculation Run", 4, 2, d(9, 12), "pending", 0, 0, 3),
    ("Compliance Sign-off: SOX Control Review", 5, 4, d(9, 17), "in_progress", 1, 1, None),
    ("Vendor File Transmission", 6, 1, d(10, 18), "in_progress", 0, 0, None),
    ("Tax Engine Reconciliation", 7, 4, d(11, 12), "in_progress", 0, 0, None),
    ("Finance Approval", 8, 4, d(12, 17), "pending", 0, 0, None),
    ("Reconciliation", 9, 1, d(15, 17), "pending", 0, 0, None),
]

DELAY_PATTERNS = [
    ("Benefits Data Feed Validation", 1.5,
     "Slips ~1.5 days on average, worse near US federal holidays (e.g. Labor Day, Sep 7)."),
    ("Compliance Sign-off: SOX Control Review", 0.5,
     "Rarely late, but any delay has previously required Compliance Lead involvement."),
]

# Closed-out past cycles - dummy history so the History page has more than
# one point of comparison. Not connected to runbook_steps at all (see
# db_schema.sql's cycle_history comment); purely for display + the
# Historical Cycle Store's "Prior Escalation History" ToT criterion.
#
# (cycle_id, period_label, closed_at, steps_total, steps_on_time,
#  tier2_escalations, tier3_escalations, compliance_status, note)
CYCLE_HISTORY = [
    ("2026-08A", "Aug 1-15, 2026", datetime(2026, 8, 15, 18, 0, 0).isoformat(),
     9, 7, 1, 0, "On time",
     "Benefits Data Feed Validation slipped ~2 days; resolved via a Tier 2 "
     "escalation to the Payroll Operations Lead."),
    ("2026-08B", "Aug 16-31, 2026", datetime(2026, 8, 31, 17, 0, 0).isoformat(),
     9, 9, 0, 0, "On time",
     "Clean cycle - every step completed on schedule, no escalations."),
]


def seed() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())

    conn.executemany(
        "INSERT INTO users (id, name, role) VALUES (?, ?, ?)", USERS
    )

    sequence_to_id: dict[int, int] = {}
    for (name, seq, owner_id, deadline, status, is_compliance, alerts, _) in STEPS:
        cur = conn.execute(
            """INSERT INTO runbook_steps
               (cycle_id, step_name, sequence, owner_user_id, deadline,
                status, is_compliance_step, prior_alerts_sent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (CYCLE_ID, name, seq, owner_id, deadline, status, is_compliance, alerts),
        )
        sequence_to_id[seq] = cur.lastrowid

    for (_, seq, *_rest, depends_on_seq) in STEPS:
        if depends_on_seq is not None:
            conn.execute(
                "UPDATE runbook_steps SET depends_on_step_id = ? WHERE id = ?",
                (sequence_to_id[depends_on_seq], sequence_to_id[seq]),
            )

    conn.executemany(
        "INSERT INTO delay_patterns (step_name, typical_delay_days, note) VALUES (?, ?, ?)",
        DELAY_PATTERNS,
    )

    conn.executemany(
        """INSERT INTO cycle_history
           (cycle_id, period_label, closed_at, steps_total, steps_on_time,
            tier2_escalations, tier3_escalations, compliance_status, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        CYCLE_HISTORY,
    )

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with cycle {CYCLE_ID} (Sep 1-15, 2026) - "
          f"{len(STEPS)} steps, {len(USERS)} users, "
          f"{len(CYCLE_HISTORY)} past cycles on file.")


if __name__ == "__main__":
    seed()
