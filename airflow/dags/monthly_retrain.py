"""
QuantAgents — Monthly Retrain Airflow DAG
Runs on the 1st of every month. Regenerates training data, retrains all 3 models,
validates performance, runs bias detection, and promotes to production if improved.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.dates import days_ago


# ── Default args ──────────────────────────────────────────────────────────────

default_args = {
    "owner": "quantagents",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ── Task functions ─────────────────────────────────────────────────────────────

def _generate_training_data(**ctx):
    """Regenerate synthetic + historical training data."""
    import sys
    import logging
    sys.path.insert(0, "/opt/airflow/backend")
    logging.basicConfig(level=logging.INFO)

    from ml.data_generator import generate_all
    paths = generate_all(verbose=True)
    for name, path in paths.items():
        import pandas as pd
        df = pd.read_parquet(path)
        print(f"  {name}: {len(df):,} rows")
    ctx["ti"].xcom_push(key="data_paths", value={k: str(v) for k, v in paths.items()})


def _train_models(**ctx):
    """Train all 3 models with Optuna tuning."""
    import sys
    sys.path.insert(0, "/opt/airflow/backend")

    from ml.train_models import train_all
    results = train_all(n_trials=30, track_mlflow=True)
    ctx["ti"].xcom_push(key="train_results", value=results)
    print("Training complete:", {k: {m: v for m, v in r.items() if isinstance(v, float)}
                                  for k, r in results.items()})


def _validate_models(**ctx):
    """Validate trained models meet minimum performance thresholds."""
    import sys
    sys.path.insert(0, "/opt/airflow/backend")
    import json

    train_results = ctx["ti"].xcom_pull(key="train_results", task_ids="train_models")

    thresholds = {
        "confidence_calibrator": {"test_auc": 0.60},
        "reward_predictor": {"r2_30d": 0.10},
        "options_pricer": {"test_f1_weighted": 0.55},
    }

    failures = []
    for model, reqs in thresholds.items():
        metrics = train_results.get(model, {})
        for metric, min_val in reqs.items():
            actual = metrics.get(metric, 0)
            if actual < min_val:
                failures.append(f"{model}.{metric}={actual:.4f} < {min_val}")

    ctx["ti"].xcom_push(key="validation_failures", value=failures)
    if failures:
        print("VALIDATION FAILURES:", failures)
        raise ValueError(f"Model validation failed: {failures}")
    print("All models validated ✅")


def _run_bias_detection(**ctx):
    """Detect bias across 6 dimensions. Fail if HIGH severity bias found."""
    import sys
    sys.path.insert(0, "/opt/airflow/backend")

    from ml.model_analysis import detect_bias

    high_bias = []
    for model_name in ["confidence_calibrator", "reward_predictor", "options_pricer"]:
        result = detect_bias(model_name)
        if result.get("bias_severity") == "HIGH":
            high_bias.append(f"{model_name}: {result['disparate_impact_flags']}")

    ctx["ti"].xcom_push(key="high_bias_models", value=high_bias)
    if high_bias:
        # Log alert but don't block — notify and log to MLflow
        print(f"⚠️ HIGH BIAS DETECTED in {len(high_bias)} models: {high_bias}")
        # In production: send Slack alert
    else:
        print("No HIGH bias detected ✅")


def _decide_promotion(**ctx):
    """Branch: promote if validation passed and no HIGH bias."""
    failures = ctx["ti"].xcom_pull(key="validation_failures", task_ids="validate_models") or []
    high_bias = ctx["ti"].xcom_pull(key="high_bias_models", task_ids="bias_detection") or []

    if not failures and not high_bias:
        return "promote_models"
    return "skip_promotion"


def _promote_models(**ctx):
    """Promote all 3 models to production using the registry."""
    import sys
    from pathlib import Path
    sys.path.insert(0, "/opt/airflow/backend")

    from ml.model_registry import get_registry
    registry = get_registry()

    for model_name in ["confidence_calibrator", "reward_predictor", "options_pricer"]:
        new_path = Path(f"models/{model_name}.pkl")
        if new_path.exists():
            registry.promote(model_name, new_path)
            print(f"Promoted {model_name} to production")


def _skip_promotion(**ctx):
    print("⚠️ Promotion skipped — validation/bias failures. Models remain unchanged.")


def _notify_completion(**ctx):
    """Send completion notification (Slack/email in production)."""
    promoted = ctx["ti"].xcom_pull(task_ids="decide_promotion") == "promote_models"
    print(f"Monthly retrain {'COMPLETED and PROMOTED' if promoted else 'COMPLETED (no promotion)'}")
    # In production: mlflow.log_metric("monthly_retrain_promoted", int(promoted))


# ── DAG definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="monthly_retrain",
    description="QuantAgents monthly model retrain pipeline",
    default_args=default_args,
    schedule_interval="0 2 1 * *",  # 2 AM on 1st of every month
    start_date=days_ago(1),
    catchup=False,
    tags=["quantagents", "ml", "retrain"],
    max_active_runs=1,
) as dag:

    t_data = PythonOperator(
        task_id="generate_training_data",
        python_callable=_generate_training_data,
    )

    t_train = PythonOperator(
        task_id="train_models",
        python_callable=_train_models,
    )

    t_validate = PythonOperator(
        task_id="validate_models",
        python_callable=_validate_models,
    )

    t_bias = PythonOperator(
        task_id="bias_detection",
        python_callable=_run_bias_detection,
    )

    t_decide = BranchPythonOperator(
        task_id="decide_promotion",
        python_callable=_decide_promotion,
    )

    t_promote = PythonOperator(
        task_id="promote_models",
        python_callable=_promote_models,
    )

    t_skip = PythonOperator(
        task_id="skip_promotion",
        python_callable=_skip_promotion,
    )

    t_notify = PythonOperator(
        task_id="notify_completion",
        python_callable=_notify_completion,
        trigger_rule="none_failed_min_one_success",
    )

    # Pipeline: data → train → [validate ‖ bias] → branch → promote or skip → notify
    t_data >> t_train >> [t_validate, t_bias] >> t_decide >> [t_promote, t_skip] >> t_notify
