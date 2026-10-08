#!/usr/bin/env python3
"""
predict_health.py — Live Inference Engine for SoH, RUL with Uncertainty & SHAP
--------------------------------------------------------------------------------
Provides standalone and API-callable health prediction:
  - Estimated State of Health (SoH %)
  - Remaining Useful Life (RUL) with P10 (pessimistic), P50 (median), P90 (optimistic) bounds
  - Top SHAP contributing degradation signals
  - Health status indicator (HEALTHY, DEGRADED, EOL_WARNING)
"""

import os
import pickle
import json
import numpy as np
import pandas as pd

from battery_preprocessing import FEATURE_COLUMNS, engineer_features

# Cached models in memory
_MODELS_LOADED = False
_SOH_MODEL = None
_RUL_P10 = None
_RUL_P50 = None
_RUL_P90 = None
_SCALER = None
_FEATURE_IMPORTANCES = None

def _load_health_models():
    global _MODELS_LOADED, _SOH_MODEL, _RUL_P10, _RUL_P50, _RUL_P90, _SCALER, _FEATURE_IMPORTANCES
    if _MODELS_LOADED:
        return
        
    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    if not os.path.exists(models_dir) or not os.path.exists(os.path.join(models_dir, "soh_model.pkl")):
        parent_models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        if os.path.exists(parent_models_dir):
            models_dir = parent_models_dir

    soh_path = os.path.join(models_dir, "soh_model.pkl")
    p10_path = os.path.join(models_dir, "rul_p10.pkl")
    p50_path = os.path.join(models_dir, "rul_p50.pkl")
    p90_path = os.path.join(models_dir, "rul_p90.pkl")
    scaler_path = os.path.join(models_dir, "health_scaler.pkl")
    attrib_path = os.path.join(models_dir, "health_feature_attribution.json")
    
    if not os.path.exists(soh_path):
        from train_health_models import train_and_evaluate
        train_and_evaluate()
        
    _SOH_MODEL = pickle.load(open(soh_path, "rb"))
    _RUL_P10 = pickle.load(open(p10_path, "rb"))
    _RUL_P50 = pickle.load(open(p50_path, "rb"))
    _RUL_P90 = pickle.load(open(p90_path, "rb"))
    _SCALER = pickle.load(open(scaler_path, "rb"))
    
    if os.path.exists(attrib_path):
        with open(attrib_path) as f:
            _FEATURE_IMPORTANCES = json.load(f).get("features", [])
            
    _MODELS_LOADED = True

def predict_battery_health(cycle_index: int = 150, 
                           r_int_mohm: float = 34.5, 
                           dq_dv_peak: float = 2.85, 
                           delta_v: float = 0.015,
                           temp_ambient_c: float = 25.0,
                           c_rate: float = 1.0,
                           energy_throughput_kwh: float = 2.5,
                           coulombic_efficiency: float = 99.80) -> dict:
    """
    Computes SoH, RUL with P10-P90 uncertainty bounds, and SHAP explanations.
    """
    _load_health_models()
    
    raw_dict = {
        "cycle_index": [cycle_index],
        "r_int_mohm": [r_int_mohm],
        "dq_dv_peak": [dq_dv_peak],
        "delta_v_cycle": [delta_v],
        "v_drop_1c": [(r_int_mohm / 1000.0) * 5.0],
        "temp_ambient_c": [temp_ambient_c],
        "c_rate": [c_rate],
        "energy_throughput_kwh": [energy_throughput_kwh],
        "coulombic_efficiency": [coulombic_efficiency],
        "r_int_growth_ratio": [r_int_mohm / 30.0],
        "energy_per_cycle_wh": [(energy_throughput_kwh * 1000.0) / max(1, cycle_index)]
    }
    
    df_in = pd.DataFrame(raw_dict)
    X_raw = df_in[FEATURE_COLUMNS].values
    X_scaled = _SCALER.transform(X_raw)
    
    # 1. SoH Prediction
    soh_pred = float(_SOH_MODEL.predict(X_scaled)[0])
    soh_pred = max(0.0, min(100.0, round(soh_pred, 2)))
    
    # 2. RUL Quantile Predictions
    p10 = max(0, int(round(float(_RUL_P10.predict(X_scaled)[0]))))
    p50 = max(p10, int(round(float(_RUL_P50.predict(X_scaled)[0]))))
    p90 = max(p50, int(round(float(_RUL_P90.predict(X_scaled)[0]))))
    
    # 3. Health Status Classification
    if soh_pred >= 90.0:
        health_status = "HEALTHY"
        status_color = "#16a34a"
    elif soh_pred >= 80.0:
        health_status = "DEGRADED_NORMAL"
        status_color = "#d97706"
    else:
        health_status = "EOL_CRITICAL"
        status_color = "#dc2626"
        
    # 4. Top Feature Attributions (SHAP)
    top_explanations = []
    if _FEATURE_IMPORTANCES:
        for item in _FEATURE_IMPORTANCES[:5]:
            top_explanations.append({
                "signal": item["feature"],
                "attribution_pct": item["percentage"],
                "description": f"{item['percentage']}% impact on capacity fade"
            })
            
    return {
        "soh_percent": soh_pred,
        "rul_cycles_median": p50,
        "rul_uncertainty_bounds": {
            "p10_pessimistic": p10,
            "p50_expected": p50,
            "p90_optimistic": p90,
            "uncertainty_interval_width": p90 - p10
        },
        "health_status": health_status,
        "status_color": status_color,
        "is_eol": bool(soh_pred <= 80.0),
        "active_cycle": cycle_index,
        "measured_r_int_mohm": r_int_mohm,
        "top_contributing_signals": top_explanations
    }

if __name__ == "__main__":
    print("Testing live health inference...")
    res = predict_battery_health(cycle_index=180, r_int_mohm=36.2, dq_dv_peak=2.70, delta_v=0.018)
    print(json.dumps(res, indent=2))
