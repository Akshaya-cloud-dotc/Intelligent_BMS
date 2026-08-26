import pandas as pd
import numpy as np
import json
import os

def classify_operating_modes(df, recompute_thresholds=True, threshold_path="mode_thresholds.json"):
    """
    Applies dynamic thresholds, smoothing, and hysteresis to classify rows
    into IDLE, CRUISE, ACCEL, and DECEL.
    """
    df = df.copy()
    
    # 1. Smoothing
    df['smoothed_current'] = df['current'].rolling(window=3, min_periods=1).mean()
    df['dI_dt'] = df['smoothed_current'].diff().fillna(0)
    
    # 2. Dynamic Thresholds
    if recompute_thresholds or not os.path.exists(threshold_path):
        idle_threshold = max(0.5, 0.05 * df['current'].abs().mean())
        stability_threshold = max(0.1, 0.5 * df['dI_dt'].std())
        
        thresholds = {
            "idle_threshold": idle_threshold,
            "stability_threshold": stability_threshold,
            "acceleration_threshold": stability_threshold,
            "deceleration_threshold": stability_threshold
        }
        with open(threshold_path, 'w') as f:
            json.dump(thresholds, f, indent=4)
    else:
        with open(threshold_path, 'r') as f:
            thresholds = json.load(f)
            idle_threshold = thresholds["idle_threshold"]
            stability_threshold = thresholds["stability_threshold"]
    
    accel_thresh = thresholds["acceleration_threshold"]
    decel_thresh = thresholds["deceleration_threshold"]
    
    # 3. Initial Classification
    raw_modes = []
    for idx, row in df.iterrows():
        i = row['smoothed_current']
        di = row['dI_dt']
        
        if abs(i) < idle_threshold:
            raw_modes.append('IDLE')
        elif abs(di) <= stability_threshold:
            raw_modes.append('CRUISE')
        elif di > accel_thresh:
            # Positive dI/dt (current increasing)
            # Depending on convention, if discharge is negative, a positive di means moving towards zero or charging.
            # Usually, rapid load increase during discharge means current goes more negative (di < 0).
            # Wait, if current is discharge (-100A), an increase in load means -120A, so di = -20.
            # Let's use absolute current changes for ACCEL/DECEL.
            # d(|I|)/dt
            raw_modes.append('ACCEL_RAW')
        else:
            raw_modes.append('DECEL_RAW')
            
    # Let's compute rate of change of absolute current to correctly identify ACCEL/DECEL regardless of charge/discharge polarity
    df['abs_current'] = df['smoothed_current'].abs()
    df['dAbsI_dt'] = df['abs_current'].diff().fillna(0)
    
    raw_modes = []
    for idx, row in df.iterrows():
        i = row['smoothed_current']
        d_abs_i = row['dAbsI_dt']
        
        if abs(i) < idle_threshold:
            raw_modes.append('IDLE')
        elif abs(d_abs_i) <= stability_threshold:
            raw_modes.append('CRUISE')
        elif d_abs_i > accel_thresh:
            raw_modes.append('ACCEL') # Absolute current is increasing rapidly
        else:
            raw_modes.append('DECEL') # Absolute current is decreasing rapidly
            
    df['Raw_Mode'] = raw_modes
    
    # 4. Hysteresis / Persistence Filtering
    PERSIST_SAMPLES = 3
    final_modes = []
    current_mode = 'IDLE'
    streak = 0
    candidate_mode = 'IDLE'
    
    for mode in raw_modes:
        if mode == candidate_mode:
            streak += 1
        else:
            candidate_mode = mode
            streak = 1
            
        if streak >= PERSIST_SAMPLES:
            current_mode = candidate_mode
            
        final_modes.append(current_mode)
        
    df['Operating_Mode'] = final_modes
    df.drop(columns=['smoothed_current', 'dI_dt', 'abs_current', 'dAbsI_dt', 'Raw_Mode'], inplace=True)
    return df
