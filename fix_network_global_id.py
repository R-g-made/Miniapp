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
            
            # Удаляем импорт NetworkGlobalID
            content = content.replace("from tonutils.clients.protocol import NetworkGlobalID", "")
            content = content.replace(", NetworkGlobalID", "")
            
            # Заменяем использование на простые строки
            content = content.replace("NetworkGlobalID.TESTNET", "'testnet'")
            content = content.replace("NetworkGlobalID.MAINNET", "'mainnet'")
            
            if content != original:
                path.write_text(content, encoding="utf-8")
                print(f"Updated: {path}")
        except Exception as e:
            print(f"Error with {path}: {e}")

print("Done!")
