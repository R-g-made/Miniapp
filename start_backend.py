import sys
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    root_dir = Path(__file__).parent
    sys.path.insert(0, str(root_dir))
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
