"""
Hospital Capacity Prediction - Production Pipeline
===================================================
Monthly automated retraining pipeline using real NHS data
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
import pandas as pd
import pickle
import os
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

# Check if running in Airflow container
if os.path.exists("/opt/airflow/project"):
    ROOT_DIR = Path("/opt/airflow/project")
else:
    ROOT_DIR = Path(__file__).resolve().parents[1]

TRAINING_DATA_PATH = str(ROOT_DIR / "data" / "training_data_real.csv")
CANDIDATE_MODEL_PATH = str(ROOT_DIR / "models" / "candidate_model.pkl")
PRODUCTION_MODEL_PATH = str(ROOT_DIR / "models" / "production_model.pkl")
METRICS_LOG_PATH = str(ROOT_DIR / "models" / "metrics_log.csv")

# Model thresholds
OCCUPANCY_THRESHOLD = 0.92
AUC_FLOOR = 0.70
MIN_IMPROVEMENT = 0.01

# ============================================================================
# PIPELINE FUNCTIONS
# ============================================================================

def task_check_data(**context):
    """Check if required data files exist"""
    print("=" * 60)
    print("CHECKING DATA FILES")
    print("=" * 60)

    required_files = [
        str(ROOT_DIR / "Fact_GA_Beds.csv"),
        str(ROOT_DIR / "Fact_Flu_Beds.csv"),
        str(ROOT_DIR / "Fact_CC_Adult.csv"),
    ]

    all_exist = True
    for file_path in required_files:
        exists = os.path.exists(file_path)
        print(f"{'✓' if exists else '✗'} {file_path}")
        if not exists:
            all_exist = False

    if not all_exist:
        raise FileNotFoundError("Required data files not found!")

    print("\n✓ All required data files exist")
    return True


def task_train_model(**context):
    """Train candidate model using existing training data"""
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

    print("=" * 60)
    print("MODEL TRAINING")
    print("=" * 60)

    # Load training data
    if not os.path.exists(TRAINING_DATA_PATH):
        raise FileNotFoundError(f"Training data not found: {TRAINING_DATA_PATH}")

    df = pd.read_csv(TRAINING_DATA_PATH)
    print(f"✓ Loaded {len(df)} training samples")

    # Prepare features and target
    target_col = "high_occupancy"

    # Exclude non-numeric columns
    exclude_cols = [
        target_col, "date", "org_key", "org_code", "org_name",
        "service_code", "service_name", "region", "region_name",
        "icb_code", "icb_name", "trust_code", "trust_name",
        "city", "keyword", "season"
    ]

    # Select only numeric features
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    feature_cols = [col for col in numeric_cols if col not in exclude_cols and col != target_col]

    X = df[feature_cols].fillna(0)
    y = df[target_col]

    print(f"✓ Features: {len(feature_cols)}")
    print(f"✓ Samples: {len(X)}")
    print(f"✓ Positive class: {y.sum()} ({y.mean()*100:.1f}%)")

    # Time-based split
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"\n✓ Train: {len(X_train)} samples")
    print(f"✓ Test: {len(X_test)} samples")

    # Train model
    print("\nTraining Random Forest...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)

    auc = roc_auc_score(y_test, y_pred_proba)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=3, scoring='roc_auc', n_jobs=-1)

    print("\n" + "=" * 60)
    print("METRICS")
    print("=" * 60)
    print(f"AUC:         {auc:.4f}")
    print(f"Precision:   {precision:.4f}")
    print(f"Recall:      {recall:.4f}")
    print(f"F1 Score:    {f1:.4f}")
    print(f"CV AUC:      {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")

    # Save model
    os.makedirs(os.path.dirname(CANDIDATE_MODEL_PATH), exist_ok=True)
    with open(CANDIDATE_MODEL_PATH, 'wb') as f:
        pickle.dump({
            'model': model,
            'feature_cols': feature_cols,
            'auc': auc,
            'metrics': {
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'cv_auc_mean': cv_scores.mean(),
                'cv_auc_std': cv_scores.std()
            }
        }, f)

    print(f"\n✓ Model saved: {CANDIDATE_MODEL_PATH}")

    # Push to XCom
    context["ti"].xcom_push(key="candidate_auc", value=float(auc))
    context["ti"].xcom_push(key="candidate_precision", value=float(precision))
    context["ti"].xcom_push(key="candidate_recall", value=float(recall))
    context["ti"].xcom_push(key="candidate_f1", value=float(f1))

    return {
        'auc': float(auc),
        'precision': float(precision),
        'recall': float(recall),
        'f1': float(f1)
    }


def task_evaluate_and_decide(**context):
    """Decide whether to promote candidate model"""
    print("=" * 60)
    print("EVALUATION AND DECISION")
    print("=" * 60)

    # Get candidate AUC from XCom or from model file
    ti = context["ti"]
    candidate_auc = ti.xcom_pull(key="candidate_auc", task_ids="train_model")

    # If XCom failed, read from model file
    if candidate_auc is None:
        print("XCom not available, reading from model file...")
        if os.path.exists(CANDIDATE_MODEL_PATH):
            with open(CANDIDATE_MODEL_PATH, 'rb') as f:
                candidate_data = pickle.load(f)
                candidate_auc = candidate_data.get('auc', 0.0)
        else:
            raise ValueError("Cannot get candidate AUC - model file not found")

    candidate_auc = float(candidate_auc)

    print(f"\nCandidate AUC: {candidate_auc:.4f}")
    print(f"AUC Floor:     {AUC_FLOOR:.4f}")

    # Check if production model exists
    prod_auc = None
    if os.path.exists(PRODUCTION_MODEL_PATH):
        with open(PRODUCTION_MODEL_PATH, 'rb') as f:
            prod_data = pickle.load(f)

            # Handle both old format (just model object) and new format (dict)
            if isinstance(prod_data, dict):
                prod_auc = prod_data.get('auc', 0.0)
            else:
                # Old format - model object only, no metrics
                print("⚠️  Old model format detected (no metrics) - treating as first model")
                prod_auc = None

        if prod_auc is not None:
            print(f"Production AUC: {prod_auc:.4f}")
    else:
        print("No production model exists - will promote automatically")

    # Decision logic
    passes_floor = candidate_auc >= AUC_FLOOR

    if prod_auc is None:
        should_promote = passes_floor
        reason = "First model" if should_promote else "Below AUC floor"
    else:
        improvement = candidate_auc - prod_auc
        passes_improvement = improvement >= MIN_IMPROVEMENT
        should_promote = passes_floor and passes_improvement
        reason = f"Improvement: {improvement:.4f}"

    print("\n" + "=" * 60)
    print("DECISION")
    print("=" * 60)
    print(f"Passes floor? {passes_floor}")
    print(f"Reason: {reason}")
    print(f"Decision: {'PROMOTE' if should_promote else 'SKIP'}")

    # Log metrics
    os.makedirs(os.path.dirname(METRICS_LOG_PATH), exist_ok=True)
    log_entry = pd.DataFrame([{
        'timestamp': datetime.now(),
        'candidate_auc': candidate_auc,
        'production_auc': prod_auc,
        'promoted': should_promote
    }])

    if os.path.exists(METRICS_LOG_PATH):
        existing_log = pd.read_csv(METRICS_LOG_PATH)
        log_entry = pd.concat([existing_log, log_entry], ignore_index=True)

    log_entry.to_csv(METRICS_LOG_PATH, index=False)
    print(f"\n✓ Logged to: {METRICS_LOG_PATH}")

    return "promote_model" if should_promote else "skip_promotion"


def task_promote(**context):
    """Promote candidate to production"""
    import shutil

    print("=" * 60)
    print("MODEL PROMOTION")
    print("=" * 60)

    if not os.path.exists(CANDIDATE_MODEL_PATH):
        raise FileNotFoundError(f"Candidate model not found: {CANDIDATE_MODEL_PATH}")

    # Copy candidate to production
    shutil.copy2(CANDIDATE_MODEL_PATH, PRODUCTION_MODEL_PATH)

    print(f"✓ Promoted: {CANDIDATE_MODEL_PATH}")
    print(f"       to: {PRODUCTION_MODEL_PATH}")

    return True


def task_notify(**context):
    """Send notification (placeholder)"""
    ti = context["ti"]
    candidate_auc = ti.xcom_pull(key="candidate_auc", task_ids="train_model")

    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Candidate AUC: {candidate_auc:.4f}")
    print(f"Timestamp: {datetime.now()}")
    print("\nIn production, this would send:")
    print("  - Email to ML team")
    print("  - Slack notification")
    print("  - Dashboard update")

    return True


# ============================================================================
# DAG DEFINITION
# ============================================================================

default_args = {
    "owner": "mlops-team",
    "depends_on_past": False,
    "email": ["mlops@hospital.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="hospital_capacity_production",
    default_args=default_args,
    description="Production hospital capacity prediction pipeline",
    schedule_interval="0 2 1 * *",  # Monthly: 1st day at 2 AM
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["production", "hospital", "mlops"],
    max_active_runs=1,
) as dag:

    start = EmptyOperator(task_id="start")

    check_data = PythonOperator(
        task_id="check_data",
        python_callable=task_check_data,
        provide_context=True,
    )

    train_model = PythonOperator(
        task_id="train_model",
        python_callable=task_train_model,
        provide_context=True,
    )

    evaluate_and_decide = BranchPythonOperator(
        task_id="evaluate_and_decide",
        python_callable=task_evaluate_and_decide,
        provide_context=True,
    )

    promote_model = PythonOperator(
        task_id="promote_model",
        python_callable=task_promote,
        provide_context=True,
    )

    skip_promotion = EmptyOperator(task_id="skip_promotion")

    notify = PythonOperator(
        task_id="notify",
        python_callable=task_notify,
        provide_context=True,
        trigger_rule="none_failed_min_one_success",
    )

    end = EmptyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    # Workflow
    start >> check_data >> train_model >> evaluate_and_decide
    evaluate_and_decide >> promote_model >> notify >> end
    evaluate_and_decide >> skip_promotion >> notify >> end
