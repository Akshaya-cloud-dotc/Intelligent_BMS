# fault_risk_config.py

# ==================================================
# 1. BASE SEVERITY WEIGHTS
# ==================================================
# These weights represent the initial dangerousness of a fault condition
# when it is first detected, before any dynamic scaling is applied based on
# measurement violation or persistence.

BASE_SEVERITY_WEIGHTS = {
    "Normal": 0.00,
    "Normal Operation": 0.00,
    "Cell Imbalance": 0.40,
    "High Voltage Gradient": 0.45,
    "Weak Cell": 0.60,
    "Overvoltage Risk": 0.80,
    "Undervoltage Risk": 0.80,
    "Overcurrent Risk": 0.90,
    "Overtemperature Risk": 0.90,
    "Sensor Fault": 0.70,
    "SENSOR_OR_DATA_INTEGRITY_FAULT": 0.70,
    "Communication Fault": 0.75,
    "Unknown Fault": 1.00,
    "UNKNOWN_FAULT_OOD": 1.00
}


# ==================================================
# 2. CHEMISTRY THRESHOLDS
# ==================================================
# Standard multi-chemistry safety thresholds used for normalization
# and override logic.
# These match the pre-existing system defaults but can be modified or
# overridden by the uploaded active_profile.json.

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
        "temp_critical_limit": 55.0,
        "current_warn_limit": 15.0,
        "current_critical_limit": 20.0,
        "imbalance_warn_limit": 0.08,
        "imbalance_critical_limit": 0.15,
        "is_fallback": True
    }
}
