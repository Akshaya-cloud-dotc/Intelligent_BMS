import os
import pandas as pd

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
excel_files = [
    f for f in os.listdir(directory)
    if f.endswith('.xlsx') and not f.startswith('~$') and not f.startswith('augmented_')
]

required = ['voltage', 'current', 'temperature', 'soc']
cell_cols = [f'cell_v{i}' for i in range(1, 9)]

all_dfs = []

# Rules for which sheets to read
for f in excel_files:
    path = os.path.join(directory, f)
    xls = pd.ExcelFile(path)
    sheets_in_file = xls.sheet_names
    
    # We want to select the sheets to avoid loading both 'All Cycles' and individual cycle sheets.
    # If there is 'All Cycles', 'All Data', or 'Balanced All', use that and skip others.
    combined_sheet = None
    for s in sheets_in_file:
        if s.lower() in ["all cycles", "all data", "balanced all"]:
            combined_sheet = s
            break
            
    sheets_to_read = []
    if combined_sheet:
        sheets_to_read = [combined_sheet]
    else:
        sheets_to_read = [s for s in sheets_in_file if s.lower() != "summary"]
        
    for sheet in sheets_to_read:
        found_header = None
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
            df = pd.read_excel(path, sheet_name=sheet, header=found_header)
            df.columns = [str(c).lower().strip() for c in df.columns]
            # Keep only standard columns
            cols_to_keep = required + cell_cols + [ntc for ntc in ['ntc1', 'ntc2', 'ntc3', 'ntc4'] if ntc in df.columns]
            if 'cycle' in df.columns:
                cols_to_keep.append('cycle')
            if 'timestamp' in df.columns:
                cols_to_keep.append('timestamp')
            df_clean = df[cols_to_keep].copy()
            df_clean['source_file'] = f
            df_clean['source_sheet'] = sheet
            all_dfs.append(df_clean)
            print(f"Loaded: {f} | Sheet: {sheet} | Rows: {len(df_clean)}")
        else:
            print(f"Skipped/NoHeader: {f} | Sheet: {sheet}")

df_all = pd.concat(all_dfs, ignore_index=True)
print(f"\nTotal concatenated rows: {len(df_all)}")

# Let's count duplicate rows based on telemetry values (excluding source metadata)
telemetry_cols = required + cell_cols
df_dedup = df_all.drop_duplicates(subset=telemetry_cols)
print(f"Total rows after dropping duplicates based on telemetry columns: {len(df_dedup)}")

# Let's print details about the final dataset
print("\nFirst few rows:")
print(df_dedup.head(3))
