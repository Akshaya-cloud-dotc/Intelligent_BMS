import subprocess
import re

try:
    print("Running schtasks query...")
    result = subprocess.run(["schtasks", "/query", "/fo", "csv"], capture_output=True, text=True, errors="ignore")
    lines = result.stdout.split("\n")
    print(f"Total tasks found: {len(lines)}")
    for line in lines:
        if "cleaned data sets" in line.lower() or "whatsapp" in line.lower() or "bms" in line.lower():
            print("Found matching task line:")
            print(line)
except Exception as e:
    print(f"Error: {e}")
