import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import joblib
import xgboost as xgb

# 1. Model Caching logic for XGBoost (prevents repeated disk reads)
_cached_xgb_model = None
_cached_xgb_mtime = None

# Alarm Hysteresis Persistence globals
_last_processed_ts = None
_recent_predictions = []
_last_confirmed_fault = "Normal"
_last_raw_fault = "Normal"
_last_hysteresis_status = "Alert Verified"

_cached_scaler = None
_cached_feature_cols = None
_cached_label_map = None

_cached_limits = {
    "min_limit": 3.0,
    "max_limit": 4.15,
    "temp_limit": 45.0
}

def init_ml_model(model_dir):
    global _cached_xgb_model, _cached_xgb_mtime, _cached_scaler, _cached_feature_cols, _cached_label_map, _cached_limits
    
    print("Starting fault detection server")
    print("Loading ML model...")
    
    model_path = os.path.join(model_dir, "bms_xgboost_model.json")
    scaler_path = os.path.join(model_dir, "bms_scaler.joblib")
    feature_path = os.path.join(model_dir, "feature_columns.json")
    label_path = os.path.join(model_dir, "label_map.json")
    
    missing_files = []
    if not os.path.exists(model_path): missing_files.append("bms_xgboost_model.json")
    if not os.path.exists(scaler_path): missing_files.append("bms_scaler.joblib")
    if not os.path.exists(feature_path): missing_files.append("feature_columns.json")
    if not os.path.exists(label_path): missing_files.append("label_map.json")
    
    if missing_files:
        err_msg = f"Missing required ML files: {', '.join(missing_files)}"
        print(f"[ERROR] {err_msg}")
        return {"status": "error", "error": err_msg, "model_loaded": False}
        
    try:
        mtime = os.path.getmtime(model_path)
        if _cached_xgb_model is None or _cached_xgb_mtime != mtime:
            model = xgb.XGBClassifier()
            model.load_model(model_path)
            _cached_xgb_model = model
            _cached_xgb_mtime = mtime
            
        if _cached_scaler is None:
            _cached_scaler = joblib.load(scaler_path)
        if _cached_feature_cols is None:
            with open(feature_path, 'r') as f:
                _cached_feature_cols = json.load(f)
        if _cached_label_map is None:
            with open(label_path, 'r') as f:
                lm = json.load(f)
                _cached_label_map = {int(k): v for k, v in lm.items()}
                
        profile_path = os.path.join(model_dir, "active_profile.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r') as f:
                    profile = json.load(f)
                    cell_params = profile.get("cell_parameters", {})
                    if cell_params.get("minimum_voltage") is not None:
                        _cached_limits["min_limit"] = float(cell_params["minimum_voltage"])
                    if cell_params.get("maximum_voltage") is not None:
                        _cached_limits["max_limit"] = float(cell_params["maximum_voltage"])
                    if cell_params.get("discharge_temperature_max") is not None:
                        _cached_limits["temp_limit"] = float(cell_params["discharge_temperature_max"])
            except Exception as e:
                pass
                
        print("ML model loaded successfully")
        return {"status": "ok", "service": "fault-detection", "model_loaded": True}
    except Exception as e:
        err_msg = f"Failed to load ML model: {str(e)}"
        print(f"[ERROR] {err_msg}")
        return {"status": "error", "error": err_msg, "model_loaded": False}

def get_xgb_model(model_dir):
    global _cached_xgb_model, _cached_xgb_mtime
    model_path = os.path.join(model_dir, "bms_xgboost_model.json")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Trained XGBoost model weights not found at: {model_path}")
        
    mtime = os.path.getmtime(model_path)
    if _cached_xgb_model is None or _cached_xgb_mtime != mtime:
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        _cached_xgb_model = model
        _cached_xgb_mtime = mtime
    return _cached_xgb_model

def run_inference(df_60, model_dir):
    """
    df_60: DataFrame containing exactly 60 rows of raw battery telemetry.
    model_dir: directory where models and scalers are saved.
    """
    if len(df_60) != 60:
        raise ValueError(f"Input must contain exactly 60 rows of telemetry, got {len(df_60)} rows.")
        
    # Standardize columns to lowercase
    df = df_60.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # Check base columns
    required = ['voltage', 'current', 'temperature', 'soc']
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    for col in required + cell_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
            
    # Compute delta_v if missing
    if 'delta_v' not in df.columns:
        df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
        
    # Fill NTCs if missing
    for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4']:
        if ntc not in df.columns:
            df[ntc] = df['temperature']
            
    # --- 1. Dynamic Mode Classification ---
    import sys
    if model_dir not in sys.path:
        sys.path.append(model_dir)
    try:
        from mode_classifier import classify_operating_modes
        threshold_path = os.path.join(model_dir, "mode_thresholds.json")
        df = classify_operating_modes(df, recompute_thresholds=False, threshold_path=threshold_path)
        mode_name = df['Operating_Mode'].iloc[-1]
        
        df['mode_IDLE'] = (df['Operating_Mode'] == 'IDLE').astype(float)
        df['mode_DECEL'] = (df['Operating_Mode'] == 'DECEL').astype(float)
        df['mode_ACCEL'] = (df['Operating_Mode'] == 'ACCEL').astype(float)
        df['mode_CRUISE'] = (df['Operating_Mode'] == 'CRUISE').astype(float)
    except Exception as e:
        print(f"Warning: Failed to use dynamic modes, falling back. {e}")
        mode_name = "CRUISE"
        for m in ['ACCEL', 'CRUISE', 'DECEL', 'IDLE']:
            df[f'mode_{m}'] = 0.0
        df['mode_CRUISE'] = 1.0
    
    # --- 2. Feature Engineering ---
    # No current inversion needed here since gateway telemetry is now in standard JBD convention
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
        
    # --- 3. Load Saved Scale and Columns config ---
    global _cached_scaler, _cached_feature_cols, _cached_label_map
    if _cached_scaler is None or _cached_feature_cols is None or _cached_label_map is None:
        res = init_ml_model(model_dir)
        if not res.get("model_loaded", False):
            raise RuntimeError(res.get("error", "Unknown error loading ML model"))
            
    scaler = _cached_scaler
    feature_cols = _cached_feature_cols
    label_map = _cached_label_map
        
    # Align features
    X_raw = df[feature_cols].values
    X_scaled = scaler.transform(X_raw) # shape [60, num_features]
    
    # --- 4. Model Inference ---
    model = get_xgb_model(model_dir)
    
    # Extract the very last row (the current time step) for prediction
    X_latest = X_scaled[-1].reshape(1, -1)
    
    # --- Out-of-Distribution (OOD) Envelope Check ---
    # Check if any normalized feature goes beyond typical training boundaries
    is_ood = bool((X_latest < -0.5).any() or (X_latest > 1.5).any())
    ood_status = "OOD (High Uncertainty)" if is_ood else "In-Envelope (Safe)"
    
    # Run prediction and output class probabilities
    probs = model.predict_proba(X_latest)[0]
    pred_idx = int(np.argmax(probs))
        
    pred_fault = label_map[pred_idx]
    confidence = float(probs[pred_idx])
    
    # Mapping probabilities to output dictionary
    all_probs_dict = {label_map[i]: float(probs[i]) for i in range(len(label_map))}
    
    # --- 4.5 Physics-Informed ML Correction (Override ML predictions using physical state bounds) ---
    latest_cells = [float(df[f'cell_v{i}'].iloc[-1]) for i in range(1, 9)]
    active_cells = [c for c in latest_cells if c >= 0.5]
    min_cell_v = min(active_cells) if active_cells else 3.2
    max_cell_v = max(active_cells) if active_cells else 3.2
    latest_delta_v = max_cell_v - min_cell_v
    latest_temp = float(df['temperature'].iloc[-1])
    
    min_limit = _cached_limits["min_limit"]
    max_limit = _cached_limits["max_limit"]
    temp_limit = _cached_limits["temp_limit"]
    
    # Live Trend Features
    latest_current = float(df['current'].iloc[-1])
    dtemp_dt = float(df['temperature'].diff().fillna(0).iloc[-1])
    
    # Override incorrect classifications using physical safety limits and live trends
    if latest_delta_v >= 0.08:
        if pred_fault in ["Normal", "Undervoltage Risk"] and min_cell_v > min_limit:
            pred_fault = "Cell Imbalance"
            confidence = max(confidence, 0.85)
            
    # Voltage Sag / Undervoltage
    if min_cell_v <= min_limit or (latest_current <= -50 and min_cell_v <= min_limit + 0.15):
        if pred_fault in ["Normal", "Cell Imbalance"]:
            pred_fault = "Undervoltage Risk"
            confidence = max(confidence, 0.88)
            
    # Voltage Rise / Overvoltage
    if max_cell_v >= max_limit or (latest_current >= 50 and max_cell_v >= max_limit - 0.15):
        if pred_fault in ["Normal", "Cell Imbalance"]:
            pred_fault = "Overvoltage Risk"
            confidence = max(confidence, 0.88)
            
    # Temperature Rise Rate & Overtemperature
    if latest_temp >= temp_limit or dtemp_dt >= 1.0:
        if pred_fault == "Normal" or latest_temp >= temp_limit:
            pred_fault = "Overtemperature Risk"
            confidence = max(confidence, 0.90)
            
    # Extreme Current Stress
    if abs(latest_current) >= 120 and pred_fault == "Normal":
        pred_fault = "Weak Cell"
        confidence = max(confidence, 0.82)
            
    # --- 5. Decision Engine ---
    recommended_action = "Normal operation. No action required."
    
    # Extract confidence risk levels
    weak_cell_high = all_probs_dict.get("Weak Cell", 0.0) > 0.50
    overvoltage_high = all_probs_dict.get("Overvoltage Risk", 0.0) > 0.40
    undervoltage_high = all_probs_dict.get("Undervoltage Risk", 0.0) > 0.40
    imbalance_high = all_probs_dict.get("Cell Imbalance", 0.0) > 0.40
    overtemperature_high = all_probs_dict.get("Overtemperature Risk", 0.0) > 0.40
    
    if overtemperature_high:
        recommended_action = "Cool battery pack/Stop operation immediately"
    elif mode_name == "ACCEL" and weak_cell_high:
        recommended_action = "Reduce allowable discharge current"
    elif mode_name == "DECEL" and overvoltage_high:
        # Note: DECEL mode covers Charging/Regen
        recommended_action = "Stop charging"
    elif mode_name == "IDLE" and imbalance_high:
        recommended_action = "Start balancing"
    elif undervoltage_high:
        recommended_action = "Reduce load/Stop discharge immediately"
    elif overvoltage_high:
        recommended_action = "Monitor pack voltage; reduce charge rate"
    elif imbalance_high:
        recommended_action = "Schedule balancing at next idle cycle"
        
    # --- 6. Physical Relaxation (Recovery) Verification ---
    relaxation_status = "Monitoring / Data Unavailable"
    currents = df['current'].values
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    cells_data = {col: df[col].values for col in cell_cols}
    
    # Detect transition from load (|current| >= 0.5A) to idle (|current| < 0.05A)
    load_indices = np.where(np.abs(currents[:-1]) >= 0.5)[0]
    idle_indices = np.where(np.abs(currents[1:]) < 0.05)[0] + 1
    
    common_transitions = []
    for l_idx in load_indices:
        next_idles = idle_indices[(idle_indices > l_idx) & (idle_indices <= l_idx + 5)]
        if len(next_idles) > 0:
            common_transitions.append((l_idx, next_idles[0]))
            
    if common_transitions:
        # Evaluate the latest load-to-idle transition rebound spread
        l_idx, i_idx = common_transitions[-1]
        rebounds = {}
        for col in cell_cols:
            v_load = cells_data[col][l_idx]
            v_idle = cells_data[col][i_idx]
            if currents[l_idx] < -0.5:
                # Discharge recovery (rebound up)
                rebounds[col] = v_idle - v_load
            else:
                # Charge recovery (relax down)
                rebounds[col] = v_load - v_idle
        
        max_rebound = max(rebounds.values())
        min_rebound = min(rebounds.values())
        rebound_spread = max_rebound - min_rebound
        
        if rebound_spread > 0.015:
            faulty_cell_col = max(rebounds, key=rebounds.get)
            faulty_cell_num = faulty_cell_col.replace("cell_v", "")
            relaxation_status = f"Idle Transition Detected / Cell {faulty_cell_num} High Ri Verified"
        else:
            relaxation_status = "Idle Transition Detected / Rebounds Normal"
            
    # --- 7. Alarm Hysteresis (Persistence Check) ---
    global _last_processed_ts, _recent_predictions, _last_confirmed_fault, _last_raw_fault, _last_hysteresis_status
    latest_ts = df['timestamp'].iloc[-1] if 'timestamp' in df.columns else None
    
    if latest_ts is not None and latest_ts != _last_processed_ts:
        _last_processed_ts = latest_ts
        _last_raw_fault = pred_fault
        
        _recent_predictions.append(pred_fault)
        if len(_recent_predictions) > 3:
            _recent_predictions.pop(0)
            
        if len(_recent_predictions) == 3 and len(set(_recent_predictions)) == 1:
            _last_confirmed_fault = _recent_predictions[0]
            _last_hysteresis_status = "Alert Verified"
        else:
            _last_confirmed_fault = "Normal"
            if pred_fault != "Normal":
                _last_hysteresis_status = "Transient Filtered / Pending"
            else:
                _last_hysteresis_status = "Alert Verified"
                
    confirmed_fault = _last_confirmed_fault
    hysteresis_status = _last_hysteresis_status
    raw_fault = _last_raw_fault

    # Output structure
    output = {
        "Operating Mode": mode_name,
        "Fault Prediction": confirmed_fault,
        "Raw Prediction": raw_fault,
        "Confidence Score": f"{confidence * 100:.2f}%",
        "All Class Probabilities": {k: f"{v * 100:.2f}%" for k, v in all_probs_dict.items()},
        "Recommended Action": recommended_action,
        "OOD Status": ood_status,
        "NTC Spread": f"{df['ntc_spread'].iloc[-1]:.2f} °C",
        "Relaxation Status": relaxation_status,
        "Hysteresis Status": hysteresis_status
    }
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict battery faults and operating modes.")
    parser.add_argument("--file", type=str, help="Path to an Excel file with battery telemetry.")
    parser.add_argument("--sheet", type=str, default="Charging", help="Sheet name to read from.")
    parser.add_argument("--model_dir", type=str, default=r"c:\Users\aksha\Downloads\CLEANED DATA SETS", help="Directory containing model weights and scaler.")
    args = parser.parse_ok = parser.parse_args()
    
    filepath = args.file
    if not filepath:
        # Fallback to a file in output_dir
        directory = args.model_dir
        excel_files = [f for f in os.listdir(directory) if f.endswith('.xlsx')]
        if not excel_files:
            print(json.dumps({"error": "No Excel files found in model_dir. Please provide a file using --file."}))
            sys.exit(1)
        filepath = os.path.join(directory, excel_files[0])
        
    try:
        # Load data
        xls = pd.ExcelFile(filepath)
        sheet_name = args.sheet if args.sheet in xls.sheet_names else xls.sheet_names[0]
        df_full = pd.read_excel(filepath, sheet_name=sheet_name)
        
        # Take latest 60 rows
        if len(df_full) < 60:
            print(json.dumps({"error": f"File sheet {sheet_name} has only {len(df_full)} rows, need at least 60."}))
            sys.exit(1)
            
        df_60 = df_full.iloc[-60:].reset_index(drop=True)
        
        # Run inference
        result = run_inference(df_60, args.model_dir)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
