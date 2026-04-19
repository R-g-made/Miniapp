import os
from pathlib import Path

root = Path(__file__).parent

# Фиксим все файлы: tests, scripts, и т.д.
directories_to_fix = [
    root / "tests",
    root / "scripts"
]

for dir_path in directories_to_fix:
    if not dir_path.exists():
        continue
        
    for path in dir_path.rglob("*.py"):
        try:
            content = path.read_text(encoding="utf-8")
            original = content
            
            content = content.replace("from app.", "from backend.")
            content = content.replace("import app.", "import backend.")
            
            if content != original:
                path.write_text(content, encoding="utf-8")
                print(f"Updated: {path}")
        except Exception as e:
            print(f"Error with {path}: {e}")

print("Done!")
