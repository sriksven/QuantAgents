"""
QuantAgents — Alpha Vantage MCP Server
Exposes 4 tools: technical indicators (SMA, EMA, RSI, MACD),
economic indicators, historical OHLCV, and earnings data.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests
from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("alpha-vantage")

BASE_URL = "https://www.alphavantage.co/query"
RATE_LIMIT = 0.25  # free tier ≤ 5 req/min; premium: 75 req/min


def _av_get(params: dict) -> dict[str, Any]:
    """Make a rate-limited Alpha Vantage request."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        return {"error": "ALPHA_VANTAGE_API_KEY environment variable not set"}
    params["apikey"] = api_key
    try:
        resp = requests.get(BASE_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if "Error Message" in data:
            return {"error": data["Error Message"]}
        if "Note" in data:
            return {"error": "Alpha Vantage rate limit reached. Retry shortly.", "note": data["Note"]}
        return data
    except Exception as exc:
        return {"error": str(exc)}


# ── Tool 1: Get Technical Indicators ─────────────────────────────────────────

@mcp.tool()
def get_technical_indicators(
    ticker: str,
    indicators: str = "RSI,MACD,SMA20,SMA50,EMA9,BBANDS",
    interval: str = "daily",
) -> dict[str, Any]:
    """
    Fetch technical indicators for a stock from Alpha Vantage.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        indicators: Comma-separated list of indicators. Options: RSI, MACD, SMA20, SMA50, SMA200, EMA9, EMA21, BBANDS, ADX, STOCH
        interval: "daily", "weekly", or "monthly"

    Returns:
        Dict with each requested indicator's latest values and signal
    """
    results: dict[str, Any] = {"ticker": ticker.upper(), "interval": interval, "indicators": {}}
    requested = [i.strip().upper() for i in indicators.split(",")]

    for indicator in requested:
        time.sleep(RATE_LIMIT)
        try:
            if indicator == "RSI":
                data = _av_get({"function": "RSI", "symbol": ticker, "interval": interval, "time_period": 14, "series_type": "close"})
                series = data.get("Technical Analysis: RSI", {})
                if series:
                    latest_date = max(series.keys())
                    rsi_val = float(series[latest_date]["RSI"])
                    results["indicators"]["RSI"] = {
                        "value": rsi_val,
                        "date": latest_date,
                        "signal": "overbought" if rsi_val > 70 else "oversold" if rsi_val < 30 else "neutral",
                    }
            elif indicator == "MACD":
                data = _av_get({"function": "MACD", "symbol": ticker, "interval": interval, "series_type": "close"})
                series = data.get("Technical Analysis: MACD", {})
                if series:
                    latest_date = max(series.keys())
                    row = series[latest_date]
                    macd = float(row["MACD"])
                    signal = float(row["MACD_Signal"])
                    hist = float(row["MACD_Hist"])
                    results["indicators"]["MACD"] = {
                        "macd": macd,
                        "signal": signal,
                        "histogram": hist,
                        "date": latest_date,
                        "crossover": "bullish" if macd > signal else "bearish",
                    }
            elif indicator.startswith("SMA"):
                period = int(indicator[3:]) if len(indicator) > 3 else 20
                data = _av_get({"function": "SMA", "symbol": ticker, "interval": interval, "time_period": period, "series_type": "close"})
                series = data.get(f"Technical Analysis: SMA", {})
                if series:
                    latest_date = max(series.keys())
                    results["indicators"][indicator] = {
                        "value": float(series[latest_date]["SMA"]),
                        "date": latest_date,
                    }
            elif indicator.startswith("EMA"):
                period = int(indicator[3:]) if len(indicator) > 3 else 9
                data = _av_get({"function": "EMA", "symbol": ticker, "interval": interval, "time_period": period, "series_type": "close"})
                series = data.get("Technical Analysis: EMA", {})
                if series:
                    latest_date = max(series.keys())
                    results["indicators"][indicator] = {
                        "value": float(series[latest_date]["EMA"]),
                        "date": latest_date,
                    }
            elif indicator == "BBANDS":
                data = _av_get({"function": "BBANDS", "symbol": ticker, "interval": interval, "time_period": 20, "series_type": "close"})
                series = data.get("Technical Analysis: BBANDS", {})
                if series:
                    latest_date = max(series.keys())
                    row = series[latest_date]
                    results["indicators"]["BBANDS"] = {
                        "upper": float(row["Real Upper Band"]),
                        "middle": float(row["Real Middle Band"]),
                        "lower": float(row["Real Lower Band"]),
                        "date": latest_date,
                    }
            elif indicator == "ADX":
                data = _av_get({"function": "ADX", "symbol": ticker, "interval": interval, "time_period": 14})
                series = data.get("Technical Analysis: ADX", {})
                if series:
                    latest_date = max(series.keys())
                    adx = float(series[latest_date]["ADX"])
                    results["indicators"]["ADX"] = {
                        "value": adx,
                        "date": latest_date,
                        "trend_strength": "strong" if adx > 25 else "weak",
                    }
        except Exception as exc:
            results["indicators"][indicator] = {"error": str(exc)}

    return results


# ── Tool 2: Get Historical OHLCV ─────────────────────────────────────────────

@mcp.tool()
def get_historical_ohlcv(
    ticker: str,
    outputsize: str = "compact",
    interval: str = "daily",
) -> dict[str, Any]:
    """
    Get historical OHLCV data for a ticker.

    Args:
        ticker: Stock ticker symbol
        outputsize: "compact" (100 data points) or "full" (20+ years)
        interval: "daily", "weekly", or "monthly"

    Returns:
        Dict with list of OHLCV records sorted newest-first
    """
    func_map = {"daily": "TIME_SERIES_DAILY", "weekly": "TIME_SERIES_WEEKLY", "monthly": "TIME_SERIES_MONTHLY"}
    key_map = {"daily": "Time Series (Daily)", "weekly": "Weekly Time Series", "monthly": "Monthly Time Series"}

    data = _av_get({
        "function": func_map.get(interval, "TIME_SERIES_DAILY"),
        "symbol": ticker.upper(),
        "outputsize": outputsize,
    })

    if "error" in data:
        return data

    series = data.get(key_map.get(interval, "Time Series (Daily)"), {})
    records = []
    for date_str, row in sorted(series.items(), reverse=True)[:60]:
        records.append({
            "date": date_str,
            "open": float(row.get("1. open", 0)),
            "high": float(row.get("2. high", 0)),
            "low": float(row.get("3. low", 0)),
            "close": float(row.get("4. close", 0)),
            "volume": int(row.get("5. volume", 0)),
        })

    return {"ticker": ticker.upper(), "interval": interval, "records": records, "count": len(records)}


# ── Tool 3: Get Economic Indicators ──────────────────────────────────────────

@mcp.tool()
def get_economic_indicators(indicators: str = "CPI,FEDFUNDS,UNEMPLOYMENT,T10Y2Y") -> dict[str, Any]:
    """
    Get macro economic indicators from Alpha Vantage.

    Args:
        indicators: Comma-separated list. Options: CPI, FEDFUNDS, UNEMPLOYMENT, T10Y2Y, REAL_GDP, INFLATION, RETAIL_SALES, NONFARM_PAYROLL

    Returns:
        Dict with each indicator's latest value and trend
    """
    func_map = {
        "CPI": "CPI", "FEDFUNDS": "FEDERAL_FUNDS_RATE",
        "UNEMPLOYMENT": "UNEMPLOYMENT", "T10Y2Y": "TREASURY_YIELD",
        "REAL_GDP": "REAL_GDP", "INFLATION": "INFLATION",
        "RETAIL_SALES": "RETAIL_SALES", "NONFARM_PAYROLL": "NONFARM_PAYROLL",
    }
    results: dict[str, Any] = {}
    for ind in [i.strip().upper() for i in indicators.split(",")]:
        func = func_map.get(ind)
        if not func:
            results[ind] = {"error": f"Unknown indicator: {ind}"}
            continue
        time.sleep(RATE_LIMIT)
        kwargs: dict[str, Any] = {"function": func}
        if ind == "T10Y2Y":
            kwargs["maturity"] = "10year"
        data = _av_get(kwargs)
        series = data.get("data", [])
        if series:
            latest = series[0]
            prev = series[1] if len(series) > 1 else latest
            try:
                curr_val = float(latest.get("value", 0))
                prev_val = float(prev.get("value", 0))
                trend = "rising" if curr_val > prev_val else "falling" if curr_val < prev_val else "flat"
            except (ValueError, TypeError):
                curr_val, trend = None, "unknown"
            results[ind] = {"value": curr_val, "date": latest.get("date"), "trend": trend}
        else:
            results[ind] = data.get("error", {"error": "No data"})

    return {"economic_indicators": results}


# ── Tool 4: Get Earnings Data ─────────────────────────────────────────────────

@mcp.tool()
def get_earnings_data(ticker: str) -> dict[str, Any]:
    """
    Get historical and upcoming earnings data including EPS surprises.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with annual earnings, quarterly earnings (last 8), and EPS beat/miss history
    """
    data = _av_get({"function": "EARNINGS", "symbol": ticker.upper()})
    if "error" in data:
        return data

    annual = data.get("annualEarnings", [])[:4]
    quarterly = data.get("quarterlyEarnings", [])[:8]

    # Compute beat/miss record
    beat_count = miss_count = 0
    for q in quarterly:
        try:
            reported = float(q.get("reportedEPS", 0) or 0)
            estimated = float(q.get("estimatedEPS", 0) or 0)
            surprise = float(q.get("surprisePercentage", 0) or 0)
            if surprise > 0:
                beat_count += 1
            elif surprise < 0:
                miss_count += 1
        except (ValueError, TypeError):
            pass

    return {
        "ticker": ticker.upper(),
        "annual_earnings": annual,
        "quarterly_earnings": quarterly,
        "beat_miss_record": {
            "beats": beat_count,
            "misses": miss_count,
            "total": len(quarterly),
            "beat_rate": round(beat_count / len(quarterly), 2) if quarterly else None,
        },
    }


if __name__ == "__main__":
    mcp.run()
