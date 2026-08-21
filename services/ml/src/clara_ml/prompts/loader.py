from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class PromptLoader:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()

    def load(self, role: str, intent: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", role):
            raise KeyError(f"Role '{role}' not found")

        path = (self.base_dir / f"{role}.yaml").resolve()
        if self.base_dir not in path.parents:
            raise KeyError(f"Role '{role}' not found")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        intents = data.get("intents", {})
        if intent not in intents:
            raise KeyError(f"Intent '{intent}' not found for role '{role}'")
        return {
            "role": role,
            "intent": intent,
            "system": data.get("system", ""),
            "template": intents[intent],
        }
