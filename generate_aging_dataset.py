#!/usr/bin/env python3
"""
generate_aging_dataset.py — LG INR21700-M50 NMC Battery Degradation Dataset Generator
--------------------------------------------------------------------------------------
Simulates cycling degradation profiles for 72 distinct LG M50 cells (NMC 5000mAh)
incorporating:
  - Solid Electrolyte Interphase (SEI) growth & Loss of Lithium Inventory (LLI)
  - Loss of Active Material (LAM) and internal resistance growth (R_int)
  - Temperature (Arrhenius aging acceleration) and C-rate stress dependencies
  - Capacity fade from 100% (5.0 Ah) down to and past 80% EOL threshold
  - Output features: cycle_index, discharge_capacity_ah, soh_percent, r_int_mohm,
    temp_avg, c_rate, delta_v_cycle, dq_dv_peak, rul_cycles_true, cell_id
"""

import os
import numpy as np
import pandas as pd

def generate_lg_m50_aging_data(num_cells: int = 72, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    
    records = []
    
    # Datasheet specs for LG INR21700-M50
    NOMINAL_CAPACITY = 5.00  # Ah
    NOMINAL_R_INT = 30.0     # mOhm
    EOL_SOH = 80.0           # % (Standard End-of-Life)
    
    for cell_idx in range(1, num_cells + 1):
        cell_id = f"M50_Cell_{cell_idx:02d}"
        
        # Cell-to-cell manufacturing variance
        q_init = NOMINAL_CAPACITY * np.random.uniform(0.985, 1.025)  # 4.925 - 5.125 Ah
        r_init = NOMINAL_R_INT * np.random.uniform(0.92, 1.10)       # 27.6 - 33.0 mOhm
        
        # Operating stress conditions for this cell
        temp_c = np.random.choice([20.0, 25.0, 30.0, 35.0, 42.0], p=[0.15, 0.35, 0.25, 0.15, 0.10])
        c_rate = np.random.choice([0.5, 1.0, 1.5, 2.0], p=[0.25, 0.40, 0.25, 0.10])
        
        # Arrhenius temperature acceleration factor
        temp_k = temp_c + 273.15
        temp_ref_k = 298.15 # 25 C
        ea = 35000.0 # J/mol activation energy
        r_gas = 8.314
        arrhenius_factor = np.exp((ea / r_gas) * (1.0 / temp_ref_k - 1.0 / temp_k))
        
        # C-rate mechanical stress factor
        c_rate_factor = 1.0 + 0.35 * (c_rate - 0.5)
        
        # Combined aging acceleration factor
        aging_rate_mult = arrhenius_factor * c_rate_factor * np.random.uniform(0.92, 1.08)
        
        # Total lifetime cycles to ~75% SoH (500-750 cycles depending on stress)
        max_cycles = int(np.random.uniform(550, 780) / (aging_rate_mult ** 0.6))
        
        # Find exact cycle where cell reaches 80% EOL for ground truth RUL
        # SEI + LLI growth follows sqrt(cycle) + linear LAM + cubic knee onset
        sei_coeff = 0.00075 * aging_rate_mult
        lam_coeff = 0.00018 * aging_rate_mult
        knee_coeff = 0.0000008 * aging_rate_mult
        
        # Precompute capacity curve to determine true EOL cycle
        cycles = np.arange(1, max_cycles + 1)
        fade_fractions = sei_coeff * np.sqrt(cycles) + lam_coeff * cycles + knee_coeff * (cycles ** 2.2)
        capacities = q_init * np.maximum(0.65, 1.0 - fade_fractions)
        soh_values = (capacities / NOMINAL_CAPACITY) * 100.0
        
        # True EOL cycle (where SoH crosses 80.0%)
        eol_candidates = np.where(soh_values <= EOL_SOH)[0]
        eol_cycle = int(cycles[eol_candidates[0]]) if len(eol_candidates) > 0 else max_cycles
        
        for cyc_idx, cyc in enumerate(cycles):
            cap_true = capacities[cyc_idx]
            soh_true = soh_values[cyc_idx]
            
            # Remaining Useful Life in cycles (capped at 0 after EOL)
            rul_true = max(0, eol_cycle - cyc)
            
            # Internal Resistance growth (mOhm)
            r_growth_factor = 1.0 + 0.0018 * aging_rate_mult * cyc + 0.000003 * (cyc ** 2.0)
            r_int = r_init * r_growth_factor + np.random.normal(0, 0.4)
            r_int = max(25.0, r_int)
            
            # Incremental Capacity (dQ/dV) peak height degrades proportionally to active material
            dq_dv_peak = 3.2 * (soh_true / 100.0) ** 1.4 + np.random.normal(0, 0.04)
            
            # Cell spread / delta_v increases as cell ages
            delta_v_cyc = 0.006 + 0.00008 * cyc + (0.04 if soh_true < 82.0 else 0.0) + np.random.normal(0, 0.002)
            delta_v_cyc = max(0.003, delta_v_cyc)
            
            # Voltage drop under 1C discharge (V)
            v_drop_1c = (r_int / 1000.0) * (NOMINAL_CAPACITY * 1.0)
            
            # Energy throughput (cumulative kWh delivered by this cell)
            energy_throughput_kwh = cyc * (cap_true * 3.63) / 1000.0
            
            # Coulombic efficiency (%)
            coulombic_eff = 99.85 - 0.0005 * cyc + np.random.normal(0, 0.05)
            coulombic_eff = min(99.98, max(97.5, coulombic_eff))
            
            records.append({
                "cell_id": cell_id,
                "cycle_index": int(cyc),
                "discharge_capacity_ah": round(float(cap_true), 4),
                "soh_percent": round(float(soh_true), 2),
                "rul_cycles_true": int(rul_true),
                "r_int_mohm": round(float(r_int), 3),
                "dq_dv_peak": round(float(dq_dv_peak), 4),
                "delta_v_cycle": round(float(delta_v_cyc), 4),
                "v_drop_1c": round(float(v_drop_1c), 4),
                "temp_ambient_c": round(float(temp_c), 1),
                "c_rate": round(float(c_rate), 2),
                "energy_throughput_kwh": round(float(energy_throughput_kwh), 4),
                "coulombic_efficiency": round(float(coulombic_eff), 3),
                "is_eol": bool(soh_true <= EOL_SOH)
            })
            
    df = pd.DataFrame(records)
    return df

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "lg_m50_aging_dataset.csv")
    print("Generating 72-cell LG INR21700-M50 electrochemical aging dataset...")
    df = generate_lg_m50_aging_data(num_cells=72, seed=42)
    df.to_csv(out_path, index=False)
    print(f"Dataset generated: {len(df)} cycles across {df['cell_id'].nunique()} cells.")
    print(f"Saved to: {out_path}")
    print("\nDataset Summary:")
    print(df.describe().T[["mean", "std", "min", "50%", "max"]])
