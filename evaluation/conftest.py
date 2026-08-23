from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ML_SRC = REPO_ROOT / "services" / "ml" / "src"
API_SRC = REPO_ROOT / "services" / "api" / "src"

for path in (REPO_ROOT, ML_SRC, API_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
