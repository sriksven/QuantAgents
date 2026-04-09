"""
QuantAgents — Fetch Options Chains
Snapshots the current options chain for each ticker from yfinance.
Saves as Parquet in data/options/.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
OPTIONS_DIR = DATA_DIR / "options"
OPTIONS_DIR.mkdir(parents=True, exist_ok=True)

MAX_EXPIRY_DAYS = int(os.getenv("MAX_EXPIRY_DAYS", "90"))


def fetch_options_chain(ticker: str) -> pd.DataFrame | None:
    """
    Fetch all options for expiries within MAX_EXPIRY_DAYS.
    Returns a combined calls+puts DataFrame, or None on failure.
    """
    try:
        tk = yf.Ticker(ticker)
        expirations = tk.options
        if not expirations:
            logger.warning("No options data for %s", ticker)
            return None

        cutoff = datetime.utcnow() + timedelta(days=MAX_EXPIRY_DAYS)
        valid_expiries = [
            exp for exp in expirations
            if datetime.strptime(exp, "%Y-%m-%d") <= cutoff
        ]

        if not valid_expiries:
            logger.info("No expiries within %d days for %s", MAX_EXPIRY_DAYS, ticker)
            return None

        dfs: list[pd.DataFrame] = []
        for expiry in valid_expiries:
            try:
                chain = tk.option_chain(expiry)
                calls = chain.calls.copy()
                puts = chain.puts.copy()
                calls["option_type"] = "call"
                puts["option_type"] = "put"
                calls["expiry"] = expiry
                puts["expiry"] = expiry
                dfs.extend([calls, puts])
            except Exception as exc:
                logger.warning("Failed to get chain for %s exp=%s: %s", ticker, expiry, exc)

        if not dfs:
            return None

        df = pd.concat(dfs, ignore_index=True)
        df["ticker"] = ticker
        df["snapshot_date"] = datetime.utcnow().strftime("%Y-%m-%d")

        # Standardize column names
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

        # Filter out clearly bad data
        if "impliedvolatility" in df.columns:
            df = df[df["impliedvolatility"].between(0.0, 10.0, inclusive="both")]
        if "strike" in df.columns:
            df = df[df["strike"] > 0]

        logger.info(
            "Fetched %d option contracts for %s (%d expiries)",
            len(df), ticker, len(valid_expiries),
        )
        return df

    except Exception as exc:
        logger.error("Options fetch failed for %s: %s", ticker, exc)
        return None


def save_options(ticker: str, df: pd.DataFrame) -> Path:
    out = OPTIONS_DIR / f"{ticker}.parquet"
    df.to_parquet(out, index=False, engine="pyarrow")
    return out


def fetch_all_options(tickers: list[str] | None = None) -> dict[str, bool]:
    if tickers is None:
        from fetch_prices import get_tickers
        tickers = get_tickers()

    results: dict[str, bool] = {}
    for ticker in tickers:
        df = fetch_options_chain(ticker)
        if df is not None and not df.empty:
            save_options(ticker, df)
            results[ticker] = True
        else:
            results[ticker] = False

    logger.info(
        "Options fetch complete: %d/%d succeeded",
        sum(results.values()), len(results),
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from fetch_prices import get_tickers
    results = fetch_all_options(get_tickers()[:5])
    print(results)
