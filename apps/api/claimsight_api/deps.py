from __future__ import annotations

from claimsight_graphrag.retriever import HybridRetriever
from claimsight_graphrag.store import get_store

_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever(get_store())
    return _retriever


def store_kind() -> str:
    return get_store().kind()
