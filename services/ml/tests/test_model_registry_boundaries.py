"""Regression locks for the model-registry construction boundary.

The test deliberately inspects production source rather than a mocked request
path: a future model-backed feature must not regain a direct constructor while
all current request paths happen to exercise the registry.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.llm.model_registry import build_task_client


ML_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ML_ROOT / "src" / "clara_ml"
REGISTRY_SOURCE = SOURCE_ROOT / "llm" / "model_registry.py"


def _direct_deepseek_client_constructors(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "DeepSeekClient"
    ]


def test_only_task_registry_constructs_production_deepseek_clients() -> None:
    constructors = {
        path.relative_to(SOURCE_ROOT).as_posix(): _direct_deepseek_client_constructors(path)
        for path in SOURCE_ROOT.rglob("*.py")
    }
    non_registry = {
        relative_path: lines
        for relative_path, lines in constructors.items()
        if lines and SOURCE_ROOT / relative_path != REGISTRY_SOURCE
    }

    assert _direct_deepseek_client_constructors(REGISTRY_SOURCE)
    assert non_registry == {}


def test_client_exposes_no_runtime_constructor_bypass() -> None:
    assert not hasattr(DeepSeekClient, "from_runtime")


def test_text_task_builder_cannot_be_reused_for_audio_transport() -> None:
    assert "audio" not in inspect.signature(build_task_client).parameters
