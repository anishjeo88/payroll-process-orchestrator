"""Knowledge Retrieval Agent - Checkpoints 3 & 5.

A real Chroma vector store (persisted at data/chroma/) holding the Runbook,
Escalation Matrix, Policy Documents, and Cycle History corpus, queried by
genuine semantic similarity (Chroma's own embedding model - no API key
needed for retrieval itself), and wrapped in a LangChain LCEL chain that
asks Claude to synthesize a grounded, cited answer from what was retrieved.

Same contract as before regardless of whether an API key is present:
`retrieve()` always returns top-k ranked, source-cited chunks - only the
optional `synthesize()` step needs Claude, and falls back to returning the
raw chunks if no key is set.
"""

from __future__ import annotations

from pathlib import Path

import chromadb

from coordination.llm import has_api_key
from guardrails.static_constraints import filter_superseded

CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma"
COLLECTION_NAME = "payroll_knowledge"

_CORPUS = [
    {
        "id": "policy-esc-1",
        "text": "Escalation Matrix: Tier 1 (direct owner) applies for the first "
                "2 hours after a deadline. Tier 2 (team lead) applies once a Tier 1 "
                "alert has gone unanswered, or the step is on the critical path.",
        "source": "Escalation Matrix v3",
        "status": "current",
    },
    {
        "id": "policy-esc-1-old",
        "text": "Escalation Matrix: Tier 1 applies for the first 4 hours, "
                "escalate to Tier 3 directly after that.",
        "source": "Escalation Matrix v2 (2026-06)",
        "status": "superseded",
    },
    {
        "id": "policy-compliance-1",
        "text": "Compliance sign-off steps must never be routed through automated "
                "Tree-of-Thought escalation. Any overdue compliance step with an "
                "unanswered alert goes directly to the Payroll Manager and the "
                "Compliance Lead.",
        "source": "Compliance Handbook v1",
        "status": "current",
    },
    {
        "id": "history-benefits-1",
        "text": "Benefits Data Feed Validation has slipped in prior cycles, "
                "typically by about 1.5 days, most often around US federal "
                "holidays. Prior incidents were resolved without senior escalation.",
        "source": "Cycle History (Apr 2026)",
        "status": "current",
    },
]


def _get_collection():
    """Gets (or creates + seeds, on first run) the persistent Chroma
    collection. Chroma's default embedding function runs entirely locally -
    no API key or network call needed for retrieval itself."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(COLLECTION_NAME)

    if collection.count() == 0:
        collection.add(
            ids=[c["id"] for c in _CORPUS],
            documents=[c["text"] for c in _CORPUS],
            metadatas=[{"source": c["source"], "status": c["status"]} for c in _CORPUS],
        )
    return collection


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Real semantic search: embeds `query` and returns the top_k nearest
    chunks by cosine distance, each with its source citation. Filters
    superseded sources first (guardrails/static_constraints.py) by
    over-fetching, then trimming, so a superseded chunk never displaces a
    current one just because it scored higher before filtering."""
    collection = _get_collection()
    raw = collection.query(query_texts=[query], n_results=min(top_k * 2, collection.count()))

    candidates = []
    for doc_id, text, meta, distance in zip(
        raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    ):
        candidates.append({
            "id": doc_id, "text": text, "source": meta["source"], "status": meta["status"],
            "score": round(1 - distance, 3),  # cosine distance -> similarity
        })

    return filter_superseded(candidates)[:top_k]


_SYNTHESIS_PROMPT = """You are the Knowledge Retrieval Agent for a payroll orchestrator. \
Answer the question using ONLY the retrieved context below - do not add anything not \
supported by it, and cite each source by name. If the context doesn't answer the \
question, say so plainly instead of guessing.

Question: {question}

Retrieved context:
{context}

Answer (2-3 sentences, with inline source citations):"""


def synthesize(question: str, chunks: list[dict]) -> str:
    """LangChain LCEL pipeline: format the retrieved chunks into a prompt,
    ask Claude to answer strictly from them, parse the string out. Falls
    back to just listing the raw chunks if no API key is configured or the
    call fails, so the caller never has to special-case this."""
    if not chunks:
        return "Nothing on file for that."

    if not has_api_key():
        return "\n\n".join(f"_{c['source']}_ — {c['text']}" for c in chunks)

    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda

    from coordination.llm import get_chat_anthropic

    def _format_context(_: dict) -> dict:
        context = "\n".join(f"- ({c['source']}) {c['text']}" for c in chunks)
        return {"question": question, "context": context}

    chain = (
        RunnableLambda(_format_context)
        | ChatPromptTemplate.from_template(_SYNTHESIS_PROMPT)
        | get_chat_anthropic()
        | StrOutputParser()
    )

    try:
        return chain.invoke({})
    except Exception as exc:  # network/auth error - degrade, don't crash the page
        fallback = "\n\n".join(f"_{c['source']}_ — {c['text']}" for c in chunks)
        return f"{fallback}\n\n_(Claude synthesis unavailable: {exc})_"
