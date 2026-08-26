import os

directories = [
    r"c:\Users\Adith\Downloads\CLEANED DATA SETS",
    r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS"
]

for d in directories:
    if os.path.exists(d):
        print(f"\n--- Searching in {d} ---")
        for f in os.listdir(d):
            if f.endswith('.py') or f.endswith('.sh') or f.endswith('.bat'):
                path = os.path.join(d, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as file:
                        content = file.read()
                        if "whatsapp" in content.lower() or "send_whatsapp" in content.lower() or "whatsapp_desktop_helper" in content.lower():
                            print(f"Found reference in file: {f}")
                            # Print lines containing it
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if "whatsapp" in line.lower() or "send_whatsapp" in line.lower() or "whatsapp_desktop_helper" in line.lower():
                                    print(f"  Line {i+1}: {line.strip()}")
                except Exception as e:
                    print(f"Error reading {f}: {e}")
