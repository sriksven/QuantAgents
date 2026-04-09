"""
QuantAgents — Anomaly Detection
Flags statistical anomalies in price and options data.
Does NOT fail the pipeline — produces a report and sends alerts on critical anomalies.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
PROCESSED_DIR = DATA_DIR / "processed"
ANOMALY_DIR = DATA_DIR / "anomalies"
ANOMALY_DIR.mkdir(parents=True, exist_ok=True)

PRICE_STD_THRESHOLD = float(os.getenv("PRICE_STD_THRESHOLD", "3.0"))  # >3σ daily move
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "5.0"))  # 5x avg volume
MAX_IV_THRESHOLD = float(os.getenv("MAX_IV_THRESHOLD", "5.0"))  # IV > 500%


def detect_price_anomalies(df: pd.DataFrame, ticker: str) -> list[dict]:
    """Detect price and volume anomalies."""
    anomalies = []
    if df.empty or "close" not in df.columns:
        return anomalies

    df = df.sort_values("date").copy()
    df["daily_return"] = df["close"].pct_change()

    # Price anomaly: >N standard deviation daily move
    mean_ret = df["daily_return"].mean()
    std_ret = df["daily_return"].std()
    if std_ret > 0:
        z_scores = (df["daily_return"] - mean_ret) / std_ret
        extreme_moves = df[z_scores.abs() > PRICE_STD_THRESHOLD]
        for _, row in extreme_moves.iterrows():
            anomalies.append({
                "ticker": ticker,
                "type": "price_extreme_move",
                "severity": "warning",
                "date": str(row.get("date", "")),
                "value": round(float(row["daily_return"]) * 100, 2),
                "message": f"{ticker} moved {row['daily_return']*100:.1f}% on {row.get('date', 'N/A')} (>{PRICE_STD_THRESHOLD}σ)",
            })

    # Volume anomaly: >N× 20-day avg
    if "volume" in df.columns:
        avg_vol = df["volume"].rolling(20).mean()
        spikes = df[(df["volume"] > VOLUME_SPIKE_MULTIPLIER * avg_vol) & avg_vol.notna()]
        for _, row in spikes.iterrows():
            anomalies.append({
                "ticker": ticker,
                "type": "volume_spike",
                "severity": "info",
                "date": str(row.get("date", "")),
                "value": round(float(row["volume"]), 0),
                "message": f"{ticker} volume spike on {row.get('date', 'N/A')}: {row['volume']:,.0f} ({VOLUME_SPIKE_MULTIPLIER}× avg)",
            })

    # Staleness check: latest date too old
    if "date" in df.columns:
        latest = pd.to_datetime(df["date"]).max()
        gap = (pd.Timestamp.utcnow().replace(tzinfo=None) - latest.replace(tzinfo=None)).days
        if gap > 4:
            anomalies.append({
                "ticker": ticker,
                "type": "data_staleness",
                "severity": "critical",
                "date": str(latest.date()),
                "value": gap,
                "message": f"{ticker} data is {gap} days old — possible fetch failure",
            })

    return anomalies


def detect_options_anomalies(df: pd.DataFrame, ticker: str) -> list[dict]:
    """Detect options data anomalies."""
    anomalies = []
    if df.empty:
        return anomalies

    # IV > MAX_IV_THRESHOLD (data error)
    if "impliedvolatility" in df.columns:
        bad_iv = df[df["impliedvolatility"] > MAX_IV_THRESHOLD]
        if not bad_iv.empty:
            anomalies.append({
                "ticker": ticker,
                "type": "iv_data_error",
                "severity": "warning",
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "value": int(len(bad_iv)),
                "message": f"{ticker} has {len(bad_iv)} option rows with IV > {MAX_IV_THRESHOLD*100:.0f}% (possible data error)",
            })

    # Negative greeks
    for greek in ["delta", "gamma", "vega", "theta"]:
        if greek in df.columns:
            # Theta should be negative, delta range -1 to 1
            if greek == "delta":
                bad = df[(df["delta"] < -1) | (df["delta"] > 1)]
            elif greek == "gamma":
                bad = df[df["gamma"] < 0]
            elif greek == "vega":
                bad = df[df["vega"] < 0]
            else:
                continue
            if not bad.empty:
                anomalies.append({
                    "ticker": ticker,
                    "type": f"invalid_{greek}",
                    "severity": "warning",
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "value": int(len(bad)),
                    "message": f"{ticker} has {len(bad)} rows with invalid {greek}",
                })

    return anomalies


def detect_all_anomalies(tickers: list[str] | None = None) -> dict:
    if tickers is None:
        tickers = [p.stem for p in PROCESSED_DIR.glob("*.parquet") if "_options" not in p.stem]

    all_anomalies: list[dict] = []

    for ticker in tickers:
        price_path = PROCESSED_DIR / f"{ticker}.parquet"
        if price_path.exists():
            df = pd.read_parquet(price_path)
            all_anomalies.extend(detect_price_anomalies(df, ticker))

        opts_path = PROCESSED_DIR / f"{ticker}_options.parquet"
        if opts_path.exists():
            df = pd.read_parquet(opts_path)
            all_anomalies.extend(detect_options_anomalies(df, ticker))

    critical = [a for a in all_anomalies if a["severity"] == "critical"]
    warnings = [a for a in all_anomalies if a["severity"] == "warning"]
    info = [a for a in all_anomalies if a["severity"] == "info"]

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_anomalies": len(all_anomalies),
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "info_count": len(info),
        "anomalies": all_anomalies,
    }

    # Save report
    out_path = ANOMALY_DIR / f"anomalies_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2))

    if critical:
        logger.error("CRITICAL ANOMALIES DETECTED: %s", [a["message"] for a in critical])
        alert_via_slack(critical)
    if warnings:
        logger.warning("Warnings: %d anomalies", len(warnings))

    logger.info(
        "Anomaly detection complete: %d critical, %d warnings, %d info",
        len(critical), len(warnings), len(info),
    )
    return report


def alert_via_slack(anomalies: list[dict]) -> None:
    """Send Slack alert for critical anomalies."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.info("No SLACK_WEBHOOK_URL set — skipping Slack alert")
        return
    try:
        import requests
        messages = "\n".join(f"• {a['message']}" for a in anomalies)
        payload = {"text": f":rotating_light: *QuantAgents Data Anomalies*\n{messages}"}
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as exc:
        logger.warning("Slack alert failed: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = detect_all_anomalies()
    print(f"Anomalies: {report['total_anomalies']} ({report['critical_count']} critical)")
