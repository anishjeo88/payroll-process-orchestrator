"""Long-term semantic memory (Chroma) - Checkpoints 3, 5 & 6.

Collections: Runbook, Escalation Matrix, Policy Documents, and Cycle History
(stakeholder preferences, free-text exception notes). Queried exclusively by
the Knowledge Retrieval Agent (agents/knowledge_retrieval.py) - top-3 ranked
chunks by cosine similarity, returned with source citations; other agents
never query Chroma directly.

Every query is filtered per guardrails/static_constraints.py's source
version filter, excluding chunks with status = superseded regardless of
their similarity score.

Implemented in a later phase.
"""
