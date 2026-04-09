"""
QuantAgents — Fetch SEC EDGAR Filings
Fetches 10-K, 10-Q, and 8-K filings metadata for each ticker.
Uses the free SEC EDGAR full-text search API (no API key needed).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
FILINGS_DIR = DATA_DIR / "filings"
FILINGS_DIR.mkdir(parents=True, exist_ok=True)

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start}&enddt={end}&forms={form}"
EDGAR_COMPANY_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
EDGAR_CIK_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K&dateRange=custom&startdt=2020-01-01&enddt=2025-12-31"

HEADERS = {"User-Agent": "QuantAgents research@quantagents.ai"}
LOOKBACK_DAYS = int(os.getenv("FILINGS_LOOKBACK_DAYS", "90"))
RATE_LIMIT_DELAY = 0.15  # SEC EDGAR allows ~10 requests/second


def get_cik_for_ticker(ticker: str) -> str | None:
    """Look up CIK number for a ticker using EDGAR company search."""
    url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        if not hits:
            return None
        # Get CIK from first hit
        cik = hits[0].get("_source", {}).get("entity_id", "")
        if cik:
            return cik.zfill(10)
        return None
    except Exception as exc:
        logger.error("CIK lookup failed for %s: %s", ticker, exc)
        return None


def fetch_recent_filings(ticker: str, cik: str, form_types: list[str], days: int) -> list[dict]:
    """Fetch recent filings of given form types from EDGAR."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    filings = []

    url = (
        f"https://efts.sec.gov/LATEST/search-index?"
        f"q=%22{ticker}%22"
        f"&forms={','.join(form_types)}"
        f"&dateRange=custom"
        f"&startdt={start.strftime('%Y-%m-%d')}"
        f"&enddt={end.strftime('%Y-%m-%d')}"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        for hit in hits:
            src = hit.get("_source", {})
            filings.append({
                "ticker": ticker,
                "cik": cik,
                "form_type": src.get("form_type"),
                "filing_date": src.get("file_date"),
                "accession_no": src.get("accession_no"),
                "display_name": src.get("display_names", [None])[0],
                "period_of_report": src.get("period_of_report"),
                "fetched_at": datetime.utcnow().isoformat(),
            })
    except Exception as exc:
        logger.error("Filing fetch failed for %s: %s", ticker, exc)

    return filings


def fetch_company_facts(cik: str) -> dict | None:
    """Fetch structured financial facts (revenue, income, etc.) from EDGAR XBRL."""
    url = EDGAR_FACTS_URL.format(cik=cik)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        facts = resp.json()
        # Extract key financials
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        key_concepts = [
            "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
            "NetIncomeLoss", "OperatingIncomeLoss", "EarningsPerShareBasic",
            "Assets", "Liabilities", "StockholdersEquity",
            "CashAndCashEquivalentsAtCarryingValue",
            "LongTermDebt", "CommonStockSharesOutstanding",
        ]
        extracted: dict = {}
        for concept in key_concepts:
            data = us_gaap.get(concept, {})
            units = data.get("units", {})
            # Prefer USD units
            for unit_key in ["USD", "shares"]:
                if unit_key in units:
                    entries = units[unit_key]
                    # Get most recent 10-K value
                    annual = [e for e in entries if e.get("form") == "10-K"]
                    if annual:
                        annual.sort(key=lambda x: x.get("end", ""), reverse=True)
                        extracted[concept] = {
                            "value": annual[0].get("val"),
                            "period_end": annual[0].get("end"),
                            "unit": unit_key,
                        }
                    break
        return extracted
    except Exception as exc:
        logger.error("Company facts fetch failed for CIK %s: %s", cik, exc)
        return None


def fetch_all_filings(tickers: list[str] | None = None) -> dict[str, bool]:
    """Fetch filings for all tickers."""
    if tickers is None:
        from fetch_prices import get_tickers
        tickers = get_tickers()

    results: dict[str, bool] = {}
    for ticker in tickers:
        try:
            cik = get_cik_for_ticker(ticker)
            if not cik:
                logger.warning("No CIK found for %s — skipping", ticker)
                results[ticker] = False
                time.sleep(RATE_LIMIT_DELAY)
                continue

            filings = fetch_recent_filings(ticker, cik, ["10-K", "10-Q", "8-K"], LOOKBACK_DAYS)
            facts = fetch_company_facts(cik)

            output = {
                "ticker": ticker,
                "cik": cik,
                "filings": filings,
                "key_financials": facts,
                "fetched_at": datetime.utcnow().isoformat(),
            }
            out_path = FILINGS_DIR / f"{ticker}.json"
            out_path.write_text(json.dumps(output, indent=2))
            logger.info("Saved %d filings for %s", len(filings), ticker)
            results[ticker] = True

        except Exception as exc:
            logger.error("Failed filing fetch for %s: %s", ticker, exc)
            results[ticker] = False

        time.sleep(RATE_LIMIT_DELAY)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from fetch_prices import get_tickers
    results = fetch_all_filings(get_tickers()[:5])  # first 5 for quick test
    print(results)
