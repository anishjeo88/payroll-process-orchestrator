"""Shared Claude API access for every agent that reasons with an LLM
(Escalation Decision's CrewAI agents, the Orchestrator's tool-use chat, the
Knowledge Retrieval Agent's LCEL answer-synthesis step).

Centralised here so every integration checks for a key the same way and
degrades the same way when one isn't set - the demo must keep working with
the deterministic fallbacks (agents/escalation_decision.py's heuristic
scorer, interface/pages/2_Agent_Chat.py's rule-based handler) until a real
ANTHROPIC_API_KEY is added to .env.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def get_anthropic_client():
    """Raises if ANTHROPIC_API_KEY isn't set - callers should check
    has_api_key() first and fall back to their deterministic path instead
    of calling this speculatively."""
    import anthropic

    return anthropic.Anthropic()


def get_chat_anthropic(temperature: float = 0.2):
    """A LangChain-wrapped Claude client, for LCEL chains
    (agents/knowledge_retrieval.py)."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=CLAUDE_MODEL, temperature=temperature)


def get_crewai_llm():
    """A CrewAI-compatible LLM handle for Claude
    (coordination/crew_escalation.py). CrewAI takes a LiteLLM-style model
    string and reads ANTHROPIC_API_KEY from the environment itself."""
    from crewai import LLM

    return LLM(model=f"anthropic/{CLAUDE_MODEL}", temperature=0.2)
