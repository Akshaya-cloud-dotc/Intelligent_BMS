import os
backend_dir = r'C:\Users\Adith\Downloads\CLEANED DATA SETS\Intelligent_BMS\backend'
for filename in os.listdir(backend_dir):
    if not filename.endswith('.py'): continue
    filepath = os.path.join(backend_dir, filename)
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'MODEL_DIR = os.path.dirname(os.path.abspath(__file__))' in content:
        new_header = '''PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
'''
        content = content.replace('MODEL_DIR = os.path.dirname(os.path.abspath(__file__))', new_header)
        
        # Replace specific file references
        content = content.replace('os.path.join(MODEL_DIR, "bms_telemetry_raw.csv")', 'os.path.join(DATA_DIR, "bms_telemetry_raw.csv")')
        content = content.replace('os.path.join(MODEL_DIR, "bms_telemetry_filtered.csv")', 'os.path.join(DATA_DIR, "bms_telemetry_filtered.csv")')
        content = content.replace('os.path.join(MODEL_DIR, "cycle_history.json")', 'os.path.join(DATA_DIR, "cycle_history.json")')
        content = content.replace('os.path.join(MODEL_DIR, "augmented_telemetry_dataset.xlsx")', 'os.path.join(DATA_DIR, "augmented_telemetry_dataset.xlsx")')
        
        content = content.replace('os.path.join(MODEL_DIR, "scratch"', 'os.path.join(OUTPUTS_DIR, "scratch"')
        content = content.replace('os.path.join(MODEL_DIR, "uploads"', 'os.path.join(OUTPUTS_DIR, "uploads"')
        content = content.replace('os.path.join(MODEL_DIR, "backend_error.log")', 'os.path.join(OUTPUTS_DIR, "backend_error.log")')
        content = content.replace('send_from_directory(MODEL_DIR,', 'send_from_directory(FRONTEND_DIR,')
        
        # Incremental train script path fix
        content = content.replace('os.path.join(MODEL_DIR, "incremental_train.py")', 'os.path.join(os.path.dirname(os.path.abspath(__file__)), "incremental_train.py")')

    with open(filepath, 'w') as f:
        f.write(content)
print("Updated python files.")
