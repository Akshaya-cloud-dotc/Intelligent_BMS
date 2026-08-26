import os
import json
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score, confusion_matrix

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

import sys
if PROJECT_ROOT not in sys.path:
    sys.path.append(os.path.join(PROJECT_ROOT, "backend"))
from mode_classifier import classify_operating_modes

def engineer_features(df):
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    if 'delta_v' not in df.columns:
        df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
        
    for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4']:
        if ntc not in df.columns:
            df[ntc] = df['temperature']
            
    if 'Operating_Mode' not in df.columns:
        try:
            threshold_path = os.path.join(MODELS_DIR, "mode_thresholds.json")
            df = classify_operating_modes(df, recompute_thresholds=False, threshold_path=threshold_path)
        except Exception:
            df['Operating_Mode'] = 'CRUISE'
            
    df['mode_IDLE'] = (df['Operating_Mode'] == 'IDLE').astype(float)
    df['mode_DECEL'] = (df['Operating_Mode'] == 'DECEL').astype(float)
    df['mode_ACCEL'] = (df['Operating_Mode'] == 'ACCEL').astype(float)
    df['mode_CRUISE'] = (df['Operating_Mode'] == 'CRUISE').astype(float)
    
    df['cell_max'] = df[cell_cols].max(axis=1)
    df['cell_min'] = df[cell_cols].min(axis=1)
    df['cell_mean'] = df[cell_cols].mean(axis=1)
    df['cell_std'] = df[cell_cols].std(axis=1)
    df['cell_range'] = df['cell_max'] - df['cell_min']
    
    df['dv_dt'] = df['delta_v'].diff().fillna(0)
    df['dtemp_dt'] = df['temperature'].diff().fillna(0)
    df['dsoc_dt'] = df['soc'].diff().fillna(0)
    df['dvoltage_dt'] = df['voltage'].diff().fillna(0)
    
    df['rolling_mean_voltage'] = df['voltage'].rolling(window=10, min_periods=1).mean()
    df['rolling_std_voltage'] = df['voltage'].rolling(window=10, min_periods=1).std().fillna(0)
    df['rolling_mean_temperature'] = df['temperature'].rolling(window=10, min_periods=1).mean()
    df['rolling_std_temperature'] = df['temperature'].rolling(window=10, min_periods=1).std().fillna(0)
    
    df['ntc_spread'] = df[['ntc1', 'ntc2', 'ntc3', 'ntc4']].max(axis=1) - df[['ntc1', 'ntc2', 'ntc3', 'ntc4']].min(axis=1)
    
    for i in range(1, 9):
        col = f'cell_v{i}'
        df[f'cell_drop_rate_{i}'] = df[col].diff().clip(upper=0).abs().fillna(0)
        df[f'cell_rise_rate_{i}'] = df[col].diff().clip(lower=0).fillna(0)
        
    return df

IN_DIST_FILE = os.path.join(DATA_DIR, "augmented_telemetry_dataset.xlsx")
OOD_FILE = os.path.join(DATA_DIR, "synthetic_ood_dataset.csv")

def train_ood():
    print("Loading datasets...")
    df_in = pd.read_excel(IN_DIST_FILE)
    df_ood = pd.read_csv(OOD_FILE)
    
    scaler_path = os.path.join(MODELS_DIR, "bms_scaler.joblib")
    features_path = os.path.join(MODELS_DIR, "feature_columns.json")
    
    if not os.path.exists(scaler_path) or not os.path.exists(features_path):
        raise FileNotFoundError("Scaler or feature_columns.json not found in models directory.")
        
    scaler = joblib.load(scaler_path)
    with open(features_path, 'r') as f:
        feature_cols = json.load(f)
        
    print(f"Loaded {len(feature_cols)} feature columns.")
    
    print("Applying feature engineering...")
    df_in_feat = engineer_features(df_in)
    df_ood_feat = engineer_features(df_ood)
    
    # We only train on a sample of in-distribution to speed up IsolationForest
    # Randomly sample 20,000 rows from df_in for training the envelope
    df_in_train = df_in_feat.sample(n=min(20000, len(df_in_feat)), random_state=42)
    X_in_train = scaler.transform(df_in_train[feature_cols].values)
    
    print("Training IsolationForest on known distributions...")
    # contamination=0.01 means we assume 1% of the training data might be noisy/anomalous
    iso_forest = IsolationForest(n_estimators=100, contamination=0.01, random_state=42, n_jobs=-1)
    iso_forest.fit(X_in_train)
    
    # Save the detector
    detector_path = os.path.join(MODELS_DIR, "ood_detector.joblib")
    joblib.dump(iso_forest, detector_path)
    print(f"Saved OOD detector to {detector_path}")
    
    print("Calibrating OOD thresholds...")
    # Test on the remaining in-distribution data
    df_in_test = df_in_feat.drop(df_in_train.index).sample(n=min(10000, len(df_in_feat) - len(df_in_train)), random_state=42)
    X_in_test = scaler.transform(df_in_test[feature_cols].values)
    
    # Test on OOD data
    df_ood_test = df_ood_feat.sample(n=min(10000, len(df_ood_feat)), random_state=42)
    X_ood_test = scaler.transform(df_ood_test[feature_cols].values)
    
    # IsolationForest score_samples returns NEGATIVE anomaly scores. 
    # Lower values = more anomalous.
    in_scores = iso_forest.score_samples(X_in_test)
    ood_scores = iso_forest.score_samples(X_ood_test)
    
    # We want to convert to a positive "Anomaly Score" where 0 = normal, 1 = extremely anomalous
    # Let's shift and scale. 
    max_normal_score = np.max(in_scores) # typically around 0
    min_ood_score = np.min(ood_scores)   # typically around -0.8
    
    # Define an empirical threshold: 99th percentile of in-distribution scores
    # meaning 1% false positive rate on normal data.
    threshold_raw = np.percentile(in_scores, 1) # 1st percentile of negative scores
    
    print(f"Raw threshold set at: {threshold_raw:.4f}")
    
    # Calculate performance on validation sets
    in_predictions = (in_scores < threshold_raw).astype(int)
    ood_predictions = (ood_scores < threshold_raw).astype(int)
    
    fpr = np.mean(in_predictions)
    tpr = np.mean(ood_predictions)
    
    print(f"Calibration Results:")
    print(f"False Positive Rate (Known data incorrectly flagged OOD): {fpr*100:.2f}%")
    print(f"True Positive Rate (Synthetic OOD correctly flagged): {tpr*100:.2f}%")
    
    config = {
        "critical_threshold_raw": float(threshold_raw),
        "false_positive_rate": float(fpr),
        "true_positive_rate": float(tpr),
        "description": "If IsolationForest.score_samples() < critical_threshold_raw, flag as UNKNOWN_FAULT_OOD."
    }
    
    config_path = os.path.join(MODELS_DIR, "ood_config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
        
    print(f"Saved OOD configuration to {config_path}")

if __name__ == "__main__":
    train_ood()
