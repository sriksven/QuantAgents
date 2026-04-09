"""
QuantAgents — Fetch Daily Stock Prices
Fetches OHLCV data for a watchlist of tickers from yfinance.
Saves as Parquet files in data/prices/.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
PRICES_DIR = DATA_DIR / "prices"
PRICES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "365"))

# Default watchlist — override via TICKERS env var (comma-separated)
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG", "MA", "HD", "CVX",
    "ABBV", "BAC", "KO", "MRK", "PEP", "AVGO", "COST", "LLY", "TMO",
    "CSCO", "ACN", "MCD", "NKE", "DHR", "TXN", "NEE", "PM", "LIN",
    "ORCL", "AMD", "INTC", "QCOM",
]


def get_tickers() -> list[str]:
    env = os.getenv("TICKERS", "")
    return [t.strip().upper() for t in env.split(",") if t.strip()] or DEFAULT_TICKERS


def fetch_ticker(ticker: str, start: datetime, end: datetime) -> pd.DataFrame | None:
    """Fetch OHLCV for a single ticker. Returns None on failure."""
    try:
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,   # adjusts for splits and dividends
            progress=False,
        )
        if df.empty:
            logger.warning("No data for %s (may be weekend, holiday, or invalid ticker)", ticker)
            return None

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        df["ticker"] = ticker

        # Validate basic integrity
        if df[["open", "high", "low", "close"]].isnull().all().any():
            logger.warning("All-null OHLC for %s — skipping", ticker)
            return None

        # Ensure correct types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        logger.info("Fetched %d rows for %s", len(df), ticker)
        return df

    except Exception as exc:
        logger.error("Failed to fetch %s: %s", ticker, exc)
        return None


def save_ticker(ticker: str, df: pd.DataFrame) -> Path:
    """Save ticker data as Parquet."""
    out = PRICES_DIR / f"{ticker}.parquet"
    df.to_parquet(out, index=False, engine="pyarrow")
    return out


def fetch_all_prices(
    tickers: list[str] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, bool]:
    """
    Fetch prices for all tickers.
    Returns a dict of {ticker: success}.
    """
    tickers = tickers or get_tickers()
    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)

    results: dict[str, bool] = {}
    for ticker in tickers:
        df = fetch_ticker(ticker, start, end)
        if df is not None and not df.empty:
            save_ticker(ticker, df)
            results[ticker] = True
        else:
            results[ticker] = False

    success_count = sum(results.values())
    logger.info(
        "Price fetch complete: %d/%d tickers succeeded",
        success_count,
        len(tickers),
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = fetch_all_prices()
    failed = [t for t, ok in results.items() if not ok]
    if failed:
        logger.warning("Failed tickers: %s", failed)
    print(f"Done. {sum(results.values())}/{len(results)} succeeded.")
