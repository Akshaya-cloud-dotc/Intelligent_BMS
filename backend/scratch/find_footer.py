import os

p = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS\live_dashboard_v3.html"
if os.path.exists(p):
    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "footer" in line.lower() or "class=\"footer\"" in line or "class='footer'" in line:
            print(f"Line {i+1}: {line.strip()}")
            # Print next 5 lines
            for j in range(1, 6):
                if i + j < len(lines):
                    print(f"Line {i+1+j}: {lines[i+j].strip()}")
