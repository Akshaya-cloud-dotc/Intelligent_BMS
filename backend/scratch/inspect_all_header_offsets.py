import os
import pandas as pd

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
excel_files = [
    f for f in os.listdir(directory)
    if f.endswith('.xlsx') and not f.startswith('~$') and not f.startswith('augmented_')
]

required = ['voltage', 'current', 'temperature', 'soc']
cell_cols = [f'cell_v{i}' for i in range(1, 9)]

for f in excel_files:
    path = os.path.join(directory, f)
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        if sheet.lower() == "summary":
            continue
        found_header = None
        # Try different headers
        for h in [0, 1, 2, 3]:
            try:
                df = pd.read_excel(path, sheet_name=sheet, header=h, nrows=3)
                cols = [str(c).lower().strip() for c in df.columns]
                has_req = all(col in cols for col in required) and all(col in cols for col in cell_cols)
                if has_req:
                    found_header = h
                    break
            except Exception:
                pass
        
        if found_header is not None:
            # Let's count the total rows in the sheet
            df_full = pd.read_excel(path, sheet_name=sheet, header=found_header)
            print(f"File: {f} | Sheet: {sheet} | Header row: {found_header} | Rows: {len(df_full)}")
        else:
            print(f"File: {f} | Sheet: {sheet} | NO VALID HEADER FOUND")
