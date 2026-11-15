from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.embedding_provider import EmbeddingProvider
from app.services.retrieval_service import keyword_search, retrieve_evidence


def evaluate_rankings(
    queries: Sequence[Mapping[str, Any]],
    rankings: Mapping[str, Sequence[str]],
    k: int = 3,
) -> dict[str, Any]:
    if k < 1:
        raise ValueError("k must be at least 1")
    per_query = []
    for query in queries:
        query_id = str(query["id"])
        relevant = set(query.get("relevant_chunk_ids", []))
        retrieved = list(rankings.get(query_id, []))[:k]
        hits = len(relevant.intersection(retrieved))
        first_relevant = next((rank for rank, item in enumerate(retrieved, start=1) if item in relevant), None)
        per_query.append({
            "query_id": query_id,
            "precision_at_k": hits / k,
            "recall_at_k": hits / len(relevant) if relevant else 0.0,
            "reciprocal_rank": 1 / first_relevant if first_relevant else 0.0,
            "retrieved_chunk_ids": retrieved,
        })
    count = len(per_query)
    return {
        "query_count": count,
        "k": k,
        "precision_at_k": sum(row["precision_at_k"] for row in per_query) / count if count else 0.0,
        "recall_at_k": sum(row["recall_at_k"] for row in per_query) / count if count else 0.0,
        "mean_reciprocal_rank": sum(row["reciprocal_rank"] for row in per_query) / count if count else 0.0,
        "per_query": per_query,
    }


def evaluate_keyword(queries, documents, k: int = 3) -> dict[str, Any]:
    rankings = {}
    for query in queries:
        results = keyword_search(query["query"], documents, limit=k)
        rankings[str(query["id"])] = [str(item["chunk_id"]) for item in results]
    return evaluate_rankings(queries, rankings, k=k)


async def evaluate_hybrid(
    queries,
    documents,
    embedding_provider: EmbeddingProvider,
    k: int = 3,
) -> dict[str, Any]:
    rankings = {}
    modes = []
    for query in queries:
        evidence, mode, _notice = await retrieve_evidence(
            query["query"], documents, limit=k, embedding_provider=embedding_provider
        )
        rankings[str(query["id"])] = [str(item["chunk_id"]) for item in evidence]
        modes.append(mode)
    result = evaluate_rankings(queries, rankings, k=k)
    result["retrieval_modes"] = modes
    result["hybrid_runs"] = sum(mode == "hybrid" for mode in modes)
    return result
