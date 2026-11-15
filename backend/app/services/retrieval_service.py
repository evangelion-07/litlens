from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
from app.services.embedding_cache import cached_embed

from app.services.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    configured_embedding_provider,
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)?")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "what", "when", "where", "which", "who", "why", "with",
}


def tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_PATTERN.findall((text or "").lower()) if token not in _STOP_WORDS]


def keyword_search(
    query: str,
    documents: Sequence[Mapping[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank chunks with a compact BM25 implementation and return only term matches."""
    terms = set(tokenize(query))
    if not terms or not documents or limit < 1:
        return []

    token_counts = [Counter(tokenize(str(document.get("text", "")))) for document in documents]
    lengths = [sum(counts.values()) for counts in token_counts]
    average_length = (sum(lengths) / len(lengths)) if lengths else 0.0
    document_frequency = {
        term: sum(1 for counts in token_counts if counts.get(term, 0) > 0)
        for term in terms
    }
    scored: list[tuple[float, int, Mapping[str, Any]]] = []
    k1, b = 1.5, 0.75

    for index, (document, counts) in enumerate(zip(documents, token_counts)):
        score = 0.0
        for term in terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_document_frequency = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * lengths[index] / max(average_length, 1.0))
            score += inverse_document_frequency * (frequency * (k1 + 1)) / denominator
        if score > 0:
            scored.append((score, index, document))

    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[2].get("paper_id", "")),
            item[2].get("page_number") or 0,
            item[2].get("ordinal") or 0,
        )
    )
    results = []
    for score, _, document in scored[:limit]:
        result = dict(document)
        result["score"] = score
        result["retrieval_mode"] = "keyword"
        results.append(result)
    return results


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def fuse_rankings(
    keyword_results: Sequence[Mapping[str, Any]],
    semantic_results: Sequence[Mapping[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Fuse two ranked lists with reciprocal rank fusion."""
    reciprocal_rank_constant = 60
    by_id: dict[str, dict[str, Any]] = {}
    scores: Counter[str] = Counter()
    for ranked in (keyword_results, semantic_results):
        for rank, result in enumerate(ranked, start=1):
            chunk_id = str(result.get("chunk_id", ""))
            if not chunk_id:
                continue
            scores[chunk_id] += 1 / (reciprocal_rank_constant + rank)
            by_id.setdefault(chunk_id, dict(result))
    ordered = sorted(by_id, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:limit]
    fused = []
    for chunk_id in ordered:
        item = by_id[chunk_id]
        item["score"] = scores[chunk_id]
        item["retrieval_mode"] = "hybrid"
        fused.append(item)
    return fused


async def retrieve_evidence(
    query: str,
    documents: Sequence[Mapping[str, Any]],
    limit: int = 5,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[list[dict[str, Any]], str, str | None]:
    keyword_results = keyword_search(query, documents, limit=max(limit * 4, limit))
    provider = embedding_provider or configured_embedding_provider()
    if provider is None or not documents:
        mode = "keyword" if provider is None else "keyword"
        return _assign_evidence_ids(keyword_results[:limit]), mode, None

    try:
        vectors = await cached_embed(provider, [query, *(str(item.get("text", "")) for item in documents)])
        if len(vectors) != len(documents) + 1:
            raise EmbeddingProviderError("Embedding count does not match source documents")
        semantic_ranked = []
        for index, document in enumerate(documents):
            similarity = cosine_similarity(vectors[0], vectors[index + 1])
            if similarity >= 0.15:
                result = dict(document)
                result["score"] = similarity
                semantic_ranked.append(result)
        semantic_ranked.sort(key=lambda item: (-item["score"], str(item.get("chunk_id", ""))))
        semantic_ranked = semantic_ranked[:max(limit * 4, limit)]
        if not semantic_ranked:
            return _assign_evidence_ids(keyword_results[:limit]), "keyword-fallback", None
        combined = fuse_rankings(keyword_results, semantic_ranked, limit)
        return _assign_evidence_ids(combined), "hybrid", None
    except Exception:
        # Keyword retrieval remains available when an optional embedding provider is down.
        return (
            _assign_evidence_ids(keyword_results[:limit]),
            "keyword-fallback",
            "Semantic retrieval was unavailable; keyword retrieval was used.",
        )


def _assign_evidence_ids(results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    assigned = []
    for index, item in enumerate(results, start=1):
        result = dict(item)
        result["evidence_id"] = f"E{index}"
        assigned.append(result)
    return assigned
