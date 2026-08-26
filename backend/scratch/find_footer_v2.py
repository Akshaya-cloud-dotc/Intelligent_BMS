import os

p = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS\live_dashboard_v3.html"
if os.path.exists(p):
    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "footer" in line.lower() or "class=\"footer\"" in line or "class='footer'" in line:
            # Clean string to ascii for printing safely
            ascii_line = line.strip().encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1}: {ascii_line}")
            # Print next 5 lines
            for j in range(1, 10):
                if i + j < len(lines):
                    next_line = lines[i+j].strip().encode('ascii', errors='replace').decode('ascii')
                    print(f"  Line {i+1+j}: {next_line}")
