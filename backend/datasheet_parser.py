import re
import os
import json

try:
    import pdfplumber
except ImportError:
    pass

def extract_parameters_from_pdf(pdf_path):
    """
    Extracts battery parameters from a given PDF datasheet using Regex keyword matching.
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

    # Normalization
    text = text.replace('\n', ' ')
    
    # 1. Chemistry Detection
    chemistry = "Unknown"
    chem_match = re.search(r'(NMC|LFP|LiFePO4|LTO|Lithium Titanate|Nickel Manganese Cobalt|Lithium Iron Phosphate)', text, re.IGNORECASE)
    if chem_match:
        found = chem_match.group(1).upper()
        if "NMC" in found or "COBALT" in found: chemistry = "NMC"
        elif "LFP" in found or "PHOSPHATE" in found or "LIFEPO4" in found: chemistry = "LiFePO4"
        elif "LTO" in found or "TITANATE" in found: chemistry = "LTO"

    # 2. Extract Numerical Values using Regex
    params = {
        "chemistry": chemistry,
        "nominal_voltage": None,
        "max_charge_voltage": None,
        "cutoff_voltage": None,
        "capacity_ah": None,
        "max_continuous_current": None,
        "max_temperature": None
    }

    # Regex patterns
    patterns = {
        "nominal_voltage": r'Nominal\s*Voltage.*?([\d\.]+)\s*V',
        "max_charge_voltage": r'(?:Charge|Charging)\s*Voltage.*?([\d\.]+)\s*V',
        "cutoff_voltage": r'(?:Discharge\s*Cut-?off|End\s*of\s*Discharge).*?([\d\.]+)\s*V',
        "capacity_ah": r'Capacity.*?([\d\.]+)\s*(?:Ah|mAh)',
        "max_continuous_current": r'(?:Continuous\s*Discharge|Max\s*Discharge\s*Current).*?([\d\.]+)\s*(?:A|mA|C)',
        "max_temperature": r'(?:Operating\s*Temperature|Discharge\s*Temperature).*?(?:to|~|-)\s*([\d\.]+)\s*(?:°C|C|deg)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1))
                params[key] = val
            except ValueError:
                pass
                
    # Normalize Capacity (if extracted in mAh)
    if params["capacity_ah"] and params["capacity_ah"] > 1000:
        params["capacity_ah"] = params["capacity_ah"] / 1000.0

    return params

def save_active_profile(params, output_dir):
    """
    Saves the extracted parameters to active_profile.json
    """
    if not params:
        return False
        
    # Generate the threshold structures expected by the backend
    nom_v = params.get("nominal_voltage") or 3.6
    max_v = params.get("max_charge_voltage") or 4.2
    min_v = params.get("cutoff_voltage") or 2.8
    max_curr = params.get("max_continuous_current") or 20.0
    max_temp = params.get("max_temperature") or 55.0
    
    profile = {
        "source": "Datasheet Parser",
        "chemistry": params.get("chemistry", "NMC"),
        "cell_parameters": {
            "nominal_voltage": nom_v,
            "capacity_ah": params.get("capacity_ah") or 3.0
        },
        "thresholds": {
            "cell_voltage": {
                "warning": {
                    "min": round(min_v + 0.2, 2),
                    "max": round(max_v - 0.1, 2)
                },
                "critical": {
                    "min": min_v,
                    "max": max_v
                }
            },
            "temperature": {
                "warning": max_temp - 10.0,
                "critical": max_temp
            },
            "current": {
                "warning": max_curr * 0.8,
                "critical": max_curr
            },
            "imbalance": {
                "warning": 0.08,
                "critical": 0.15
            }
        }
    }
    
    path = os.path.join(output_dir, "active_profile.json")
    with open(path, 'w') as f:
        json.dump(profile, f, indent=4)
        
    return profile
