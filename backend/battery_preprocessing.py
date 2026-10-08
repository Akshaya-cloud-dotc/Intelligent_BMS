#!/usr/bin/env python3
"""
battery_preprocessing.py — Feature Engineering & Grouped Cross-Validation Splitter
-----------------------------------------------------------------------------------
Prepares clean, normalized feature matrices for:
  1. SoH (State of Health) Estimation
  2. RUL (Remaining Useful Life) Quantile Regression
  3. Cell-Grouped Cross-Validation (prevents data leakage across cells)
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold

FEATURE_COLUMNS = [
    "cycle_index",
    "r_int_mohm",
    "r_int_growth_ratio",
    "dq_dv_peak",
    "delta_v_cycle",
    "v_drop_1c",
    "temp_ambient_c",
    "c_rate",
    "coulombic_efficiency"
]

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Computes physical and degradation features from cycling telemetry."""
    data = df.copy()
    
    # Internal resistance growth relative to 30 mOhm nominal
    data["r_int_growth_ratio"] = data["r_int_mohm"] / 30.0
    
    # Voltage drop under 1C current load
    if "v_drop_1c" not in data.columns:
        data["v_drop_1c"] = (data["r_int_mohm"] / 1000.0) * 5.0
        
    return data

def get_grouped_train_test_split(df: pd.DataFrame, test_cell_ratio: float = 0.20, seed: int = 42):
    """Splits dataset strictly by Cell ID so holdout cells are 100% unseen."""
    unique_cells = np.array(sorted(df["cell_id"].unique()))
    np.random.seed(seed)
    np.random.shuffle(unique_cells)
    
    n_test = max(1, int(len(unique_cells) * test_cell_ratio))
    test_cells = unique_cells[:n_test]
    train_cells = unique_cells[n_test:]
    
    train_df = df[df["cell_id"].isin(train_cells)].copy().reset_index(drop=True)
    test_df = df[df["cell_id"].isin(test_cells)].copy().reset_index(drop=True)
    
    print(f"[Grouped Split] Train Cells: {len(train_cells)} ({len(train_df)} cycles) | Test Cells: {len(test_cells)} ({len(test_df)} cycles)")
    return train_df, test_df, train_cells, test_cells

def prepare_training_matrices(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Extracts X and y arrays and fits standard scaler on training set only."""
    train_feat = engineer_features(train_df)
    test_feat = engineer_features(test_df)
    
    X_train = train_feat[FEATURE_COLUMNS].values
    y_soh_train = train_feat["soh_percent"].values
    y_rul_train = train_feat["rul_cycles_true"].values
    groups_train = train_feat["cell_id"].values
    
    X_test = test_feat[FEATURE_COLUMNS].values
    y_soh_test = test_feat["soh_percent"].values
    y_rul_test = test_feat["rul_cycles_true"].values
    groups_test = test_feat["cell_id"].values
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    return {
        "X_train": X_train_scaled,
        "X_train_raw": X_train,
        "y_soh_train": y_soh_train,
        "y_rul_train": y_rul_train,
        "groups_train": groups_train,
        "X_test": X_test_scaled,
        "X_test_raw": X_test,
        "y_soh_test": y_soh_test,
        "y_rul_test": y_rul_test,
        "groups_test": groups_test,
        "scaler": scaler,
        "feature_names": FEATURE_COLUMNS
    }

if __name__ == "__main__":
    from generate_aging_dataset import generate_lg_m50_aging_data
    df = generate_lg_m50_aging_data(num_cells=72)
    train_df, test_df, tr_cells, te_cells = get_grouped_train_test_split(df)
    data = prepare_training_matrices(train_df, test_df)
    print("Features successfully prepared:", data["feature_names"])
