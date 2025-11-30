"""
Hospital Capacity Prediction - Simple Airflow DAG
==================================================
Simplified version for testing
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "mlops-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def task_check_data(**context):
    """Check if data files exist"""
    import os

    files_to_check = [
        "/opt/airflow/Fact_GA_Beds.csv",
        "/opt/airflow/project/Fact_GA_Beds.csv",
        "/opt/airflow/data",
        "/opt/airflow/src",
    ]

    print("=" * 60)
    print("CHECKING DATA FILES")
    print("=" * 60)

    for file_path in files_to_check:
        exists = os.path.exists(file_path)
        print(f"{'✓' if exists else '✗'} {file_path}")

    # List directories
    for dir_path in ["/opt/airflow", "/opt/airflow/project"]:
        if os.path.exists(dir_path):
            print(f"\nContents of {dir_path}:")
            print(os.listdir(dir_path))

    return True

def task_check_modules(**context):
    """Check if Python modules can be imported"""
    print("=" * 60)
    print("CHECKING PYTHON MODULES")
    print("=" * 60)

    modules_to_check = [
        "pandas",
        "numpy",
        "sklearn",
    ]

    for module_name in modules_to_check:
        try:
            __import__(module_name)
            print(f"✓ {module_name} is installed")
        except ImportError as e:
            print(f"✗ {module_name} is NOT installed: {e}")

    # Check sys.path
    import sys
    print("\nPython path:")
    for path in sys.path:
        print(f"  - {path}")

    return True

with DAG(
    dag_id="hospital_capacity_test",
    default_args=default_args,
    description="Test hospital capacity pipeline setup",
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["hospital", "test", "mlops"],
) as dag:

    check_data = PythonOperator(
        task_id="check_data_files",
        python_callable=task_check_data,
        provide_context=True,
    )

    check_modules = PythonOperator(
        task_id="check_python_modules",
        python_callable=task_check_modules,
        provide_context=True,
    )

    list_files = BashOperator(
        task_id="list_project_files",
        bash_command="ls -la /opt/airflow/project/ 2>&1 || echo 'Project directory not found'",
    )

    check_data >> check_modules >> list_files
