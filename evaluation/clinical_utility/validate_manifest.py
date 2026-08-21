from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import (
    FreezeError,
    load_frozen_json,
    verify_freeze,
)

CONDITIONS = {
    "full_authorized",
    "naive_rag",
    "btsa_or_tpr",
    "glhs_no_thss",
    "thss_default",
    "thss_strict",
}


def validate(task_manifest: Path, model_manifest: Path, freeze_manifest: Path) -> None:
    task = load_frozen_json(task_manifest)
    model = load_frozen_json(model_manifest)
    verify_freeze(freeze_manifest)
    if task.get("status") != "frozen" or set(task.get("conditions", [])) != CONDITIONS:
        raise FreezeError("utility_conditions_not_frozen_or_incomplete")
    families = {entry.get("family") for entry in model.get("models", []) if entry.get("family")}
    if model.get("status") != "frozen" or len(families) < 2:
        raise FreezeError("two_frozen_model_families_required")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.tasks, args.models, args.freeze)
    except FreezeError as exc:
        parser.error(str(exc))
