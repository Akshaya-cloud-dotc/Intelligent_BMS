import os

p = r"c:\Users\Adith\Downloads\CLEANED DATA SETS\CLEANED DATA SETS\live_dashboard_v3.html"
if os.path.exists(p):
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    
    print("Length of HTML:", len(content))
    # Let's print all paragraphs (<p>) or divs with text in the HTML to find the model explanation
    import re
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
    print(f"Found {len(paragraphs)} paragraphs:")
    for i, para in enumerate(paragraphs):
        para_clean = re.sub('<[^<]+?>', '', para).strip()
        if len(para_clean) > 20:
            print(f"P {i}: {para_clean[:120]}...")
            if "model" in para_clean.lower() or "fault" in para_clean.lower() or "train" in para_clean.lower() or "synthetic" in para_clean.lower():
                print("   *** Matches keywords! ***")
else:
    print("File not found")
