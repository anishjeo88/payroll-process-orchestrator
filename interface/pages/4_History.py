"""Past cycles and delay patterns, read from long-term memory (SQLite via
the Historical Cycle Store tool) - the cross-cycle facts that already shape
today's Escalation Decision / Knowledge Retrieval answers.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from interface.theme import render_banner
from interface.utils import role_selector
from tools.historical_cycle_store import get_cycle_history

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "payroll.db"

st.set_page_config(page_title="History · Payroll Process Orchestrator", page_icon="🗂️", layout="wide")
role_selector()

render_banner("🗂️ Payrcoll Cycle History & Delay Patterns", [
    "A historical view of past cycles and the delay patterns that shape today's Escalation Decision and Knowledge Retrieval answers.",
])

st.subheader("Previous Cycles")
history = get_cycle_history()
if history:
    df = pd.DataFrame(history).rename(columns={
        "cycle_id": "Cycle", "period_label": "Period", "steps_total": "Steps",
        "steps_on_time": "On time", "tier2_escalations": "Tier 2",
        "tier3_escalations": "Tier 3", "compliance_status": "Compliance", "note": "Note",
    })
    st.dataframe(df[["Cycle", "Period", "Steps", "On time", "Tier 2", "Tier 3", "Compliance", "Note"]],
                 use_container_width=True, hide_index=True)
else:
    st.caption("No past cycles on file yet.")

st.subheader("Delay Patterns")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
patterns = [dict(r) for r in conn.execute("SELECT * FROM delay_patterns").fetchall()]
conn.close()

if patterns:
    st.dataframe(pd.DataFrame(patterns)[["step_name", "typical_delay_days", "note"]],
                 use_container_width=True, hide_index=True)
else:
    st.caption("No delay patterns on file.")
