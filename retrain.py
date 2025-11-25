import os
import pickle
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score

DATA_PATH = 'data/merged_hospital_data.csv'
MODEL_DIR = 'models'
PRODUCTION_MODEL = os.path.join(MODEL_DIR, 'production_model.pkl')
CANDIDATE_MODEL = os.path.join(MODEL_DIR, 'candidate_model.pkl')

os.makedirs(MODEL_DIR, exist_ok=True)

def load_data():
    if not os.path.exists(DATA_PATH):
        print('Data file not found at ' + DATA_PATH)
        return None
    return pd.read_csv(DATA_PATH)

def train_candidate(df):
    X = df.drop(['target', 'date'], axis=1, errors='ignore')
    y = df['target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    preds = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, preds)
    precision = precision_score(y_test, (preds >= 0.5).astype(int))
    print('Candidate Model AUC: ' + str(auc))
    print('Candidate Model Precision: ' + str(precision))
    with open(CANDIDATE_MODEL, 'wb') as f:
        pickle.dump(model, f)
    return {'auc': auc, 'precision': precision}

if __name__ == '__main__':
    print('Starting retraining job...')
    df = load_data()
    if df is None:
        print('No data available, exiting.')
    else:
        metrics = train_candidate(df)
        print('Retraining complete. Metrics: ' + str(metrics))
