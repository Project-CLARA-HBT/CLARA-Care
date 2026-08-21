from __future__ import annotations

import json
from pathlib import Path

from evaluation.property_assurance.mutation_overlay import MutantOverlay, apply_overlay


def test_anchor_catalog_applies_one_real_source_overlay_per_candidate(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    catalog = json.loads(
        (root / "research/assurance_soict/mutation_site_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    applied = [
        apply_overlay(
            repository_root=root,
            overlay_root=tmp_path / item["id"],
            mutant=MutantOverlay(
                mutant_id=item["id"],
                source_path=item["source_path"],
                anchor=item["anchor"],
                replacement=item["replacement"],
            ),
        )
        for item in catalog["candidates"]
    ]
    assert len(applied) == 45
    assert all(item.original_sha256 != item.mutated_sha256 for item in applied)
    anchored_families = {item["family_seed"] for item in catalog["candidates"]}
    unanchored_families = set(catalog["unanchored_family_seeds"])
    assert anchored_families.isdisjoint(unanchored_families)
    assert anchored_families | unanchored_families == {f"M{index:02d}" for index in range(1, 16)}
