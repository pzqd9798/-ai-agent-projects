"""Enhanced search backends — 6 search providers with unified interface, caching, and fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

import requests

from config import Configuration

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Unified result format
# ---------------------------------------------------------------------------


def make_result(
    results: list[dict[str, Any]],
    backend: str,
    answer: str | None = None,
    notices: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "results": results,
        "backend": backend,
        "answer": answer,
        "notices": notices or [],
    }


def make_item(
    title: str = "",
    url: str = "",
    content: str = "",
    raw_content: str = "",
) -> dict[str, str]:
    return {
        "title": title,
        "url": url,
        "content": content,
        "raw_content": raw_content,
    }


# ---------------------------------------------------------------------------
# Backend: Tavily
# ---------------------------------------------------------------------------


def search_tavily(query: str, config: Configuration, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    try:
        from tavily import TavilyClient
        api_key = os.getenv("TAVILY_API_KEY", "")
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="advanced" if getattr(config, "fetch_full_page", True) else "basic",
            max_results=max_results,
        )
        results = [
            make_item(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                raw_content=r.get("raw_content", ""),
            )
            for r in response.get("results", [])
        ]
        return make_result(results, "tavily", answer=response.get("answer"))
    except Exception as exc:
        logger.exception("Tavily search failed")
        return make_result([], "tavily", notices=[str(exc)])


# ---------------------------------------------------------------------------
# Backend: DuckDuckGo
# ---------------------------------------------------------------------------


def search_duckduckgo(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(make_item(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    content=r.get("body", ""),
                ))
        return make_result(results, "duckduckgo")
    except Exception as exc:
        logger.exception("DuckDuckGo search failed")
        return make_result([], "duckduckgo", notices=[str(exc)])


# ---------------------------------------------------------------------------
# Backend: SearXNG
# ---------------------------------------------------------------------------


def search_searxng(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    try:
        base_url = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080")
        resp = requests.get(
            f"{base_url}/search",
            params={"q": query, "format": "json"},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            make_item(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
            )
            for r in data.get("results", [])[:max_results]
        ]
        return make_result(results, "searxng")
    except Exception as exc:
        logger.exception("SearXNG search failed")
        return make_result([], "searxng", notices=[str(exc)])


# ---------------------------------------------------------------------------
# Backend: Perplexity (now implemented!)
# ---------------------------------------------------------------------------


def search_perplexity(query: str, config: Configuration, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    """Search via Perplexity API (requires PERPLEXITY_API_KEY)."""
    try:
        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        if not api_key:
            return make_result([], "perplexity", notices=["PERPLEXITY_API_KEY not configured"])

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": "Search the web and return factual results with sources."},
                {"role": "user", "content": query},
            ],
            "max_tokens": 1024,
        }
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT * 2,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        # Perplexity returns answer text; extract any URLs
        import re
        urls = re.findall(r'https?://[^\s<>"]+', answer)
        results = [
            make_item(title=f"Source {i+1}", url=u, content="See full answer for context")
            for i, u in enumerate(urls[:max_results])
        ]
        if not results:
            results = [make_item(title="Perplexity Answer", url="", content=answer[:500])]
        return make_result(results, "perplexity", answer=answer)
    except Exception as exc:
        logger.exception("Perplexity search failed")
        return make_result([], "perplexity", notices=[str(exc)])


# ---------------------------------------------------------------------------
# Backend: Advanced (multi-source fusion)
# ---------------------------------------------------------------------------


def search_advanced(query: str, config: Configuration, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    """Try multiple backends and merge results (best-effort fusion)."""
    all_results: list[dict[str, Any]] = []
    all_notices: list[str] = []
    backends_used: list[str] = []
    seen_urls: set[str] = set()

    # Try DDG (free, reliable)
    ddg_result = search_duckduckgo(query, max_results=max_results)
    if ddg_result.get("results"):
        backends_used.append("duckduckgo")
        for r in ddg_result["results"]:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({**r, "source_backend": "duckduckgo"})
    all_notices.extend(ddg_result.get("notices", []))

    # Try SearXNG if available
    searxng_result = search_searxng(query, max_results=max_results)
    if searxng_result.get("results"):
        backends_used.append("searxng")
        for r in searxng_result["results"]:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({**r, "source_backend": "searxng"})

    if not all_results:
        return make_result([], "advanced", notices=["All backends failed"] + all_notices)

    return make_result(
        all_results[:max_results],
        f"advanced({','.join(backends_used)})",
        notices=all_notices,
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class SearchCache:
    """Simple in-memory TTL cache for search results."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def _key(self, query: str, backend: str, max_results: int) -> str:
        raw = f"{query}|{backend}|{max_results}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, query: str, backend: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any] | None:
        key = self._key(query, backend, max_results)
        entry = self._cache.get(key)
        if entry:
            ts, result = entry
            if time.time() - ts < self.ttl:
                logger.debug("Cache hit for %s/%s", backend, query[:50])
                return result
            del self._cache[key]
        return None

    def set(self, query: str, backend: str, result: dict[str, Any], max_results: int = DEFAULT_MAX_RESULTS) -> None:
        key = self._key(query, backend, max_results)
        self._cache[key] = (time.time(), result)

    def clear(self) -> None:
        self._cache.clear()


# Singleton
search_cache = SearchCache(ttl_seconds=int(os.getenv("SEARCH_CACHE_TTL", "300")))


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------


def search(
    query: str,
    config: Configuration,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    use_cache: bool = True,
    loop_count: int = 0,
) -> dict[str, Any]:
    """Unified search dispatch with caching and fallback."""
    search_api = _resolve_backend(config)

    # Check cache
    if use_cache:
        cached = search_cache.get(query, search_api, max_results)
        if cached:
            return cached

    # Dispatch
    if search_api == "tavily":
        result = search_tavily(query, config, max_results=max_results)
    elif search_api == "duckduckgo":
        result = search_duckduckgo(query, max_results=max_results)
    elif search_api == "searxng":
        result = search_searxng(query, max_results=max_results)
    elif search_api == "perplexity":
        result = search_perplexity(query, config, max_results=max_results)
    elif search_api == "advanced":
        result = search_advanced(query, config, max_results=max_results)
    else:
        logger.warning("Unknown backend '%s', falling back to DuckDuckGo", search_api)
        result = search_duckduckgo(query, max_results=max_results)

    # Cache successful results
    if use_cache and result.get("results"):
        search_cache.set(query, search_api, result, max_results)

    return result


def _resolve_backend(config: Configuration) -> str:
    search_api = getattr(config, "search_api", "duckduckgo")
    if hasattr(search_api, "value"):
        return search_api.value
    return str(search_api)
