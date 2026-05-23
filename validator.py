import json
import re
from urllib.parse import urlparse


with open("boericke_remedies.json", "r", encoding="utf-8") as f:
    remedies = json.load(f)


total = len(remedies)
errors = []
warnings = []


BOILERPLATE = ["Médi-T", "William BOERICKE", "HOMOEOPATHIC MATERIA MEDICA", "Copyright"]

for index, remedy in enumerate(remedies):
    abbrev = remedy.get("abbreviation", f"Unknown-{index}")
    
    # 1. SCHEMA & TYPE CHECKS
    required_keys = ["abbreviation", "full_name", "common_name", "source_url", "letter", "general", "sections"]
    for key in required_keys:
        if key not in remedy:
            errors.append(f"[{abbrev}] Missing required key: '{key}'")
            
    if not isinstance(remedy.get("sections", {}), dict):
        errors.append(f"[{abbrev}] 'sections' is not a dictionary.")
    
    if "keywords" in remedy and not isinstance(remedy["keywords"], list):
        errors.append(f"[{abbrev}] 'keywords' is not a list.")

    # 2. CONTENT QUALITY CHECKS: 'general' text
    general_text = remedy.get("general", "")
    
    
    if len(general_text) > 0 and len(general_text) < 30:
        warnings.append(f"[{abbrev}] 'general' text is very short ({len(general_text)} chars). Might be truncated.")
        
    
    for noise in BOILERPLATE:
        if noise.lower() in general_text.lower():
            errors.append(f"[{abbrev}] 'general' contains boilerplate noise: {noise}")

    # 3. CONTENT QUALITY CHECKS: 'sections'
    sections = remedy.get("sections", {})
    
    for sec_name, sec_text in sections.items():
        # Are the section headers actual headers, or did the parser accidentally grab a whole sentence?
        if len(sec_name) > 35:
            errors.append(f"[{abbrev}] Section name too long ('{sec_name[:20]}...'). Regex likely failed.")
            
        # Is the section name purely alphabetical? (Shouldn't contain HTML or weird punctuation)
        if not re.match(r"^[A-Za-z\s\-\/]+$", sec_name):
            warnings.append(f"[{abbrev}] Section name contains unusual characters: '{sec_name}'")
            
        # Is the section content suspiciously short?
        if len(sec_text) < 5:
            warnings.append(f"[{abbrev}] Section '{sec_name}' has almost no content ({len(sec_text)} chars).")

        # Did boilerplate bleed into the section text?
        for noise in BOILERPLATE:
            if noise.lower() in sec_text.lower():
                errors.append(f"[{abbrev}] Section '{sec_name}' contains boilerplate noise: {noise}")

    # 4. LOGICAL CONSISTENCY CHECKS
    url_path = urlparse(remedy.get("source_url", "")).path
    if abbrev.lower().replace("-", "") not in url_path.replace("-", ""):
        warnings.append(f"[{abbrev}] Abbreviation does not seem to match its source URL ({url_path}).")

# --- Print Report ---
print("=" * 50)
print(f" VALIDATION REPORT ({total} Remedies Checked)")
print("=" * 50)

print(f"\n ERRORS (Hard failures - schema broken or definite bad content): {len(errors)}")
for e in errors[:20]: # Print top 20
    print(f"  - {e}")
if len(errors) > 20: print(f"  ...and {len(errors) - 20} more errors.")

print(f"\n WARNINGS (Suspicious content, requires manual check): {len(warnings)}")
for w in warnings[:20]:
    print(f"  - {w}")
if len(warnings) > 20: print(f"  ...and {len(warnings) - 20} more warnings.")

print("\n" + "=" * 50)
if not errors and not warnings:
    print(" Dataset is extremely clean! All heuristics passed.")
else:
    print(" Please review the flagged items above.")