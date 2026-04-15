"""
QuantAgents — SEC EDGAR MCP Server
Exposes 2 tools: search_filings and get_company_facts.
Uses the free SEC EDGAR API (no key required).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("sec-edgar")

HEADERS = {"User-Agent": "QuantAgents research@quantagents.ai"}
BASE_SEARCH = "https://efts.sec.gov/LATEST/search-index"
BASE_FACTS = "https://data.sec.gov/api/xbrl/companyfacts"
RATE_LIMIT = 0.12  # 10 req/s max


def _get_cik(ticker: str) -> str | None:
    """Resolve ticker → zero-padded CIK."""
    url = f"{BASE_SEARCH}?q=%22{ticker.upper()}%22&forms=10-K"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        if hits:
            cik = hits[0].get("_source", {}).get("entity_id", "")
            return cik.zfill(10) if cik else None
    except Exception as exc:
        logger.warning("CIK lookup for %s: %s", ticker, exc)
    return None


# ── Tool 1: Search Filings ────────────────────────────────────────────────────


@mcp.tool()
def search_filings(
    ticker: str,
    form_types: str = "10-K,10-Q,8-K",
    days_back: int = 180,
) -> dict[str, Any]:
    """
    Search SEC EDGAR for recent filings for a company.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        form_types: Comma-separated list of form types (e.g., "10-K,10-Q,8-K")
        days_back: How many days back to search (default 180)

    Returns:
        Dict with company info and list of recent filings with accession numbers and dates
    """
    from datetime import datetime, timedelta

    cik = _get_cik(ticker)
    if not cik:
        return {"error": f"Could not find CIK for ticker: {ticker}", "ticker": ticker}

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)

    url = (
        f"{BASE_SEARCH}?"
        f"q=%22{ticker.upper()}%22"
        f"&forms={form_types}"
        f"&dateRange=custom"
        f"&startdt={start_date.strftime('%Y-%m-%d')}"
        f"&enddt={end_date.strftime('%Y-%m-%d')}"
        f"&_source=file_date,form_type,period_of_report,display_names,accession_no,entity_id"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        time.sleep(RATE_LIMIT)

        filings = []
        for hit in hits[:20]:
            src = hit.get("_source", {})
            filings.append(
                {
                    "form_type": src.get("form_type"),
                    "filing_date": src.get("file_date"),
                    "period_of_report": src.get("period_of_report"),
                    "accession_no": src.get("accession_no"),
                    "display_name": (src.get("display_names") or [""])[0],
                    "edgar_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={src.get('form_type', '')}&dateb=&owner=include&count=10",
                }
            )

        return {
            "ticker": ticker.upper(),
            "cik": cik,
            "total_found": len(hits),
            "filings": filings,
            "search_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        }
    except Exception as exc:
        logger.error("search_filings(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 2: Get Company Facts (XBRL) ─────────────────────────────────────────


@mcp.tool()
def get_company_facts(ticker: str) -> dict[str, Any]:
    """
    Get structured financial facts from SEC XBRL data (revenue, net income, EPS, etc.).

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with key financial metrics extracted from the latest annual and quarterly filings
    """
    cik = _get_cik(ticker)
    if not cik:
        return {"error": f"Could not find CIK for ticker: {ticker}", "ticker": ticker}

    url = f"{BASE_FACTS}/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            return {"error": f"No XBRL facts found for {ticker} (CIK {cik})", "ticker": ticker}
        resp.raise_for_status()
        time.sleep(RATE_LIMIT)

        facts = resp.json()
        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        KEY_CONCEPTS = {
            "revenue": [
                "Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet",
            ],
            "net_income": ["NetIncomeLoss"],
            "operating_income": ["OperatingIncomeLoss"],
            "eps_basic": ["EarningsPerShareBasic"],
            "eps_diluted": ["EarningsPerShareDiluted"],
            "total_assets": ["Assets"],
            "total_liabilities": ["Liabilities"],
            "stockholders_equity": ["StockholdersEquity"],
            "cash": ["CashAndCashEquivalentsAtCarryingValue"],
            "long_term_debt": ["LongTermDebt"],
            "shares_outstanding": ["CommonStockSharesOutstanding"],
            "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
            "free_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        }

        extracted: dict[str, Any] = {}
        for label, concepts in KEY_CONCEPTS.items():
            for concept in concepts:
                data = us_gaap.get(concept, {})
                units = data.get("units", {})
                for unit_key in ["USD", "USD/shares", "shares"]:
                    if unit_key in units:
                        entries = units[unit_key]
                        # Annual (10-K) — most recent 4 years
                        annual = sorted(
                            [e for e in entries if e.get("form") == "10-K"],
                            key=lambda x: x.get("end", ""),
                            reverse=True,
                        )[:4]
                        # Quarterly (10-Q) — most recent 4 quarters
                        quarterly = sorted(
                            [e for e in entries if e.get("form") == "10-Q"],
                            key=lambda x: x.get("end", ""),
                            reverse=True,
                        )[:4]
                        extracted[label] = {
                            "concept": concept,
                            "unit": unit_key,
                            "annual": [
                                {"period": e.get("end"), "value": e.get("val")} for e in annual
                            ],
                            "quarterly": [
                                {"period": e.get("end"), "value": e.get("val")} for e in quarterly
                            ],
                        }
                        break
                if label in extracted:
                    break

        entity_name = facts.get("entityName", "")
        return {
            "ticker": ticker.upper(),
            "cik": cik,
            "entity_name": entity_name,
            "financials": extracted,
        }
    except Exception as exc:
        logger.error("get_company_facts(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


if __name__ == "__main__":
    mcp.run()
