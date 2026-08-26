import os
import time
import json
import urllib.request
import pandas as pd

# Flask endpoint URL
URL = "http://127.0.0.1:5000/api/telemetry"
RESET_URL = "http://127.0.0.1:5000/api/reset"

def post_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

# Target telemetry file
directory = os.path.dirname(os.path.abspath(__file__))
files = [f for f in os.listdir(directory) if f.endswith('.xlsx')]

if not files:
    print("No Excel files found in the directory to simulate!")
    exit(1)

filepath = os.path.join(directory, files[0])
print(f"Simulating sensors using data from: {os.path.basename(filepath)}")

def load_clean_df(filepath, sheet_name):
    try:
        # Preview first 10 rows to detect where the actual header is
        df_preview = pd.read_excel(filepath, sheet_name=sheet_name, header=None, nrows=10)
        header_idx = 0
        for idx, row in df_preview.iterrows():
            row_vals = [str(val).lower().strip() for val in row.values]
            if 'voltage' in row_vals and 'current' in row_vals:
                header_idx = idx
                break
        df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_idx)
        df.columns = [str(c).lower().strip() for c in df.columns]
        return df
    except Exception:
        return None

# Load a sheet robustly
xls = pd.ExcelFile(filepath)
df = None
for sheet in xls.sheet_names:
    temp_df = load_clean_df(filepath, sheet)
    if temp_df is not None:
        cell_cols = [f'cell_v{i}' for i in range(1, 9)]
        required = ['voltage', 'current', 'temperature', 'soc']
        if all(col in temp_df.columns for col in required) and all(col in temp_df.columns for col in cell_cols):
            df = temp_df
            print(f"Successfully loaded telemetry from sheet: '{sheet}'")
            break

if df is None:
    print(f"Error: Could not find any valid telemetry sheet in {os.path.basename(filepath)}")
    exit(1)

# Reset the server buffer first
try:
    post_json(RESET_URL, {})
    print("Server telemetry buffer reset successfully.")
except Exception as e:
    print("Warning: Could not connect to Flask server. Make sure bms_dashboard_backend.py is running!")
    exit(1)

# Loop and send first 70 rows
print("\nStarting Sensor Simulation Stream...")
print("Sending telemetry row-by-row every 0.1 seconds...")
print("-" * 80)

for idx in range(70):
    row_data = df.iloc[idx]
    
    temp = float(row_data['temperature'])
    if idx >= 60:
        temp = 48.5 # Force high temperature to trigger Overtemperature Risk!
        
    # Construct telemetry payload (handling possible missing NTCs/delta_v)
    payload = {
        "voltage": float(row_data['voltage']),
        "current": float(row_data['current']),
        "temperature": temp,
        "soc": float(row_data['soc']),
    }
    for i in range(1, 9):
        payload[f"cell_v{i}"] = float(row_data[f"cell_v{i}"])
        
    if 'delta_v' in row_data:
        payload['delta_v'] = float(row_data['delta_v'])
    else:
        payload['delta_v'] = max([payload[f"cell_v{i}"] for i in range(1, 9)]) - min([payload[f"cell_v{i}"] for i in range(1, 9)])
        
    for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4']:
        if ntc in row_data:
            payload[ntc] = float(row_data[ntc])
            if idx >= 60:
                payload[ntc] = 48.5
        else:
            payload[ntc] = temp
            
    # Send row to server
    try:
        resp_json = post_json(URL, payload)
        
        buffer_len = resp_json.get("buffer_length", 0)
        status = resp_json.get("status", "unknown")
        
        if status == "success":
            pred = resp_json.get("prediction", {})
            print(f"Row {idx+1:03d} | Buffer: {buffer_len}/60 | Mode: {pred.get('Operating Mode')} | Fault: {pred.get('Fault Prediction')} ({pred.get('Confidence Score')}) | Action: {pred.get('Recommended Action')}")
        else:
            print(f"Row {idx+1:03d} | Buffer: {buffer_len}/60 | Status: {status} (Accumulating initial window...)")
            
    except Exception as e:
        print(f"Error sending row {idx+1}: {e}")
        break
        
    time.sleep(0.1)

print("-" * 80)
print("Simulation complete.")
