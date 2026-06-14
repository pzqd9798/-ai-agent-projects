"""Hybrid search fusion — merges results from multiple backends with scoring."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def fusion_score(
    results_by_backend: dict[str, list[dict[str, Any]]],
    *,
    weight_tavily: float = 1.2,
    weight_perplexity: float = 1.0,
    weight_default: float = 0.8,
    decay_factor: float = 0.7,
) -> list[dict[str, Any]]:
    """Reciprocal rank fusion across backends, weighted by source quality.

    Returns deduplicated, scored results sorted by relevance.
    """
    # Collect all results by URL
    url_scores: dict[str, float] = defaultdict(float)
    url_items: dict[str, dict[str, Any]] = {}
    backend_weights = {
        "tavily": weight_tavily,
        "perplexity": weight_perplexity,
    }

    for backend, results in results_by_backend.items():
        w = backend_weights.get(backend, weight_default)
        for rank, item in enumerate(results, start=1):
            url = item.get("url", "")
            if not url:
                # Use title as fallback key
                url = f"__nourl__{item.get('title', '')}"

            # Reciprocal rank with source weight
            score = w / (rank + 1) * (decay_factor ** (rank - 1))
            url_scores[url] += score

            if url not in url_items:
                url_items[url] = dict(item)
                url_items[url]["_matched_backends"] = [backend]
            else:
                url_items[url]["_matched_backends"].append(backend)
                # Take longer content
                if len(item.get("content", "")) > len(url_items[url].get("content", "")):
                    url_items[url]["content"] = item["content"]
                if len(item.get("raw_content", "")) > len(url_items[url].get("raw_content", "")):
                    url_items[url]["raw_content"] = item.get("raw_content", "")

    # Sort by score
    sorted_urls = sorted(url_scores, key=lambda u: url_scores[u], reverse=True)

    results = []
    for url in sorted_urls:
        item = url_items[url]
        item["score"] = round(url_scores[url], 4)
        item["matched_backends"] = item.pop("_matched_backends", [])
        results.append(item)

    return results


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
