import os
from pathlib import Path

root = Path(__file__).parent
backend_dir = root / "backend"

for path in backend_dir.rglob("*.py"):
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
