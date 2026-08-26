import os
import pandas as pd

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
f = "BMS_2026-06-16.xlsx"
path = os.path.join(directory, f)

if os.path.exists(path):
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        if sheet == "Summary":
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=1, nrows=5)
        print(f"\nSheet: {sheet}")
        print(list(df.columns))
        print(df.head(2))
