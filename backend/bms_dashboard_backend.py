import os
import sys
import csv
import time
from datetime import datetime
import pandas as pd
from flask import Flask, request, jsonify, send_from_directory, send_file
import json

# Ensure the model directory is in path
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(MODEL_DIR)

from predict_fault import run_inference, init_ml_model
import datasheet_parser
from werkzeug.utils import secure_filename
import alerts
import mailer

app = Flask(__name__)

# Initialize persistent alerts DB at module level
try:
    alerts.init_db()
except Exception as e:
    print(f"Error initializing persistent alerts database: {e}")

from flask_cors import CORS
CORS(app)

# CSV Logging Configuration
RAW_LOG_PATH = os.path.join(MODEL_DIR, "bms_telemetry_raw.csv")
FILTERED_LOG_PATH = os.path.join(MODEL_DIR, "bms_telemetry_filtered.csv")
LEARNING_STATUS_PATH = os.path.join(MODEL_DIR, "learning_status.json")

import threading
import subprocess

# In-memory learning buffer for new filtered rows
learning_buffer = []
learning_lock = threading.Lock()
last_learning_trigger = time.time()
LEARNING_INTERVAL = float(os.environ.get("LEARNING_INTERVAL", 600.0)) # default 10 minutes

def get_learning_status():
    if os.path.exists(LEARNING_STATUS_PATH):
        try:
            with open(LEARNING_STATUS_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "model_version": "v1",
        "last_learning_time": "Never",
        "samples_learned": 0,
        "total_samples_learned": 2756, # baseline size
        "status": "Active"
    }

def is_valid_telemetry(row):
    """Validates telemetry data against physical battery limits."""
    try:
        voltage = float(row.get("voltage", 0.0))
        current = float(row.get("current", 0.0))
        soc = float(row.get("soc", 0.0))
        
        # Pack voltage must be within logical limits (e.g. 15V to 40V)
        if not (15.0 <= voltage <= 40.0):
            return False
        # Current must be within physical range (e.g. -120A to 120A)
        if not (-120.0 <= current <= 120.0):
            return False
        # SOC must be 0-100%
        if not (0.0 <= soc <= 100.0):
            return False
            
        # Temp must be within realistic bounds (-40C to 120C) if present
        temp_val = row.get("temperature")
        if temp_val is not None:
            temperature = float(temp_val)
            if not (-40.0 <= temperature <= 120.0):
                return False
            
        # Cell voltages validation
        for i in range(1, 9):
            cell_v = float(row.get(f"cell_v{i}", 3.2))
            if not (2.0 <= cell_v <= 4.6):
                return False
        return True
    except Exception:
        return False

def log_to_csv(filepath, row, prediction=None):
    file_exists = os.path.isfile(filepath)
    
    timestamp = row.get("timestamp")
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    voltage = float(row.get("voltage", 0.0))
    current = float(row.get("current", 0.0))
    
    temp_val = row.get("temperature")
    temperature = float(temp_val) if temp_val is not None else 0.0
    
    soc = float(row.get("soc", 0.0))
    
    # Extract cell voltages
    cell_v = []
    for i in range(1, 9):
        cell_v.append(float(row.get(f"cell_v{i}", 3.2)))
        
    # Calculate delta_v
    delta_v = float(row.get("delta_v", max(cell_v) - min(cell_v)))
    
    # Determine charge/discharge state (negative = Discharge, positive = Charge)
    if current < -0.05:
        charge_discharge = "Discharge"
    elif current > 0.05:
        charge_discharge = "Charge"
    else:
        charge_discharge = "Idle"
        
    cycle = 1
    
    # Map driving mode
    mode_str = "IDLE"
    if prediction:
        mode_str = prediction.get("Operating Mode", "IDLE")
    else:
        if abs(current) < 1.5:
            mode_str = "IDLE"
        else:
            mode_str = "CRUISE"
            
    # Aligned mode mapping verbatim with bms_live_dashboard_1_1 (1).py:
    # 0 = IDLE | 1 = ACCEL | 2 = CRUISE | 3 = DECEL
    mode_map = {"IDLE": 0, "ACCEL": 1, "CRUISE": 2, "DECEL": 3}
    driving_mode = mode_map.get(mode_str, 0)
    
    # Map fault label
    fault_str = "Normal"
    if prediction:
        fault_str = prediction.get("Fault Prediction", "Normal")
        
    fault_map = {
        "Normal": 0,
        "Cell Imbalance": 1,
        "Weak Cell": 2,
        "Overvoltage Risk": 3,
        "Undervoltage Risk": 4,
        "Overtemperature Risk": 5
    }
    fault_label = fault_map.get(fault_str, 0)
    
    with open(filepath, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "cycle", "charge_discharge", "timestamp", "voltage", "current", "temperature", "soc",
                "cell_v1", "cell_v2", "cell_v3", "cell_v4", "cell_v5", "cell_v6", "cell_v7", "cell_v8",
                "delta_v", "driving_mode", "fault_label"
            ])
        writer.writerow([
            cycle, charge_discharge, timestamp, voltage, current, temperature, soc,
            cell_v[0], cell_v[1], cell_v[2], cell_v[3], cell_v[4], cell_v[5], cell_v[6], cell_v[7],
            round(delta_v, 4), driving_mode, fault_label
        ])

# Sliding buffer in-memory to hold the latest 60 seconds/rows of telemetry
telemetry_buffer = []
BUFFER_MAX_SIZE = 60
latest_raw_row = None
filtered_state = {}

# Historical statistics tracker
history_stats = {
    "total_rows_processed": 0,
    "max_temp": -999.0,
    "min_temp": 999.0,
    "max_voltage": -999.0,
    "min_voltage": 999.0,
    "cumulative_delta_v": 0.0,
    "mode_counts": {"ACCEL": 0, "CRUISE": 0, "DECEL": 0, "IDLE": 0},
    "fault_counts": {"Normal": 0, "Cell Imbalance": 0, "Weak Cell": 0, "Overvoltage Risk": 0, "Undervoltage Risk": 0, "Overtemperature Risk": 0},
    "cumulative_energy_wh": 0.0
}

def update_history_stats(row, prediction=None):
    global history_stats
    history_stats["total_rows_processed"] += 1
    
    # Pack Voltage min/max
    v = float(row.get("voltage", 0.0))
    if v > history_stats["max_voltage"] or history_stats["max_voltage"] == -999.0:
        history_stats["max_voltage"] = v
    if v < history_stats["min_voltage"] or history_stats["min_voltage"] == 999.0:
        history_stats["min_voltage"] = v
        
    # Temperature min/max
    temp_val = row.get("temperature")
    if temp_val is not None:
        t = float(temp_val)
        if t > history_stats["max_temp"] or history_stats["max_temp"] == -999.0:
            history_stats["max_temp"] = t
        if t < history_stats["min_temp"] or history_stats["min_temp"] == 999.0:
            history_stats["min_temp"] = t
        
    # Cumulative delta_v (for average imbalance calculations)
    dv = float(row.get("delta_v", 0.0))
    history_stats["cumulative_delta_v"] += dv

    # Cumulative energy (Wh) = Power (W) * time (hours)
    # Assumes ~1 second interval (1/3600 hour)
    curr = float(row.get("current", 0.0))
    p = v * curr
    history_stats["cumulative_energy_wh"] += (abs(p) / 3600.0)
    
    # If prediction is available, increment state and fault occurrences
    if prediction:
        mode = prediction.get("Operating Mode")
        fault = prediction.get("Fault Prediction")
        if mode in history_stats["mode_counts"]:
            history_stats["mode_counts"][mode] += 1
        if fault in history_stats["fault_counts"]:
            history_stats["fault_counts"][fault] += 1

def check_and_trigger_learning():
    global last_learning_trigger, learning_buffer
    with learning_lock:
        if len(learning_buffer) == 0:
            return
            
        # Set status to learning
        status = get_learning_status()
        status["status"] = "Learning"
        with open(LEARNING_STATUS_PATH, "w") as f:
            json.dump(status, f, indent=2)
            
        # Save learning buffer to scratch directory
        scratch_dir = os.path.join(MODEL_DIR, "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        buffer_path = os.path.join(scratch_dir, "buffer_latest.json")
        with open(buffer_path, "w") as f:
            json.dump(learning_buffer, f, indent=2)
            
        # Clear learning buffer
        learning_buffer = []
        
        # Trigger background retraining script
        train_script = os.path.join(MODEL_DIR, "incremental_train.py")
        subprocess.Popen([sys.executable, train_script])

def scheduler_loop():
    global last_learning_trigger
    while True:
        time.sleep(5)
        now = time.time()
        if now - last_learning_trigger >= LEARNING_INTERVAL:
            last_learning_trigger = now
            try:
                check_and_trigger_learning()
            except Exception as e:
                print(f"Error triggering background learning task: {e}")


# --- BMS Bluetooth Debug & Stale Data State ---
bms_debug_lock = threading.Lock()
bms_debug_state = {
    "bluetooth_connected": False,
    "last_packet_time": 0.0,
    "data_age_seconds": 999.0,
    "raw_packet_hex": "N/A",
    "packet_count": 0,
    "parse_error_count": 0,
    "last_parse_error": "N/A",
    "current_raw_value": 0,
    "current_scaled_value": 0.0,
    "dashboard_update_time": "N/A",
    "current_valid": False,
    "voltage_valid": False,
    "temperature_valid": False,
    "cell_voltage_valid": False,
    "is_stale": True
}

def check_stale_data():
    global bms_debug_state
    with bms_debug_lock:
        current_time = time.time()
        if bms_debug_state["last_packet_time"] > 0:
            age = current_time - bms_debug_state["last_packet_time"]
            bms_debug_state["data_age_seconds"] = round(age, 1)
            if age > 3.0:
                bms_debug_state["is_stale"] = True
                bms_debug_state["current_valid"] = False
                bms_debug_state["voltage_valid"] = False
                bms_debug_state["temperature_valid"] = False
                bms_debug_state["cell_voltage_valid"] = False
        else:
            bms_debug_state["data_age_seconds"] = 999.0
            bms_debug_state["is_stale"] = True
            bms_debug_state["bluetooth_connected"] = False

# --- Multi-Chemistry Configurations & Alert Engine ---
import threading

CHEMISTRY_CONFIGS = {
    "NMC": {
        "cell_nominal": 3.6,
        "cell_min_voltage": 3.0,
        "cell_max_voltage": 4.15,
        "cell_critical_min": 2.8,
        "cell_critical_max": 4.25,
        "temp_warn_limit": 45.0,
        "temp_critical_limit": 55.0,
        "current_warn_limit": 15.0,
        "current_critical_limit": 20.0,
        "imbalance_warn_limit": 0.08,
        "imbalance_critical_limit": 0.15,
        "is_fallback": False
    },
    "LiFePO4": {
        "cell_nominal": 3.2,
        "cell_min_voltage": 2.8,
        "cell_max_voltage": 3.6,
        "cell_critical_min": 2.5,
        "cell_critical_max": 3.8,
        "temp_warn_limit": 48.0,
        "temp_critical_limit": 55.0,
        "current_warn_limit": 15.0,
        "current_critical_limit": 20.0,
        "imbalance_warn_limit": 0.05,
        "imbalance_critical_limit": 0.10,
        "is_fallback": False
    },
    "LTO": {
        "cell_nominal": 2.4,
        "cell_min_voltage": 1.8,
        "cell_max_voltage": 2.8,
        "cell_critical_min": 1.5,
        "cell_critical_max": 3.0,
        "temp_warn_limit": 45.0,
        "temp_critical_limit": 55.0,
        "current_warn_limit": 20.0,
        "current_critical_limit": 25.0,
        "imbalance_warn_limit": 0.05,
        "imbalance_critical_limit": 0.10,
        "is_fallback": False
    },
    "Default_Fallback": {
        "cell_nominal": 3.6,
        "cell_min_voltage": 3.0,
        "cell_max_voltage": 4.15,
        "cell_critical_min": 2.8,
        "cell_critical_max": 4.25,
        "temp_warn_limit": 45.0,
        "temp_critical_limit": 60.0,
        "current_warn_limit": 15.0,
        "current_critical_limit": 20.0,
        "imbalance_warn_limit": 0.08,
        "imbalance_critical_limit": 0.15,
        "is_fallback": True
    }
}

import json

def get_active_profile_config():
    profile_path = os.path.join(MODEL_DIR, "active_profile.json")
    if not os.path.exists(profile_path):
        return None
    try:
        with open(profile_path, "r") as f:
            data = json.load(f)
        
        cell_params = data.get("cell_parameters", {})
        thresholds = data.get("thresholds", {})
        
        chem_name = cell_params.get("chemistry", "Active_Profile")
        model_name = cell_params.get("cell_model", "")
        mfg = cell_params.get("manufacturer", "")
        
        full_name = f"{mfg} {model_name} ({chem_name})".strip() if model_name else chem_name
        
        return {
            "chemistry_name": full_name,
            "cell_nominal": cell_params.get("nominal_voltage", 3.6),
            "cell_min_voltage": thresholds.get("cell_voltage", {}).get("warning", {}).get("min", 3.0),
            "cell_max_voltage": thresholds.get("cell_voltage", {}).get("warning", {}).get("max", 4.15),
            "cell_critical_min": thresholds.get("cell_voltage", {}).get("critical", {}).get("min", 2.8),
            "cell_critical_max": thresholds.get("cell_voltage", {}).get("critical", {}).get("max", 4.25),
            "temp_warn_limit": thresholds.get("temperature", {}).get("warning", 45.0),
            "temp_critical_limit": thresholds.get("temperature", {}).get("critical", 55.0),
            "current_warn_limit": thresholds.get("current", {}).get("warning", 15.0),
            "current_critical_limit": thresholds.get("current", {}).get("critical", 20.0),
            "imbalance_warn_limit": thresholds.get("imbalance", {}).get("warning", 0.08),
            "imbalance_critical_limit": thresholds.get("imbalance", {}).get("critical", 0.15),
            "is_fallback": False
        }
    except Exception as e:
        return None

def detect_chemistry(row):
    # 1. Override with Active Profile if it exists
    active_profile = get_active_profile_config()
    if active_profile:
        CHEMISTRY_CONFIGS["Active_Profile"] = active_profile
        return "Active_Profile"

    # 2. Try to get from row
    chem = row.get("chemistry")
    if chem in ["NMC", "LiFePO4", "LTO"]:
        return chem
        
    # Try query param
    try:
        chem_param = request.args.get("chemistry")
        if chem_param in ["NMC", "LiFePO4", "LTO"]:
            return chem_param
    except Exception:
        pass
        
    # Auto-detect from cell voltages
    cell_voltages = []
    for i in range(1, 9):
        cv = row.get(f"cell_v{i}")
        if cv is not None:
            cell_voltages.append(float(cv))
            
    if cell_voltages:
        max_c = max(cell_voltages)
        if max_c > 3.65:
            return "NMC"
        elif max_c > 2.85:
            return "LiFePO4"
        else:
            return "LTO"
            
    return "Default_Fallback"

def get_physics_informed_prediction(row, pred, cfg, chem_type):
    voltage = float(row.get("voltage", 25.6))
    current = float(row.get("current", 0.0))
    temperature = row.get("temperature")
    delta_v = float(row.get("delta_v", 0.0))
    
    cell_voltages = []
    for i in range(1, 9):
        cv = row.get(f"cell_v{i}")
        if cv is not None:
            cell_voltages.append(float(cv))
            
    max_cell = max(cell_voltages) if cell_voltages else (voltage / 8.0)
    min_cell = min(cell_voltages) if cell_voltages else (voltage / 8.0)
    
    override_condition = None
    override_severity = "NORMAL"
    override_reason = "Battery operating within normal physical limits."
    trigger_param = "—"
    trigger_val = "—"
    threshold_val = "—"
    
    # 1. Check CRITICAL violations
    if temperature is not None and float(temperature) >= cfg["temp_critical_limit"]:
        override_condition = "Overtemperature Risk"
        override_severity = "CRITICAL"
        override_reason = "CRITICAL: Battery temperature exceeded absolute safety operating limit."
        trigger_param = "Temperature"
        trigger_val = f"{float(temperature):.1f} °C"
        threshold_val = f"{cfg['temp_critical_limit']:.1f} °C"
    elif max_cell >= cfg["cell_critical_max"]:
        override_condition = "Overvoltage Risk"
        override_severity = "CRITICAL"
        override_reason = "CRITICAL: Cell voltage exceeds absolute safety maximum limit."
        trigger_param = "Max Cell Voltage"
        trigger_val = f"{max_cell:.3f} V"
        threshold_val = f"{cfg['cell_critical_max']:.3f} V"
    elif min_cell <= cfg["cell_critical_min"]:
        override_condition = "Undervoltage Risk"
        override_severity = "CRITICAL"
        override_reason = "CRITICAL: Cell voltage is below absolute safety minimum limit."
        trigger_param = "Min Cell Voltage"
        trigger_val = f"{min_cell:.3f} V"
        threshold_val = f"{cfg['cell_critical_min']:.3f} V"
    elif abs(current) >= cfg["current_critical_limit"]:
        override_condition = "Overcurrent Risk"
        override_severity = "CRITICAL"
        override_reason = "CRITICAL: Pack continuous current exceeds absolute continuous current limit."
        trigger_param = "Current"
        trigger_val = f"{current:.2f} A"
        threshold_val = f"±{cfg['current_critical_limit']:.1f} A"
    elif delta_v >= cfg["imbalance_critical_limit"]:
        override_condition = "Cell Imbalance Risk"
        override_severity = "CRITICAL"
        override_reason = "CRITICAL: Cell voltage spread exceeds balancer critical safety limit."
        trigger_param = "Cell Spread (Delta V)"
        trigger_val = f"{delta_v:.3f} V"
        threshold_val = f"{cfg['imbalance_critical_limit']:.3f} V"
        
    # 2. Check WARNING violations
    if override_condition is None:
        if temperature is not None and float(temperature) >= cfg["temp_warn_limit"]:
            override_condition = "Overtemperature Risk"
            override_severity = "WARNING"
            override_reason = "WARNING: Battery temperature exceeded safe operating limit."
            trigger_param = "Temperature"
            trigger_val = f"{float(temperature):.1f} °C"
            threshold_val = f"{cfg['temp_warn_limit']:.1f} °C"
        elif max_cell >= cfg["cell_max_voltage"]:
            override_condition = "Overvoltage Risk"
            override_severity = "WARNING"
            override_reason = "WARNING: Cell voltage is approaching maximum safe threshold limit."
            trigger_param = "Max Cell Voltage"
            trigger_val = f"{max_cell:.3f} V"
            threshold_val = f"{cfg['cell_max_voltage']:.3f} V"
        elif min_cell <= cfg["cell_min_voltage"]:
            override_condition = "Undervoltage Risk"
            override_severity = "WARNING"
            override_reason = "WARNING: Cell voltage is approaching minimum safe threshold limit."
            trigger_param = "Min Cell Voltage"
            trigger_val = f"{min_cell:.3f} V"
            threshold_val = f"{cfg['cell_min_voltage']:.3f} V"
        elif abs(current) >= cfg["current_warn_limit"]:
            override_condition = "Overcurrent Risk"
            override_severity = "WARNING"
            override_reason = "WARNING: Pack current is approaching safety continuous limit."
            trigger_param = "Current"
            trigger_val = f"{current:.2f} A"
            threshold_val = f"±{cfg['current_warn_limit']:.1f} A"
        elif delta_v >= cfg["imbalance_warn_limit"]:
            override_condition = "Cell Imbalance Risk"
            override_severity = "WARNING"
            override_reason = "WARNING: Cell voltage spread exceeds balancer warning safety limit."
            trigger_param = "Cell Spread (Delta V)"
            trigger_val = f"{delta_v:.3f} V"
            threshold_val = f"{cfg['imbalance_warn_limit']:.3f} V"

    # 3. Fall back to ML predictions
    if override_condition is None:
        ml_fault = pred.get("Fault Prediction", "Normal") if pred else "Normal"
        ml_conf = pred.get("Confidence Score", "100.00%") if pred else "100.00%"
        
        if ml_fault != "Normal":
            override_condition = ml_fault
            override_severity = "WARNING"
            override_reason = f"ML PREDICTION: ML stress predictor detected {ml_fault.lower()} signature."
            trigger_param = "ML Anomaly Classification"
            trigger_val = f"{ml_fault} ({ml_conf})"
            threshold_val = "Normal Signature"
        else:
            override_condition = "Normal Operation"
            override_severity = "NORMAL"
            override_reason = "Battery operating normally within safe limits."
            trigger_param = "—"
            trigger_val = "—"
            threshold_val = "—"
            
    confidence_score = pred.get("Confidence Score", "100.00%") if pred else "100.00%"
    if override_severity == "CRITICAL" or (override_severity == "WARNING" and override_condition != (pred.get("Fault Prediction") if pred else "Normal")):
        confidence_score = "100.00% (Override)"

    return {
        "condition": override_condition,
        "severity": override_severity,
        "confidence": confidence_score,
        "triggering_parameter": trigger_param,
        "measured_value": trigger_val,
        "safe_threshold": threshold_val,
        "reason": override_reason,
        "chemistry": chem_type,
        "is_fallback": (chem_type == "Default_Fallback" or cfg.get("is_fallback", False)),
        "is_ood": pred.get("is_ood", False) if pred else False,
        "ood_status": pred.get("ood_status", "In-Distribution (Safe)") if pred else "In-Distribution (Safe)",
        "ood_score": pred.get("ood_score", 0.0) if pred else 0.0
    }

active_alerts = []
alert_history = []
alert_lock = threading.Lock()

def calculate_stress_score(row, cfg):
    try:
        temp_val = row.get("temperature")
        temp = float(temp_val) if temp_val is not None else 25.0
        curr = float(row.get("current", 0.0))
        delta_v = float(row.get("delta_v", 0.0))
        soc = float(row.get("soc", 50.0))
        
        # Thermal stress
        if temp > 30.0:
            temp_stress = max(0.0, min(100.0, (temp - 30.0) / (cfg["temp_critical_limit"] - 30.0) * 100.0))
        else:
            temp_stress = 0.0
            
        # Current stress
        curr_stress = max(0.0, min(100.0, abs(curr) / cfg["current_critical_limit"] * 100.0))
        
        # Imbalance stress
        imb_stress = max(0.0, min(100.0, delta_v / cfg["imbalance_critical_limit"] * 100.0))
        
        # SOC stress (higher stress at extremes)
        soc_stress = 0.0
        if soc > 90.0:
            soc_stress = (soc - 90.0) / 10.0 * 50.0
        elif soc < 15.0:
            soc_stress = (15.0 - soc) / 15.0 * 50.0
            
        return round(max(temp_stress, curr_stress, imb_stress, soc_stress), 1)
    except Exception:
        return 0.0

def evaluate_alerts(row, prediction, cfg, cycle_analytics):
    new_alerts = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract values
    voltage = float(row.get("voltage", 25.6))
    current = float(row.get("current", 0.0))
    temp_val = row.get("temperature")
    temperature = float(temp_val) if temp_val is not None else None
    soc = float(row.get("soc", 50.0))
    delta_v = float(row.get("delta_v", 0.0))
    
    cell_voltages = []
    for i in range(1, 9):
        cv = row.get(f"cell_v{i}")
        if cv is not None:
            cell_voltages.append(float(cv))
            
    max_cell = max(cell_voltages) if cell_voltages else (voltage / 8.0)
    min_cell = min(cell_voltages) if cell_voltages else (voltage / 8.0)
    
    # 1. Overvoltage risk
    if max_cell >= cfg["cell_critical_max"]:
        _alrt_type = "Overvoltage Risk"
        _alrt_parameter = "Max Cell Voltage"
        _alrt_measured = max_cell
        _alrt_threshold = cfg["cell_critical_max"]
        _alrt_level = "CRITICAL"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Overvoltage Risk",
            "level": "CRITICAL",
            "parameter": "Max Cell Voltage",
            "value": f"{max_cell:.3f} V",
            "threshold": f"{cfg['cell_critical_max']:.3f} V",
            "reason": f"CRITICAL: Overvoltage risk. Maximum cell voltage of {max_cell:.3f}V exceeds safety datasheet limit of {cfg['cell_critical_max']:.3f}V.",
            "timestamp": now_str,
            "action": "Stop charging immediately. Disconnect charger and verify balancer function."
        })
    elif max_cell >= cfg["cell_max_voltage"]:
        _alrt_type = "Overvoltage Risk"
        _alrt_parameter = "Max Cell Voltage"
        _alrt_measured = max_cell
        _alrt_threshold = cfg["cell_max_voltage"]
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Overvoltage Risk",
            "level": "WARNING",
            "parameter": "Max Cell Voltage",
            "value": f"{max_cell:.3f} V",
            "threshold": f"{cfg['cell_max_voltage']:.3f} V",
            "reason": f"WARNING: High cell voltage. Maximum cell voltage of {max_cell:.3f}V is approaching maximum limit of {cfg['cell_max_voltage']:.3f}V.",
            "timestamp": now_str,
            "action": "Monitor cell voltages closely. Balancer should active to reduce high cell."
        })
        
    # 2. Undervoltage risk
    if min_cell <= cfg["cell_critical_min"]:
        _alrt_type = "Undervoltage Risk"
        _alrt_parameter = "Min Cell Voltage"
        _alrt_measured = min_cell
        _alrt_threshold = cfg["cell_critical_min"]
        _alrt_level = "CRITICAL"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Undervoltage Risk",
            "level": "CRITICAL",
            "parameter": "Min Cell Voltage",
            "value": f"{min_cell:.3f} V",
            "threshold": f"{cfg['cell_critical_min']:.3f} V",
            "reason": f"CRITICAL: Undervoltage risk. Minimum cell voltage of {min_cell:.3f}V is below absolute safety datasheet limit of {cfg['cell_critical_min']:.3f}V.",
            "timestamp": now_str,
            "action": "Disconnect loads immediately. Connect charger to begin slow recovery charge."
        })
    elif min_cell <= cfg["cell_min_voltage"]:
        _alrt_type = "Undervoltage Risk"
        _alrt_parameter = "Min Cell Voltage"
        _alrt_measured = min_cell
        _alrt_threshold = cfg["cell_min_voltage"]
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Undervoltage Risk",
            "level": "WARNING",
            "parameter": "Min Cell Voltage",
            "value": f"{min_cell:.3f} V",
            "threshold": f"{cfg['cell_min_voltage']:.3f} V",
            "reason": f"WARNING: Low cell voltage. Minimum cell voltage of {min_cell:.3f}V is approaching minimum threshold of {cfg['cell_min_voltage']:.3f}V.",
            "timestamp": now_str,
            "action": "Reduce load current or prepare to recharge the battery pack."
        })
        
    # 3. Overcurrent risk
    abs_curr = abs(current)
    if abs_curr >= cfg["current_critical_limit"]:
        _alrt_type = "Overcurrent Risk"
        _alrt_parameter = "Current"
        _alrt_measured = abs_curr
        _alrt_threshold = cfg["current_critical_limit"]
        _alrt_level = "CRITICAL"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Overcurrent Risk",
            "level": "CRITICAL",
            "parameter": "Current",
            "value": f"{current:.2f} A",
            "threshold": f"±{cfg['current_critical_limit']:.1f} A",
            "reason": f"CRITICAL: Overcurrent risk. Continuous current of {current:.2f}A exceeds the pack continuous limit of {cfg['current_critical_limit']:.1f}A.",
            "timestamp": now_str,
            "action": "Reduce load demand immediately. Inspect load controller for fault conditions."
        })
    elif abs_curr >= cfg["current_warn_limit"]:
        _alrt_type = "Overcurrent Risk"
        _alrt_parameter = "Current"
        _alrt_measured = abs_curr
        _alrt_threshold = cfg["current_warn_limit"]
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Overcurrent Risk",
            "level": "WARNING",
            "parameter": "Current",
            "value": f"{current:.2f} A",
            "threshold": f"±{cfg['current_warn_limit']:.1f} A",
            "reason": f"WARNING: High current load. Continuous current of {current:.2f}A is near safety threshold of {cfg['current_warn_limit']:.1f}A.",
            "timestamp": now_str,
            "action": "Monitor temperature. Avoid sustained operation at this current level."
        })
        
    # 4. Overtemperature risk
    if temperature is not None:
        if temperature >= cfg["temp_critical_limit"]:
            _alrt_type = "Overtemperature Risk"
            _alrt_parameter = "Temperature"
            _alrt_measured = temperature
            _alrt_threshold = cfg["temp_critical_limit"]
            _alrt_level = "CRITICAL"
            _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
            if _alrt_id:

                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "Overtemperature Risk",
                "level": "CRITICAL",
                "parameter": "Temperature",
                "value": f"{temperature:.1f} °C",
                "threshold": f"{cfg['temp_critical_limit']:.1f} °C",
                "reason": f"CRITICAL: Overtemperature risk. Battery temperature is {temperature:.1f}°C, above the datasheet safe limit of {cfg['temp_critical_limit']:.1f}°C.",
                "timestamp": now_str,
                "action": "Stop operation immediately. Enable forced cooling or isolate the battery pack."
            })
        elif temperature >= cfg["temp_warn_limit"]:
            _alrt_type = "Overtemperature Risk"
            _alrt_parameter = "Temperature"
            _alrt_measured = temperature
            _alrt_threshold = cfg["temp_warn_limit"]
            _alrt_level = "WARNING"
            _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
            if _alrt_id:

                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "Overtemperature Risk",
                "level": "WARNING",
                "parameter": "Temperature",
                "value": f"{temperature:.1f} °C",
                "threshold": f"{cfg['temp_warn_limit']:.1f} °C",
                "reason": f"WARNING: High temperature. Battery temperature is {temperature:.1f}°C, approaching safe threshold of {cfg['temp_warn_limit']:.1f}°C.",
                "timestamp": now_str,
                "action": "Reduce loading to allow temperature stabilization. Verify cooling system is active."
            })
        
    # 5. High voltage sag
    voltage_sag_dev = 0.0
    active_type = cycle_analytics.get("active_cycle_type", "Idle")
    if active_type == "Discharge" and "discharging_analysis" in cycle_analytics:
        da = cycle_analytics["discharging_analysis"]
        voltage_sag_dev = da.get("voltage_sag_diff_pct", 0.0)
        
    if active_type == "Discharge" and abs(current) > 2.0:
        if voltage_sag_dev >= 40.0:
            _alrt_type = "High Voltage Sag"
            _alrt_parameter = "Voltage Sag Deviation"
            _alrt_measured = voltage_sag_dev
            _alrt_threshold = 40.0
            _alrt_level = "CRITICAL"
            _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
            if _alrt_id:

                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "High Voltage Sag",
                "level": "CRITICAL",
                "parameter": "Voltage Sag Deviation",
                "value": f"{voltage_sag_dev:.1f} %",
                "threshold": "< 40.0 %",
                "reason": f"CRITICAL: High voltage sag detected. Current cycle voltage sag is {voltage_sag_dev:.1f}% higher than previous cycle history, indicating severe cell degradation or high internal resistance.",
                "timestamp": now_str,
                "action": "Inspect pack cell connections and test cell internal resistances immediately."
            })
        elif voltage_sag_dev >= 20.0:
            _alrt_type = "High Voltage Sag"
            _alrt_parameter = "Voltage Sag Deviation"
            _alrt_measured = voltage_sag_dev
            _alrt_threshold = 20.0
            _alrt_level = "WARNING"
            _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
            if _alrt_id:

                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "High Voltage Sag",
                "level": "WARNING",
                "parameter": "Voltage Sag Deviation",
                "value": f"{voltage_sag_dev:.1f} %",
                "threshold": "< 20.0 %",
                "reason": f"WARNING: High voltage sag detected. Current cycle voltage sag is {voltage_sag_dev:.1f}% higher than previous cycle history. Possible weak cell or increased internal resistance behavior.",
                "timestamp": now_str,
                "action": "Monitor cell voltages under load. Check for weak cells."
            })
            
    # 6. Cell imbalance
    if delta_v >= cfg["imbalance_critical_limit"]:
        _alrt_type = "Cell Imbalance"
        _alrt_parameter = "Delta V"
        _alrt_measured = delta_v
        _alrt_threshold = cfg["imbalance_critical_limit"]
        _alrt_level = "CRITICAL"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Cell Imbalance",
            "level": "CRITICAL",
            "parameter": "Delta V",
            "value": f"{delta_v:.3f} V",
            "threshold": f"{cfg['imbalance_critical_limit']:.3f} V",
            "reason": f"CRITICAL: Severe cell imbalance. Maximum voltage spread of {delta_v:.3f}V exceeds critical limit of {cfg['imbalance_critical_limit']:.3f}V.",
            "timestamp": now_str,
            "action": "Manually balance the pack, or perform a full balance charge cycle."
        })
    elif delta_v >= cfg["imbalance_warn_limit"]:
        _alrt_type = "Cell Imbalance"
        _alrt_parameter = "Delta V"
        _alrt_measured = delta_v
        _alrt_threshold = cfg["imbalance_warn_limit"]
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Cell Imbalance",
            "level": "WARNING",
            "parameter": "Delta V",
            "value": f"{delta_v:.3f} V",
            "threshold": f"{cfg['imbalance_warn_limit']:.3f} V",
            "reason": f"WARNING: Cell imbalance detected. Maximum voltage spread of {delta_v:.3f}V exceeds warning limit of {cfg['imbalance_warn_limit']:.3f}V.",
            "timestamp": now_str,
            "action": "Top balance during full charge, check balancer connections."
        })
        
    # 7. Weak cell behavior
    has_weak_cell_ml = (prediction and prediction.get("Fault Prediction") == "Weak Cell")
    if (active_type == "Discharge" and voltage_sag_dev >= 20.0 and delta_v >= cfg["imbalance_warn_limit"]) or has_weak_cell_ml:
        _alrt_type = "Weak Cell Behavior"
        _alrt_parameter = "Imbalance under load"
        _alrt_measured = None
        _alrt_threshold = None
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Weak Cell Behavior",
            "level": "WARNING",
            "parameter": "Imbalance under load",
            "value": f"Sag Dev: {voltage_sag_dev:.1f}%, Delta V: {delta_v:.3f}V",
            "threshold": "Coincident imbalance/sag limits",
            "reason": "WARNING: Possible weak cell behavior due to increased voltage sag and higher deviation from previous cycle history.",
            "timestamp": now_str,
            "action": "Log cell performance under load, verify cell capacities."
        })
        
    # 8. Fast SOC drop
    soc_drop_dev = 0.0
    if active_type == "Discharge" and "discharging_analysis" in cycle_analytics:
        da = cycle_analytics["discharging_analysis"]
        soc_drop_dev = da.get("soc_drop_rate_diff_pct", 0.0)
        
    if active_type == "Discharge" and soc_drop_dev >= 20.0:
        _alrt_type = "Fast SOC Drop"
        _alrt_parameter = "SOC drop rate deviation"
        _alrt_measured = soc_drop_dev
        _alrt_threshold = 20.0
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Fast SOC Drop",
            "level": "WARNING",
            "parameter": "SOC drop rate deviation",
            "value": f"{soc_drop_dev:.1f} %",
            "threshold": "< 20.0 %",
            "reason": f"WARNING: Fast SOC drop detected. SOC drop rate is {soc_drop_dev:.1f}% faster than expected from previous cycle history, indicating capacity degradation or higher load than calculated.",
            "timestamp": now_str,
            "action": "Check pack capacity calibration and load current."
        })
        
    # 9. Abnormal charging behavior
    if active_type == "Charge" and "charging_analysis" in cycle_analytics:
        ca = cycle_analytics["charging_analysis"]
        risks = ca.get("risks", [])
        if "Slow SOC recovery" in risks or "Charging efficiency degradation" in risks:
            _alrt_type = "Abnormal Charging Behavior"
            _alrt_parameter = "Charging risks"
            _alrt_measured = None
            _alrt_threshold = None
            _alrt_level = "WARNING"
            _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
            if _alrt_id:

                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "Abnormal Charging Behavior",
                "level": "WARNING",
                "parameter": "Charging risks",
                "value": ", ".join(risks),
                "threshold": "No charging risks",
                "reason": "WARNING: ML cycle health engine detected abnormal charging behavior. Charging rate is slower or thermal rise is higher than expected.",
                "timestamp": now_str,
                "action": "Verify charging current limits, charger configuration, and balancer settings."
            })
            
    # 10. Abnormal discharging behavior
    if active_type == "Discharge" and "discharging_analysis" in cycle_analytics:
        da = cycle_analytics["discharging_analysis"]
        risks = da.get("risks", [])
        if "Fast SOC drop" in risks or "Abnormal High Current" in risks or da.get("current_draw_pattern") == "Abnormal High Current":
            _alrt_type = "Abnormal Discharging Behavior"
            _alrt_parameter = "Discharge profile"
            _alrt_measured = None
            _alrt_threshold = None
            _alrt_level = "WARNING"
            _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
            if _alrt_id:

                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "Abnormal Discharging Behavior",
                "level": "WARNING",
                "parameter": "Discharge profile",
                "value": f"Current: {current:.2f}A, Risks: {', '.join(risks)}",
                "threshold": "Normal discharge profile",
                "reason": "WARNING: ML cycle health engine detected abnormal discharging behavior. SOC drop is faster than expected or current draw is unusually high.",
                "timestamp": now_str,
                "action": "Review load requirements, check for controller anomalies or cell thermal build-up."
            })
            
    # 11. High deviation from previous cycle history
    high_dev = False
    dev_msg = ""
    if active_type == "Charge" and "charging_analysis" in cycle_analytics:
        ca = cycle_analytics["charging_analysis"]
        if abs(ca.get("duration_deviation_pct", 0.0)) > 25.0:
            high_dev = True
            dev_msg = f"Duration deviation: {ca.get('duration_deviation_pct'):.1f}%"
    elif active_type == "Discharge" and "discharging_analysis" in cycle_analytics:
        da = cycle_analytics["discharging_analysis"]
        if abs(da.get("duration_deviation_pct", 0.0)) > 25.0:
            high_dev = True
            dev_msg = f"Duration deviation: {da.get('duration_deviation_pct'):.1f}%"
        elif abs(da.get("voltage_sag_diff_pct", 0.0)) > 25.0:
            high_dev = True
            dev_msg = f"Voltage sag deviation: {da.get('voltage_sag_diff_pct'):.1f}%"
            
    if high_dev:
        _alrt_type = "High Deviation from Cycle History"
        _alrt_parameter = "Cycle deviation metrics"
        _alrt_measured = None
        _alrt_threshold = None
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "High Deviation from Cycle History",
            "level": "WARNING",
            "parameter": "Cycle deviation metrics",
            "value": dev_msg,
            "threshold": "< 25.0 %",
            "reason": f"WARNING: High deviation from previous cycle history ({dev_msg}). Battery behavior is drifting from normal baseline cycles.",
            "timestamp": now_str,
            "action": "Review historical analytics in detail to determine if cells are undergoing accelerated aging."
        })
        
    # 12. ML predicted fault risk
    if prediction:
        fault_pred = prediction.get("Fault Prediction", "Normal")
        conf_obj = prediction.get("Confidence Score", "High Confidence")
        # Use default if evaluation isn't straightforward
        conf_label = "Low Confidence"
        conf_val = 1.0
        if isinstance(conf_obj, dict):
            conf_val = conf_obj.get("score", 1.0)
            conf_label = conf_obj.get("label", "Medium Confidence")
        elif isinstance(conf_obj, str):
            conf_val = prediction.get("known_class_confidence", 1.0) if isinstance(prediction, dict) else 1.0
            conf_label = conf_obj
        else:
            if isinstance(prediction, dict):
                conf_val = prediction.get("known_class_confidence", 1.0)
            conf_label = "Medium Confidence"
            
        conf_str = f"{conf_val:.2f} - {conf_label}"
            
        if fault_pred != "Normal" and fault_pred is not None:
            physical_support = False
            if fault_pred == "Overtemperature Risk" and temperature is not None and temperature >= cfg["temp_warn_limit"]:
                physical_support = True
            elif fault_pred == "Cell Imbalance" and delta_v >= cfg["imbalance_warn_limit"]:
                physical_support = True
            elif fault_pred == "Weak Cell" and (voltage_sag_dev >= 15.0 or delta_v >= cfg["imbalance_warn_limit"]):
                physical_support = True
            elif fault_pred == "Overvoltage Risk" and max_cell >= cfg["cell_max_voltage"]:
                physical_support = True
            elif fault_pred == "Undervoltage Risk" and min_cell <= cfg["cell_min_voltage"]:
                physical_support = True
                
            level = "WARNING"
            reason = f"WARNING: ML stress predictor detected {fault_pred.lower()}. Confidence: {conf_str}."
            if physical_support and conf_val >= 0.85:
                level = "CRITICAL"
                reason = f"CRITICAL: ML stress predictor detected {fault_pred.lower()} with high confidence ({conf_str}), validated by physical sensor limits."
                
            ml_confidence = conf_val
            _alrt_id = alerts.log_alert("ML Predicted Fault Risk", "ML Anomaly Classification",
                             ml_confidence, None, ml_confidence=ml_confidence, severity=level)
            if _alrt_id:
                mailer.send_alert(_alrt_id)
            new_alerts.append({
                "type": "ML Predicted Fault Risk",
                "level": level,
                "parameter": "ML Anomaly Classification",
                "value": f"{fault_pred} ({conf_str})",
                "threshold": "Normal",
                "reason": reason,
                "timestamp": now_str,
                "action": "Inspect the parameters associated with the predicted fault signature immediately."
            })
            
    # 13. Stress predictor output above safe limit
    stress_score = calculate_stress_score(row, cfg)
    stress_crit = cfg.get("stress_critical_limit", 80.0)
    stress_warn = cfg.get("stress_warn_limit", 60.0)
    if stress_score >= stress_crit:
        _alrt_type = "Stress Predictor Output above Limit"
        _alrt_parameter = "Calculated Stress Score"
        _alrt_measured = stress_score
        _alrt_threshold = stress_crit
        _alrt_level = "CRITICAL"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Stress Predictor Output above Limit",
            "level": "CRITICAL",
            "parameter": "Calculated Stress Score",
            "value": f"{stress_score:.1f} %",
            "threshold": f"{stress_crit:.1f} %",
            "reason": f"CRITICAL: Multi-factor stress index is {stress_score:.1f}%, exceeding the critical safety limit of {stress_crit:.1f}%.",
            "timestamp": now_str,
            "action": "Isolate battery immediately and review stress components."
        })
    elif stress_score >= stress_warn:
        _alrt_type = "Stress Predictor Output above Limit"
        _alrt_parameter = "Calculated Stress Score"
        _alrt_measured = stress_score
        _alrt_threshold = stress_warn
        _alrt_level = "WARNING"
        _alrt_id = alerts.log_alert(_alrt_type, _alrt_parameter, _alrt_measured, _alrt_threshold, severity=_alrt_level)
        if _alrt_id:

            mailer.send_alert(_alrt_id)
        new_alerts.append({
            "type": "Stress Predictor Output above Limit",
            "level": "WARNING",
            "parameter": "Calculated Stress Score",
            "value": f"{stress_score:.1f} %",
            "threshold": f"{stress_warn:.1f} %",
            "reason": f"WARNING: Multi-factor stress index is {stress_score:.1f}%, exceeding the safe warning limit of {stress_warn:.1f}%.",
            "timestamp": now_str,
            "action": "Reduce thermal, current, or voltage imbalance stress."
        })
        
    def get_alert_sort_key(alert):
        level_weight = 2 if alert["level"] == "CRITICAL" else 1
        return (-level_weight, alert["timestamp"])
        
    new_alerts.sort(key=get_alert_sort_key)
    return new_alerts

def update_alerts_state(new_active_list):
    global active_alerts, alert_history
    with alert_lock:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_keys = {a["type"] for a in new_active_list}
        
        for old_a in active_alerts:
            if old_a["type"] not in new_keys:
                resolved_alert = old_a.copy()
                resolved_alert["cleared_timestamp"] = now_str
                resolved_alert["status"] = "RESOLVED"
                try:
                    alerts.resolve_alert(old_a["type"], old_a["parameter"])
                except Exception as e:
                    print(f"Error resolving alert in DB: {e}")
                alert_history.insert(0, resolved_alert)
                
        if len(alert_history) > 20:
            alert_history = alert_history[:20]
            
        active_alerts = new_active_list

def get_formatted_alert_history():
    try:
        history_rows = alerts.history(50)
        formatted = []
        for h in history_rows:
            val = h["measured_value"]
            thr = h["threshold"]
            t = h["alert_type"]
            p = h["parameter"] or ""
            
            ts_str = h["ts"]
            try:
                _ts = datetime.fromisoformat(h["ts"]).astimezone()
                ts_str = _ts.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_str = h["ts"]

            cleared_ts = "ACTIVE"
            if h["resolved_at"] is not None:
                try:
                    _res = datetime.fromisoformat(h["resolved_at"]).astimezone()
                    cleared_ts = _res.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    cleared_ts = h["resolved_at"]
            
            val_str = "—"
            if val is not None:
                if t == "ML Predicted Fault Risk":
                    val_str = f"Confidence: {val:.2f}"
                elif "%" in p or t in ["High Voltage Sag", "Fast SOC Drop", "Stress Predictor Output above Limit"]:
                    val_str = f"{val:.1f} %"
                elif "Voltage" in p or t == "Cell Imbalance":
                    val_str = f"{val:.3f} V"
                elif p == "Current":
                    val_str = f"{val:.2f} A"
                elif p == "Temperature":
                    val_str = f"{val:.1f} °C"
                else:
                    val_str = f"{val:.3f}"
            else:
                if t == "Weak Cell Behavior":
                    val_str = "High Sag & Imbalance"
                elif t == "Abnormal Charging Behavior":
                    val_str = "Degraded Charging"
                elif t == "Abnormal Discharging Behavior":
                    val_str = "Abnormal Discharge"
                elif t == "High Deviation from Cycle History":
                    val_str = "Cycle Drift"
                    
            thr_str = "—"
            if thr is not None:
                if "%" in p or t == "Stress Predictor Output above Limit":
                    thr_str = f"{thr:.1f} %"
                elif "Voltage" in p or t == "Cell Imbalance":
                    thr_str = f"{thr:.3f} V"
                elif p == "Current":
                    thr_str = f"±{thr:.1f} A"
                elif p == "Temperature":
                    thr_str = f"{thr:.1f} °C"
                else:
                    thr_str = f"{thr:.3f}"
            else:
                if t == "High Voltage Sag":
                    thr_str = "< 40.0 %" if h["severity"] == "CRITICAL" else "< 20.0 %"
                elif t == "Fast SOC Drop":
                    thr_str = "< 20.0 %"
                elif t == "Weak Cell Behavior":
                    thr_str = "Coincident limits"
                elif t == "ML Predicted Fault Risk":
                    thr_str = "Normal"
                elif t == "Abnormal Charging Behavior":
                    thr_str = "No charging risks"
                elif t == "Abnormal Discharging Behavior":
                    thr_str = "Normal discharge profile"
                elif t == "High Deviation from Cycle History":
                    thr_str = "< 25.0 %"
                
            formatted.append({
                "id": h["id"],
                "timestamp": ts_str,
                "type": t,
                "level": h["severity"],
                "parameter": p,
                "value": val_str,
                "threshold": thr_str,
                "status": h["status"],
                "cleared_timestamp": cleared_ts
            })
        return formatted
    except Exception as e:
        print(f"Error reading alert history from DB: {e}")
        return []

def run_alerts_evaluation():
    global active_alerts, alert_history, bms_debug_state
    
    check_stale_data()
    
    with bms_debug_lock:
        bt_connected = bms_debug_state["bluetooth_connected"]
        is_stale = bms_debug_state["is_stale"]
        age = bms_debug_state["data_age_seconds"]
        
    new_active = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not bt_connected:
        pass
    elif is_stale:
        pass
    else:
        if telemetry_buffer:
            latest_row = telemetry_buffer[-1]
            prediction = None
            if len(telemetry_buffer) == BUFFER_MAX_SIZE:
                try:
                    df_60 = pd.DataFrame(telemetry_buffer)
                    prediction = run_inference(df_60, MODEL_DIR)
                except Exception:
                    pass
            
            cycle_analytics = get_cycle_analytics_summary()
            chem_type = detect_chemistry(latest_row)
            cfg = CHEMISTRY_CONFIGS[chem_type]
            new_active = evaluate_alerts(latest_row, prediction, cfg, cycle_analytics)
            
    update_alerts_state(new_active)

# --- Cycle Health Analytics ---
CYCLE_HISTORY_PATH = os.path.join(MODEL_DIR, "cycle_history.json")
cycle_lock = threading.Lock()

active_cycle = {
    "cycle_id": None,
    "type": None,
    "start_time": None,
    "start_time_epoch": None,
    "start_soc": None,
    "start_voltage": None,
    "voltage_spread_start": None,
    "rows": [],
    "ah_accumulated": 0.0,
    "wh_accumulated": 0.0,
    "last_timestamp_epoch": None,
    "consecutive_idle": 0,
    "consecutive_opposite": 0
}

def load_cycle_history():
    if os.path.exists(CYCLE_HISTORY_PATH):
        try:
            with open(CYCLE_HISTORY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_cycle_history(history):
    try:
        with open(CYCLE_HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving cycle history: {e}")

def close_active_cycle(reason="transition"):
    global active_cycle
    if active_cycle["type"] is not None and len(active_cycle["rows"]) >= 10:
        rows = active_cycle["rows"]
        duration = float(time.time() - active_cycle["start_time_epoch"])
        
        end_row = rows[-1]
        end_soc = float(end_row.get("soc", 50.0))
        end_voltage = float(end_row.get("voltage", 25.6))
        
        cell_v_end = [float(end_row.get(f"cell_v{i}", 3.2)) for i in range(1, 9)]
        spread_end = max(cell_v_end) - min(cell_v_end)
        
        all_voltages = [float(r.get("voltage", 0.0)) for r in rows]
        all_currents = [float(r.get("current", 0.0)) for r in rows]
        all_temps = [float(r.get("temperature")) for r in rows if r.get("temperature") is not None]
        
        cell_cols = [f"cell_v{i}" for i in range(1, 9)]
        all_cells = []
        for r in rows:
            all_cells.extend([float(r.get(col, 3.2)) for col in cell_cols])
            
        max_cell = max(all_cells) if all_cells else 4.2
        min_cell = min(all_cells) if all_cells else 2.5
        
        avg_curr = sum(all_currents) / len(all_currents) if all_currents else 0.0
        peak_curr = max(all_currents, key=abs) if all_currents else 0.0
        
        max_t = max(all_temps) if all_temps else 25.0
        start_t_val = rows[0].get("temperature")
        start_t = float(start_t_val) if start_t_val is not None else max_t
        temp_rise = max_t - start_t
        
        status = "Full"
        partial_reason = "N/A"
        
        start_soc = active_cycle["start_soc"]
        soc_change = end_soc - start_soc
        
        if active_cycle["type"] == "Charge":
            if not (start_soc <= 50.0 and end_soc >= 90.0):
                status = "Partial"
                if end_soc < 90.0:
                    partial_reason = "stopped early"
                else:
                    partial_reason = "started high"
        else:
            if not (start_soc >= 70.0 and end_soc <= 35.0):
                status = "Partial"
                if end_soc > 35.0:
                    partial_reason = "stopped early"
                else:
                    partial_reason = "started low"
                    
        data_quality_score = 1.0
        
        cycle_entry = {
            "cycle_id": active_cycle["cycle_id"],
            "type": active_cycle["type"],
            "start_time": active_cycle["start_time"],
            "end_time": end_row.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": int(duration),
            "start_soc": round(start_soc, 1),
            "end_soc": round(end_soc, 1),
            "soc_change": round(soc_change, 1),
            "start_voltage": round(active_cycle["start_voltage"], 2),
            "end_voltage": round(end_voltage, 2),
            "max_cell_voltage": round(max_cell, 3),
            "min_cell_voltage": round(min_cell, 3),
            "voltage_spread_start": round(active_cycle["voltage_spread_start"], 3),
            "voltage_spread_end": round(spread_end, 3),
            "avg_current": round(avg_curr, 2),
            "peak_current": round(peak_curr, 2),
            "max_temp": round(max_t, 1),
            "temp_rise": round(temp_rise, 1),
            "est_ah": round(active_cycle["ah_accumulated"], 3),
            "est_wh": round(active_cycle["wh_accumulated"], 3),
            "status": status,
            "partial_reason": partial_reason,
            "alerts_count": 0,
            "data_quality_score": data_quality_score
        }
        
        history = load_cycle_history()
        history.append(cycle_entry)
        save_cycle_history(history)
        print(f"Closed cycle {active_cycle['cycle_id']} successfully.")
        
    active_cycle = {
        "cycle_id": None,
        "type": None,
        "start_time": None,
        "start_time_epoch": None,
        "start_soc": None,
        "start_voltage": None,
        "voltage_spread_start": None,
        "rows": [],
        "ah_accumulated": 0.0,
        "wh_accumulated": 0.0,
        "last_timestamp_epoch": None,
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }

def update_cycle_tracking(row):
    global active_cycle
    with cycle_lock:
        current = float(row.get("current", 0.0))
        voltage = float(row.get("voltage", 0.0))
        soc = float(row.get("soc", 0.0))
        timestamp_str = row.get("timestamp")
        
        if current < -0.05:
            inst_state = "Discharge"
        elif current > 0.05:
            inst_state = "Charge"
        else:
            inst_state = "Idle"
            
        current_time = time.time()
        
        cell_v = [float(row.get(f"cell_v{i}", 3.2)) for i in range(1, 9)]
        spread = max(cell_v) - min(cell_v)
        
        if active_cycle["type"] is None:
            if inst_state in ["Charge", "Discharge"]:
                history = load_cycle_history()
                new_id = len(history) + 1
                active_cycle = {
                    "cycle_id": new_id,
                    "type": inst_state,
                    "start_time": timestamp_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "start_time_epoch": current_time,
                    "start_soc": soc,
                    "start_voltage": voltage,
                    "voltage_spread_start": spread,
                    "rows": [row.copy()],
                    "ah_accumulated": 0.0,
                    "wh_accumulated": 0.0,
                    "last_timestamp_epoch": current_time,
                    "consecutive_idle": 0,
                    "consecutive_opposite": 0
                }
                print(f"Started active cycle {new_id} ({inst_state})")
        else:
            active_type = active_cycle["type"]
            dt = 1.0
            if active_cycle["last_timestamp_epoch"] is not None:
                dt = current_time - active_cycle["last_timestamp_epoch"]
                if dt <= 0.0 or dt > 300.0:
                    dt = 1.0
            
            active_cycle["ah_accumulated"] += abs(current) * dt / 3600.0
            active_cycle["wh_accumulated"] += (voltage * abs(current)) * dt / 3600.0
            active_cycle["last_timestamp_epoch"] = current_time
            active_cycle["rows"].append(row.copy())
            
            if inst_state == "Idle":
                active_cycle["consecutive_idle"] += 1
                active_cycle["consecutive_opposite"] = 0
            elif inst_state != active_type:
                active_cycle["consecutive_opposite"] += 1
                active_cycle["consecutive_idle"] = 0
            else:
                active_cycle["consecutive_idle"] = 0
                active_cycle["consecutive_opposite"] = 0
                
            if active_cycle["consecutive_idle"] >= 10 or active_cycle["consecutive_opposite"] >= 5:
                close_active_cycle(reason="transition")

def get_cycle_analytics_summary():
    history = load_cycle_history()
    
    active_type = active_cycle["type"] if active_cycle["type"] is not None else "Idle"
    
    # Defaults
    expected_soc = 50.0
    time_remaining_str = "N/A"
    comparison_insight = "Monitoring active..."
    degradation_trend = "Cycle history insufficient — monitoring only."
    confidence_score = "Low"
    confidence_reason = f"Insufficient cycle history (0/{len(history)} completed)."
    partial_status = "Normal"
    cell_imbalance_trend = "Normal"
    thermal_rise_trend = "Normal"
    
    deviation_level = "Normal deviation"
    state_analysis_msg = "Idle Monitoring: System is stable with no unusual drift."
    likely_fault_to_occur = "None"
    behavior_trend = "Stable"
    charging_expected_vs_actual = "N/A"
    discharging_expected_vs_actual = "N/A"
    idle_status_msg = "All parameters stable. No unusual drift compared to previous cycle history."
    charging_risks_active = []
    discharging_risks_active = []

    # Past cycles counts
    past_charges = [c for c in history if c["type"] == "Charge"]
    past_discharges = [c for c in history if c["type"] == "Discharge"]
    
    total_past_of_type = len(past_charges) if active_type == "Charge" else (len(past_discharges) if active_type == "Discharge" else len(history))
    if total_past_of_type >= 5:
        confidence_score = "High"
        confidence_reason = f"Cycle history sufficient ({total_past_of_type} completed)."
    elif total_past_of_type >= 1:
        confidence_score = "Medium"
        confidence_reason = f"Comparing with {total_past_of_type} completed cycle(s)."
    else:
        confidence_score = "Low"
        confidence_reason = "No previous completed cycles. Monitoring only."

    # Averages
    avg_duration_per_soc = 3600.0 / 40.0
    avg_temp_rise_per_soc = 3.5 / 40.0
    avg_spread_end = 0.02
    avg_avg_current = 7.5
    avg_voltage_change_per_soc = 8.0 / 40.0
    avg_rate = 0.0174
    avg_efficiency = 95.0

    if active_type == "Charge":
        if past_charges:
            count = len(past_charges)
            avg_duration_per_soc = sum(c["duration_sec"] / max(0.1, abs(c["soc_change"])) for c in past_charges) / count
            avg_temp_rise_per_soc = sum(c["temp_rise"] / max(0.1, abs(c["soc_change"])) for c in past_charges) / count
            avg_spread_end = sum(c["voltage_spread_end"] for c in past_charges) / count
            avg_avg_current = sum(abs(c["avg_current"]) for c in past_charges) / count
            avg_voltage_change_per_soc = sum((c["end_voltage"] - c["start_voltage"]) / max(0.1, abs(c["soc_change"])) for c in past_charges) / count
            avg_rate = sum(abs(c["soc_change"]) / max(1.0, c["duration_sec"]) for c in past_charges) / count
            avg_efficiency = 95.0
        else:
            avg_rate = 0.0174
            avg_temp_rise_per_soc = 3.5 / 40.0
            avg_spread_end = 0.02
            avg_duration_per_soc = 90.0
            avg_avg_current = 7.5
            avg_voltage_change_per_soc = 0.20
            avg_efficiency = 95.0
    elif active_type == "Discharge":
        if past_discharges:
            count = len(past_discharges)
            avg_duration_per_soc = sum(c["duration_sec"] / max(0.1, abs(c["soc_change"])) for c in past_discharges) / count
            avg_temp_rise_per_soc = sum(c["temp_rise"] / max(0.1, abs(c["soc_change"])) for c in past_discharges) / count
            avg_spread_end = sum(c["voltage_spread_end"] for c in past_discharges) / count
            avg_avg_current = sum(abs(c["avg_current"]) for c in past_discharges) / count
            avg_voltage_change_per_soc = sum((c["start_voltage"] - c["end_voltage"]) / max(0.1, abs(c["soc_change"])) for c in past_discharges) / count
            avg_rate = sum(abs(c["soc_change"]) / max(1.0, c["duration_sec"]) for c in past_discharges) / count
            avg_efficiency = 91.0
        else:
            avg_rate = 0.0199
            avg_temp_rise_per_soc = 4.0 / 35.0
            avg_spread_end = 0.03
            avg_duration_per_soc = 85.0
            avg_avg_current = 8.5
            avg_voltage_change_per_soc = 0.034
            avg_efficiency = 91.0

    # Trend
    if len(history) >= 2:
        prev_history = history[:-1]
        last_cycle = history[-1]
        avg_prev_spread = sum(c["voltage_spread_end"] for c in prev_history) / len(prev_history)
        if last_cycle["voltage_spread_end"] > avg_prev_spread * 1.10:
            behavior_trend = "Degrading"
            cell_imbalance_trend = "Increasing imbalance trend"
        elif last_cycle["voltage_spread_end"] < avg_prev_spread * 0.90:
            behavior_trend = "Improving"
            cell_imbalance_trend = "Improving balance trend"
        else:
            behavior_trend = "Stable"
            
        avg_prev_temp_rise = sum(c["temp_rise"] for c in prev_history) / len(prev_history)
        if last_cycle["temp_rise"] > avg_prev_temp_rise * 1.15:
            behavior_trend = "Degrading"
            thermal_rise_trend = "Increasing thermal rise"

    # Active charging/discharging/idle details
    charging_analysis = {}
    discharging_analysis = {}
    idle_analysis = {}
    
    if active_type == "Charge" and active_cycle["rows"]:
        rows = active_cycle["rows"]
        latest_row = rows[-1]
        soc = float(latest_row.get("soc", 50.0))
        current = float(latest_row.get("current", 0.0))
        voltage = float(latest_row.get("voltage", 25.6))
        temp_val = latest_row.get("temperature")
        temp = float(temp_val) if temp_val is not None else 25.0
        
        elapsed_sec = float(time.time() - active_cycle["start_time_epoch"])
        start_soc = active_cycle["start_soc"]
        start_voltage = active_cycle["start_voltage"]
        start_t_val = rows[0].get("temperature")
        start_t = float(start_t_val) if start_t_val is not None else temp
        temp_rise = temp - start_t
        
        cell_voltages = [float(latest_row.get(f"cell_v{i}", 3.2)) for i in range(1, 9)]
        current_spread = max(cell_voltages) - min(cell_voltages) if cell_voltages else 0.0
        
        soc_diff = abs(soc - start_soc)
        expected_soc = start_soc + (avg_rate * elapsed_sec)
        expected_soc = max(0.0, min(100.0, expected_soc))
        
        current_rate = soc_diff / elapsed_sec if elapsed_sec > 10 else avg_rate
        soc_left = max(0.0, 96.0 - soc)
        est_sec_left = soc_left / current_rate if current_rate > 0.0001 else 3600
        time_remaining_str = f"{int(est_sec_left/60)}m {int(est_sec_left%60)}s"
        
        expected_duration = avg_duration_per_soc * soc_diff
        duration_deviation = ((elapsed_sec - expected_duration) / max(1.0, expected_duration)) * 100 if soc_diff > 1 else 0.0
        
        expected_voltage_rise = avg_voltage_change_per_soc * soc_diff
        actual_voltage_rise = voltage - start_voltage
        voltage_rise_dev = ((actual_voltage_rise - expected_voltage_rise) / max(0.1, expected_voltage_rise)) * 100 if soc_diff > 1 else 0.0
        
        expected_temp_rise = avg_temp_rise_per_soc * soc_diff
        temp_dev = ((temp_rise - expected_temp_rise) / max(0.1, expected_temp_rise)) * 100 if soc_diff > 1 else 0.0
        
        actual_efficiency = max(70.0, min(99.0, avg_efficiency - (current_spread * 15.0) - (temp_rise * 0.2)))
        efficiency_diff = actual_efficiency - avg_efficiency
        
        # Risk thresholds & classification
        deviation_reasons = []
        if elapsed_sec > 15.0:
            if duration_deviation > 15.0 or (soc_diff > 2 and current_rate < avg_rate * 0.85):
                charging_risks_active.append("Slow SOC recovery")
                charging_risks_active.append("Charging efficiency degradation")
                likely_fault_to_occur = "Capacity Degradation"
                deviation_level = "Possible degradation"
                deviation_reasons.append(f"Actual SOC recovery is lower than expected by {abs(duration_deviation):.0f}% compared to previous cycle history")
                
            if temp_rise > expected_temp_rise * 1.25 and temp_rise > 3.0:
                charging_risks_active.append("Excessive temperature rise")
                likely_fault_to_occur = "Overtemperature Risk"
                deviation_level = "High deviation"
                deviation_reasons.append(f"Temperature rise is {temp_dev:.0f}% higher than previous cycle history")
                
            if current_spread > avg_spread_end * 1.30 and current_spread > 0.08:
                charging_risks_active.append("Cell imbalance during charging")
                charging_risks_active.append("Possible weak cell behavior")
                likely_fault_to_occur = "Cell Imbalance"
                deviation_level = "Possible weak cell behavior"
                deviation_reasons.append(f"Cell voltage spread is {((current_spread - avg_spread_end)/avg_spread_end)*100:.0f}% higher than previous cycle history")
                
            if max(cell_voltages) >= 4.15:
                charging_risks_active.append("Overvoltage risk")
                charging_risks_active.append("Abnormal voltage rise")
                likely_fault_to_occur = "Overvoltage Risk"
                deviation_level = "High deviation"
                deviation_reasons.append("Maximum cell voltage reached critical threshold (4.15V)")
                
        if deviation_reasons:
            state_analysis_msg = "Charging Analysis: " + ". ".join(deviation_reasons) + " Possible charging degradation risk detected."
        else:
            deviation_level = "Normal deviation"
            state_analysis_msg = "Charging Analysis: Charging normally. Current parameters are within expected deviations compared to previous cycle history."
            
        charging_expected_vs_actual = f"Expected SOC: {expected_soc:.1f}% | Actual SOC: {soc:.1f}% (Diff: {soc - expected_soc:+.1f}%)"
            
        charging_analysis = {
            "expected_soc_rate": f"{avg_rate*100:.3f}%/s",
            "actual_soc_rate": f"{current_rate*100:.3f}%/s",
            "soc_rate_diff_pct": round(((current_rate - avg_rate)/avg_rate)*100, 1),
            "soc_reached": f"{soc:.1f}%",
            "expected_duration_str": f"{int(expected_duration/60)}m {int(expected_duration%60)}s",
            "actual_duration_str": f"{int(elapsed_sec/60)}m {int(elapsed_sec%60)}s",
            "duration_deviation_pct": round(duration_deviation, 1),
            "expected_voltage_rise": f"{expected_voltage_rise:.3f} V",
            "actual_voltage_rise": f"{actual_voltage_rise:.3f} V",
            "voltage_rise_diff_pct": round(voltage_rise_dev, 1),
            "expected_temp_rise": f"{expected_temp_rise:.1f} °C",
            "actual_temp_rise": f"{temp_rise:.1f} °C",
            "temp_rise_diff_pct": round(temp_dev, 1),
            "expected_efficiency": f"{avg_efficiency:.1f}%",
            "actual_efficiency": f"{actual_efficiency:.1f}%",
            "efficiency_diff_pct": round(efficiency_diff, 1),
            "risks": charging_risks_active
        }
        
    elif active_type == "Discharge" and active_cycle["rows"]:
        rows = active_cycle["rows"]
        latest_row = rows[-1]
        soc = float(latest_row.get("soc", 50.0))
        current = float(latest_row.get("current", 0.0))
        voltage = float(latest_row.get("voltage", 25.6))
        temp_val = latest_row.get("temperature")
        temp = float(temp_val) if temp_val is not None else 25.0
        
        elapsed_sec = float(time.time() - active_cycle["start_time_epoch"])
        start_soc = active_cycle["start_soc"]
        start_voltage = active_cycle["start_voltage"]
        start_t_val = rows[0].get("temperature")
        start_t = float(start_t_val) if start_t_val is not None else temp
        temp_rise = temp - start_t
        
        cell_voltages = [float(latest_row.get(f"cell_v{i}", 3.2)) for i in range(1, 9)]
        current_spread = max(cell_voltages) - min(cell_voltages) if cell_voltages else 0.0
        
        soc_diff = abs(soc - start_soc)
        expected_soc = start_soc - (avg_rate * elapsed_sec)
        expected_soc = max(0.0, min(100.0, expected_soc))
        
        current_rate = soc_diff / elapsed_sec if elapsed_sec > 10 else avg_rate
        soc_left = max(0.0, soc - 35.0)
        est_sec_left = soc_left / current_rate if current_rate > 0.0001 else 3600
        time_remaining_str = f"{int(est_sec_left/60)}m {int(est_sec_left%60)}s"
        
        expected_duration = avg_duration_per_soc * soc_diff
        duration_deviation = ((elapsed_sec - expected_duration) / max(1.0, expected_duration)) * 100 if soc_diff > 1 else 0.0
        
        expected_voltage_sag = avg_voltage_change_per_soc * soc_diff
        actual_voltage_sag = start_voltage - voltage
        voltage_sag_dev = ((actual_voltage_sag - expected_voltage_sag) / max(0.1, expected_voltage_sag)) * 100 if soc_diff > 1 else 0.0
        
        expected_temp_rise = avg_temp_rise_per_soc * soc_diff
        temp_dev = ((temp_rise - expected_temp_rise) / max(0.1, expected_temp_rise)) * 100 if soc_diff > 1 else 0.0
        
        actual_efficiency = max(65.0, min(99.0, avg_efficiency - (current_spread * 12.0) - (temp_rise * 0.15)))
        efficiency_diff = actual_efficiency - avg_efficiency
        
        deviation_reasons = []
        if elapsed_sec > 15.0:
            if duration_deviation < -15.0 or (soc_diff > 2 and current_rate > avg_rate * 1.15):
                discharging_risks_active.append("Fast SOC drop")
                discharging_risks_active.append("Possible degradation trend")
                likely_fault_to_occur = "Capacity Degradation"
                deviation_level = "Possible degradation"
                deviation_reasons.append(f"SOC drop rate is {((current_rate - avg_rate)/avg_rate)*100:.0f}% faster than previous cycle history")
                
            if expected_voltage_sag > 0.05 and actual_voltage_sag > 0.1:
                if voltage_sag_dev > 20.0 and actual_voltage_sag > 0.8:
                    discharging_risks_active.append("High voltage sag")
                    discharging_risks_active.append("Weak cell behavior")
                    likely_fault_to_occur = "Weak Cell"
                    deviation_level = "Possible weak cell behavior"
                    deviation_reasons.append(f"Voltage sag is {voltage_sag_dev:.0f}% higher than previous cycle history")
                    
            if temp_rise > expected_temp_rise * 1.25 and temp_rise > 3.0:
                discharging_risks_active.append("Excessive temperature rise")
                likely_fault_to_occur = "Overtemperature Risk"
                deviation_level = "High deviation"
                deviation_reasons.append(f"Temperature rise is {temp_dev:.0f}% higher than previous cycle history")
                
            if min(cell_voltages) <= 3.0:
                discharging_risks_active.append("Undervoltage risk")
                likely_fault_to_occur = "Undervoltage Risk"
                deviation_level = "High deviation"
                deviation_reasons.append("Minimum cell voltage reached critical threshold (3.0V)")
                
        if deviation_reasons:
            state_analysis_msg = "Discharging Analysis: " + ". ".join(deviation_reasons) + " Possible weak cell or high internal resistance behavior detected."
        else:
            deviation_level = "Normal deviation"
            state_analysis_msg = "Discharging Analysis: Discharging normally. Current parameters are within expected deviations compared to previous cycle history."
            
        discharging_expected_vs_actual = f"Expected Sag: {expected_voltage_sag:.2f}V | Actual Sag: {actual_voltage_sag:.2f}V (Diff: {actual_voltage_sag - expected_voltage_sag:+.2f}V)"
            
        discharging_analysis = {
            "expected_soc_drop_rate": f"{avg_rate*100:.3f}%/s",
            "actual_soc_drop_rate": f"{current_rate*100:.3f}%/s",
            "soc_drop_rate_diff_pct": round(((current_rate - avg_rate)/avg_rate)*100, 1),
            "soc_drop": f"{soc_diff:.1f}%",
            "expected_duration_str": f"{int(expected_duration/60)}m {int(expected_duration%60)}s",
            "actual_duration_str": f"{int(elapsed_sec/60)}m {int(elapsed_sec%60)}s",
            "duration_deviation_pct": round(duration_deviation, 1),
            "expected_voltage_sag": f"{expected_voltage_sag:.3f} V",
            "actual_voltage_sag": f"{actual_voltage_sag:.3f} V",
            "voltage_sag_diff_pct": round(voltage_sag_dev, 1),
            "expected_temp_rise": f"{expected_temp_rise:.1f} °C",
            "actual_temp_rise": f"{temp_rise:.1f} °C",
            "temp_rise_diff_pct": round(temp_dev, 1),
            "expected_efficiency": f"{avg_efficiency:.1f}%",
            "actual_efficiency": f"{actual_efficiency:.1f}%",
            "efficiency_diff_pct": round(efficiency_diff, 1),
            "current_draw_pattern": "Normal" if abs(current) < avg_avg_current * 1.25 else "Abnormal High Current",
            "risks": discharging_risks_active
        }
        
    else: # Idle state
        v = 25.6
        t = 25.0
        spread = 0.01
        
        if latest_raw_row:
            v = float(latest_raw_row.get("voltage", 25.6))
            t_val = latest_raw_row.get("temperature")
            t = float(t_val) if t_val is not None else 25.0
            cell_v = [float(latest_raw_row.get(f"cell_v{i}", 3.2)) for i in range(1, 9)]
            spread = max(cell_v) - min(cell_v) if cell_v else 0.0
            
        unusual_drift = "None"
        if spread > 0.12:
            deviation_level = "Possible weak cell behavior"
            state_analysis_msg = f"Idle Analysis: Cell voltage spread is high ({spread:.3f}V) while system is in rest state. Possible self-discharge or cell imbalance drift."
            idle_status_msg = f"Abnormal cell spread ({spread:.3f}V) detected in rest state."
            likely_fault_to_occur = "Cell Imbalance"
            unusual_drift = "Cell spread drift detected"
        else:
            deviation_level = "Normal deviation"
            state_analysis_msg = "Idle Monitoring: System is stable with no unusual drift."
            idle_status_msg = "All parameters stable. No unusual drift compared to previous cycle history."
            
        idle_analysis = {
            "status": "Normal" if unusual_drift == "None" else "Abnormal",
            "voltage_stable": True,
            "current_stable": True,
            "soc_stable": True,
            "temp_stable": True,
            "unusual_drift": unusual_drift,
            "voltage_drift": "0.005 V" if unusual_drift == "None" else "0.012 V",
            "temp_drift": "0.1 °C",
            "soc_drift": "0.0 %",
            "msg": idle_status_msg
        }

    # Final degradation trend formatting
    if len(history) < 3:
        degradation_trend = "Cycle history insufficient — monitoring only."
    elif behavior_trend == "Degradating":
        degradation_trend = "Possible degradation trend detected based on previous cycle comparison."
    else:
        degradation_trend = "Battery performance stable across completed cycles."

    return {
        "active_cycle_type": active_type,
        "active_cycle_id": active_cycle["cycle_id"] if active_cycle["cycle_id"] is not None else 0,
        "elapsed_time_str": f"{int((time.time() - active_cycle['start_time_epoch']) / 60)}m {int((time.time() - active_cycle['start_time_epoch']) % 60)}s" if active_cycle["start_time_epoch"] is not None else "0m",
        "current_soc": round(active_cycle["rows"][-1].get("soc", 50.0), 1) if active_cycle["rows"] else expected_soc,
        "expected_soc": round(expected_soc, 1),
        "time_remaining_str": time_remaining_str,
        "comparison_insight": comparison_insight,
        "partial_status": partial_status,
        "degradation_trend": degradation_trend,
        "cell_imbalance_trend": cell_imbalance_trend,
        "thermal_rise_trend": thermal_rise_trend,
        "confidence_score": confidence_score,
        "confidence_reason": confidence_reason,
        "deviation_level": deviation_level,
        "state_analysis_msg": state_analysis_msg,
        "likely_fault_to_occur": likely_fault_to_occur,
        "behavior_trend": behavior_trend,
        "charging_expected_vs_actual": charging_expected_vs_actual,
        "discharging_expected_vs_actual": discharging_expected_vs_actual,
        "idle_status_msg": idle_status_msg,
        "charging_risks_active": charging_risks_active,
        "discharging_risks_active": discharging_risks_active,
        "charging_analysis": charging_analysis,
        "discharging_analysis": discharging_analysis,
        "idle_analysis": idle_analysis
    }

# Simple CORS headers helper (allows local network frontend connections)
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route('/api/telemetry', methods=['POST'])
def add_telemetry():
    """
    Accepts a single new row of telemetry from sensors or simulator.
    Dual logs the row, validates it, maintains sliding buffer, and runs inference.
    """
    _token = os.environ.get("INGEST_TOKEN")
    if _token and request.headers.get("X-Ingest-Token") != _token:
        return jsonify({"error": "unauthorized"}), 401

    global latest_raw_row
    try:
        new_row = request.json
        if not new_row:
            return jsonify({"error": "No data provided"}), 400
            
        # 1. Update latest raw row
        latest_raw_row = new_row
        
        # Update debug state from payload
        with bms_debug_lock:
            if "bluetooth_connected" in new_row:
                bms_debug_state["bluetooth_connected"] = bool(new_row.get("bluetooth_connected", False))
                if bms_debug_state["bluetooth_connected"]:
                    bms_debug_state["last_packet_time"] = time.time()
                    bms_debug_state["is_stale"] = False
                bms_debug_state["raw_packet_hex"] = new_row.get("raw_packet_hex", "N/A")
                bms_debug_state["packet_count"] = int(new_row.get("packet_count", bms_debug_state["packet_count"]))
                bms_debug_state["parse_error_count"] = int(new_row.get("parse_error_count", bms_debug_state["parse_error_count"]))
                bms_debug_state["last_parse_error"] = new_row.get("last_parse_error", "N/A")
                bms_debug_state["current_raw_value"] = int(new_row.get("current_raw_value", 0))
                bms_debug_state["current_scaled_value"] = float(new_row.get("current_scaled_value", 0.0))
                bms_debug_state["current_valid"] = bool(new_row.get("current_valid", False))
                bms_debug_state["voltage_valid"] = bool(new_row.get("voltage_valid", False))
                bms_debug_state["temperature_valid"] = bool(new_row.get("temperature_valid", False))
                bms_debug_state["cell_voltage_valid"] = bool(new_row.get("cell_voltage_valid", False))
            else:
                # If we get a raw post from local simulator without BLE header (backward compatible)
                bms_debug_state["bluetooth_connected"] = True
                bms_debug_state["last_packet_time"] = time.time()
                bms_debug_state["is_stale"] = False
                
                v = float(new_row.get("voltage", 0.0))
                i = float(new_row.get("current", 0.0))
                t = float(new_row.get("temperature", 0.0))
                
                bms_debug_state["voltage_valid"] = (15.0 <= v <= 40.0)
                bms_debug_state["current_valid"] = (-120.0 <= i <= 120.0)
                bms_debug_state["temperature_valid"] = (-40.0 <= t <= 120.0)
                
                cell_ok = True
                for idx in range(1, 9):
                    cell_val = float(new_row.get(f"cell_v{idx}", 3.2))
                    if not (2.0 <= cell_val <= 4.6):
                        cell_ok = False
                bms_debug_state["cell_voltage_valid"] = cell_ok
                
                bms_debug_state["current_scaled_value"] = i
                bms_debug_state["current_raw_value"] = int(i * 100)
                bms_debug_state["raw_packet_hex"] = "SIMULATION_DATA"
                bms_debug_state["packet_count"] += 1
                
            bms_debug_state["dashboard_update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. Log raw row immediately
        log_to_csv(RAW_LOG_PATH, new_row)
        
        # 3. Check stale status and physical validity
        check_stale_data()
        
        is_valid = True
        with bms_debug_lock:
            if (not bms_debug_state["current_valid"] or 
                not bms_debug_state["voltage_valid"] or 
                not bms_debug_state["temperature_valid"] or 
                not bms_debug_state["cell_voltage_valid"] or
                bms_debug_state["is_stale"] or
                not bms_debug_state["bluetooth_connected"]):
                is_valid = False
                
        if not is_valid:
            avg_delta_v = (history_stats["cumulative_delta_v"] / history_stats["total_rows_processed"]) if history_stats["total_rows_processed"] > 0 else 0.0
            
            run_alerts_evaluation()
            
            with bms_debug_lock:
                bluetooth_connected = bms_debug_state["bluetooth_connected"]
                is_stale = bms_debug_state["is_stale"]
                data_age_seconds = bms_debug_state["data_age_seconds"]
                last_packet_time = bms_debug_state["last_packet_time"]
                
            return jsonify({
                "buffer_length": len(telemetry_buffer),
                "status": "Waiting for valid live data",
                "prediction": None,
                "live_prediction": None,
                "live_row": telemetry_buffer[-1] if telemetry_buffer else None,
                "raw_row": latest_raw_row,
                "learning_status": get_learning_status(),
                "cycle_analytics": get_cycle_analytics_summary(),
                "bluetooth_connected": bluetooth_connected,
                "is_stale": is_stale,
                "data_age_seconds": data_age_seconds,
                "last_packet_time": last_packet_time,
                "active_alerts": active_alerts,
                "alert_history": get_formatted_alert_history(),
                "historical_stats": {
                    "total_rows_processed": history_stats["total_rows_processed"],
                    "max_temp": history_stats["max_temp"] if history_stats["max_temp"] != -999.0 else None,
                    "min_temp": history_stats["min_temp"] if history_stats["min_temp"] != 999.0 else None,
                    "max_voltage": history_stats["max_voltage"] if history_stats["max_voltage"] != -999.0 else None,
                    "min_voltage": history_stats["min_voltage"] if history_stats["min_voltage"] != 999.0 else None,
                    "avg_delta_v": round(avg_delta_v, 4),
                    "mode_counts": history_stats["mode_counts"],
                    "fault_counts": history_stats["fault_counts"],
                    "cumulative_energy_wh": round(history_stats["cumulative_energy_wh"], 3)
                }
            })
            
        # 4. Apply EMA Signal Smoothing (Noise Filtering)
        global filtered_state
        smoothed_row = new_row.copy()
        
        keys_to_smooth = ["voltage", "current", "temperature"] + [f"cell_v{i}" for i in range(1, 9)]
        for key in keys_to_smooth:
            if key in new_row:
                if new_row[key] is None:
                    smoothed_row[key] = None
                    continue
                val = float(new_row[key])
                if key not in filtered_state or filtered_state[key] is None:
                    filtered_state[key] = val
                else:
                    # Apply instant updates for fast changing voltage and current; smooth temperature
                    alpha = 1.0 if (key in ["voltage", "current"] or key.startswith("cell_v")) else 0.3
                    filtered_state[key] = round(alpha * val + (1.0 - alpha) * filtered_state[key], 4)
                smoothed_row[key] = filtered_state[key]
                
        cell_voltages = [smoothed_row[f"cell_v{i}"] for i in range(1, 9)]
        smoothed_row["delta_v"] = round(max(cell_voltages) - min(cell_voltages), 4)

        # Extraction and debug logging helper
        def extract_raw_temp_bytes_from_hex(raw_hex):
            try:
                if not raw_hex or raw_hex == "N/A" or raw_hex == "SIMULATION_DATA":
                    return "N/A"
                data_bytes = bytes.fromhex(raw_hex)
                if len(data_bytes) >= 27 and data_bytes[0] == 0xDD and data_bytes[2] == 0x03:
                    ntc_count = data_bytes[26]
                    temp_bytes = data_bytes[27 : 27 + ntc_count * 2]
                    return temp_bytes.hex().upper()
            except Exception:
                pass
            return "N/A"

        # Log temperature debug info
        raw_hex = new_row.get("raw_packet_hex", "N/A")
        raw_temp_bytes = extract_raw_temp_bytes_from_hex(raw_hex)
        print(f"[DEBUG TEMP] Raw Temp Bytes: {raw_temp_bytes} | Parsed: {new_row.get('temperature')} | Sent to frontend: {smoothed_row.get('temperature')}")

        # Log voltage comparison debug info
        bms_voltage = float(new_row.get("voltage", 0.0))
        cell_voltages_list = [float(new_row[f"cell_v{i}"]) for i in range(1, 9) if new_row.get(f"cell_v{i}") is not None]
        cell_sum = sum(cell_voltages_list)
        sent_voltage = float(smoothed_row.get("voltage", 0.0))
        v_diff = abs(bms_voltage - cell_sum)
        print(f"[DEBUG VOLT] BMS Pack Voltage: {bms_voltage:.2f}V | Cell Voltages Sum: {cell_sum:.3f}V | Sent Voltage: {sent_voltage:.2f}V | Difference: {v_diff:.3f}V")

        # Log smoothed row
        log_to_csv(FILTERED_LOG_PATH, smoothed_row)
        
        # Track cycle info
        update_cycle_tracking(smoothed_row)
        
        # Add new row to sliding inference buffer
        telemetry_buffer.append(smoothed_row)
        if len(telemetry_buffer) > BUFFER_MAX_SIZE:
            telemetry_buffer.pop(0)
            
        prediction = None
        if len(telemetry_buffer) == BUFFER_MAX_SIZE:
            df_60 = pd.DataFrame(telemetry_buffer)
            prediction = run_inference(df_60, MODEL_DIR)
            
        update_history_stats(smoothed_row, prediction)
        
        with learning_lock:
            learning_row = smoothed_row.copy()
            if prediction:
                learning_row["model_predicted_label"] = prediction.get("Raw Prediction", "Normal")
                learning_row["model_predicted_conf"] = prediction.get("Confidence Score", "100.0%")
            else:
                learning_row["model_predicted_label"] = "Normal"
                learning_row["model_predicted_conf"] = "100.0%"
            learning_buffer.append(learning_row)
            
        avg_delta_v = (history_stats["cumulative_delta_v"] / history_stats["total_rows_processed"]) if history_stats["total_rows_processed"] > 0 else 0.0
        
        run_alerts_evaluation()
        
        with bms_debug_lock:
            bluetooth_connected = bms_debug_state["bluetooth_connected"]
            is_stale = bms_debug_state["is_stale"]
            data_age_seconds = bms_debug_state["data_age_seconds"]
            last_packet_time = bms_debug_state["last_packet_time"]
            
        # Physics-informed prediction override integration
        chem_type = detect_chemistry(smoothed_row)
        cfg = CHEMISTRY_CONFIGS[chem_type]
        live_prediction = get_physics_informed_prediction(smoothed_row, prediction, cfg, chem_type)

        response_data = {
            "buffer_length": len(telemetry_buffer),
            "status": "success" if prediction else "accumulating",
            "prediction": prediction,
            "live_prediction": live_prediction,
            "live_row": smoothed_row,
            "raw_row": latest_raw_row,
            "learning_status": get_learning_status(),
            "cycle_analytics": get_cycle_analytics_summary(),
            "bluetooth_connected": bluetooth_connected,
            "is_stale": is_stale,
            "data_age_seconds": data_age_seconds,
            "last_packet_time": last_packet_time,
            "active_alerts": active_alerts,
            "alert_history": get_formatted_alert_history(),
            "historical_stats": {
                "total_rows_processed": history_stats["total_rows_processed"],
                "max_temp": history_stats["max_temp"] if history_stats["max_temp"] != -999.0 else None,
                "min_temp": history_stats["min_temp"] if history_stats["min_temp"] != 999.0 else None,
                "max_voltage": history_stats["max_voltage"] if history_stats["max_voltage"] != -999.0 else None,
                "min_voltage": history_stats["min_voltage"] if history_stats["min_voltage"] != 999.0 else None,
                "avg_delta_v": round(avg_delta_v, 4),
                "mode_counts": history_stats["mode_counts"],
                "fault_counts": history_stats["fault_counts"],
                "cumulative_energy_wh": round(history_stats["cumulative_energy_wh"], 3)
            }
        }
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_error.log")
        with open(log_path, "a") as f:
            f.write(f"\n--- ERROR ON POST telemetry ---\n")
            traceback.print_exc(file=f)
        return jsonify({"error": str(e)}), 500

@app.route('/api/telemetry', methods=['GET'])
def get_current_status():
    """
    Returns the current buffer size, latest prediction, and running historical statistics.
    """
    try:
        check_stale_data()
        
        run_alerts_evaluation()
        
        with bms_debug_lock:
            bluetooth_connected = bms_debug_state["bluetooth_connected"]
            is_stale = bms_debug_state["is_stale"]
            data_age_seconds = bms_debug_state["data_age_seconds"]
            last_packet_time = bms_debug_state["last_packet_time"]
            
        prediction = None
        if not is_stale and bluetooth_connected and len(telemetry_buffer) == BUFFER_MAX_SIZE:
            df_60 = pd.DataFrame(telemetry_buffer)
            prediction = run_inference(df_60, MODEL_DIR)
            
        avg_delta_v = (history_stats["cumulative_delta_v"] / history_stats["total_rows_processed"]) if history_stats["total_rows_processed"] > 0 else 0.0
        
        live_prediction = None
        if telemetry_buffer and not is_stale:
            latest_row = telemetry_buffer[-1]
            chem_type = detect_chemistry(latest_row)
            cfg = CHEMISTRY_CONFIGS[chem_type]
            live_prediction = get_physics_informed_prediction(latest_row, prediction, cfg, chem_type)
            
        active_prof = get_active_profile_config()
        current_chem = active_prof.get("chemistry_name", "Unknown") if active_prof else "Default"

        return jsonify({
            "buffer_length": len(telemetry_buffer),
            "status": "success" if (prediction and not is_stale) else ("Waiting for valid live data" if is_stale else "accumulating"),
            "prediction": prediction if not is_stale else None,
            "live_prediction": live_prediction,
            "active_profile_name": current_chem,
            "live_row": telemetry_buffer[-1] if (telemetry_buffer and not is_stale) else None,
            "raw_row": latest_raw_row,
            "learning_status": get_learning_status(),
            "cycle_analytics": get_cycle_analytics_summary(),
            "bluetooth_connected": bluetooth_connected,
            "is_stale": is_stale,
            "data_age_seconds": data_age_seconds,
            "last_packet_time": last_packet_time,
            "active_alerts": active_alerts,
            "alert_history": get_formatted_alert_history(),
            "historical_stats": {
                "total_rows_processed": history_stats["total_rows_processed"],
                "max_temp": history_stats["max_temp"] if history_stats["max_temp"] != -999.0 else None,
                "min_temp": history_stats["min_temp"] if history_stats["min_temp"] != 999.0 else None,
                "max_voltage": history_stats["max_voltage"] if history_stats["max_voltage"] != -999.0 else None,
                "min_voltage": history_stats["min_voltage"] if history_stats["min_voltage"] != 999.0 else None,
                "avg_delta_v": round(avg_delta_v, 4),
                "mode_counts": history_stats["mode_counts"],
                "fault_counts": history_stats["fault_counts"],
                "cumulative_energy_wh": round(history_stats["cumulative_energy_wh"], 3)
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """
    Exposes currently active alerts and full alert history.
    """
    try:
        run_alerts_evaluation()
        with alert_lock:
            # Determine system level
            sys_level = "NORMAL"
            for a in active_alerts:
                if a["level"] == "CRITICAL":
                    sys_level = "CRITICAL"
                    break
                elif a["level"] == "WARNING":
                    sys_level = "WARNING"
            
            return jsonify({
                "active_alerts": active_alerts,
                "alert_history": get_formatted_alert_history(),
                "system_level": sys_level
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug_bms', methods=['GET'])
def debug_bms():
    check_stale_data()
    with bms_debug_lock:
        return jsonify(bms_debug_state.copy())

@app.route('/api/predict_file', methods=['POST'])
def predict_excel():
    """
    Upload an Excel file or pass a local file name to run predictions on the latest 60 rows.
    """
    try:
        data = request.json
        filename = data.get("filename") if data else None
        
        if not filename:
            files = [f for f in os.listdir(MODEL_DIR) if f.endswith('.xlsx')]
            if not files:
                return jsonify({"error": "No Excel telemetry files found."}), 400
            filepath = os.path.join(MODEL_DIR, files[0])
        else:
            filepath = os.path.join(MODEL_DIR, filename)
            
        if not os.path.exists(filepath):
            return jsonify({"error": f"File {filename} not found."}), 404
            
        xls = pd.ExcelFile(filepath)
        df_full = pd.read_excel(filepath, sheet_name=xls.sheet_names[0])
        if len(df_full) < 60:
            return jsonify({"error": f"File contains only {len(df_full)} rows, need at least 60."}), 400
            
        df_60 = df_full.iloc[-60:].reset_index(drop=True)
        prediction = run_inference(df_60, MODEL_DIR)
        
        return jsonify({
            "status": "success",
            "source_file": os.path.basename(filepath),
            "prediction": prediction
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload_datasheet', methods=['POST'])
def upload_datasheet():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(MODEL_DIR, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # Parse PDF
        params = datasheet_parser.extract_parameters_from_pdf(file_path)
        if params:
            # Save to active_profile.json
            profile = datasheet_parser.save_active_profile(params, MODEL_DIR)
            
            # Immediately update the loaded CHEMISTRY_CONFIGS
            import bms_dashboard_backend
            bms_dashboard_backend.CHEMISTRY_CONFIGS["Active_Profile"] = profile
            
            return jsonify({
                "status": "success",
                "message": "Datasheet successfully parsed",
                "parameters": params,
                "profile": profile
            })
        else:
            return jsonify({"status": "error", "message": "Failed to parse parameters from PDF"}), 500
            
    return jsonify({"status": "error", "message": "Invalid file format, please upload a PDF"}), 400

@app.route('/api/reset', methods=['POST'])
def reset_buffer():
    """Resets both the sliding window buffer, active alerts, alert history, and the historical statistics."""
    global history_stats, active_alerts, alert_history
    telemetry_buffer.clear()
    with alert_lock:
        active_alerts.clear()
        alert_history.clear()
    history_stats = {
        "total_rows_processed": 0,
        "max_temp": -999.0,
        "min_temp": 999.0,
        "max_voltage": -999.0,
        "min_voltage": 999.0,
        "cumulative_delta_v": 0.0,
        "mode_counts": {"ACCEL": 0, "CRUISE": 0, "DECEL": 0, "IDLE": 0},
        "fault_counts": {"Normal": 0, "Cell Imbalance": 0, "Weak Cell": 0, "Overvoltage Risk": 0, "Undervoltage Risk": 0, "Overtemperature Risk": 0},
        "cumulative_energy_wh": 0.0
    }
    return jsonify({"status": "buffer and historical stats reset successful"})

@app.route('/api/download_raw_log', methods=['GET'])
def download_raw_log():
    """Exposes download of the raw telemetry CSV log via Wi-Fi."""
    if os.path.exists(RAW_LOG_PATH):
        return send_file(RAW_LOG_PATH, as_attachment=True, download_name="bms_telemetry_raw.csv")
    else:
        return jsonify({"error": "No raw log file found."}), 404

@app.route('/api/download_filtered_log', methods=['GET'])
def download_filtered_log():
    """Exposes download of the filtered telemetry CSV log via Wi-Fi."""
    if os.path.exists(FILTERED_LOG_PATH):
        return send_file(FILTERED_LOG_PATH, as_attachment=True, download_name="bms_telemetry_filtered.csv")
    else:
        return jsonify({"error": "No filtered log file found."}), 404

@app.route('/api/live-bms-data', methods=['GET', 'POST'])
def live_bms_data_mirror():
    """Mirrors `/api/telemetry` for compatibility with other frontend setups."""
    if request.method == 'POST':
        return add_telemetry()
    else:
        return get_current_status()

@app.route('/')
def serve_dashboard():
    """Serves the HTML dashboard frontend from the root URL."""
    return send_from_directory(MODEL_DIR, 'live_dashboard_v3.html')

@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
    else:
        status = init_ml_model(MODEL_DIR)
        response = jsonify(status)
        
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == '__main__':
    # Start the background learning scheduler thread
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    
    print("BMS Dashboard Python Backend starting...")
    init_ml_model(MODEL_DIR)
    
    print("Starting web server on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
