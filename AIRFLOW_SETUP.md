# Airflow MLOps Pipeline - Setup and Deployment Guide

This document explains how to set up and run the Hospital Capacity Prediction Airflow MLOps pipeline.

## Quick Start

### 1. Create Required Directories

```bash
mkdir -p logs plugins config
```

### 2. Start Airflow

```bash
# Start all services
docker compose up -d

# Watch logs (optional)
docker compose logs -f
```

First startup may take 2-3 minutes because:
- PostgreSQL and Redis will initialize
- Airflow database migration will run
- Admin user will be created
- Python packages will install (scikit-learn, pandas, pytrends, etc.)

### 3. Access Web UI

Open in browser: http://localhost:8080

**Login credentials:**
- Username: `airflow`
- Password: `airflow`

### 4. Activate DAGs

In the Web UI:
1. Go to "DAGs" tab
2. Find `hospital_capacity_production` DAG
3. Toggle the switch on the left to activate it

## Available DAGs

### hospital_capacity_production

**Schedule:** Monthly (1st day of month at 2:00 AM)

**Workflow:**
```
start → check_data → train_model → evaluate_and_decide
                                          ↓
                                    promote / skip
                                          ↓
                                       notify → end
```

**What it does:**
- Validates that required data files exist
- Trains candidate model with latest data
- Compares with current production model
- Promotes if AUC ≥ 0.70 and min 1% improvement
- Logs metrics and sends notifications

## Manual Execution

### From Web UI

1. Click on the DAG
2. Click "Trigger DAG" button in top right
3. Monitor task status in "Graph" view

### From CLI

```bash
# Enter the container
docker exec -it hospital-capacity-prediction-airflow-scheduler-1 bash

# Manually trigger DAG
airflow dags trigger hospital_capacity_production

# Check DAG status
airflow dags list

# View task logs
airflow tasks logs hospital_capacity_production train_model <execution_date>
```

## Service Management

```bash
# Stop all services
docker compose down

# Restart services
docker compose restart

# Restart specific service
docker compose restart airflow-scheduler

# Remove containers and volumes (warning: data loss!)
docker compose down -v
```

## Troubleshooting

### DAGs not showing up

```bash
# List DAGs
docker exec hospital-capacity-prediction-airflow-scheduler-1 airflow dags list

# Check DAG parse errors
docker exec hospital-capacity-prediction-airflow-scheduler-1 airflow dags list-import-errors
```

### Import errors

```bash
# Check Python path in container
docker exec hospital-capacity-prediction-airflow-scheduler-1 python -c "import sys; print('\n'.join(sys.path))"

# Verify src module is accessible
docker exec hospital-capacity-prediction-airflow-scheduler-1 ls -la /opt/airflow/src
```

### Task failures

```bash
# View scheduler error logs
docker compose logs airflow-scheduler | grep ERROR

# View specific task log
docker exec hospital-capacity-prediction-airflow-scheduler-1 cat /opt/airflow/logs/dag_id=hospital_capacity_production/run_id=*/task_id=train_model/attempt=1.log
```

### Data files not found

```bash
# Check volume mappings
docker exec hospital-capacity-prediction-airflow-scheduler-1 ls -la /opt/airflow/
docker exec hospital-capacity-prediction-airflow-scheduler-1 ls -la /opt/airflow/data/
docker exec hospital-capacity-prediction-airflow-scheduler-1 ls -la /opt/airflow/models/

# If files missing, copy from host
docker cp Fact_GA_Beds.csv <container_id>:/opt/airflow/
```

## Monitoring

### Metrics Log

Track model performance over time:

```bash
cat models/metrics_log.csv
```

Columns:
- `timestamp`: Evaluation time
- `candidate_auc`: Candidate model AUC score
- `production_auc`: Production model AUC score
- `promoted`: Was the model promoted? (True/False)

### Airflow Flower (Celery Monitoring)

```bash
# Start Flower
docker compose --profile flower up -d

# Access at http://localhost:5555
```

## Directory Structure

```
.
├── dags/
│   ├── hospital_capacity_production.py  # Main production pipeline
│   ├── hospital_capacity_simple.py      # Simplified test DAG
│   └── test_dag.py                      # Basic test DAG
├── data/
│   ├── training_data_real.csv           # Processed training data
│   ├── Fact_GA_Beds.csv                 # General & Acute beds
│   ├── Fact_Flu_Beds.csv                # Flu beds data
│   └── Fact_CC_Adult.csv                # Critical Care data
├── models/
│   ├── candidate_model.pkl              # Candidate model
│   ├── production_model.pkl             # Production model
│   └── metrics_log.csv                  # Metrics history
├── logs/                                # Airflow execution logs
├── docker-compose.yaml                  # Airflow services configuration
└── README.md                            # Project documentation
```

## Production Deployment Notes

**Security:**
- Change default passwords
- Set `AIRFLOW__CORE__FERNET_KEY`
- Configure SMTP for email notifications
- Use secrets management (e.g., AWS Secrets Manager, HashiCorp Vault)

**Scaling:**
- Increase worker count: `docker compose up -d --scale airflow-worker=3`
- Use production-grade Postgres and Redis configurations
- Consider managed Airflow (e.g., AWS MWAA, Google Cloud Composer)

**Monitoring:**
- Add Prometheus/Grafana integration
- Set up log aggregation (ELK Stack)
- Configure alerts via PagerDuty/Slack webhooks
- Monitor model drift metrics

## Database Integration (Hospital Deployment)

When deploying to a hospital environment, connect to their HIS (Hospital Information System) database:

### Configure Connection

In Airflow UI → Admin → Connections:

```
Connection ID: hospital_db
Connection Type: Postgres (or mssql/oracle)
Host: hospital-db.internal
Schema: clinical_data
Login: airflow_readonly
Password: ***
Port: 5432
```

### Modify DAG to Use SQL

Update `dags/hospital_capacity_production.py`:

```python
from airflow.providers.postgres.hooks.postgres import PostgresHook

def extract_hospital_data(**context):
    hook = PostgresHook(postgres_conn_id="hospital_db")

    sql = """
        SELECT date, ward, beds_available, beds_occupied
        FROM bed_occupancy
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    """

    df = hook.get_pandas_df(sql)
    # Continue with feature engineering...
```

This eliminates the need for CSV files and enables real-time predictions with live hospital data.
