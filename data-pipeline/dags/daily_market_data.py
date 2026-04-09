"""
QuantAgents — Daily Market Data Airflow DAG
Fetches, preprocesses, validates, and versions financial data every day at 6 PM EST.

Pipeline:
  fetch_prices ─┐
  fetch_filings ─┼─► preprocess ─► validate_schema ─► detect_anomalies ─► version_data
  fetch_options ─┤                                                       └─► alert_on_anomaly
  fetch_news    ─┘
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Make the scripts importable
sys.path.insert(0, "/opt/airflow/scripts")

DEFAULT_ARGS = {
    "owner": "quantagents",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=60),
}

# Watchlist tickers — can be overridden via Airflow Variables
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG", "MA",
    "HD", "CVX", "ABBV", "BAC", "AMD",
]


def _get_tickers():
    try:
        from airflow.models import Variable
        raw = Variable.get("quantagents_tickers", default_var=",".join(DEFAULT_TICKERS))
        return [t.strip().upper() for t in raw.split(",") if t.strip()]
    except Exception:
        return DEFAULT_TICKERS


# ── Task callables ────────────────────────────────────────────────────────────

def task_fetch_prices(**context):
    from fetch_prices import fetch_all_prices
    tickers = _get_tickers()
    results = fetch_all_prices(tickers=tickers)
    failed = [t for t, ok in results.items() if not ok]
    if failed:
        context["ti"].xcom_push(key="failed_price_tickers", value=failed)
    return {"success": sum(results.values()), "failed": len(failed)}


def task_fetch_filings(**context):
    from fetch_filings import fetch_all_filings
    tickers = _get_tickers()
    results = fetch_all_filings(tickers=tickers)
    return {"success": sum(results.values())}


def task_fetch_options(**context):
    from fetch_options import fetch_all_options
    tickers = _get_tickers()
    results = fetch_all_options(tickers=tickers)
    return {"success": sum(results.values())}


def task_fetch_news(**context):
    from fetch_news import fetch_all_news
    tickers = _get_tickers()
    results = fetch_all_news(tickers=tickers)
    return {"success": sum(results.values())}


def task_preprocess(**context):
    from preprocess import preprocess_all
    results = preprocess_all()
    return {"success": sum(results.values()), "total": len(results)}


def task_validate_schema(**context):
    from validate_schema import validate_all
    summary = validate_all()
    context["ti"].xcom_push(key="validation_summary", value=summary)
    return {"passed": summary["passed"], "failed": summary["failed"]}


def task_detect_anomalies(**context):
    from detect_anomalies import detect_all_anomalies
    report = detect_all_anomalies()
    context["ti"].xcom_push(key="anomaly_report", value={
        "total": report["total_anomalies"],
        "critical": report["critical_count"],
    })
    return report


def task_version_data(**context):
    """Commit current processed data to DVC."""
    import subprocess
    data_dir = os.getenv("DATA_DIR", "/opt/airflow/data")
    run_date = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        # Add data to DVC tracking
        subprocess.run(["dvc", "add", f"{data_dir}/processed"], check=True, capture_output=True)
        subprocess.run(["dvc", "push"], capture_output=True)  # may fail if no remote — OK
        return {"status": "versioned", "date": run_date}
    except subprocess.CalledProcessError as exc:
        # DVC failures are non-critical — log and continue
        return {"status": "dvc_failed", "error": str(exc), "date": run_date}


def task_alert_on_anomaly(**context):
    """Send alerts if critical anomalies were detected."""
    anomaly_report = context["ti"].xcom_pull(
        key="anomaly_report", task_ids="detect_anomalies"
    ) or {}
    critical_count = anomaly_report.get("critical_count", 0)

    if critical_count > 0:
        from detect_anomalies import alert_via_slack
        # Re-load to get the actual anomaly messages
        anomalies = anomaly_report.get("anomalies", [])
        critical = [a for a in anomalies if a.get("severity") == "critical"]
        alert_via_slack(critical)
        return {"alerted": True, "critical_anomalies": critical_count}

    return {"alerted": False}


# ── DAG Definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="daily_market_data",
    description="Fetch, preprocess, validate, and version financial data daily",
    schedule="0 23 * * 1-5",  # 6 PM EST = 11 PM UTC, Mon-Fri
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["data", "daily", "production"],
    doc_md="""
    ## Daily Market Data Pipeline

    Fetches financial data for the watchlist tickers:
    - Prices from yfinance (OHLCV, 1 year history)
    - SEC EDGAR filings (10-K, 10-Q, 8-K)
    - Options chains (all expiries within 90 days)
    - News articles from Tavily

    Then preprocesses, validates, detects anomalies, and versions with DVC.

    **Override tickers**: Set the `quantagents_tickers` Airflow Variable.
    """,
) as dag:

    # ── Fetch tasks (run in parallel) ─────────────────────────────────────────
    fetch_prices = PythonOperator(
        task_id="fetch_prices",
        python_callable=task_fetch_prices,
    )

    fetch_filings = PythonOperator(
        task_id="fetch_filings",
        python_callable=task_fetch_filings,
    )

    fetch_options = PythonOperator(
        task_id="fetch_options",
        python_callable=task_fetch_options,
    )

    fetch_news = PythonOperator(
        task_id="fetch_news",
        python_callable=task_fetch_news,
    )

    # ── Preprocess (after all fetches) ────────────────────────────────────────
    preprocess = PythonOperator(
        task_id="preprocess",
        python_callable=task_preprocess,
    )

    # ── Validate ──────────────────────────────────────────────────────────────
    validate_schema = PythonOperator(
        task_id="validate_schema",
        python_callable=task_validate_schema,
    )

    # ── Detect anomalies (parallel with validate) ─────────────────────────────
    detect_anomalies = PythonOperator(
        task_id="detect_anomalies",
        python_callable=task_detect_anomalies,
    )

    # ── Version data ──────────────────────────────────────────────────────────
    version_data = PythonOperator(
        task_id="version_data",
        python_callable=task_version_data,
    )

    # ── Alert on anomalies ────────────────────────────────────────────────────
    alert_on_anomaly = PythonOperator(
        task_id="alert_on_anomaly",
        python_callable=task_alert_on_anomaly,
        trigger_rule="all_done",  # runs even if detect_anomalies finds issues
    )

    # ── Task dependencies ─────────────────────────────────────────────────────
    # Parallel fetch → preprocess
    [fetch_prices, fetch_filings, fetch_options, fetch_news] >> preprocess

    # Preprocess → validate + detect (parallel)
    preprocess >> [validate_schema, detect_anomalies]

    # Both must pass before versioning
    [validate_schema, detect_anomalies] >> version_data

    # Alert runs after anomaly detection (regardless of outcome)
    detect_anomalies >> alert_on_anomaly
