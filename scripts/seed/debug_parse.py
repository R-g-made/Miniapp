import sys
from pathlib import Path
import re

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

catalog_path = Path(__file__).parent / "FinalCatalog.md"

print(f"Catalog path: {catalog_path}")
print(f"Exists: {catalog_path.exists()}")

with open(catalog_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("\nFirst 100 lines:")
for i, line in enumerate(lines[:100]):
    print(f"{i+1}: {repr(line)}")
