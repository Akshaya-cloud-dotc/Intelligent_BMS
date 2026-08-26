import os
import pandas as pd

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
excel_files = [
    f for f in os.listdir(directory)
    if f.endswith('.xlsx') and not f.startswith('~$') and not f.startswith('augmented_')
]

print(f"Found {len(excel_files)} excel files:")
total_rows = 0
for f in excel_files:
    path = os.path.join(directory, f)
    try:
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            cols = [str(c).lower().strip() for c in df.columns]
            required = ['voltage', 'current', 'temperature', 'soc']
            cell_cols = [f'cell_v{i}' for i in range(1, 9)]
            has_req = all(col in cols for col in required) and all(col in cols for col in cell_cols)
            print(f"File: {f}, Sheet: {sheet}, Rows: {len(df)}, HasReqCols: {has_req}")
            if has_req:
                total_rows += len(df)
    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"Total baseline rows across all matching sheets: {total_rows}")
