import os
import pandas as pd

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
files = ["BMS_2026-06-16.xlsx", "BMS_2026-06-17_.xlsx", "BMS_2026-06-18_Charging_Discharging_Idle.xlsx"]

for f in files:
    path = os.path.join(directory, f)
    if os.path.exists(path):
        xls = pd.ExcelFile(path)
        print(f"\n--- Columns in {f} ---")
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, nrows=5)
            print(f"Sheet: {sheet}")
            print(list(df.columns))
