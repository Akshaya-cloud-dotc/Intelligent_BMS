#!/usr/bin/env python3
"""
generate_realistic_fault_datasets.py
------------------------------------
Generates physics-informed datasets with realistic dynamical progressions:
1. Normal Baseline Phase (Pack ~29.15V, Cells ~3.64-3.65V, Delta V ~0.015V, Temp ~28.5°C)
2. Risk Developing Phase ("That risk coming" - Warning limits approached and crossed)
3. Active Critical Fault Phase (Safety limits breached - Overvoltage >4.25V, Undervoltage <2.80V, 
   Cell Imbalance dV >0.20V, Weak Cell sag dV >0.25V, Overtemp >60°C, Overcurrent >20A)

Generates:
- bms_data_labeled.xlsx (6,000 rows, 1,000 per stage)
- data/bms_data_labeled.xlsx
- data/BMS_Fault_Overvoltage.xlsx (200 rows)
- data/BMS_Fault_Undervoltage.xlsx (200 rows)
- data/BMS_Fault_Cell_Imbalance.xlsx (200 rows)
- data/BMS_Fault_Weak_Cell.xlsx (200 rows)
- data/BMS_Fault_Overtemperature.xlsx (200 rows)
- data/BMS_Fault_Overcurrent.xlsx (200 rows)
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

np.random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# 1. GENERATE OVERVOLTAGE
# ─────────────────────────────────────────────────────────────────────────────
def generate_overvoltage_block(n_rows=1000):
    n_normal = 40 if n_rows >= 500 else 30
    n_risk = 70 if n_rows >= 500 else 50
    n_crit = n_rows - n_normal - n_risk

    rows = []
    base_time = datetime(2026, 6, 16, 11, 0, 0)
    
    # 1. Normal
    for i in range(n_normal):
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.645 + np.sin(i * 0.05) * 0.005
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        cur = round(2.0 + np.random.normal(0, 0.1), 2)
        temp = round(28.5 + np.random.normal(0, 0.2), 1)
        soc = round(65.0 + (i * 0.02), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.1, 1),
            "cycle": 1, "source_file": "BMS_Fault_Overvoltage.xlsx", "source_sheet": "Sheet1",
            "fault_label": 3, "split": "TRAIN", "charge_discharge": "Charge",
            "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })

    # 2. Risk Coming (Fast charge +8.5A, cells rise 3.65V -> 4.18V, approaching warning limit 4.15V)
    for i in range(n_risk):
        t = i / float(n_risk)
        cur = round(8.5 + np.random.normal(0, 0.15), 2)
        base_v = 3.65 + t * (4.18 - 3.65)
        noise = np.random.normal(0, 0.003, 8)
        cells = [round(base_v + noise[j] + (j * 0.0015), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(28.5 + t * 6.5 + np.random.normal(0, 0.2), 1)
        soc = round(66.0 + t * 28.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": min(98.0, soc),
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.3, 1), "ntc4": round(temp + 0.2, 1),
            "cycle": 1, "source_file": "BMS_Fault_Overvoltage.xlsx", "source_sheet": "Sheet1",
            "fault_label": 3, "split": "TRAIN", "charge_discharge": "Charge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Overvoltage Risk"
        })

    # 3. Critical Overvoltage (Cells reach 4.26V -> 4.36V, Pack reaches 34.1V -> 34.8V, exceeding 33.6V)
    for i in range(n_crit):
        t = i / float(n_crit)
        cur = round(8.5 + np.random.normal(0, 0.1), 2)
        base_v = 4.26 + t * 0.10
        noise = np.random.normal(0, 0.003, 8)
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        cells[7] = round(cells[7] + 0.015, 3) # cell 8 leading
        v_pack = round(sum(cells), 2)
        temp = round(35.0 + t * 6.0 + np.random.normal(0, 0.2), 1)
        soc = 100.0
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": round(temp + 0.3, 1), "ntc3": round(temp - 0.2, 1), "ntc4": temp,
            "cycle": 1, "source_file": "BMS_Fault_Overvoltage.xlsx", "source_sheet": "Sheet1",
            "fault_label": 3, "split": "TRAIN", "charge_discharge": "Charge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + n_risk + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Overvoltage"
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 2. GENERATE UNDERVOLTAGE
# ─────────────────────────────────────────────────────────────────────────────
def generate_undervoltage_block(n_rows=1000):
    n_normal = 40 if n_rows >= 500 else 30
    n_risk = 70 if n_rows >= 500 else 50
    n_crit = n_rows - n_normal - n_risk

    rows = []
    base_time = datetime(2026, 6, 16, 12, 0, 0)
    
    # 1. Normal
    for i in range(n_normal):
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.640 - np.sin(i * 0.05) * 0.005
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        cur = round(-2.5 + np.random.normal(0, 0.1), 2)
        temp = round(28.5 + np.random.normal(0, 0.2), 1)
        soc = round(45.0 - (i * 0.02), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.1, 1),
            "cycle": 1, "source_file": "BMS_Fault_Undervoltage.xlsx", "source_sheet": "Sheet1",
            "fault_label": 4, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })

    # 2. Risk Coming (discharge -11A, cells drop 3.60V -> 2.92V, approaching 3.00V warning)
    for i in range(n_risk):
        t = i / float(n_risk)
        cur = round(-11.0 + np.random.normal(0, 0.2), 2)
        base_v = 3.60 - t * (3.60 - 2.92)
        noise = np.random.normal(0, 0.003, 8)
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(28.5 + t * 4.5 + np.random.normal(0, 0.15), 1)
        soc = round(max(5.0, 44.0 - t * 36.0), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.2, 1),
            "cycle": 1, "source_file": "BMS_Fault_Undervoltage.xlsx", "source_sheet": "Sheet1",
            "fault_label": 4, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Undervoltage Risk"
        })

    # 3. Critical Undervoltage (cells 2.75V down to 2.45V, pack 21.6V -> 19.6V, clearly below 22.0V)
    for i in range(n_crit):
        t = i / float(n_crit)
        cur = round(-11.5 + np.random.normal(0, 0.15), 2)
        base_v = 2.75 - t * (2.75 - 2.45)
        noise = np.random.normal(0, 0.003, 8)
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        cells[3] = round(cells[3] - 0.020, 3)
        v_pack = round(sum(cells), 2)
        temp = round(33.0 + t * 3.0 + np.random.normal(0, 0.15), 1)
        soc = round(max(0.0, 5.0 - t * 5.0), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.2, 1),
            "cycle": 1, "source_file": "BMS_Fault_Undervoltage.xlsx", "source_sheet": "Sheet1",
            "fault_label": 4, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + n_risk + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Undervoltage"
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 3. GENERATE CELL IMBALANCE
# ─────────────────────────────────────────────────────────────────────────────
def generate_cell_imbalance_block(n_rows=1000):
    n_normal = 40 if n_rows >= 500 else 30
    n_risk = 70 if n_rows >= 500 else 50
    n_crit = n_rows - n_normal - n_risk

    rows = []
    base_time = datetime(2026, 6, 16, 13, 0, 0)
    
    # 1. Normal Balanced
    for i in range(n_normal):
        noise = np.random.normal(0, 0.002, 8)
        base_v = 3.645
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        cur = round(-4.0 + np.random.normal(0, 0.1), 2)
        temp = round(28.8 + np.random.normal(0, 0.15), 1)
        soc = round(70.0 - (i * 0.015), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.1, 1),
            "cycle": 1, "source_file": "BMS_Fault_Cell_Imbalance.xlsx", "source_sheet": "Sheet1",
            "fault_label": 1, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })

    # 2. Risk Coming (Cell 4 drifts down, delta_v grows from 0.020V to 0.145V)
    for i in range(n_risk):
        t = i / float(n_risk)
        cur = round(-5.0 + np.random.normal(0, 0.15), 2)
        noise = np.random.normal(0, 0.002, 8)
        base_v = 3.620 - t * 0.04
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        cells[3] = round(cells[3] - (0.02 + t * 0.125), 3)
        v_pack = round(sum(cells), 2)
        temp = round(29.0 + t * 2.0 + np.random.normal(0, 0.15), 1)
        soc = round(69.0 - t * 10.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.1, 1),
            "cycle": 1, "source_file": "BMS_Fault_Cell_Imbalance.xlsx", "source_sheet": "Sheet1",
            "fault_label": 1, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Cell Imbalance Risk"
        })

    # 3. Critical Imbalance (delta_v reaches 0.22V -> 0.34V, cell 4 lagging deeply)
    for i in range(n_crit):
        t = i / float(n_crit)
        cur = round(-5.0 + np.random.normal(0, 0.15), 2)
        noise = np.random.normal(0, 0.002, 8)
        base_v = 3.580
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        cells[3] = round(cells[3] - (0.160 + t * 0.150), 3)
        v_pack = round(sum(cells), 2)
        temp = round(31.0 + t * 1.5 + np.random.normal(0, 0.15), 1)
        soc = round(58.0 - t * 15.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.1, 1),
            "cycle": 1, "source_file": "BMS_Fault_Cell_Imbalance.xlsx", "source_sheet": "Sheet1",
            "fault_label": 1, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + n_risk + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Cell Imbalance"
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 4. GENERATE WEAK CELL
# ─────────────────────────────────────────────────────────────────────────────
def generate_weak_cell_block(n_rows=1000):
    n_normal = 40 if n_rows >= 500 else 30
    n_risk = 70 if n_rows >= 500 else 50
    n_crit = n_rows - n_normal - n_risk

    rows = []
    base_time = datetime(2026, 6, 16, 14, 0, 0)
    
    # 1. Normal (Low current / Idle resting state)
    for i in range(n_normal):
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.650
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        cur = round(-0.5 + np.random.normal(0, 0.05), 2)
        temp = round(28.2 + np.random.normal(0, 0.1), 1)
        soc = 75.0
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": temp, "ntc4": temp,
            "cycle": 1, "source_file": "BMS_Fault_Weak_Cell.xlsx", "source_sheet": "Sheet1",
            "fault_label": 2, "split": "TRAIN", "charge_discharge": "Idle",
            "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })

    # 2. Risk Coming (Load steps to -8A, Cell 3 high Ri starts showing voltage sag to 3.32V, dV ~0.15V)
    for i in range(n_risk):
        t = i / float(n_risk)
        cur = round(-7.5 + np.random.normal(0, 0.15), 2)
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.560 - t * 0.04
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        cells[2] = round(cells[2] - (0.05 + t * 0.12), 3)
        v_pack = round(sum(cells), 2)
        temp = round(28.5 + t * 3.0 + np.random.normal(0, 0.1), 1)
        soc = round(74.0 - t * 8.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp + 1.2, 1), "ntc4": temp,
            "cycle": 1, "source_file": "BMS_Fault_Weak_Cell.xlsx", "source_sheet": "Sheet1",
            "fault_label": 2, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Weak Cell Risk"
        })

    # 3. Critical Weak Cell (Heavy accel -12.5A, Cell 3 drops to 2.82V, dV ~0.30V)
    for i in range(n_crit):
        t = i / float(n_crit)
        cur = round(-12.5 + np.random.normal(0, 0.15), 2)
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.480
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        cells[2] = round(cells[2] - (0.22 + t * 0.10), 3)
        v_pack = round(sum(cells), 2)
        temp = round(32.0 + t * 3.5 + np.random.normal(0, 0.15), 1)
        soc = round(65.0 - t * 15.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp + 3.0, 1), "ntc4": temp,
            "cycle": 1, "source_file": "BMS_Fault_Weak_Cell.xlsx", "source_sheet": "Sheet1",
            "fault_label": 2, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + n_risk + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Weak Cell"
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 5. GENERATE OVERTEMPERATURE
# ─────────────────────────────────────────────────────────────────────────────
def generate_overtemperature_block(n_rows=1000):
    n_normal = 40 if n_rows >= 500 else 30
    n_risk = 70 if n_rows >= 500 else 50
    n_crit = n_rows - n_normal - n_risk

    rows = []
    base_time = datetime(2026, 6, 16, 15, 0, 0)
    
    # 1. Normal Cool
    for i in range(n_normal):
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.640
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        cur = round(-5.0 + np.random.normal(0, 0.1), 2)
        temp = round(28.5 + np.random.normal(0, 0.15), 1)
        soc = round(80.0 - (i * 0.015), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": round(temp - 0.2, 1), "ntc4": round(temp + 0.1, 1),
            "cycle": 1, "source_file": "BMS_Fault_Overtemperature.xlsx", "source_sheet": "Sheet1",
            "fault_label": 5, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })

    # 2. Risk Coming (Temp climbs 29°C -> 56°C, approaching 50-55°C limit)
    for i in range(n_risk):
        t = i / float(n_risk)
        cur = round(-9.5 + np.random.normal(0, 0.15), 2)
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.600 - t * 0.08
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(29.0 + t * (56.5 - 29.0) + np.random.normal(0, 0.2), 1)
        soc = round(79.0 - t * 15.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": round(temp + 1.5, 1), "ntc3": round(temp - 1.0, 1), "ntc4": temp,
            "cycle": 1, "source_file": "BMS_Fault_Overtemperature.xlsx", "source_sheet": "Sheet1",
            "fault_label": 5, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Overtemperature Risk"
        })

    # 3. Critical Overtemp (Temp reaches 58°C -> 68°C, exceeding 60°C critical)
    for i in range(n_crit):
        t = i / float(n_crit)
        cur = round(-10.0 + np.random.normal(0, 0.1), 2)
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.510 - t * 0.05
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(57.5 + t * (68.5 - 57.5) + np.random.normal(0, 0.2), 1)
        soc = round(63.0 - t * 15.0, 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": round(temp + 2.0, 1), "ntc2": temp, "ntc3": round(temp - 1.5, 1), "ntc4": temp,
            "cycle": 1, "source_file": "BMS_Fault_Overtemperature.xlsx", "source_sheet": "Sheet1",
            "fault_label": 5, "split": "TRAIN", "charge_discharge": "Discharge",
            "timestamp": (base_time + timedelta(seconds=(n_normal + n_risk + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Overtemperature"
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 6. GENERATE OVERCURRENT
# ─────────────────────────────────────────────────────────────────────────────
def generate_overcurrent_block(n_rows=200):
    n_normal = 30
    n_risk = 50
    n_crit = n_rows - n_normal - n_risk

    rows = []
    base_time = datetime(2026, 6, 16, 16, 0, 0)
    
    # 1. Normal
    for i in range(n_normal):
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.640
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        cur = round(-5.0 + np.random.normal(0, 0.1), 2)
        temp = round(28.5 + np.random.normal(0, 0.15), 1)
        soc = 75.0
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": temp, "ntc4": temp,
            "mode": 1, "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })

    # 2. Risk Coming (Current rises -10A -> -18A, crossing warning 15A)
    for i in range(n_risk):
        t = i / float(n_risk)
        cur = round(-10.0 - t * 8.5 + np.random.normal(0, 0.2), 2)
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.600 - t * 0.10
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(29.0 + t * 6.0, 1)
        soc = 70.0
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": temp, "ntc4": temp,
            "mode": 1, "timestamp": (base_time + timedelta(seconds=(n_normal + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Overcurrent Risk"
        })

    # 3. Critical Overcurrent (Current surges -22A -> -26A, exceeding 20A critical)
    for i in range(n_crit):
        t = i / float(n_crit)
        cur = round(-21.5 - t * 4.5 + np.random.normal(0, 0.2), 2)
        noise = np.random.normal(0, 0.003, 8)
        base_v = 3.450 - t * 0.15
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(36.0 + t * 8.0, 1)
        soc = 65.0
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": temp, "ntc3": temp, "ntc4": temp,
            "mode": 1, "timestamp": (base_time + timedelta(seconds=(n_normal + n_risk + i) * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Overcurrent"
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 7. GENERATE PURE NORMAL (1000 rows)
# ─────────────────────────────────────────────────────────────────────────────
def generate_normal_block(n_rows=1000):
    rows = []
    base_time = datetime(2026, 6, 16, 9, 0, 0)
    for i in range(n_rows):
        noise = np.random.normal(0, 0.003, 8)
        cycle_phase = (i % 200) / 200.0
        if cycle_phase < 0.4:
            cur = round(-4.5 + np.random.normal(0, 0.2), 2)
            base_v = 3.630 - cycle_phase * 0.05
            chg = "Discharge"
        elif cycle_phase < 0.6:
            cur = round(0.0 + np.random.normal(0, 0.05), 2)
            base_v = 3.620
            chg = "Idle"
        else:
            cur = round(3.5 + np.random.normal(0, 0.2), 2)
            base_v = 3.630 + (cycle_phase - 0.6) * 0.05
            chg = "Charge"
            
        cells = [round(base_v + noise[j] + (j * 0.001), 3) for j in range(8)]
        v_pack = round(sum(cells), 2)
        temp = round(28.5 + np.sin(i * 0.02) * 1.5 + np.random.normal(0, 0.1), 1)
        soc = round(72.0 - (i * 0.01), 1)
        dv = round(max(cells) - min(cells), 3)
        rows.append({
            "voltage": v_pack, "current": cur, "temperature": temp, "soc": soc,
            **{f"cell_v{j+1}": cells[j] for j in range(8)},
            "delta_v": dv, "ntc1": temp, "ntc2": round(temp + 0.2, 1), "ntc3": round(temp - 0.2, 1), "ntc4": temp,
            "cycle": 1, "source_file": "BMS_balanced_6_June.xlsx", "source_sheet": "Sheet1",
            "fault_label": 0, "split": "TRAIN", "charge_discharge": chg,
            "timestamp": (base_time + timedelta(seconds=i * 0.5)).strftime("%Y-%m-%d %H:%M:%S"),
            "label": "Normal"
        })
    return pd.DataFrame(rows)


def main():
    print("Generating comprehensive realistic datasets with Normal onset and Risk transitions...")
    
    df_normal = generate_normal_block(1000)
    df_imbalance = generate_cell_imbalance_block(1000)
    df_weak_cell = generate_weak_cell_block(1000)
    df_overvoltage = generate_overvoltage_block(1000)
    df_undervoltage = generate_undervoltage_block(1000)
    df_overtemp = generate_overtemperature_block(1000)

    # Combine into bms_data_labeled.xlsx (6,000 contiguous rows)
    combined = pd.concat([
        df_normal,
        df_imbalance,
        df_weak_cell,
        df_overvoltage,
        df_undervoltage,
        df_overtemp
    ], ignore_index=True)

    dest_labeled_root = os.path.join(PROJECT_ROOT, "bms_data_labeled.xlsx")
    dest_labeled_data = os.path.join(DATA_DIR, "bms_data_labeled.xlsx")
    print(f"Writing bms_data_labeled.xlsx ({len(combined)} rows)...")
    combined.to_excel(dest_labeled_root, index=False)
    combined.to_excel(dest_labeled_data, index=False)
    print("  -> Saved to root and data/")

    # Also generate individual 200-row benchmark files in data/
    print("Generating individual 200-row benchmark files in data/...")
    cols_200 = ["timestamp", "voltage", "current", "temperature", "soc", "mode", "delta_v",
                "cell_v1", "cell_v2", "cell_v3", "cell_v4", "cell_v5", "cell_v6", "cell_v7", "cell_v8", "label"]

    def export_individual(df_source, filename):
        df = df_source.copy()
        if "mode" not in df.columns:
            df["mode"] = 1
        sub_cols = [c for c in cols_200 if c in df.columns]
        out_path = os.path.join(DATA_DIR, filename)
        df[sub_cols].to_excel(out_path, index=False)
        print(f"  -> Saved {filename} ({len(df)} rows)")

    export_individual(generate_overvoltage_block(200), "BMS_Fault_Overvoltage.xlsx")
    export_individual(generate_undervoltage_block(200), "BMS_Fault_Undervoltage.xlsx")
    export_individual(generate_cell_imbalance_block(200), "BMS_Fault_Cell_Imbalance.xlsx")
    export_individual(generate_weak_cell_block(200), "BMS_Fault_Weak_Cell.xlsx")
    export_individual(generate_overtemperature_block(200), "BMS_Fault_Overtemperature.xlsx")
    export_individual(generate_overcurrent_block(200), "BMS_Fault_Overcurrent.xlsx")

    print("\nDataset generation completed successfully!")

if __name__ == "__main__":
    main()
