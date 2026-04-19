import re
from pathlib import Path
from collections import defaultdict

CATALOG_ASSET_PATH = Path(r"c:\Users\maxvr\OneDrive\Desktop\CatalogAsset")

def normalize_case_name(name):
    """Normalize case name by removing extra words like FULL, (items), etc."""
    name = name.lower().strip()
    # Remove extra suffixes
    name = re.sub(r"\s*\(.*?\)", "", name)  # remove (36 items) etc
    name = re.sub(r"\s*full", "", name)  # remove FULL
    name = re.sub(r"\s*ss", "", name)  # remove SS (for DOGS SS)
    name = re.sub(r"\s*\d+", "", name)  # remove numbers
    name = re.sub(r"\s+", " ", name).strip()  # collapse spaces
    return name

print("Catalog.md case names:")
catalog_case_names = [
    "DOGES (Goodies)",
    "Slon",
    "Blum",
    "DOGS (Sticker Store)",
    "Monkey",
    "NOT"
]

for name in catalog_case_names:
    print(f"  Original: {name}")
    print(f"  Normalized: {normalize_case_name(name)}")

print("\nCatalogAsset directory case names:")
for case_dir in CATALOG_ASSET_PATH.iterdir():
    if case_dir.is_dir():
        print(f"  Original: {case_dir.stem}")
        print(f"  Normalized: {normalize_case_name(case_dir.stem)}")
