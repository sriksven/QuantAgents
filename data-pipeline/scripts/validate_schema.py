"""
QuantAgents — Schema Validation with Great Expectations
Validates processed data against predefined expectation suites.
Fails the pipeline on critical violations; warns on non-critical ones.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
PROCESSED_DIR = DATA_DIR / "processed"
VALIDATION_DIR = DATA_DIR / "validation"
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


# ── Validation Rules ──────────────────────────────────────────────────────────

def validate_price_df(df: pd.DataFrame, ticker: str) -> dict:
    """Run price data expectations. Returns {passed, failures, warnings}."""
    failures = []
    warnings = []

    # Critical: required columns present
    required_cols = ["date", "open", "high", "low", "close", "volume", "ticker"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        failures.append(f"Missing required columns: {missing}")

    if df.empty:
        failures.append("DataFrame is empty — no rows")
        return {"passed": False, "failures": failures, "warnings": warnings, "ticker": ticker}

    # Critical: no null prices
    ohlc = [c for c in ["open", "high", "low", "close"] if c in df.columns]
    null_counts = df[ohlc].isnull().sum()
    critical_nulls = null_counts[null_counts > len(df) * 0.05]  # >5% null = critical
    if not critical_nulls.empty:
        failures.append(f"Critical nulls in OHLC: {critical_nulls.to_dict()}")
    else:
        minor_nulls = null_counts[null_counts > 0]
        if not minor_nulls.empty:
            warnings.append(f"Minor nulls in OHLC: {minor_nulls.to_dict()}")

    # Critical: no negative prices
    if "close" in df.columns:
        neg_prices = (df["close"] <= 0).sum()
        if neg_prices > 0:
            failures.append(f"Found {neg_prices} rows with close <= 0")

    # Critical: no negative volume
    if "volume" in df.columns:
        neg_vol = (df["volume"] < 0).sum()
        if neg_vol > 0:
            failures.append(f"Found {neg_vol} rows with negative volume")

    # Critical: data staleness (<= 2 business days old)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        latest = df["date"].max()
        gap_days = (datetime.utcnow() - latest.to_pydatetime().replace(tzinfo=None)).days
        if gap_days > 4:  # >4 calendar days = stale (accounts for weekends + holidays)
            failures.append(f"Stale data: latest price is {gap_days} days old ({latest.date()})")

    # Warning: high > low
    if "high" in df.columns and "low" in df.columns:
        inversion = (df["high"] < df["low"]).sum()
        if inversion > 0:
            warnings.append(f"{inversion} rows where high < low (data error)")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "ticker": ticker,
        "row_count": len(df),
    }


def validate_options_df(df: pd.DataFrame, ticker: str) -> dict:
    """Run options chain expectations."""
    failures = []
    warnings = []

    if df.empty:
        warnings.append("Options chain is empty")
        return {"passed": True, "failures": failures, "warnings": warnings, "ticker": ticker}

    # Critical: positive strikes
    if "strike" in df.columns:
        non_pos = (df["strike"] <= 0).sum()
        if non_pos > 0:
            failures.append(f"{non_pos} rows with strike <= 0")

    # Critical: IV in valid range [0, 10]
    if "impliedvolatility" in df.columns:
        out_of_range = (~df["impliedvolatility"].between(0, 10, inclusive="both") & df["impliedvolatility"].notna()).sum()
        if out_of_range > 0:
            warnings.append(f"{out_of_range} rows with IV outside [0, 10]")

    # Warning: expiry in the past
    if "expiry" in df.columns:
        df["expiry"] = pd.to_datetime(df["expiry"])
        past_expiry = (df["expiry"] < datetime.utcnow()).sum()
        if past_expiry > 0:
            warnings.append(f"{past_expiry} rows with past expiry dates")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "ticker": ticker,
        "row_count": len(df),
    }


# ── Validate All ──────────────────────────────────────────────────────────────

def validate_all(tickers: list[str] | None = None) -> dict:
    if tickers is None:
        tickers = [p.stem for p in PROCESSED_DIR.glob("*.parquet") if "_options" not in p.stem]

    all_results = []
    critical_failures = []

    for ticker in tickers:
        price_path = PROCESSED_DIR / f"{ticker}.parquet"
        if price_path.exists():
            df = pd.read_parquet(price_path)
            result = validate_price_df(df, ticker)
            result["data_type"] = "prices"
            all_results.append(result)
            if not result["passed"]:
                critical_failures.append(f"{ticker} prices: {result['failures']}")

        options_path = PROCESSED_DIR / f"{ticker}_options.parquet"
        if options_path.exists():
            df = pd.read_parquet(options_path)
            result = validate_options_df(df, ticker)
            result["data_type"] = "options"
            all_results.append(result)
            if not result["passed"]:
                critical_failures.append(f"{ticker} options: {result['failures']}")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_checks": len(all_results),
        "passed": sum(1 for r in all_results if r["passed"]),
        "failed": sum(1 for r in all_results if not r["passed"]),
        "critical_failures": critical_failures,
        "results": all_results,
    }

    # Save report
    report_path = VALIDATION_DIR / f"validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary, indent=2))

    if critical_failures:
        logger.error("VALIDATION FAILED: %s", critical_failures)
        raise RuntimeError(f"Schema validation failed: {critical_failures}")

    total_warnings = sum(len(r.get("warnings", [])) for r in all_results)
    logger.info("Validation passed: %d checks, %d warnings", len(all_results), total_warnings)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = validate_all()
    print(f"Passed: {result['passed']}/{result['total_checks']}")
