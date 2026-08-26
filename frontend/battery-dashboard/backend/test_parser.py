import os
import json
from parser import extract_parameters_from_pdf

EXPECTED_RESULTS = {
    "LG_INR21700-M50.pdf": {
        "manufacturer": "LG Energy Solution",
        "cell_model": "INR21700-M50",
        "chemistry": "Li-ion NMC",
        "nominal_voltage": 3.63,
        "maximum_voltage": 4.20,
        "minimum_voltage": 2.50,
        "nominal_capacity": 5000,
        "energy_wh": 18.2,
        "standard_charge_current": 1.455,
        "maximum_continuous_discharge_current": 7.275,
        "internal_resistance": 25,
        "charge_temperature_min": 0,
        "charge_temperature_max": 50,
        "discharge_temperature_min": -30,
        "discharge_temperature_max": 60,
        "weight": 68
    },
    "Panasonic_NCR18650B.pdf": {
        "manufacturer": "Panasonic",
        "cell_model": "NCR18650B",
        "chemistry": "Li-ion NCA",
        "nominal_voltage": 3.60,
        "maximum_voltage": 4.20,
        "minimum_voltage": 2.50,
        "nominal_capacity": 3350,
        "energy_wh": 12.1,
        "standard_charge_current": 1.625,
        "maximum_continuous_discharge_current": 4.875,
        "internal_resistance": 100,
        "charge_temperature_min": 0,
        "charge_temperature_max": 40,
        "discharge_temperature_min": -20,
        "discharge_temperature_max": 60,
        "weight": 47.5
    },
    "Samsung_INR18650-30Q.pdf": {
        "manufacturer": "Samsung SDI",
        "cell_model": "INR18650-30Q",
        "chemistry": "Li-ion NMC",
        "nominal_voltage": 3.60,
        "maximum_voltage": 4.20,
        "minimum_voltage": 2.50,
        "nominal_capacity": 3000,
        "energy_wh": 10.8,
        "standard_charge_current": 1.5,
        "maximum_continuous_discharge_current": 15,
        "internal_resistance": 20,
        "charge_temperature_min": 0,
        "charge_temperature_max": 50,
        "discharge_temperature_min": -20,
        "discharge_temperature_max": 75,
        "weight": 48
    },
    "Cegasa_26650_LFP.pdf": {
        "manufacturer": "Cegasa",
        "cell_model": "26650 LFP",
        "chemistry": "LiFePO4",
        "nominal_voltage": 3.20,
        "maximum_voltage": 3.65,
        "minimum_voltage": 2.50,
        "nominal_capacity": 3200,
        "energy_wh": 10.24,
        "standard_charge_current": 1.6,
        "maximum_continuous_discharge_current": 9.6,
        "internal_resistance": 25,
        "charge_temperature_min": 0,
        "charge_temperature_max": 55,
        "discharge_temperature_min": -20,
        "discharge_temperature_max": 60,
        "weight": 86
    },
    "Molicel_INR21700-P42A.pdf": {
        "manufacturer": "Molicel",
        "cell_model": "INR21700-P42A",
        "chemistry": "Li-ion NMC",
        "nominal_voltage": 3.60,
        "maximum_voltage": 4.20,
        "minimum_voltage": 2.50,
        "nominal_capacity": 4200,
        "energy_wh": 15.5,
        "standard_charge_current": 4.2,
        "maximum_continuous_discharge_current": 45,
        "internal_resistance": 10,
        "charge_temperature_min": 0,
        "charge_temperature_max": 45,
        "discharge_temperature_min": -40,
        "discharge_temperature_max": 60,
        "weight": 70
    }
}

def run_validations(pdf_directory: str = "test_pdfs"):
    print("Starting Parser Validation Suite...")
    
    if not os.path.exists(pdf_directory):
        print(f"Directory '{pdf_directory}' not found. Please place your PDFs there to run validations.")
        return

    passed_tests = 0
    total_tests = len(EXPECTED_RESULTS)

    for pdf_filename, expected in EXPECTED_RESULTS.items():
        pdf_path = os.path.join(pdf_directory, pdf_filename)
        
        if not os.path.exists(pdf_path):
            print(f"[-] Missing PDF: {pdf_filename}")
            continue

        print(f"\nEvaluating {pdf_filename}...")
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        try:
            # Run parser
            result_params = extract_parameters_from_pdf(pdf_bytes)
            result_json = result_params.model_dump()

            # Compare keys
            all_match = True
            for key, expected_value in expected.items():
                actual_value = result_json.get(key)
                
                # Check mapping for schema (e.g. LiFePO4 vs LiFePO4 (LFP) in JSON)
                if key == "chemistry" and "LFP" in expected_value and "LiFePO4" in actual_value:
                    print(f"  [PASS] {key}: {actual_value} (matches {expected_value})")
                    continue
                
                if actual_value != expected_value:
                    print(f"  [FAIL] {key}: Expected {expected_value}, got {actual_value}")
                    all_match = False
                else:
                    print(f"  [PASS] {key}: {actual_value}")
                    
            if all_match:
                print(f"[+] {pdf_filename} passed all validations.")
                passed_tests += 1
                
        except Exception as e:
            print(f"  [ERROR] Failed to parse {pdf_filename}: {e}")

    print(f"\nValidation Complete: {passed_tests}/{total_tests} PDFs passed.")

if __name__ == "__main__":
    run_validations()
