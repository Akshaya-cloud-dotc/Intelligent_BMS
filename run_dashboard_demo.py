#!/usr/bin/env python3
"""
run_dashboard_demo.py — Fault Replay Demo Orchestrator
-------------------------------------------------------
- Presents an interactive numbered menu (1-7, 0).
- Loads labeled telemetry from bms_data_labeled.xlsx.
- Slices contiguous time-series blocks to preserve realistic dynamical behavior.
- Prepends ~30 Normal rows for visible Normal -> Fault transitions.
- Replays at configurable rate (default 2 rows/sec).
- Stamped with "source": "replay:<fault>".
- Dashboard detects replay source and renders a prominent warning banner.
- Cleanly returns to menu after completion or interruption.
"""

import os
import sys
import time
import json
import webbrowser
import urllib.request
import urllib.error
from datetime import datetime
import pandas as pd

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

# ==============================================================================
# CONFIGURATION
# ==============================================================================
INGEST_URL = os.getenv("INGEST_URL", "https://intelligentbms-production.up.railway.app/api/telemetry")
INGEST_TOKEN = os.getenv("INGEST_TOKEN", "").strip()
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://intelligentbms-production.up.railway.app/live-monitor")
REPLAY_RATE_HZ = float(os.getenv("REPLAY_RATE_HZ", "2.0"))
REPLAY_NORMAL_PREFIX = int(os.getenv("REPLAY_NORMAL_PREFIX", "30"))
REPLAY_MAX_ROWS = int(os.getenv("REPLAY_MAX_ROWS", "300"))
DEMO_DATASET_PATH = os.getenv("DEMO_DATASET_PATH", "bms_data_labeled.xlsx")

# Cached DataFrame in memory
_CACHED_DF = None
_BROWSER_OPENED = False


def get_dataset() -> pd.DataFrame:
    """Finds and loads the labeled dataset, caching in memory."""
    global _CACHED_DF
    if _CACHED_DF is not None:
        return _CACHED_DF

    candidates = [
        DEMO_DATASET_PATH,
        os.path.join(project_root, DEMO_DATASET_PATH),
        os.path.join(project_root, "bms_data_labeled.xlsx"),
        os.path.join(project_root, "data", "bms_data_labeled.xlsx"),
        os.path.join(project_root, "data", "augmented_telemetry_dataset.xlsx")
    ]

    loaded_path = None
    for p in candidates:
        if os.path.exists(p):
            loaded_path = p
            break

    if not loaded_path:
        print("\n[ERROR] Could not find demo dataset!")
        print(f"Searched paths:\n  " + "\n  ".join(candidates))
        print("Please check DEMO_DATASET_PATH in .env.\n")
        sys.exit(1)

    print(f"Loading dataset from: {os.path.basename(loaded_path)}...", end="", flush=True)
    t0 = time.time()
    if loaded_path.endswith(".csv"):
        df = pd.read_csv(loaded_path)
    else:
        df = pd.read_excel(loaded_path)
    print(f" done ({len(df)} rows in {time.time() - t0:.2f}s).")

    # Standardize column naming
    if "fault_label" not in df.columns and "label" in df.columns:
        # map string label to int
        str_to_id = {
            "Normal": 0, "Cell Imbalance": 1, "Weak Cell": 2, 
            "Overvoltage": 3, "Overvoltage Risk": 3,
            "Undervoltage": 4, "Undervoltage Risk": 4,
            "Overtemperature": 5, "Overtemperature Risk": 5
        }
        df["fault_label"] = df["label"].map(str_to_id).fillna(0).astype(int)

    _CACHED_DF = df
    return _CACHED_DF


def extract_contiguous_block(df: pd.DataFrame, fault_id: int) -> pd.DataFrame:
    """Extracts the largest contiguous sequence for a given fault_id."""
    sub = df[df["fault_label"] == fault_id]
    if len(sub) == 0:
        return pd.DataFrame()

    diff = sub.index.to_series().diff()
    block_ids = (diff != 1).cumsum()
    best_block_id = block_ids.value_counts().index[0]
    best_indices = sub[block_ids == best_block_id].index
    return df.loc[best_indices].copy()


def prepare_replay_rows(choice: int) -> tuple[str, list[dict]]:
    """
    Constructs the sequence of rows to replay based on user selection:
    [1] Normal
    [2] Cell Imbalance
    [3] Weak Cell
    [4] Overvoltage
    [5] Undervoltage
    [6] Overtemperature
    [7] Mixed / full cycle
    """
    df = get_dataset()

    fault_map = {
        1: ("Normal", 0),
        2: ("Cell Imbalance", 1),
        3: ("Weak Cell", 2),
        4: ("Overvoltage", 3),
        5: ("Undervoltage", 4),
        6: ("Overtemperature", 5)
    }

    if choice == 1:
        fault_name = "Normal"
        normal_block = extract_contiguous_block(df, 0)
        rows_df = normal_block.iloc[:REPLAY_MAX_ROWS]
        normal_count = len(rows_df)
        fault_count = 0

    elif choice in range(2, 7):
        fault_name, fault_id = fault_map[choice]
        normal_block = extract_contiguous_block(df, 0)
        fault_block = extract_contiguous_block(df, fault_id)

        if len(fault_block) < 10:
            print(f"\n[WARNING] Only {len(fault_block)} contiguous rows found for {fault_name}.")
            ans = input("Continue anyway? (y/n): ").strip().lower()
            if ans != 'y':
                return fault_name, []

        prefix_rows = normal_block.iloc[:REPLAY_NORMAL_PREFIX]
        fault_limit = REPLAY_MAX_ROWS - len(prefix_rows)
        chosen_fault_rows = fault_block.iloc[:fault_limit]

        rows_df = pd.concat([prefix_rows, chosen_fault_rows], ignore_index=True)
        normal_count = len(prefix_rows)
        fault_count = len(chosen_fault_rows)

    elif choice == 7:
        fault_name = "Mixed Cycle"
        # Assemble multi-stage cycle: Normal -> Imbalance -> Weak Cell -> Overvoltage -> Undervoltage -> Recovery
        stages = [
            (0, 30),  # 30 normal
            (1, 50),  # 50 imbalance
            (2, 50),  # 50 weak cell
            (3, 40),  # 40 overvoltage
            (4, 40),  # 40 undervoltage
            (5, 40),  # 40 overtemp
            (0, 50)   # 50 normal recovery
        ]
        collected = []
        for fid, count in stages:
            block = extract_contiguous_block(df, fid)
            collected.append(block.iloc[:count])
        rows_df = pd.concat(collected, ignore_index=True).iloc[:REPLAY_MAX_ROWS]
        normal_count = 30
        fault_count = len(rows_df) - 30
    else:
        return "Unknown", []

    total_rows = len(rows_df)
    duration_sec = total_rows / REPLAY_RATE_HZ
    mins = int(duration_sec // 60)
    secs = int(duration_sec % 60)

    print("\n" + "-" * 65)
    print(f"{fault_name}: {normal_count} normal + {fault_count} fault rows @ {REPLAY_RATE_HZ:g}/s (~{mins}m{secs:02d}s)")
    print("-" * 65)

    # Convert DataFrame rows to telemetry payload dictionaries
    payloads = []
    for _, r in rows_df.iterrows():
        row_fault = str(r.get("label", fault_name))
        p = {
            "source": f"replay:{row_fault}",
            "fault_type": row_fault,
            "voltage": round(float(r.get("voltage", 25.6)), 2),
            "current": round(float(r.get("current", 0.0)), 2),
            "temperature": round(float(r.get("temperature", 25.0)), 1),
            "soc": round(float(r.get("soc", 50.0)), 1),
            "delta_v": round(float(r.get("delta_v", 0.02)), 4),
            "ntc1": round(float(r.get("ntc1", r.get("temperature", 25.0))), 1),
            "ntc2": round(float(r.get("ntc2", r.get("temperature", 25.0))), 1),
            "ntc3": round(float(r.get("ntc3", r.get("temperature", 25.0))), 1),
            "ntc4": round(float(r.get("ntc4", r.get("temperature", 25.0))), 1),
            "bluetooth_connected": True,
            "voltage_valid": True,
            "current_valid": True,
            "temperature_valid": True,
            "cell_voltage_valid": True,
            "is_stale": False,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        for i in range(1, 9):
            col = f"cell_v{i}"
            p[col] = round(float(r.get(col, 3.2)), 3)
        payloads.append(p)

    return fault_name, payloads


def post_row(payload: dict) -> bool:
    """POSTs a single row to INGEST_URL using INGEST_TOKEN."""
    global _BROWSER_OPENED
    try:
        # Refresh timestamp on outgoing transmission
        payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        req_data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Ingest-Token": INGEST_TOKEN
        }
        req = urllib.request.Request(INGEST_URL, data=req_data, headers=headers)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            
            # Open browser once first row is confirmed
            if not _BROWSER_OPENED:
                _BROWSER_OPENED = True
                print(f"[REPLAY] Confirmed connection! Opening dashboard: {DASHBOARD_URL}")
                try:
                    webbrowser.open(DASHBOARD_URL)
                except Exception:
                    pass

            return True
    except urllib.error.HTTPError as he:
        if he.code == 401:
            print(f"\n[ERROR] 401 Unauthorized: Ingest token rejected by {INGEST_URL}!")
            return False
        print(f"\n[HTTP Error {he.code}] {he.reason}")
        return False
    except Exception as e:
        print(f"\n[Error POSTing telemetry] {e}")
        return False


def run_replay(fault_name: str, rows: list[dict]):
    """Streams rows at REPLAY_RATE_HZ, supporting Ctrl+C cancel."""
    if not rows:
        return

    delay = 1.0 / REPLAY_RATE_HZ
    total = len(rows)
    print(f"Starting replay of {fault_name}... (Press Ctrl+C at any time to stop and return to menu)\n")

    sent_count = 0
    try:
        for idx, row in enumerate(rows, 1):
            t_start = time.time()
            success = post_row(row)
            if success:
                sent_count += 1
                v = row.get("voltage", 0.0)
                i = row.get("current", 0.0)
                t = row.get("temperature", 0.0)
                dv = row.get("delta_v", 0.0)
                print(f"\r[{idx}/{total}] V={v:.2f}V, I={i:+.1f}A, T={t:.1f}°C, ΔV={dv:.3f}V | {fault_name}", end="", flush=True)
            
            elapsed = time.time() - t_start
            sleep_time = max(0.01, delay - elapsed)
            time.sleep(sleep_time)

        print(f"\n\n✅ Replay complete! ({sent_count}/{total} rows successfully streamed).")
    except KeyboardInterrupt:
        print(f"\n\n[PAUSED] Replay stopped by user after {sent_count}/{total} rows.")
    
    print("Returning to menu in 1.5 seconds...")
    time.sleep(1.5)


def main_menu():
    # Pre-load dataset so selection is instant
    get_dataset()

    while True:
        print("\n" + "=" * 60)
        print("       INTELLIGENT BMS -- FAULT REPLAY DEMO LAUNCHER       ")
        print("=" * 60)
        print("  [1] Normal")
        print("  [2] Cell Imbalance")
        print("  [3] Weak Cell")
        print("  [4] Overvoltage")
        print("  [5] Undervoltage")
        print("  [6] Overtemperature")
        print("  [7] Mixed / full cycle")
        print("  [0] Exit")
        print("-" * 60)
        
        try:
            choice_str = input("Select an option (0-7): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not choice_str.isdigit():
            print("Invalid input. Please enter a number from 0 to 7.")
            continue

        choice = int(choice_str)
        if choice == 0:
            print("Exiting demo launcher. Goodbye!")
            break
        elif choice in range(1, 8):
            fault_name, rows = prepare_replay_rows(choice)
            if rows:
                run_replay(fault_name, rows)
        else:
            print("Choice out of range. Please choose between 0 and 7.")


if __name__ == "__main__":
    main_menu()
