"""
QuantAgents — Tavily News MCP Server
Exposes 2 tools powered by the Tavily search API.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("tavily-news")


def _get_client():
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable not set")
    from tavily import TavilyClient

    return TavilyClient(api_key=api_key)


# ── Tool 1: Search News ───────────────────────────────────────────────────────


@mcp.tool()
def search_news(
    query: str,
    max_results: int = 10,
    days_back: int = 7,
    include_domains: str = "",
    exclude_domains: str = "",
) -> dict[str, Any]:
    """
    Search for recent news articles using Tavily.

    Args:
        query: Natural language search query (e.g., "Apple iPhone sales Q4 2024")
        max_results: Number of results to return (max 20)
        days_back: How many days back to search
        include_domains: Comma-separated domains to prioritize (e.g., "reuters.com,bloomberg.com")
        exclude_domains: Comma-separated domains to exclude

    Returns:
        Dict with articles list (title, url, content snippet, published_date, relevance_score)
    """
    try:
        client = _get_client()

        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": min(max_results, 20),
            "search_depth": "basic",
            "include_answer": True,
            "topic": "news",
        }
        if include_domains:
            kwargs["include_domains"] = [d.strip() for d in include_domains.split(",")]
        if exclude_domains:
            kwargs["exclude_domains"] = [d.strip() for d in exclude_domains.split(",")]

        result = client.search(**kwargs)

        articles = []
        seen_urls: set[str] = set()
        for item in result.get("results", []):
            url = item.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            articles.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "content": item.get("content", "")[:800],
                    "published_date": item.get("published_date", ""),
                    "relevance_score": round(float(item.get("score", 0)), 3),
                    "source": url.split("/")[2] if "/" in url else url,
                }
            )

        return {
            "query": query,
            "answer_summary": result.get("answer", ""),
            "article_count": len(articles),
            "articles": articles,
        }
    except Exception as exc:
        logger.error("search_news(%s) failed: %s", query, exc)
        return {"error": str(exc), "query": query, "articles": []}


# ── Tool 2: Get Article Content ───────────────────────────────────────────────


@mcp.tool()
def get_article_content(url: str) -> dict[str, Any]:
    """
    Fetch and extract the full content of a specific article URL.

    Args:
        url: Full URL of the article to extract

    Returns:
        Dict with title, full content text, and metadata
    """
    try:
        client = _get_client()
        result = client.extract(urls=[url])

        results = result.get("results", [])
        if not results:
            return {"error": f"Could not extract content from: {url}", "url": url}

        item = results[0]
        return {
            "url": url,
            "title": item.get("title", ""),
            "content": item.get("raw_content", "")[:5000],  # truncate to 5k chars
            "metadata": {
                "author": item.get("author", ""),
                "published_date": item.get("published_date", ""),
                "source": url.split("/")[2] if "/" in url else "",
            },
        }
    except Exception as exc:
        logger.error("get_article_content(%s) failed: %s", url, exc)
        return {"error": str(exc), "url": url}


if __name__ == "__main__":
    mcp.run()
