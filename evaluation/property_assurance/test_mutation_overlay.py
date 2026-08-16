from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.mutation_overlay import MutantOverlay, apply_overlay


def _source(root: Path, contents: str) -> None:
    path = root / "src" / "gate.py"
    path.parent.mkdir(parents=True)
    path.write_text(contents, encoding="utf-8")


def test_overlay_copies_and_changes_exactly_one_anchored_site(tmp_path: Path) -> None:
    root, overlay = tmp_path / "repo", tmp_path / "overlay"
    _source(root, "if enforce_state_check:\n    reject()\n")
    applied = apply_overlay(
        repository_root=root,
        overlay_root=overlay,
        mutant=MutantOverlay("M01-A", "src/gate.py", "enforce_state_check", "False"),
    )
    assert applied.original_sha256 != applied.mutated_sha256
    assert "if enforce_state_check" in (root / "src/gate.py").read_text(encoding="utf-8")
    assert "if False" in (overlay / "src/gate.py").read_text(encoding="utf-8")


def test_overlay_rejects_ambiguous_or_cosmetic_mutation(tmp_path: Path) -> None:
    root, overlay = tmp_path / "repo", tmp_path / "overlay"
    _source(root, "check(); check()\n")
    with pytest.raises(FreezeError, match="govmut_overlay_anchor_not_unique"):
        apply_overlay(
            repository_root=root,
            overlay_root=overlay,
            mutant=MutantOverlay("M", "src/gate.py", "check()", "skip()"),
        )
    with pytest.raises(FreezeError, match="govmut_overlay_is_cosmetic"):
        apply_overlay(
            repository_root=root,
            overlay_root=overlay,
            mutant=MutantOverlay("M", "src/gate.py", "check()", "check()"),
        )
