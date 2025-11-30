"""
Simple Test DAG to verify Airflow is working
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

def print_hello():
    print("Hello from Airflow!")
    print("DAG is working correctly!")
    return "Success"

default_args = {
    "owner": "test",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="test_simple_dag",
    default_args=default_args,
    description="Simple test DAG",
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["test"],
) as dag:

    task1 = PythonOperator(
        task_id="print_hello",
        python_callable=print_hello,
    )

    task2 = BashOperator(
        task_id="print_date",
        bash_command="date",
    )

    task1 >> task2
