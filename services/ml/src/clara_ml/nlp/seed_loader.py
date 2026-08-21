from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_seed_json(seed_dir: Path) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    if not seed_dir.exists():
        return data
    for p in sorted(seed_dir.glob("*.json")):
        with p.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, list):
            data.extend(payload)
        else:
            data.append(payload)
    return data
