from schemas import CellParameters, PackParameters, FaultThresholds, CalculationResponse, AdaptationMetrics, ReconfigurationItem
from chemistry_profiles import get_base_profile, get_profile_for_detected

def format_temp(min_t, max_t):
    if min_t is not None and max_t is not None:
        return f"{min_t}–{max_t}°C"
    elif min_t is not None:
        return f">{min_t}°C"
    elif max_t is not None:
        return f"<{max_t}°C"
    return "Not found in datasheet"

def calculate_pack_data(cell: CellParameters, s: int, p: int) -> CalculationResponse:
    # 0. Recalculate cell-level dynamics based on frontend overrides
    if cell.nominal_voltage is not None and cell.nominal_capacity is not None:
        cell.energy_wh = round(cell.nominal_voltage * (cell.nominal_capacity / 1000.0), 2)
        
    if cell.cell_model == "INR21700-M50" and cell.nominal_capacity is not None:
        cell.standard_charge_current = round(0.3 * (cell.nominal_capacity / 1000.0), 3)
        cell.standard_charge_current_string = f"0.3C ({cell.standard_charge_current} A)"

    # 1. Calculate Pack Parameters
    
    # Defaults in case extraction failed
    c_nom_v = cell.nominal_voltage if cell.nominal_voltage is not None else 3.6
    c_max_v = cell.maximum_voltage if cell.maximum_voltage is not None else 4.2
    c_min_v = cell.minimum_voltage if cell.minimum_voltage is not None else 2.5
    c_cap_mah = cell.nominal_capacity if cell.nominal_capacity is not None else 5000.0
    c_cap_ah = c_cap_mah / 1000.0
    c_max_discharge = cell.maximum_continuous_discharge_current if cell.maximum_continuous_discharge_current is not None else 7.3
    c_std_charge = cell.standard_charge_current if cell.standard_charge_current is not None else 1.5

    pack_nom_v = c_nom_v * s
    pack_max_v = c_max_v * s
    pack_min_v = c_min_v * s
    pack_cap_ah = c_cap_ah * p
    pack_energy_wh = pack_nom_v * pack_cap_ah
    pack_max_discharge = c_max_discharge * p
    pack_std_charge = c_std_charge * p

    pack_params = PackParameters(
        pack_nominal_voltage=round(pack_nom_v, 2),
        pack_maximum_voltage=round(pack_max_v, 2),
        pack_minimum_voltage=round(pack_min_v, 2),
        pack_capacity=round(pack_cap_ah, 2), # Ah
        pack_energy_wh=round(pack_energy_wh, 2),
        pack_standard_charge_current=round(pack_std_charge, 3),
        pack_maximum_discharge_current=round(pack_max_discharge, 3)
    )

    # 2. Calculate Fault Thresholds
    ov_critical = pack_max_v
    ov_warning = 0.95 * ov_critical
    oc_critical = c_max_discharge * p
    oc_warning = 0.90 * oc_critical

    temp_max = cell.discharge_temperature_max
    if temp_max is None:
        temp_max = cell.charge_temperature_max
    if temp_max is None:
        temp_max = 60.0  # Fallback

    ot_normal_min = 0.0 # Not used by gauge, but kept for completeness
    ot_normal_max = temp_max - 5.0
    ot_warning_min = temp_max - 5.0
    ot_warning_max = temp_max
    ot_critical = temp_max

    faults = FaultThresholds(
        overvoltage_warning=round(ov_warning, 2),
        overvoltage_critical=round(ov_critical, 2),
        overcurrent_warning=round(oc_warning, 2),
        overcurrent_critical=round(oc_critical, 2),
        overtemperature_normal_min=round(ot_normal_min, 2),
        overtemperature_normal_max=round(ot_normal_max, 2),
        overtemperature_warning_min=round(ot_warning_min, 2),
        overtemperature_warning_max=round(ot_warning_max, 2),
        overtemperature_critical=round(ot_critical, 2)
    )

    # 3. Adaptation Engine
    detected_raw = cell.chemistry if cell.chemistry else "Unknown"
    key, profile = get_profile_for_detected(detected_raw)
    
    reconfig_items = []
    
    # Format actual numerical values for temperatures
    charge_temp_actual = format_temp(cell.charge_temperature_min, cell.charge_temperature_max)
    if charge_temp_actual == "Not found in datasheet":
        # Fallback to general operating temp if explicitly charge is missing, or leave as unknown
        charge_temp_actual = format_temp(cell.operating_temperature_min, cell.operating_temperature_max)
        if charge_temp_actual == "Not found in datasheet":
             charge_temp_actual = "0–45°C (Default)"

    discharge_temp_actual = format_temp(cell.discharge_temperature_min, cell.discharge_temperature_max)
    if discharge_temp_actual == "Not found in datasheet":
        discharge_temp_actual = format_temp(cell.operating_temperature_min, cell.operating_temperature_max)
        if discharge_temp_actual == "Not found in datasheet":
             discharge_temp_actual = "-20–60°C (Default)"

    # NMC Base is the reference
    if key == "NCA":
        if cell.maximum_continuous_discharge_current is not None:
             reconfig_items.append(ReconfigurationItem(parameter="Maximum Continuous Current", current_setting="7.3 A", new_setting=f"{cell.maximum_continuous_discharge_current} A"))
        reconfig_items.append(ReconfigurationItem(parameter="Charge Temperature Range", current_setting="0–45°C", new_setting=charge_temp_actual))
        
    elif key == "LCO":
        reconfig_items.append(ReconfigurationItem(parameter="Maximum Voltage", current_setting="4.2 V", new_setting=f"{c_max_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Charge Temperature Range", current_setting="0–45°C", new_setting=charge_temp_actual))
        reconfig_items.append(ReconfigurationItem(parameter="Discharge Temperature Range", current_setting="-20–60°C", new_setting=discharge_temp_actual))
        
    elif key == "LFP":
        reconfig_items.append(ReconfigurationItem(parameter="Nominal Voltage", current_setting="3.6 V", new_setting=f"{c_nom_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Maximum Voltage", current_setting="4.2 V", new_setting=f"{c_max_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Overvoltage Threshold", current_setting="4.2 V", new_setting=f"{c_max_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Charge Temperature Range", current_setting="0–45°C", new_setting=charge_temp_actual))
        reconfig_items.append(ReconfigurationItem(parameter="Discharge Temperature Range", current_setting="-20–60°C", new_setting=discharge_temp_actual))
        reconfig_items.append(ReconfigurationItem(parameter="SOC Curve Category", current_setting="NMC Curve", new_setting="LFP Curve"))
        
    elif key == "LTO":
        reconfig_items.append(ReconfigurationItem(parameter="Nominal Voltage", current_setting="3.6 V", new_setting=f"{c_nom_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Maximum Voltage", current_setting="4.2 V", new_setting=f"{c_max_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Minimum Voltage", current_setting="2.5 V", new_setting=f"{c_min_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Overvoltage Threshold", current_setting="4.2 V", new_setting=f"{c_max_v} V"))
        reconfig_items.append(ReconfigurationItem(parameter="Charge Temperature Range", current_setting="0–45°C", new_setting=charge_temp_actual))
        reconfig_items.append(ReconfigurationItem(parameter="Discharge Temperature Range", current_setting="-20–60°C", new_setting=discharge_temp_actual))
        reconfig_items.append(ReconfigurationItem(parameter="SOC Curve Category", current_setting="NMC Curve", new_setting="LTO Curve"))

    # For NMC, key == "NMC", the array remains empty. The frontend correctly displays "No configuration changes required."

    adaptation = AdaptationMetrics(
        base_chemistry="NMC",
        detected_chemistry=detected_raw,
        compatibility_score=profile["similarity"],
        recommendation_text=profile["recommendation"],
        expected_accuracy=profile["similarity"],
        reconfiguration_items=reconfig_items
    )

    return CalculationResponse(
        cell=cell,
        pack=pack_params,
        thresholds=faults,
        adaptation=adaptation
    )
