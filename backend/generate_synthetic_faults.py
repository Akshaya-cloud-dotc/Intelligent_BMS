#!/usr/bin/env python3
"""
AI-PBMS Physics-Informed Synthetic Fault Generator (v2)
--------------------------------------------------------
Loads all baseline Excel sheets, deduplicates rows, splits contiguously
per sheet (70/15/15) to prevent data leakage, and generates balanced,
reliable physics-informed battery faults (Cell Imbalance, Weak Cell,
Overvoltage, Undervoltage, and Thermal Hotspots) within each split.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

# Configurable physical limits for safety validation
LIMITS = {
    "min_cell_v": 2.0,      # V
    "max_cell_v": 4.5,      # V
    "max_delta_v": 0.35,    # V (max allowable spread)
    "min_temp": -40.0,      # °C
    "max_temp": 120.0,      # °C
    "min_current": -120.0,  # A
    "max_current": 120.0,   # A
    "max_dv_dt": 0.50,      # V/s (max voltage jump per second)
    "max_dt_dt": 1.0        # °C/s (max temp rise per second)
}

def load_active_profile():
    profile_path = os.path.join(os.path.dirname(__file__), "active_profile.json")
    if os.path.exists(profile_path):
        try:
            with open(profile_path, 'r') as f:
                profile = json.load(f)
                cell_params = profile.get("cell_parameters", {})
                if cell_params.get("minimum_voltage") is not None:
                    LIMITS["min_cell_v"] = float(cell_params["minimum_voltage"])
                if cell_params.get("maximum_voltage") is not None:
                    LIMITS["max_cell_v"] = float(cell_params["maximum_voltage"])
                if cell_params.get("discharge_temperature_max") is not None:
                    LIMITS["max_temp"] = float(cell_params["discharge_temperature_max"])
                if cell_params.get("charge_temperature_min") is not None:
                    LIMITS["min_temp"] = float(cell_params["charge_temperature_min"])
            print(f"Loaded dynamic chemistry limits: {LIMITS['min_cell_v']}V to {LIMITS['max_cell_v']}V")
        except Exception as e:
            print(f"Warning: Failed to load active_profile.json: {e}")

load_active_profile()

def load_baseline_data(directory):
    excel_files = [
        f for f in os.listdir(directory)
        if f.endswith('.xlsx') and not f.startswith('~$') and not f.startswith('augmented_')
    ]
    if not excel_files:
        raise FileNotFoundError("No baseline Excel files found in the directory.")
    
    all_sheets_data = []
    required = ['voltage', 'current', 'temperature', 'soc']
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    total_raw_rows = 0
    total_loaded_rows = 0
    
    for f in excel_files:
        filepath = os.path.join(directory, f)
        print(f"Scanning file: {f}...")
        try:
            xls = pd.ExcelFile(filepath)
            sheets_in_file = xls.sheet_names
            
            # Avoid loading both combined sheets and separate cycle sheets.
            # If a combined sheet exists, use it and skip individual cycles.
            combined_sheet = None
            for s in sheets_in_file:
                if s.lower() in ["all cycles", "all data", "balanced all"]:
                    combined_sheet = s
                    break
                    
            sheets_to_read = []
            if combined_sheet:
                sheets_to_read = [combined_sheet]
            else:
                sheets_to_read = [s for s in sheets_in_file if s.lower() != "summary"]
                
            for sheet in sheets_to_read:
                # Detect the header offset row
                found_header = None
                for h in [0, 1, 2, 3]:
                    try:
                        df_test = pd.read_excel(filepath, sheet_name=sheet, header=h, nrows=3)
                        cols = [str(c).lower().strip() for c in df_test.columns]
                        has_req = all(col in cols for col in required) and all(col in cols for col in cell_cols)
                        if has_req:
                            found_header = h
                            break
                    except Exception:
                        pass
                
                if found_header is not None:
                    df = pd.read_excel(filepath, sheet_name=sheet, header=found_header)
                    df.columns = [str(c).lower().strip() for c in df.columns]
                    
                    # Count original raw rows
                    total_raw_rows += len(df)
                    
                    # Clean and keep essential columns
                    cols_to_keep = required + cell_cols
                    
                    # Ensure delta_v is computed and kept
                    df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
                    cols_to_keep.append('delta_v')
                    
                    for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4']:
                        if ntc in df.columns:
                            cols_to_keep.append(ntc)
                        else:
                            df[ntc] = df['temperature']
                            cols_to_keep.append(ntc)
                            
                    if 'cycle' in df.columns:
                        cols_to_keep.append('cycle')
                    else:
                        df['cycle'] = 1
                        cols_to_keep.append('cycle')
                        
                    df_clean = df[cols_to_keep].copy()
                    df_clean['source_file'] = f
                    df_clean['source_sheet'] = sheet
                    
                    all_sheets_data.append(df_clean)
                    total_loaded_rows += len(df_clean)
                    print(f" -> Loaded {len(df_clean)} rows from sheet '{sheet}' (header row: {found_header})")
                else:
                    print(f" -> WARNING: Skipping sheet '{sheet}' in {f} (could not find matching columns)")
        except Exception as e:
            print(f" -> Error reading {f}: {e}")
            
    if not all_sheets_data:
        raise ValueError("Could not find any valid baseline sheets across files.")
        
    print(f"\nAudit: Total rows across all Excel sheets: {total_raw_rows}")
    print(f"Audit: Selected sheets row count (before deduplication): {total_loaded_rows}")
    return all_sheets_data, total_raw_rows, total_loaded_rows

# Physics-based injection rules
def inject_cell_imbalance(df_base):
    df = df_base.copy()
    N = len(df)
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    # Select random cell
    c = np.random.randint(1, 9)
    # Drift target between 50mV and 250mV
    target_drift = np.random.uniform(0.050, 0.250)
    drift = np.linspace(0.0, target_drift, N)
    
    # Apply gradual voltage depletion on selected cell
    df[f'cell_v{c}'] = df[f'cell_v{c}'] - drift
    
    # Recalculate pack voltage and delta_v
    df['voltage'] = df[cell_cols].sum(axis=1)
    df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
    df['fault_label'] = 1
    return df

def inject_weak_cell(df_base):
    df = df_base.copy()
    N = len(df)
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    c = np.random.randint(1, 9)
    # Excess internal resistance (Ohms)
    dR = np.random.uniform(0.015, 0.035)
    
    current = df['current'].values
    sag = current * dR  # Negative current = negative voltage drop
    
    # Capacity fade effect under discharge
    fade = np.linspace(0.0, 0.050, N) * (current < -0.1).astype(float)
    
    df[f'cell_v{c}'] = df[f'cell_v{c}'] + sag - fade
    
    df['voltage'] = df[cell_cols].sum(axis=1)
    df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
    df['fault_label'] = 2
    return df

def inject_overvoltage_risk(df_base):
    df = df_base.copy()
    N = len(df)
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    # Raise voltage of one or two cells toward cutoff (e.g. up to 150mV rise)
    c = np.random.randint(1, 9)
    target_rise = np.random.uniform(0.080, 0.150)
    drift = np.linspace(0.0, target_rise, N)
    
    df[f'cell_v{c}'] = df[f'cell_v{c}'] + drift
    
    df['voltage'] = df[cell_cols].sum(axis=1)
    df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
    df['fault_label'] = 3
    return df

def inject_undervoltage_risk(df_base):
    df = df_base.copy()
    N = len(df)
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    
    # Deplete voltage of cells toward cutoff (up to 200mV drop)
    c = np.random.randint(1, 9)
    target_drop = np.random.uniform(0.100, 0.220)
    drift = np.linspace(0.0, target_drop, N)
    
    df[f'cell_v{c}'] = df[f'cell_v{c}'] - drift
    
    df['voltage'] = df[cell_cols].sum(axis=1)
    df['delta_v'] = df[cell_cols].max(axis=1) - df[cell_cols].min(axis=1)
    df['fault_label'] = 4
    return df

def inject_thermal_hotspot(df_base):
    df = df_base.copy()
    N = len(df)
    ntc_cols = ['ntc1', 'ntc2', 'ntc3', 'ntc4']
    
    s = np.random.randint(1, 5)  # 1 to 4
    # Max temperature rise in °C
    T_rise_max = np.random.uniform(15.0, 25.0)
    tau = N / 3.0  # Thermal time constant
    
    idx = np.arange(N)
    temp_rise = T_rise_max * (1.0 - np.exp(-idx / tau))
    
    # Correlate rise slightly with current magnitude (I^2 heat generation)
    current = df['current'].values
    heat_factor = 1.0 + (current ** 2) * 0.001
    df[f'ntc{s}'] = df[f'ntc{s}'] + (temp_rise * heat_factor)
    
    # Recalculate pack temp as max NTC
    df['temperature'] = df[ntc_cols].max(axis=1)
    df['fault_label'] = 5
    return df

def validate_physical_limits(df):
    """
    Checks each row in the DataFrame against physical limits.
    Returns a boolean mask where True means the row is valid.
    """
    cell_cols = [f'cell_v{i}' for i in range(1, 9)]
    ntc_cols = ['ntc1', 'ntc2', 'ntc3', 'ntc4']
    
    # 1. Voltage bounds
    v_ok = (df['voltage'] >= LIMITS["min_pack_v"]) & (df['voltage'] <= LIMITS["max_pack_v"])
    for col in cell_cols:
        v_ok = v_ok & (df[col] >= LIMITS["min_cell_v"]) & (df[col] <= LIMITS["max_cell_v"])
        
    # 2. Spread bounds
    spread_ok = df['delta_v'] <= LIMITS["max_delta_v"]
    
    # 3. Temperature bounds
    t_ok = (df['temperature'] >= LIMITS["min_temp"]) & (df['temperature'] <= LIMITS["max_temp"])
    for col in ntc_cols:
        t_ok = t_ok & (df[col] >= LIMITS["min_temp"]) & (df[col] <= LIMITS["max_temp"])
        
    # 4. Current bounds
    i_ok = (df['current'] >= LIMITS["min_current"]) & (df['current'] <= LIMITS["max_current"])
    
    # 5. Jump bounds (derivatives)
    # Voltage jump per second
    dv_dt = df['voltage'].diff().abs().fillna(0.0)
    jump_v_ok = dv_dt <= LIMITS["max_dv_dt"]
    
    # Temperature jump per second
    dt_dt = df['temperature'].diff().abs().fillna(0.0)
    jump_t_ok = dt_dt <= LIMITS["max_dt_dt"]
    
    return v_ok & spread_ok & t_ok & i_ok & jump_v_ok & jump_t_ok

# Set pack voltage limits based on cell limits
LIMITS["min_pack_v"] = LIMITS["min_cell_v"] * 8
LIMITS["max_pack_v"] = LIMITS["max_cell_v"] * 8

def generate_fault_dataset(baseline_df, target_faults, inject_func, current_filter=None):
    """
    Generates target_faults rows by sampling contiguous slices from baseline_df
    and applying inject_func. Runs safety validation and replaces rejected rows.
    """
    generated_dfs = []
    total_generated = 0
    rejected_count = 0
    
    # Apply current filter if required
    if current_filter == 'charge':
        eligible_df = baseline_df[baseline_df['current'] > 0.1].reset_index(drop=True)
        if len(eligible_df) < 500:  # fallback
            eligible_df = baseline_df[baseline_df['current'] >= 0.0].reset_index(drop=True)
    elif current_filter == 'discharge':
        eligible_df = baseline_df[baseline_df['current'] < -0.1].reset_index(drop=True)
        if len(eligible_df) < 500:  # fallback
            eligible_df = baseline_df[baseline_df['current'] <= 0.0].reset_index(drop=True)
    else:
        eligible_df = baseline_df.reset_index(drop=True)
        
    if len(eligible_df) < 100:
        eligible_df = baseline_df.reset_index(drop=True)  # final fallback to any data
        
    slice_len = 100  # Generate in small contiguous blocks of 100 rows to simulate cycles
    
    while total_generated < target_faults:
        # Determine size of next block
        block_len = min(slice_len, target_faults - total_generated)
        
        # Select a random starting point in the eligible data for a contiguous slice
        if len(eligible_df) - block_len > 0:
            start_idx = np.random.randint(0, len(eligible_df) - block_len)
        else:
            start_idx = 0
            
        slice_df = eligible_df.iloc[start_idx : start_idx + block_len].copy()
        
        # Apply fault injection
        faulty_slice = inject_func(slice_df)
        
        # Validate physical limits
        valid_mask = validate_physical_limits(faulty_slice)
        valid_slice = faulty_slice[valid_mask]
        
        rejected_in_block = len(faulty_slice) - len(valid_slice)
        rejected_count += rejected_in_block
        
        if len(valid_slice) > 0:
            generated_dfs.append(valid_slice)
            total_generated += len(valid_slice)
            
    df_out = pd.concat(generated_dfs, ignore_index=True)
    # Trim to exact size
    df_out = df_out.iloc[:target_faults].reset_index(drop=True)
    return df_out, rejected_count

def main():
    directory = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Load raw baseline data
    try:
        sheets_data, total_raw_rows, total_loaded_rows = load_baseline_data(directory)
    except Exception as e:
        print(f"Error loading baseline: {e}")
        sys.exit(1)
        
    # 2. Contiguous splitting per sheet (70 / 15 / 15) to prevent leakage
    train_sheets = []
    val_sheets = []
    test_sheets = []
    
    for df in sheets_data:
        N = len(df)
        train_idx = int(0.70 * N)
        val_idx = int(0.85 * N)
        
        train_sheets.append(df.iloc[:train_idx])
        val_sheets.append(df.iloc[train_idx:val_idx])
        test_sheets.append(df.iloc[val_idx:])
        
    train_base = pd.concat(train_sheets, ignore_index=True)
    val_base = pd.concat(val_sheets, ignore_index=True)
    test_base = pd.concat(test_sheets, ignore_index=True)
    
    # Deduplicate within each split separately (excluding file metadata)
    telemetry_cols = ['voltage', 'current', 'temperature', 'soc'] + [f'cell_v{i}' for i in range(1, 9)]
    
    train_base_uniq = train_base.drop_duplicates(subset=telemetry_cols).reset_index(drop=True)
    val_base_uniq = val_base.drop_duplicates(subset=telemetry_cols).reset_index(drop=True)
    test_base_uniq = test_base.drop_duplicates(subset=telemetry_cols).reset_index(drop=True)
    
    total_uniq_healthy = len(train_base_uniq) + len(val_base_uniq) + len(test_base_uniq)
    print(f"\nDeduplicated unique healthy rows: {total_uniq_healthy}")
    print(f" -> Train baseline: {len(train_base_uniq)} rows")
    print(f" -> Val baseline  : {len(val_base_uniq)} rows")
    print(f" -> Test baseline : {len(test_base_uniq)} rows")
    
    # 3. Generate datasets for splits
    # Target counts:
    # Train: 70k normal, 14k per fault class (140k total)
    # Val  : 15k normal, 3k per fault class (30k total)
    # Test : 15k normal, 3k per fault class (30k total)
    splits_config = {
        'train': {'normal': 70000, 'fault': 14000, 'base': train_base_uniq},
        'val': {'normal': 15000, 'fault': 3000, 'base': val_base_uniq},
        'test': {'normal': 15000, 'fault': 3000, 'base': test_base_uniq}
    }
    
    final_dfs = []
    
    print("\nGenerating split-isolated physics-informed fault datasets...")
    np.random.seed(42)  # For reproducible generation
    
    for split_name, config in splits_config.items():
        print(f"\n--- Processing Split: {split_name.upper()} ---")
        base = config['base']
        n_norm = config['normal']
        n_fault = config['fault']
        
        # Class 0: Normal
        # Sample directly from the unique baseline of this split
        df_normal = base.sample(n=n_norm, replace=False, random_state=42).copy()
        df_normal['fault_label'] = 0
        df_normal['split'] = split_name
        final_dfs.append(df_normal)
        print(f"  Class 0 (Normal): {len(df_normal)} rows loaded.")
        
        # Fault injection mapping
        fault_classes = [
            {"label": 1, "name": "Cell Imbalance", "func": inject_cell_imbalance, "filter": None},
            {"label": 2, "name": "Weak Cell", "func": inject_weak_cell, "filter": "discharge"},
            {"label": 3, "name": "Overvoltage Risk", "func": inject_overvoltage_risk, "filter": "charge"},
            {"label": 4, "name": "Undervoltage Risk", "func": inject_undervoltage_risk, "filter": "discharge"},
            {"label": 5, "name": "Overtemperature Risk", "func": inject_thermal_hotspot, "filter": None}
        ]
        
        for fc in fault_classes:
            df_fault, rejections = generate_fault_dataset(
                base, n_fault, fc["func"], current_filter=fc["filter"]
            )
            df_fault['split'] = split_name
            final_dfs.append(df_fault)
            print(f"  Class {fc['label']} ({fc['name']}): {len(df_fault)} rows generated (rejected {rejections} invalid rows).")
            
    # Concatenate all splits
    augmented_df = pd.concat(final_dfs, ignore_index=True)
    
    output_path = os.path.join(directory, "augmented_telemetry_dataset.xlsx")
    print(f"\nSaving balanced dataset containing {len(augmented_df)} rows to:")
    print(f" -> {output_path}")
    
    # Save to Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        augmented_df.to_excel(writer, sheet_name="Augmented Telemetry", index=False)
        
    # Generate and save a dataset summary report
    summary_report_path = os.path.join(directory, "dataset_summary_report.txt")
    with open(summary_report_path, "w") as f_report:
        f_report.write("BMS ML Training Dataset Summary Report\n")
        f_report.write("======================================\n\n")
        f_report.write(f"Total Combined Raw Row Count: {total_uniq_healthy} unique rows (from {total_loaded_rows} total rows loaded)\n")
        f_report.write(f"Final Training Target Dataset Size: {len(augmented_df)} rows\n\n")
        f_report.write("Row distribution by split:\n")
        for s in ['train', 'val', 'test']:
            split_count = len(augmented_df[augmented_df['split'] == s])
            f_report.write(f"  - {s.upper():<5}: {split_count} rows\n")
            
        f_report.write("\nClass-wise Row Count breakdown:\n")
        class_map = {0: "Normal", 1: "Cell Imbalance", 2: "Weak Cell", 3: "Overvoltage Risk", 4: "Undervoltage Risk", 5: "Overtemperature Risk"}
        counts = augmented_df['fault_label'].value_counts().sort_index()
        for label, count in counts.items():
            name = class_map.get(int(label), f"Class {label}")
            f_report.write(f"  - {name:<22}: {count} rows ({'Real Healthy Data' if label == 0 else 'Reliable Physics-Based Synthetic Faults'})\n")
            
    print(f"Saved dataset summary report to: {summary_report_path}")
    print("\nSUCCESS: Reliable synthetic fault generation complete!")

if __name__ == "__main__":
    main()
