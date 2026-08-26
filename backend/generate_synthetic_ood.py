import os
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

INPUT_FILE = os.path.join(DATA_DIR, "augmented_telemetry_dataset.xlsx")
OUTPUT_FILE = os.path.join(DATA_DIR, "synthetic_ood_dataset.csv")

def generate_ood_data():
    print(f"Reading reference distribution from {INPUT_FILE}...")
    df_ref = pd.read_excel(INPUT_FILE)
    
    # Standardize columns internally
    orig_columns = df_ref.columns.tolist()
    
    # We will generate synthetic sequences of length 60 (standard window)
    window_size = 60
    num_sequences = 200 # Total 12,000 rows
    
    synthetic_dfs = []
    
    # Get standard deviations of physical variables to perturb proportionally
    v_std = df_ref['voltage'].std() if 'voltage' in df_ref.columns else 1.0
    c_std = df_ref['current'].std() if 'current' in df_ref.columns else 10.0
    t_std = df_ref['temperature'].std() if 'temperature' in df_ref.columns else 2.0
    
    for seq_i in range(num_sequences):
        # Sample a random sequence as base
        start_idx = np.random.randint(0, len(df_ref) - window_size)
        seq_df = df_ref.iloc[start_idx : start_idx + window_size].copy()
        
        # Reset index for easy perturbation
        seq_df = seq_df.reset_index(drop=True)
        
        # Determine anomaly type
        anomaly_type = np.random.choice([
            "rapid_oscillation",
            "physical_inconsistency",
            "sudden_jump",
            "abnormal_temp_rise",
            "multiple_weak_cells",
            "sensor_stuck"
        ])
        
        if anomaly_type == "rapid_oscillation":
            # Oscillate cell voltages rapidly (unrealistic for chemistry)
            for i in range(window_size):
                if i % 2 == 0:
                    seq_df.loc[i, 'cell_v1'] += 0.3
                    seq_df.loc[i, 'cell_v2'] -= 0.3
        
        elif anomaly_type == "physical_inconsistency":
            # High discharge current but voltage rises (impossible)
            seq_df['current'] = -150.0  # Heavy discharge
            seq_df['voltage'] = seq_df['voltage'] + np.linspace(0, 5, window_size)
            seq_df['cell_v3'] = seq_df['cell_v3'] + np.linspace(0, 0.5, window_size)
            
        elif anomaly_type == "sudden_jump":
            # Discontinuous jump in the middle
            mid = window_size // 2
            seq_df.loc[mid:, 'voltage'] += 8.0
            seq_df.loc[mid:, 'current'] -= 200.0
            
        elif anomaly_type == "abnormal_temp_rise":
            # Extreme temperature rise with zero current
            seq_df['current'] = 0.0
            seq_df['temperature'] = seq_df['temperature'] + np.linspace(0, 30, window_size)
            
        elif anomaly_type == "multiple_weak_cells":
            # Cells 1, 4, 7 all drop erratically and randomly
            for col in ['cell_v1', 'cell_v4', 'cell_v7']:
                seq_df[col] -= np.random.uniform(0.5, 1.5, window_size)
                
        elif anomaly_type == "sensor_stuck":
            # Sensor completely frozen while others move
            seq_df['cell_v5'] = 2.012  # Exact frozen value
            seq_df['temperature'] = 85.4
            seq_df['current'] = np.random.uniform(-10, 10, window_size) # Random noise
            
        # Add metadata fields
        seq_df['is_synthetic'] = 1
        seq_df['ood_source'] = 'synthetic'
        seq_df['display_label'] = 'UNKNOWN_FAULT_OOD'
        if 'fault_label' in seq_df.columns:
            seq_df['fault_label'] = 'UNKNOWN_FAULT_OOD'
            
        synthetic_dfs.append(seq_df)
        
    df_ood = pd.concat(synthetic_dfs, ignore_index=True)
    
    df_ood.to_csv(OUTPUT_FILE, index=False)
    print(f"Generated {len(df_ood)} rows of Out-Of-Distribution data.")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_ood_data()
