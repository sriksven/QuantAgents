"""
QuantAgents — Fetch News via Tavily
Searches for recent news for each ticker.
Saves structured JSON in data/news/.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
NEWS_DIR = DATA_DIR / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)

MAX_RESULTS_PER_TICKER = int(os.getenv("NEWS_MAX_RESULTS", "10"))


def fetch_news_for_ticker(ticker: str, client) -> list[dict]:
    """
    Search for recent news for a ticker using Tavily.
    Returns a list of article dicts.
    """
    queries = [
        f"{ticker} stock news",
        f"{ticker} earnings revenue analyst",
    ]
    articles: list[dict] = []
    seen_urls: set[str] = set()

    for query in queries:
        try:
            result = client.search(
                query=query,
                max_results=MAX_RESULTS_PER_TICKER,
                search_depth="basic",
                include_answer=False,
            )
            for item in result.get("results", []):
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    articles.append({
                        "title": item.get("title", ""),
                        "url": url,
                        "content": item.get("content", "")[:1000],  # truncate for storage
                        "score": item.get("score", 0),
                        "published_date": item.get("published_date", ""),
                        "query": query,
                    })
        except Exception as exc:
            logger.warning("Tavily search failed for query '%s': %s", query, exc)

    return articles


def fetch_all_news(tickers: list[str] | None = None) -> dict[str, bool]:
    """Fetch news for all tickers."""
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_key:
        logger.error("TAVILY_API_KEY not set — skipping news fetch")
        return {}

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
    except ImportError:
        logger.error("tavily-python not installed")
        return {}

    if tickers is None:
        from fetch_prices import get_tickers
        tickers = get_tickers()

    results: dict[str, bool] = {}
    for ticker in tickers:
        try:
            articles = fetch_news_for_ticker(ticker, client)
            output = {
                "ticker": ticker,
                "articles": articles,
                "article_count": len(articles),
                "fetched_at": datetime.utcnow().isoformat(),
            }
            out_path = NEWS_DIR / f"{ticker}.json"
            out_path.write_text(json.dumps(output, indent=2))
            logger.info("Saved %d articles for %s", len(articles), ticker)
            results[ticker] = True
        except Exception as exc:
            logger.error("News fetch failed for %s: %s", ticker, exc)
            results[ticker] = False

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from fetch_prices import get_tickers
    results = fetch_all_news(get_tickers()[:3])
    print(results)
