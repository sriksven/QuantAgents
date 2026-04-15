"""
QuantAgents — Yahoo Finance MCP Server
Exposes 5 tools wrapping yfinance for stock quotes, financials,
key ratios, options chains, and sector peers.
"""

from __future__ import annotations

import logging
from typing import Any

import yfinance as yf
from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("yahoo-finance")


# ── Tool 1: Get Stock Quote ────────────────────────────────────────────────────


@mcp.tool()
def get_stock_quote(ticker: str) -> dict[str, Any]:
    """
    Get real-time stock quote including price, change, market cap, volume.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict with price, change_pct, volume, market_cap, pe_ratio, 52w_high, 52w_low
    """
    try:
        tk = yf.Ticker(ticker.upper())
        info = tk.info
        if not info or "regularMarketPrice" not in info:
            return {"error": f"No data found for ticker: {ticker}"}

        return {
            "ticker": ticker.upper(),
            "company_name": info.get("longName", ""),
            "price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "previous_close": info.get("regularMarketPreviousClose"),
            "change": info.get("regularMarketChange"),
            "change_pct": info.get("regularMarketChangePercent"),
            "volume": info.get("regularMarketVolume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "eps_ttm": info.get("trailingEps"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange"),
        }
    except Exception as exc:
        logger.error("get_stock_quote(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 2: Get Financial Statements ─────────────────────────────────────────


@mcp.tool()
def get_financials(ticker: str, period: str = "annual") -> dict[str, Any]:
    """
    Get income statement, balance sheet, and cash flow data.

    Args:
        ticker: Stock ticker symbol
        period: "annual" or "quarterly"

    Returns:
        Dict with income_statement, balance_sheet, cash_flow (last 4 periods)
    """
    try:
        tk = yf.Ticker(ticker.upper())

        def df_to_dict(df) -> dict:
            if df is None or df.empty:
                return {}
            # Return last 4 columns (most recent periods)
            df = df.iloc[:, :4]
            return {
                str(col.date()): {k: (None if v != v else float(v)) for k, v in vals.items()}
                for col, vals in df.items()
            }

        if period == "quarterly":
            income = tk.quarterly_income_stmt
            balance = tk.quarterly_balance_sheet
            cashflow = tk.quarterly_cashflow
        else:
            income = tk.income_stmt
            balance = tk.balance_sheet
            cashflow = tk.cashflow

        return {
            "ticker": ticker.upper(),
            "period": period,
            "income_statement": df_to_dict(income),
            "balance_sheet": df_to_dict(balance),
            "cash_flow": df_to_dict(cashflow),
        }
    except Exception as exc:
        logger.error("get_financials(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 3: Get Key Ratios ────────────────────────────────────────────────────


@mcp.tool()
def get_key_ratios(ticker: str) -> dict[str, Any]:
    """
    Get fundamental valuation and profitability ratios.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with P/E, P/B, P/S, ROE, ROA, margins, debt ratios, growth rates
    """
    try:
        tk = yf.Ticker(ticker.upper())
        info = tk.info

        return {
            "ticker": ticker.upper(),
            # Valuation
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales_ttm": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
            # Profitability
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "net_margin": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            # Growth
            "revenue_growth_yoy": info.get("revenueGrowth"),
            "earnings_growth_yoy": info.get("earningsGrowth"),
            "revenue_quarterly_growth": info.get("revenueQuarterlyGrowth"),
            # Financial health
            "current_ratio": info.get("currentRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            # Per share
            "book_value_per_share": info.get("bookValue"),
            "eps_ttm": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
        }
    except Exception as exc:
        logger.error("get_key_ratios(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 4: Get Options Chain ─────────────────────────────────────────────────


@mcp.tool()
def get_options_chain(ticker: str, expiry: str | None = None) -> dict[str, Any]:
    """
    Get options chain for a ticker. Returns calls and puts with greeks.

    Args:
        ticker: Stock ticker symbol
        expiry: Specific expiry date (YYYY-MM-DD). If None, returns nearest expiry.

    Returns:
        Dict with calls list, puts list, iv_rank, put_call_ratio
    """
    try:
        tk = yf.Ticker(ticker.upper())
        available_expiries = tk.options
        if not available_expiries:
            return {"error": f"No options data for {ticker}", "ticker": ticker}

        target_expiry = expiry if expiry in available_expiries else available_expiries[0]
        chain = tk.option_chain(target_expiry)

        def chain_to_list(df, opt_type: str) -> list[dict]:
            if df is None or df.empty:
                return []
            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "contractSymbol": row.get("contractSymbol", ""),
                        "strike": float(row.get("strike", 0)),
                        "lastPrice": float(row.get("lastPrice", 0) or 0),
                        "bid": float(row.get("bid", 0) or 0),
                        "ask": float(row.get("ask", 0) or 0),
                        "volume": int(row.get("volume", 0) or 0),
                        "openInterest": int(row.get("openInterest", 0) or 0),
                        "impliedVolatility": float(row.get("impliedVolatility", 0) or 0),
                        "delta": float(row.get("delta", 0) or 0) if "delta" in row else None,
                        "gamma": float(row.get("gamma", 0) or 0) if "gamma" in row else None,
                        "theta": float(row.get("theta", 0) or 0) if "theta" in row else None,
                        "vega": float(row.get("vega", 0) or 0) if "vega" in row else None,
                        "inTheMoney": bool(row.get("inTheMoney", False)),
                        "option_type": opt_type,
                        "expiry": target_expiry,
                    }
                )
            return records

        calls = chain_to_list(chain.calls, "call")
        puts = chain_to_list(chain.puts, "put")

        call_vol = sum(c["volume"] for c in calls)
        put_vol = sum(p["volume"] for p in puts)

        return {
            "ticker": ticker.upper(),
            "expiry": target_expiry,
            "available_expiries": list(available_expiries[:10]),
            "calls": calls,
            "puts": puts,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "put_call_ratio": round(put_vol / call_vol, 3) if call_vol > 0 else None,
        }
    except Exception as exc:
        logger.error("get_options_chain(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 5: Get Sector Peers ──────────────────────────────────────────────────


@mcp.tool()
def get_sector_peers(ticker: str) -> dict[str, Any]:
    """
    Get peer companies in the same sector/industry for competitive analysis.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with sector, industry, peers list with basic metrics
    """
    try:
        tk = yf.Ticker(ticker.upper())
        info = tk.info
        sector = info.get("sector", "")
        industry = info.get("industry", "")

        # Use recommendations as a proxy for related tickers
        try:
            recs = tk.recommendations
            peer_tickers = []
            if recs is not None and not recs.empty and "symbol" in recs.columns:
                peer_tickers = list(recs["symbol"].dropna().unique()[:8])
        except Exception:
            peer_tickers = []

        peers = []
        for peer in peer_tickers[:5]:
            try:
                peer_info = yf.Ticker(peer).info
                peers.append(
                    {
                        "ticker": peer,
                        "name": peer_info.get("longName", ""),
                        "market_cap": peer_info.get("marketCap"),
                        "pe_trailing": peer_info.get("trailingPE"),
                        "revenue_growth": peer_info.get("revenueGrowth"),
                        "profit_margin": peer_info.get("profitMargins"),
                    }
                )
            except Exception:
                pass

        return {
            "ticker": ticker.upper(),
            "sector": sector,
            "industry": industry,
            "peers": peers,
        }
    except Exception as exc:
        logger.error("get_sector_peers(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


if __name__ == "__main__":
    mcp.run()
