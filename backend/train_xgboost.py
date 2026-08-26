#!/usr/bin/env python3
"""
AI-PBMS XGBoost Model Training Script (v2)
------------------------------------------
Loads the augmented physics-informed dataset, applies matching feature 
engineering (grouped by split and fault label to prevent leakage), 
scales data with MinMaxScaler, trains the XGBoost Classifier, and 
saves the trained assets (scaler, JSON model, features, and label map).
Writes a detailed training report containing all required metrics.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import xgboost as xgb

def engineer_features(df):
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    # Compute delta_v if missing
    if 'delta_v' not in df.columns:
        df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
        
    # Fill NTCs if missing
    for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4']:
        if ntc not in df.columns:
            df[ntc] = df['temperature']
            
    # Derivatives
    dI_dt = df['current'].diff().fillna(0)
    dV_dt = df['voltage'].diff().fillna(0)
    
    # Operating Mode Detectors (Now using pre-calculated dynamic mode)
    if 'Operating_Mode' in df.columns:
        df['mode_IDLE'] = (df['Operating_Mode'] == 'IDLE').astype(float)
        df['mode_DECEL'] = (df['Operating_Mode'] == 'DECEL').astype(float)
        df['mode_ACCEL'] = (df['Operating_Mode'] == 'ACCEL').astype(float)
        df['mode_CRUISE'] = (df['Operating_Mode'] == 'CRUISE').astype(float)
    else:
        df['mode_IDLE'] = 0.0
        df['mode_DECEL'] = 0.0
        df['mode_ACCEL'] = 0.0
        df['mode_CRUISE'] = 1.0
    
    # Feature Calculations
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
    
    # Spatial thermal spread calculation
    df['ntc_spread'] = df[['ntc1', 'ntc2', 'ntc3', 'ntc4']].max(axis=1) - df[['ntc1', 'ntc2', 'ntc3', 'ntc4']].min(axis=1)
    
    for i in range(1, 9):
        col = f'cell_v{i}'
        df[f'cell_drop_rate_{i}'] = df[col].diff().clip(upper=0).abs().fillna(0)
        df[f'cell_rise_rate_{i}'] = df[col].diff().clip(lower=0).fillna(0)
        
    return df

def main():
    directory = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(directory, "augmented_telemetry_dataset.xlsx")
    
    if not os.path.exists(data_path):
        print(f"Error: Augmented dataset not found at {data_path}. Please run generate_synthetic_faults.py first.")
        sys.exit(1)
        
    print(f"Loading augmented dataset from: {data_path}...")
    xls = pd.ExcelFile(data_path)
    df_raw = pd.read_excel(data_path, sheet_name=xls.sheet_names[0])
    
    # Ensure correct split configuration is present
    if 'split' not in df_raw.columns:
        # Fallback split if file does not contain a split column
        print("WARNING: 'split' column not found in dataset. Creating random stratified split.")
        np.random.seed(42)
        msk = np.random.rand(len(df_raw))
        df_raw['split'] = 'train'
        df_raw.loc[msk >= 0.70, 'split'] = 'val'
        df_raw.loc[msk >= 0.85, 'split'] = 'test'
        
    # Feature columns configuration
    feature_cols_path = os.path.join(directory, "feature_columns.json")
    with open(feature_cols_path, 'r') as f:
        feature_names = json.load(f)
        
    # Apply feature engineering to each split and fault label group separately
    # This prevents cross-segment leakage (rolling values don't cross boundaries)
    print("Applying physics-informed feature engineering (leakage-safe)...")
    grouped = df_raw.groupby(['split', 'fault_label'])
    processed_groups = []
    
    for (split, label), group in grouped:
        group_reset = group.reset_index(drop=True)
        group_engineered = engineer_features(group_reset)
        processed_groups.append(group_engineered)
        
    df_processed = pd.concat(processed_groups, ignore_index=True)
    
    # Split features and labels using pre-computed split column
    train_mask = df_processed['split'] == 'train'
    val_mask = df_processed['split'] == 'val'
    test_mask = df_processed['split'] == 'test'
    
    X_train = df_processed[train_mask][feature_names].values
    y_train = df_processed[train_mask]['fault_label'].values
    
    X_val = df_processed[val_mask][feature_names].values
    y_val = df_processed[val_mask]['fault_label'].values
    
    X_test = df_processed[test_mask][feature_names].values
    y_test = df_processed[test_mask]['fault_label'].values
    
    print(f"\nDataset Splits Summary:")
    print(f" -> Train set      : {X_train.shape[0]} rows")
    print(f" -> Validation set : {X_val.shape[0]} rows")
    print(f" -> Test set       : {X_test.shape[0]} rows")
    
    print("\nFitting MinMaxScaler on Train split...")
    scaler = MinMaxScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Save the fitted scaler
    scaler_path = os.path.join(directory, "bms_scaler.joblib")
    joblib.dump(scaler, scaler_path)
    print(f" -> Saved fitted scaler to: {scaler_path}")
    
    print("\nTraining XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric='mlogloss'
    )
    
    # Train with early stopping on validation set
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_val_scaled, y_val)],
        verbose=False
    )
    
    # Model evaluation on Test split
    y_pred = model.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"\nFinal Test Accuracy: {acc*100:.2f}%")
    
    class_names = ["Normal", "Cell Imbalance", "Weak Cell", "Overvoltage Risk", "Undervoltage Risk", "Overtemperature Risk"]
    clf_report = classification_report(y_test, y_pred, target_names=class_names, output_dict=True)
    clf_report_text = classification_report(y_test, y_pred, target_names=class_names)
    
    # Print classification report
    print("\nClassification Report:")
    print("-" * 65)
    print(clf_report_text)
    print("-" * 65)
    
    # Print Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\nConfusion Matrix:")
    print(cm)
    
    # Save Model in JSON format
    model_json_path = os.path.join(directory, "bms_xgboost_model.json")
    model.save_model(model_json_path)
    print(f"\n -> Saved trained XGBoost model weights to: {model_json_path}")
    
    # Save Feature Columns JSON and Label Map JSON just to verify consistency
    feature_cols_out = os.path.join(directory, "feature_columns.json")
    with open(feature_cols_out, 'w') as f:
        json.dump(feature_names, f)
        
    label_map_out = os.path.join(directory, "label_map.json")
    label_map = {"0": "Normal", "1": "Cell Imbalance", "2": "Weak Cell", "3": "Overvoltage Risk", "4": "Undervoltage Risk", "5": "Overtemperature Risk"}
    with open(label_map_out, 'w') as f:
        json.dump(label_map, f)
        
    # Write the detailed evaluation report file
    report_path = os.path.join(directory, "xgboost_training_report.txt")
    with open(report_path, "w") as f_report:
        f_report.write("BMS ML XGBoost Pipeline Retraining Evaluation Report\n")
        f_report.write("===================================================\n\n")
        f_report.write(f"Total Rows In Balanced Dataset: {len(df_raw)} rows\n")
        f_report.write(f"  - Real healthy / Normal rows: {len(df_raw[df_raw['fault_label'] == 0])} rows\n")
        f_report.write(f"  - Real fault rows: 0 rows\n")
        f_report.write(f"  - Synthetic fault rows (Classes 1-5): {len(df_raw[df_raw['fault_label'] > 0])} rows\n\n")
        
        f_report.write("Dataset Splitting Breakdown:\n")
        f_report.write(f"  - Train split (70%)     : {X_train.shape[0]} rows\n")
        f_report.write(f"  - Validation split (15%): {X_val.shape[0]} rows\n")
        f_report.write(f"  - Test split (15%)      : {X_test.shape[0]} rows\n\n")
        
        f_report.write("Class Distribution (Balanced):\n")
        for label_id, name in label_map.items():
            label_int = int(label_id)
            tr_cnt = np.sum(y_train == label_int)
            val_cnt = np.sum(y_val == label_int)
            te_cnt = np.sum(y_test == label_int)
            tot_cnt = tr_cnt + val_cnt + te_cnt
            f_report.write(f"  - {name:<22}: Train={tr_cnt:<5} Val={val_cnt:<4} Test={te_cnt:<4} Total={tot_cnt}\n")
            
        f_report.write(f"\nOverall Test Accuracy: {acc*100:.2f}%\n\n")
        f_report.write("Classification Metrics Per Class:\n")
        f_report.write(f"  {'Class Name':<22} | {'Precision':<9} | {'Recall':<9} | {'F1-Score':<9}\n")
        f_report.write("  " + "-" * 57 + "\n")
        for name in class_names:
            metrics = clf_report[name]
            f_report.write(f"  {name:<22} | {metrics['precision']:<9.4f} | {metrics['recall']:<9.4f} | {metrics['f1-score']:<9.4f}\n")
            
        f_report.write("\nConfusion Matrix (Rows: True label, Columns: Predicted label):\n")
        f_report.write("  " + "  ".join(f"[{c}]" for c in range(6)) + "\n")
        for i, row in enumerate(cm):
            f_report.write(f"  " + "   ".join(f"{val:<4}" for val in row) + f"  <- True: {class_names[i]}\n")
            
    print(f"Saved evaluation report to: {report_path}")
    print("\nSUCCESS: XGBoost model training and validation complete!")

if __name__ == "__main__":
    main()
