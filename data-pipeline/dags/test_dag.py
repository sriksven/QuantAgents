"""
QuantAgents — Test Airflow DAG
Verifies that Airflow is running and can execute a simple task.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def print_hello():
    print("QuantAgents Airflow is alive! 🚀")
    return "hello from quantagents"


default_args = {
    "owner": "quantagents",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="test_connectivity",
    description="Simple connectivity test DAG",
    schedule=None,  # manual trigger only
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["test"],
) as dag:
    hello_task = PythonOperator(
        task_id="print_hello",
        python_callable=print_hello,
    )
