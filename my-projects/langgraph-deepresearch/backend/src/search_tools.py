"""Search backend wrappers (replaces hello-agents SearchTool).

Supports Tavily, DuckDuckGo, and extensible backends.
Returns a normalised dict with ``results``, ``backend``, ``answer``, ``notices``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from config import Configuration

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


def search(
    query: str,
    config: Configuration,
    loop_count: int = 0,  # kept for interface compatibility
) -> dict[str, Any]:
    """Execute search using the configured backend.

    Returns a dict matching the hello-agents SearchTool output shape.
    """
    search_api = _resolve_backend(config)

    if search_api == "tavily":
        return _search_tavily(query, config)
    if search_api == "duckduckgo":
        return _search_duckduckgo(query)
    if search_api == "searxng":
        return _search_searxng(query, config)

    logger.warning("Unknown search backend '%s', falling back to duckduckgo", search_api)
    return _search_duckduckgo(query)


# ------------------------------------------------------------------
# Backend implementations
# ------------------------------------------------------------------

def _search_tavily(query: str, config: Configuration) -> dict[str, Any]:
    try:
        from tavily import TavilyClient

        api_key = os.getenv("TAVILY_API_KEY", "")
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="advanced" if config.fetch_full_page else "basic",
            max_results=MAX_RESULTS,
        )
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "raw_content": r.get("raw_content", ""),
            }
            for r in response.get("results", [])
        ]
        return {
            "results": results,
            "backend": "tavily",
            "answer": response.get("answer"),
            "notices": [],
        }
    except Exception as exc:
        logger.exception("Tavily search failed")
        return {"results": [], "backend": "tavily", "answer": None, "notices": [str(exc)]}


def _search_duckduckgo(query: str) -> dict[str, Any]:
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=MAX_RESULTS):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", ""),
                    "raw_content": "",
                })
        return {
            "results": results,
            "backend": "duckduckgo",
            "answer": None,
            "notices": [],
        }
    except Exception as exc:
        logger.exception("DuckDuckGo search failed")
        return {"results": [], "backend": "duckduckgo", "answer": None, "notices": [str(exc)]}


def _search_searxng(query: str, config: Configuration) -> dict[str, Any]:
    try:
        import requests

        base_url = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080")
        resp = requests.get(
            f"{base_url}/search",
            params={"q": query, "format": "json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "raw_content": "",
            }
            for r in data.get("results", [])[:MAX_RESULTS]
        ]
        return {
            "results": results,
            "backend": "searxng",
            "answer": None,
            "notices": [],
        }
    except Exception as exc:
        logger.exception("SearXNG search failed")
        return {"results": [], "backend": "searxng", "answer": None, "notices": [str(exc)]}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resolve_backend(config: Configuration) -> str:
    """Extract plain string backend from config."""
    search_api = config.search_api
    if hasattr(search_api, "value"):
        return search_api.value
    return str(search_api)
