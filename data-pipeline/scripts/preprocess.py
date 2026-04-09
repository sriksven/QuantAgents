"""
QuantAgents — Preprocess Raw Financial Data
Cleans price data, computes technical indicators and options metrics.
Input: data/prices/*.parquet, data/options/*.parquet
Output: data/processed/*.parquet
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
PRICES_DIR = DATA_DIR / "prices"
OPTIONS_DIR = DATA_DIR / "options"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ── Technical Indicators ──────────────────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    avg_vol = volume.rolling(period).mean()
    return volume / avg_vol.replace(0, np.nan)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to a price DataFrame."""
    df = df.sort_values("date").copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    df["rsi_14"] = compute_rsi(close, 14)
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(close)
    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()
    df["ema_9"] = close.ewm(span=9, adjust=False).mean()
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = compute_bollinger_bands(close)
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    df["atr_14"] = compute_atr(high, low, close)
    df["volume_ratio"] = compute_volume_ratio(volume)
    df["daily_return"] = close.pct_change(fill_method=None)
    df["volatility_20"] = df["daily_return"].rolling(20).std() * (252 ** 0.5)

    # Trend signals
    df["above_sma50"] = (close > df["sma_50"]).astype(int)
    df["above_sma200"] = (close > df["sma_200"]).astype(int)
    df["golden_cross"] = (
        (df["sma_50"] > df["sma_200"]) & (df["sma_50"].shift(1) <= df["sma_200"].shift(1))
    ).astype(int)
    df["death_cross"] = (
        (df["sma_50"] < df["sma_200"]) & (df["sma_50"].shift(1) >= df["sma_200"].shift(1))
    ).astype(int)

    return df


# ── Options Metrics ───────────────────────────────────────────────────────────

def compute_iv_rank(iv: pd.Series, lookback: int = 252) -> pd.Series:
    """IV rank: where current IV sits within its 1-year range (0-100)."""
    iv_min = iv.rolling(lookback).min()
    iv_max = iv.rolling(lookback).max()
    return ((iv - iv_min) / (iv_max - iv_min).replace(0, np.nan) * 100).clip(0, 100)


def compute_put_call_ratio(options_df: pd.DataFrame) -> float | None:
    """Compute put/call volume ratio."""
    if options_df is None or options_df.empty:
        return None
    calls = options_df[options_df["option_type"] == "call"]["volume"].sum()
    puts = options_df[options_df["option_type"] == "put"]["volume"].sum()
    return float(puts / calls) if calls > 0 else None


def compute_max_pain(options_df: pd.DataFrame) -> float | None:
    """
    Max pain: strike where option sellers lose the least.
    Computed by summing total dollar pain at each strike.
    """
    if options_df is None or options_df.empty or "strike" not in options_df.columns:
        return None
    strikes = options_df["strike"].dropna().unique()
    if len(strikes) == 0:
        return None

    pain_by_strike: dict[float, float] = {}
    for strike in strikes:
        total_pain = 0.0
        for _, row in options_df.iterrows():
            s = row.get("strike", 0)
            oi = row.get("openinterest", 0) or 0
            opt_type = row.get("option_type", "")
            if opt_type == "call" and strike > s:
                total_pain += (strike - s) * oi * 100
            elif opt_type == "put" and strike < s:
                total_pain += (s - strike) * oi * 100
        pain_by_strike[strike] = total_pain

    return min(pain_by_strike, key=pain_by_strike.get)  # type: ignore


def add_options_metrics(options_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-contract derived metrics on the options DataFrame."""
    if options_df is None or options_df.empty:
        return options_df

    df = options_df.copy()

    # IV rank (requires historical context — approximate with cross-sectional rank for now)
    if "impliedvolatility" in df.columns:
        df["iv_rank_approx"] = df.groupby("expiry")["impliedvolatility"].rank(pct=True) * 100

    # Unusual volume flag: volume > 3x open interest
    if "volume" in df.columns and "openinterest" in df.columns:
        df["unusual_volume"] = (
            df["volume"] > 3 * df["openinterest"].replace(0, np.nan)
        ).astype(int)

    # Moneyness proxy (using last price + strike)
    if "lastprice" in df.columns and "strike" in df.columns:
        df["otm_distance_pct"] = (df["strike"] - df["lastprice"]).abs() / df["lastprice"]

    return df


# ── Pipeline Entry Point ──────────────────────────────────────────────────────

def preprocess_ticker(ticker: str) -> bool:
    """Preprocess one ticker's prices and options data."""
    price_path = PRICES_DIR / f"{ticker}.parquet"
    options_path = OPTIONS_DIR / f"{ticker}.parquet"

    if not price_path.exists():
        logger.warning("No price data for %s", ticker)
        return False

    try:
        price_df = pd.read_parquet(price_path)
        price_df = add_indicators(price_df)

        # Merge options summary metrics
        options_df = None
        if options_path.exists():
            options_df = pd.read_parquet(options_path)
            options_df = add_options_metrics(options_df)
            # Store options alongside price data in separate sheet
            options_out = PROCESSED_DIR / f"{ticker}_options.parquet"
            options_df.to_parquet(options_out, index=False)

            # Add options aggregate stats to latest price row
            pc_ratio = compute_put_call_ratio(options_df)
            max_pain = compute_max_pain(options_df)
            price_df["put_call_ratio"] = pc_ratio
            price_df["max_pain"] = max_pain

        out_path = PROCESSED_DIR / f"{ticker}.parquet"
        price_df.to_parquet(out_path, index=False)
        logger.info("Preprocessed %s: %d rows, %d cols", ticker, len(price_df), len(price_df.columns))
        return True

    except Exception as exc:
        logger.error("Preprocessing failed for %s: %s", ticker, exc)
        return False


def preprocess_all(tickers: list[str] | None = None) -> dict[str, bool]:
    if tickers is None:
        tickers = [p.stem for p in PRICES_DIR.glob("*.parquet")]

    results: dict[str, bool] = {t: preprocess_ticker(t) for t in tickers}
    logger.info(
        "Preprocessing complete: %d/%d succeeded",
        sum(results.values()), len(results),
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = preprocess_all()
    print(f"Done. {sum(results.values())}/{len(results)} succeeded.")
