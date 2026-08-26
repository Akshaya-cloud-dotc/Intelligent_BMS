import os

REPLACEMENTS = {
    # Backgrounds
    'bg-pastel-bg': 'bg-[#F8F7FF]',
    'bg-pastel-secondary': 'bg-[#FDFDFF]',
    'bg-pastel-card': 'bg-[#FFFFFF]',
    
    # Text
    'text-pastel-textSecondary': 'text-[#6B7280]',
    'text-pastel-text': 'text-[#3D405B]',
    
    # Lavender
    'text-pastel-lavender': 'text-[#CDB4DB]',
    'bg-pastel-lavender/10': 'bg-[#CDB4DB]/10',
    'bg-pastel-lavender/20': 'bg-[#CDB4DB]/20',
    'bg-pastel-lavender/80': 'bg-[#CDB4DB]/80',
    'bg-pastel-lavender': 'bg-[#CDB4DB]',
    'border-pastel-lavender/50': 'border-[#CDB4DB]/50',
    'border-pastel-lavender': 'border-[#CDB4DB]',
    'ring-pastel-lavender': 'ring-[#CDB4DB]',
    
    # Blue
    'text-pastel-blue': 'text-[#A2D2FF]',
    'bg-pastel-blue/10': 'bg-[#A2D2FF]/10',
    'border-pastel-blue/30': 'border-[#A2D2FF]/30',
    'border-pastel-blue': 'border-[#A2D2FF]',
    
    # Mint
    'text-pastel-mint': 'text-[#BDE0BE]',
    'bg-pastel-mint/10': 'bg-[#BDE0BE]/10',
    'border-pastel-mint/30': 'border-[#BDE0BE]/30',
    
    # Peach
    'text-pastel-peach': 'text-[#FFD6A5]',
    'bg-pastel-peach/10': 'bg-[#FFD6A5]/10',
    'border-pastel-peach/30': 'border-[#FFD6A5]/30',
    
    # Pink
    'text-pastel-pink': 'text-[#FFC8DD]',
    
    # Status
    'text-pastel-success': 'text-[#95D5B2]',
    'bg-pastel-success/10': 'bg-[#95D5B2]/10',
    'border-pastel-success/30': 'border-[#95D5B2]/30',
    'text-pastel-warning': 'text-[#FFD6A5]',
    'text-pastel-error': 'text-[#FFB4A2]'
}

def update_classes_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    # Order matters: replace longer strings first if they overlap, but here they mostly don't
    # We sort keys by length descending to avoid partial replacements
    for key in sorted(REPLACEMENTS.keys(), key=len, reverse=True):
        new_content = new_content.replace(key, REPLACEMENTS[key])
        
    if content != new_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

def walk_dir(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.tsx') or file.endswith('.css'):
                update_classes_in_file(os.path.join(root, file))

if __name__ == '__main__':
    walk_dir('./src')
