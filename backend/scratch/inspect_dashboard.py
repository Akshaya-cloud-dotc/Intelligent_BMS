import os

files = [
    r"c:\Users\Adith\Downloads\CLEANED DATA SETS\live_dashboard_v3.html",
    r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS\live_dashboard_v3.html"
]

for p in files:
    if os.path.exists(p):
        print(f"\n--- Checking file: {p} ---")
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
            # Find snippets containing model explanation or trained or synthetic
            idx = content.find("The model is trained")
            if idx != -1:
                print("Found 'The model is trained' at index:", idx)
                print(content[idx:idx+350])
            else:
                print("Could not find 'The model is trained'. Let's search for 'trained'")
                idx2 = content.find("trained")
                if idx2 != -1:
                    print("Found 'trained' at index:", idx2)
                    print(content[idx2-100:idx2+250])
                else:
                    print("Could not find 'trained'")
