import os
import pandas as pd

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
f = "BMS_2026-06-16.xlsx"
path = os.path.join(directory, f)

if os.path.exists(path):
    df_h1 = pd.read_excel(path, sheet_name="Charging", header=1, nrows=5)
    print("--- header=1 top rows ---")
    print(df_h1.head(3))
    
    df_h2 = pd.read_excel(path, sheet_name="Charging", header=2, nrows=5)
    print("--- header=2 top rows ---")
    print(df_h2.head(3))
    print(df_h2.columns)
