import os

directory = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
for f in os.listdir(directory):
    if f.endswith('.py') or f.endswith('.sh') or f.endswith('.service'):
        path = os.path.join(directory, f)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                if "5050" in content or "open_dashboard" in content or "whatsapp" in content.lower():
                    print(f"Found in: {f}")
                    for i, line in enumerate(content.split('\n')):
                        if "5050" in line or "open_dashboard" in line or "whatsapp" in line.lower():
                            print(f"  Line {i+1}: {line.strip()}")
        except Exception as e:
            print(f"Error reading {f}: {e}")
