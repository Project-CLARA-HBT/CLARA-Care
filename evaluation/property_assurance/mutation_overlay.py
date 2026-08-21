"""Anchored one-change temporary overlays for the GovMut executable corpus."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError


@dataclass(frozen=True)
class MutantOverlay:
    mutant_id: str
    source_path: str
    anchor: str
    replacement: str


@dataclass(frozen=True)
class AppliedOverlay:
    mutant_id: str
    source_path: str
    original_sha256: str
    mutated_sha256: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_overlay(
    *, repository_root: Path, overlay_root: Path, mutant: MutantOverlay
) -> AppliedOverlay:
    """Copy exactly one source file and make one anchored semantic mutation.

    The original file remains unchanged. An anchor must occur exactly once so a
    mutant cannot silently modify multiple enforcement sites or no site at all.
    """

    if not mutant.mutant_id or not mutant.source_path or not mutant.anchor:
        raise FreezeError("govmut_overlay_fields_missing")
    if mutant.anchor == mutant.replacement:
        raise FreezeError("govmut_overlay_is_cosmetic")
    source = (repository_root / mutant.source_path).resolve()
    root = repository_root.resolve()
    if root not in source.parents or not source.is_file():
        raise FreezeError("govmut_overlay_source_outside_repository")
    relative = source.relative_to(root)
    destination = overlay_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    original = source.read_text(encoding="utf-8")
    if original.count(mutant.anchor) != 1:
        raise FreezeError("govmut_overlay_anchor_not_unique")
    mutated = original.replace(mutant.anchor, mutant.replacement, 1)
    shutil.copy2(source, destination)
    destination.write_text(mutated, encoding="utf-8")
    return AppliedOverlay(
        mutant_id=mutant.mutant_id,
        source_path=str(relative),
        original_sha256=_sha256(source),
        mutated_sha256=_sha256(destination),
    )
