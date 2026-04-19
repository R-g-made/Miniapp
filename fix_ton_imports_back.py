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
            
            # Возвращаем импорты обратно на tonutils.utils
            content = content.replace("from ton_core import to_nano", "from tonutils.utils import to_nano")
            content = content.replace("from ton_core import cell_to_hash", "from tonutils.utils import cell_to_hex")
            
            # Также исправляем cell_to_hash на cell_to_hex в коде
            content = content.replace("cell_to_hash(ext_msg.to_cell()).hex()", "cell_to_hex(ext_msg.to_cell().hash)")
            content = content.replace("tx_hash = ext_msg.normalized_hash.hex() if hasattr(ext_msg.normalized_hash, 'hex') else str(ext_msg.normalized_hash)", "tx_hash = ext_msg.normalized_hash")
            content = content.replace("tx_hash = ext_msg.hash.hex() if hasattr(ext_msg.hash, 'hex') else str(ext_msg.hash)", "tx_hash = ext_msg.hash")
            
            if content != original:
                path.write_text(content, encoding="utf-8")
                print(f"Updated: {path}")
        except Exception as e:
            print(f"Error with {path}: {e}")

print("Done!")
