import os
from pathlib import Path

root = Path(__file__).parent

directories_to_fix = [
    root / "backend",
    root / "scripts"
]

for dir_path in directories_to_fix:
    if not dir_path.exists():
        continue
        
    for path in dir_path.rglob("*.py"):
        try:
            content = path.read_text(encoding="utf-8")
            original = content
            
            # Заменяем импорты из tonutils.utils на ton_core
            content = content.replace("from tonutils.utils import to_nano", "from ton_core import to_nano")
            content = content.replace("from tonutils.utils import cell_to_hex", "from ton_core import cell_to_hash")
            
            if content != original:
                path.write_text(content, encoding="utf-8")
                print(f"Updated: {path}")
        except Exception as e:
            print(f"Error with {path}: {e}")

print("Done!")
