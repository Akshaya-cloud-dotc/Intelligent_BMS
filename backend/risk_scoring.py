import math
from datetime import datetime
from fault_risk_config import BASE_SEVERITY_WEIGHTS, CHEMISTRY_CONFIGS

# Global state for persistence and gradients
_persistence_counts = {}
_previous_telemetry = {}

def classify_confidence(confidence):
    """Fixed prediction confidence thresholds based on ML model output."""
    if confidence < 0.35:
        return "Low Confidence"
    elif confidence < 0.85:
        return "Moderate Confidence"
    else:
        return "High Confidence"

def classify_severity(severity):
    """Fixed severity thresholds."""
    if severity < 0.35:
        return "Low"
    elif severity < 0.65:
        return "Moderate"
    elif severity < 0.85:
        return "High"
    else:
        return "Critical"

def classify_risk(final_risk_score):
    """Fixed final operational risk thresholds."""
    if final_risk_score < 0.35:
        return "Low Risk"
    elif final_risk_score < 0.65:
        return "Moderate Risk"
    elif final_risk_score < 0.85:
        return "High Risk"
    else:
        return "Critical Risk"

def calculate_severity_ratio(measured_value, warning_threshold, critical_threshold, fault_direction="upper"):
    """Normalized severity calculation based on how far the value exceeded the warning limit."""
    if critical_threshold == warning_threshold:
        return 1.0 if (fault_direction == "upper" and measured_value >= warning_threshold) or (fault_direction == "lower" and measured_value <= warning_threshold) else 0.0

    if fault_direction == "upper":
        if measured_value <= warning_threshold:
            return 0.0
        ratio = (measured_value - warning_threshold) / (critical_threshold - warning_threshold)
    else:  # lower
        if measured_value >= warning_threshold:
            return 0.0
        ratio = (warning_threshold - measured_value) / (warning_threshold - critical_threshold)
        
    return max(0.0, min(1.0, ratio))

def calculate_dynamic_severity(base_severity, severity_ratio, persistence_factor=0.0, gradient_factor=0.0):
    """Combines base severity with distance-to-critical and persistence logic."""
    dynamic_severity = base_severity + severity_ratio * (1.0 - base_severity)
    
    # Include persistence: adjust severity upwards if persistent
    adjusted_severity = dynamic_severity * (0.8 + 0.2 * persistence_factor)
    
    return max(0.0, min(1.0, adjusted_severity))

def calculate_final_risk(confidence, severity, safety_override):
    """Final Risk Score is the product of ML confidence and physical severity, unless overridden."""
    if safety_override:
        return 1.0
        
    final_risk = confidence * severity
    return max(0.0, min(1.0, final_risk))

def detect_safety_override(measured_value, shutdown_threshold, fault_direction="upper"):
    if shutdown_threshold is None:
        return False
    if fault_direction == "upper" and measured_value >= shutdown_threshold:
        return True
    if fault_direction == "lower" and measured_value <= shutdown_threshold:
        return True
    return False

def _get_persistence_factor(fault_key, current_active):
    """Tracks how many consecutive samples a fault has been active."""
    global _persistence_counts
    
    if current_active:
        _persistence_counts[fault_key] = _persistence_counts.get(fault_key, 0) + 1
    else:
        # Cool down instead of immediate reset
        _persistence_counts[fault_key] = max(0, _persistence_counts.get(fault_key, 0) - 1)
        
    count = _persistence_counts[fault_key]
    factor = min(count / 5.0, 1.0) # 5 samples to reach max persistence
    return count, factor

def process_telemetry_risk(row, prediction_dict, chem_type, timestamp_epoch):
    """
    Master function to process a single telemetry row, the ML prediction output,
    and output the exact 15-field JSON response format.
    """
    global _previous_telemetry
    
    # 1. Extract Config
    cfg = CHEMISTRY_CONFIGS.get(chem_type, CHEMISTRY_CONFIGS["Default_Fallback"])
    
    # 2. Extract ML Probabilities & Confidence
    # ML model's prediction is treated as fixed confidence. We do not modify it.
    ml_fault = prediction_dict.get("Fault Prediction", "Normal") if prediction_dict else "Normal"
    ml_prob = prediction_dict.get("known_class_confidence", 1.0) if prediction_dict else 1.0
    is_ood = prediction_dict.get("is_ood", False) if prediction_dict else False
    ood_score = prediction_dict.get("ood_score", 0.0) if prediction_dict else 0.0
    
    if is_ood:
        ml_fault = "Unknown Fault / OOD"
        ml_prob = min(1.0, ood_score)
        
    # Extract Measurements
    voltage = float(row.get("voltage", 0.0))
    current = float(row.get("current", 0.0))
    temperature = float(row.get("temperature", 25.0))
    delta_v = float(row.get("delta_v", 0.0))
    
    cell_voltages = []
    for i in range(1, 9):
        cv = row.get(f"cell_v{i}")
        if cv is not None:
            cell_voltages.append(float(cv))
            
    max_cell_v = max(cell_voltages) if cell_voltages else (voltage / 8.0)
    min_cell_v = min(cell_voltages) if cell_voltages else (voltage / 8.0)
    
    # Operating Mode
    op_mode = prediction_dict.get("Operating Mode", "IDLE") if prediction_dict else "IDLE"
    
    # 3. Calculate Rate of Change (Gradients)
    delta_time = 1.0
    if _previous_telemetry:
        delta_time = max(1.0, timestamp_epoch - _previous_telemetry.get("timestamp_epoch", timestamp_epoch - 1.0))
    
    prev_max_v = _previous_telemetry.get("max_cell_v", max_cell_v)
    max_v_gradient = (max_cell_v - prev_max_v) / delta_time
    
    # Update state for next cycle
    _previous_telemetry = {
        "timestamp_epoch": timestamp_epoch,
        "max_cell_v": max_cell_v,
        "temperature": temperature,
        "current": current
    }
    
    # 4. Evaluate Physical Fault Severities
    # We test multiple conditions independently to find the most severe active fault.
    # Note: ML Fault serves as the "default" if no hard limits are breached.
    
    candidate_faults = []
    
    # A. Overtemperature
    temp_ratio = calculate_severity_ratio(temperature, cfg["temp_warn_limit"], cfg["temp_critical_limit"], "upper")
    temp_override = detect_safety_override(temperature, cfg["temp_critical_limit"] + 5.0, "upper")
    if temp_ratio > 0:
        candidate_faults.append(("Overtemperature Risk", temperature, cfg["temp_warn_limit"], cfg["temp_critical_limit"], temp_ratio, temp_override, "Temperature exceeded safe limits.", ["High absolute temperature"]))
        
    # B. Overvoltage
    ov_ratio = calculate_severity_ratio(max_cell_v, cfg["cell_max_voltage"], cfg["cell_critical_max"], "upper")
    ov_override = detect_safety_override(max_cell_v, cfg["cell_critical_max"] + 0.1, "upper")
    if ov_ratio > 0:
        candidate_faults.append(("Overvoltage Risk", max_cell_v, cfg["cell_max_voltage"], cfg["cell_critical_max"], ov_ratio, ov_override, "Cell voltage approaching or exceeding maximum limit.", ["High cell voltage"]))
        
    # C. Undervoltage
    uv_ratio = calculate_severity_ratio(min_cell_v, cfg["cell_min_voltage"], cfg["cell_critical_min"], "lower")
    uv_override = detect_safety_override(min_cell_v, cfg["cell_critical_min"] - 0.1, "lower")
    if uv_ratio > 0:
        candidate_faults.append(("Undervoltage Risk", min_cell_v, cfg["cell_min_voltage"], cfg["cell_critical_min"], uv_ratio, uv_override, "Cell voltage approaching or below minimum limit.", ["Low cell voltage"]))
        
    # D. Overcurrent
    oc_ratio = calculate_severity_ratio(abs(current), cfg["current_warn_limit"], cfg["current_critical_limit"], "upper")
    oc_override = detect_safety_override(abs(current), cfg["current_critical_limit"] + 10.0, "upper")
    if oc_ratio > 0:
        candidate_faults.append(("Overcurrent Risk", abs(current), cfg["current_warn_limit"], cfg["current_critical_limit"], oc_ratio, oc_override, "Current exceeded safe continuous limit.", ["High pack current"]))
        
    # E. Cell Imbalance
    imb_ratio = calculate_severity_ratio(delta_v, cfg["imbalance_warn_limit"], cfg["imbalance_critical_limit"], "upper")
    imb_override = detect_safety_override(delta_v, cfg["imbalance_critical_limit"] + 0.1, "upper")
    if imb_ratio > 0:
        candidate_faults.append(("Cell Imbalance Risk", delta_v, cfg["imbalance_warn_limit"], cfg["imbalance_critical_limit"], imb_ratio, imb_override, "Cell voltage spread exceeds balancer limits.", ["High delta V"]))

    # F. ML Detected Fault (if not already captured physically)
    # E.g. Weak Cell, Sensor Fault, High Voltage Gradient, Unknown/OOD
    if ml_fault not in ["Normal", "Normal Operation"]:
        # If it's an ML fault without a strict numerical limit, severity ratio is derived from confidence as a fallback,
        # but base severity provides the floor.
        ml_override = True if is_ood and ood_score > 0.8 else False
        candidate_faults.append((ml_fault, 0.0, 0.0, 0.0, ml_prob, ml_override, f"ML Model detected {ml_fault}", [f"ML Model Confidence {ml_prob*100:.1f}%"]))

    # 5. Weak Cell Evidentiary Logic
    # Do not blindly accept High Voltage Gradient as Weak Cell. Require multiple indicators.
    if ml_fault == "Weak Cell" or max_v_gradient > 0.015:
        weak_cell_evidence_count = 0
        indicators = []
        if uv_ratio > 0.5:
            weak_cell_evidence_count += 1
            indicators.append("Early lower-voltage reach")
        if ov_ratio > 0.5:
            weak_cell_evidence_count += 1
            indicators.append("Early upper-voltage reach")
        if imb_ratio > 0.5:
            weak_cell_evidence_count += 1
            indicators.append("Persistent cell deviation")
        if max_v_gradient > 0.015:
            weak_cell_evidence_count += 1
            indicators.append("Repeated high voltage gradient")
            
        if weak_cell_evidence_count >= 2:
            candidate_faults.append(("Weak Cell", max_v_gradient, 0.010, 0.020, min(1.0, max_v_gradient/0.030), False, "Multiple indicators suggest a weak or high-Ri cell.", indicators))
        elif max_v_gradient > 0.015:
            candidate_faults.append(("High Voltage Gradient", max_v_gradient, 0.010, 0.020, min(1.0, max_v_gradient/0.030), False, "Rapid cell voltage rise observed without secondary weak-cell confirmation.", ["Rapid rise"]))

    # 6. Select the Most Severe Fault
    best_fault = "Normal Operation"
    best_measured = 0.0
    best_warn = 0.0
    best_crit = 0.0
    best_sev_ratio = 0.0
    best_override = False
    best_reason = "System operating normally."
    best_indicators = []
    
    highest_severity = 0.0
    
    for (f_name, f_meas, f_warn, f_crit, f_ratio, f_over, f_rsn, f_ind) in candidate_faults:
        # Calculate dynamic severity for this candidate
        base_w = BASE_SEVERITY_WEIGHTS.get(f_name, 0.50)
        # We peek at persistence for selection
        _, p_factor = _get_persistence_factor(f_name, True)
        
        dyn_sev = calculate_dynamic_severity(base_w, f_ratio, p_factor)
        if f_over: dyn_sev = 1.0
        
        if dyn_sev > highest_severity:
            highest_severity = dyn_sev
            best_fault = f_name
            best_measured = f_meas
            best_warn = f_warn
            best_crit = f_crit
            best_sev_ratio = f_ratio
            best_override = f_over
            best_reason = f_rsn
            best_indicators = f_ind

    # 7. Apply Persistence to the Winner
    # Decay all other faults
    for k in list(_persistence_counts.keys()):
        if k != best_fault:
            _get_persistence_factor(k, False)
            
    # Increment winner
    persistence_count, persistence_factor = _get_persistence_factor(best_fault, best_fault != "Normal Operation")
    
    if best_fault == "Normal Operation":
        final_severity = 0.0
    else:
        base_w = BASE_SEVERITY_WEIGHTS.get(best_fault, 0.50)
        final_severity = calculate_dynamic_severity(base_w, best_sev_ratio, persistence_factor)
        if best_override:
            final_severity = 1.0

    # 8. Calculate Final Risk
    # If the ML model agrees with the physical fault (or it's the ML fault itself), use its confidence.
    # Otherwise, if it's a pure physical limit breach that ML missed, we assume 1.0 confidence in the sensor reading.
    active_confidence = ml_prob if (ml_fault in best_fault or ml_fault != "Normal") else 1.0
    
    final_risk_score = calculate_final_risk(active_confidence, final_severity, best_override)
    
    # 9. Format API Output
    output = {
        "predicted_fault": best_fault,
        "affected_cell": 0, # Could be derived from argmax of cell_voltages
        "prediction_confidence": round(active_confidence, 3),
        "confidence_level": classify_confidence(active_confidence),
        "fault_severity_score": round(final_severity, 3),
        "severity_level": classify_severity(final_severity),
        "final_risk_score": round(final_risk_score, 3),
        "risk_level": classify_risk(final_risk_score),
        "safety_override": bool(best_override),
        "measured_value": round(best_measured, 3),
        "warning_threshold": round(best_warn, 3),
        "critical_threshold": round(best_crit, 3),
        "shutdown_threshold": None, # Depending on chemistry config
        "reason": best_reason,
        "supporting_indicators": best_indicators,
        "persistence_count": int(persistence_count),
        "fault_duration_seconds": round(persistence_count * 1.0, 1), # Approx 1s per tick
        "operating_mode": op_mode,
        "timestamp": datetime.fromtimestamp(timestamp_epoch).strftime("%Y-%m-%dT%H:%M:%S")
    }
    
    return output
