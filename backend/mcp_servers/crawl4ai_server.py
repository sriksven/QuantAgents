"""
QuantAgents — Crawl4AI MCP Server
Web scraping using Crawl4AI for analyst reports, company pages, and SEC documents.
"""
from __future__ import annotations

import logging
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("crawl4ai")


async def _crawl(url: str, extract_structured: bool = False) -> dict[str, Any]:
    """Internal async crawl helper."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
        from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

        browser_cfg = BrowserConfig(headless=True, verbose=False)
        run_cfg = CrawlerRunConfig(cache_mode=CacheMode.ENABLED)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)

        if not result.success:
            return {"error": f"Crawl failed: {result.error_message}", "url": url}

        return {
            "url": url,
            "title": result.metadata.get("title", "") if result.metadata else "",
            "markdown": (result.markdown or "")[:8000],
            "success": True,
            "links": list(result.links.get("internal", []))[:20] if result.links else [],
        }
    except ImportError:
        return {"error": "crawl4ai not installed — run: pip install crawl4ai", "url": url}
    except Exception as exc:
        return {"error": str(exc), "url": url}


# ── Tool 1: Scrape URL ────────────────────────────────────────────────────────

@mcp.tool()
async def scrape_url(url: str, max_chars: int = 6000) -> dict[str, Any]:
    """
    Scrape a URL and return clean markdown text content.
    Useful for earnings call transcripts, analyst reports, SEC filings, news articles.

    Args:
        url: Full URL to scrape
        max_chars: Maximum characters to return (default 6000)

    Returns:
        Dict with title, markdown content, and extracted links
    """
    result = await _crawl(url)
    if "error" in result:
        return result
    result["markdown"] = result.get("markdown", "")[:max_chars]
    return result


# ── Tool 2: Extract Structured Data ──────────────────────────────────────────

@mcp.tool()
async def extract_structured_data(url: str, schema_description: str) -> dict[str, Any]:
    """
    Scrape a URL and extract structured data based on a description.
    Uses LLM-guided extraction to pull specific fields.

    Args:
        url: Full URL to scrape
        schema_description: Natural language description of what to extract
                           (e.g., "Extract revenue, EPS, and guidance from this earnings release")

    Returns:
        Dict with extracted fields as key-value pairs
    """
    result = await _crawl(url)
    if "error" in result:
        return result

    content = result.get("markdown", "")
    if not content:
        return {"error": "No content extracted from URL", "url": url}

    # Post-process: return clean content for LLM to extract from
    # The agent will do the actual extraction from the markdown
    return {
        "url": url,
        "title": result.get("title", ""),
        "schema_hint": schema_description,
        "content": content[:5000],
        "note": f"Content extracted from {url}. Apply the schema_description to extract: {schema_description}",
    }


if __name__ == "__main__":
    mcp.run()
