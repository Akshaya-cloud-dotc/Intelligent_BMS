#!/usr/bin/env python3
import os
import sys
import json
import time
import pandas as pd
import numpy as np
import joblib
import xgboost as xgb
from datetime import datetime

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))

def get_learning_status():
    status_path = os.path.join(MODEL_DIR, "learning_status.json")
    if os.path.exists(status_path):
        try:
            with open(status_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "model_version": "v1",
        "last_learning_time": "Never",
        "samples_learned": 0,
        "total_samples_learned": 2756,
        "status": "Active"
    }

def update_learning_status(new_samples, total_samples, accuracy=None, f1_score=None, confusion_matrix=None, error_msg=None):
    status_path = os.path.join(MODEL_DIR, "learning_status.json")
    status = get_learning_status()
    
    if error_msg:
        status["status"] = f"Error: {error_msg}"
    else:
        old_ver = status.get("model_version", "v1")
        try:
            ver_num = int(old_ver.replace("v", ""))
        except ValueError:
            ver_num = 1
        status["model_version"] = f"v{ver_num + 1}"
        status["last_learning_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status["samples_learned"] = new_samples
        status["total_samples_learned"] = total_samples
        status["status"] = "Active"
        if accuracy is not None:
            status["accuracy"] = accuracy
        if f1_score is not None:
            status["f1_score"] = f1_score
        if confusion_matrix is not None:
            status["confusion_matrix"] = confusion_matrix
        
    with open(status_path, "w") as f:
        json.dump(status, f, indent=2)

def label_row(row):
    """Assigns a physics-consistent fault label based on sensor values and model predictions (pseudo-labeling)."""
    try:
        voltage = float(row.get("voltage", 25.6))
        current = float(row.get("current", 0.0))
        temperature = float(row.get("temperature", 25.0))
        
        cell_v = []
        for i in range(1, 9):
            cell_v.append(float(row.get(f"cell_v{i}", 3.2)))
            
        delta_v = max(cell_v) - min(cell_v)
        
        # 1. Physics-based label assignment
        phys_label = 0
        if temperature > 45.0:
            phys_label = 5
        elif max(cell_v) > 4.18 or voltage > 33.2 or (max(cell_v) > 4.15 and current < -0.05):
            phys_label = 3
        elif min(cell_v) < 2.85 or voltage < 22.8 or (min(cell_v) < 2.90 and current > 0.05):
            phys_label = 4
        elif delta_v > 0.080 and abs(current) < 0.10:
            phys_label = 1
        elif delta_v > 0.070 and current > 0.10:
            phys_label = 2
            
        # 2. Pseudo-label cross-verification
        # If the model predicted a label with high confidence (> 80%), we align it
        model_label_str = row.get("model_predicted_label", "Normal")
        model_conf_str = str(row.get("model_predicted_conf", "0%"))
        try:
            model_conf = float(model_conf_str.replace("%", "").strip()) / 100.0
        except ValueError:
            model_conf = 0.0
            
        fault_map = {
            "Normal": 0,
            "Cell Imbalance": 1,
            "Weak Cell": 2,
            "Overvoltage Risk": 3,
            "Undervoltage Risk": 4,
            "Overtemperature Risk": 5
        }
        model_label = fault_map.get(model_label_str, 0)
        
        if model_conf > 0.80 and phys_label == model_label:
            # Physics and model high confidence agree: highly reliable label
            return phys_label
        elif phys_label != 0:
            # Fallback to physics-derived label if there is an active safety violation
            return phys_label
        else:
            # Default to normal
            return 0
    except Exception:
        return 0

def engineer_features(df):
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    if 'delta_v' not in df.columns:
        df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
        
    for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4']:
        if ntc not in df.columns:
            df[ntc] = df['temperature']
            
    dI_dt = df['current'].diff().fillna(0)
    dV_dt = df['voltage'].diff().fillna(0)
    
    df['mode_IDLE'] = 0.0
    df['mode_DECEL'] = 0.0
    df['mode_ACCEL'] = 0.0
    df['mode_CRUISE'] = 0.0
    
    is_idle = (df['current'].abs() < 0.05) & (dV_dt.abs() < 0.02)
    is_decel_regen = (df['current'] > 0.05)
    is_disch = (df['current'] <= -0.05)
    is_accel = is_disch & (dI_dt < -0.15)
    is_decel_disch = is_disch & (dI_dt > 0.15)
    
    df.loc[is_idle, 'mode_IDLE'] = 1.0
    df.loc[is_decel_regen | is_decel_disch, 'mode_DECEL'] = 1.0
    df.loc[is_accel, 'mode_ACCEL'] = 1.0
    
    cruise_mask = (df['mode_IDLE'] == 0) & (df['mode_DECEL'] == 0) & (df['mode_ACCEL'] == 0)
    df.loc[cruise_mask, 'mode_CRUISE'] = 1.0
    
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

def train():
    try:
        buffer_path = os.path.join(MODEL_DIR, "scratch", "buffer_latest.json")
        if not os.path.exists(buffer_path):
            print("No latest learning buffer found to learn from.")
            return
            
        with open(buffer_path, "r") as f:
            new_rows_raw = json.load(f)
            
        if not new_rows_raw:
            print("Learning buffer is empty.")
            return
            
        print(f"Incremental learning: labeling and appending {len(new_rows_raw)} new samples...")
        
        # Label the new telemetry rows
        new_rows_processed = []
        for r in new_rows_raw:
            inverted_current = -float(r.get("current", 0.0))
            row = {
                "cycle": 1,
                "charge_discharge": "Idle" if abs(inverted_current) <= 0.05 else ("Charge" if inverted_current > 0.05 else "Discharge"),
                "timestamp": r.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "voltage": float(r.get("voltage", 25.6)),
                "current": inverted_current,
                "temperature": float(r.get("temperature", 25.0)),
                "soc": float(r.get("soc", 50.0))
            }
            for i in range(1, 9):
                row[f"cell_v{i}"] = float(r.get(f"cell_v{i}", 3.2))
                
            cell_v = [row[f"cell_v{i}"] for i in range(1, 9)]
            row["delta_v"] = max(cell_v) - min(cell_v)
            
            for ntc in ["ntc1", "ntc2", "ntc3", "ntc4"]:
                row[ntc] = float(r.get(ntc, row["temperature"]))
                
            row["fault_label"] = label_row(r)
            new_rows_processed.append(row)
            
        df_new = pd.DataFrame(new_rows_processed)
        
        # Load the base training dataset
        dataset_path = os.path.join(MODEL_DIR, "augmented_telemetry_dataset.xlsx")
        if os.path.exists(dataset_path):
            xls = pd.ExcelFile(dataset_path)
            df_base = pd.read_excel(dataset_path, sheet_name=xls.sheet_names[0])
            df_base.columns = [str(c).lower().strip() for c in df_base.columns]
            df_combined = pd.concat([df_base, df_new], ignore_index=True)
        else:
            df_combined = df_new
            
        # Save the updated raw dataset back to Excel
        with pd.ExcelWriter(dataset_path, engine="openpyxl") as writer:
            df_combined.to_excel(writer, sheet_name="Augmented Telemetry", index=False)
            
        # Load feature columns
        feature_cols_path = os.path.join(MODEL_DIR, "feature_columns.json")
        with open(feature_cols_path, "r") as f:
            feature_names = json.load(f)
            
        # Apply feature engineering to groups
        grouped = df_combined.groupby("fault_label")
        processed_groups = []
        for label, group in grouped:
            group_reset = group.reset_index(drop=True)
            group_engineered = engineer_features(group_reset)
            processed_groups.append(group_engineered)
            
        df_processed = pd.concat(processed_groups, ignore_index=True)
        
        X = df_processed[feature_names].values
        y = df_processed["fault_label"].values
        
        # Load scaler and transform
        scaler_path = os.path.join(MODEL_DIR, "bms_scaler.joblib")
        scaler = joblib.load(scaler_path)
        X_scaled = scaler.transform(X)
        
        # Retrain XGBoost model
        print("Retraining XGBoost model on combined dataset...")
        model = xgb.XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            eval_metric="mlogloss"
        )
        model.fit(X_scaled, y)
        
        # Save the updated model
        model_json_path = os.path.join(MODEL_DIR, "bms_xgboost_model.json")
        model.save_model(model_json_path)
        print(f"Model updated successfully! Saved to {model_json_path}")
        
        # Evaluate model to compute accuracy, F1, and confusion matrix
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
        
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42, stratify=y
            )
        except Exception:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
        model_eval = xgb.XGBClassifier(
            n_estimators=80,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            eval_metric="mlogloss"
        )
        model_eval.fit(X_train, y_train)
        y_pred = model_eval.predict(X_test)
        
        acc = float(accuracy_score(y_test, y_pred))
        f1 = float(f1_score(y_test, y_pred, average="macro"))
        cm = confusion_matrix(y_test, y_pred)
        
        cm_6x6 = [[0]*6 for _ in range(6)]
        unique_labels = np.unique(np.concatenate([y_test, y_pred]))
        for r_idx, true_label in enumerate(unique_labels):
            for c_idx, pred_label in enumerate(unique_labels):
                if true_label < 6 and pred_label < 6:
                    cm_6x6[int(true_label)][int(pred_label)] = int(cm[r_idx][c_idx])
        
        # Update learning status metadata
        update_learning_status(len(new_rows_raw), len(df_combined), accuracy=acc, f1_score=f1, confusion_matrix=cm_6x6)
        
        # Clean up buffer file
        if os.path.exists(buffer_path):
            os.remove(buffer_path)
            
    except Exception as e:
        print(f"Error during background incremental training: {e}")
        update_learning_status(0, 0, str(e))

if __name__ == "__main__":
    train()
