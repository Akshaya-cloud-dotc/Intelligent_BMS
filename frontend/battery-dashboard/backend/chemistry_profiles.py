# chemistry_profiles.py

CHEMISTRY_PROFILES = {
    "NMC": {
        "nominal_voltage": "3.6-3.7 V",
        "maximum_voltage": "4.2 V",
        "minimum_voltage": "2.5 V",
        "charge_temperature": "0-45°C",
        "discharge_temperature": "-20-60°C",
        "similarity": 100,
        "recommendation": "No changes required. Chemistry matches base model perfectly."
    },
    "NCA": {
        "similarity": 95,
        "recommendation": "Minor reconfiguration required. Only current limits and some temperature thresholds need adjustment."
    },
    "LCO": {
        "similarity": 85,
        "recommendation": "Moderate reconfiguration required. Adjust voltage and temperature thresholds."
    },
    "LFP": {
        "similarity": 60,
        "recommendation": "Voltage thresholds and temperature limits must be updated. SOC curve must be changed."
    },
    "LTO": {
        "similarity": 40,
        "recommendation": "Major reconfiguration required. Reconfiguration recommended before using the fault detection model."
    }
}

CHEMISTRY_MAPPING = {
    "Li-ion NMC": "NMC",
    "Li-ion NCA": "NCA",
    "Li-ion LCO": "LCO",
    "LiFePO4": "LFP",
    "LTO": "LTO",
    "Lithium Titanate": "LTO"
}

def get_base_profile():
    return CHEMISTRY_PROFILES["NMC"]

def get_profile_for_detected(detected_chemistry_raw: str):
    key = CHEMISTRY_MAPPING.get(detected_chemistry_raw, "NMC") # default to NMC if unknown
    return key, CHEMISTRY_PROFILES.get(key, CHEMISTRY_PROFILES["NMC"])
