import os

root_dir = r"c:\Users\Adith\Downloads"
print(f"Searching for 'whatsapp' recursively inside: {root_dir}")
found = 0
for root, dirs, files in os.walk(root_dir):
    # limit depth
    depth = root[len(root_dir):].count(os.sep)
    if depth > 2:
        continue
    for f in files:
        if f.endswith('.py') or f.endswith('.bat') or f.endswith('.ps1') or f.endswith('.sh'):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                    if "whatsapp" in content.lower():
                        # Exclude self and duplicate helper if they are the main file
                        if "find_whatsapp_anywhere" in f:
                            continue
                        print(f"Found in: {path}")
                        found += 1
            except Exception as e:
                pass
print(f"Search complete. Found {found} references.")
