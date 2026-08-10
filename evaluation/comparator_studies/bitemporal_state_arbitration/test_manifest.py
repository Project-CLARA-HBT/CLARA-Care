from pathlib import Path

from evaluation.comparator_studies.bitemporal_state_arbitration.validate_manifest import (
    validate,
)


def test_comparator_manifest_prohibits_direct_claim_without_source() -> None:
    validate(
        Path("evaluation/comparator_studies/bitemporal_state_arbitration/comparator_manifest.json"),
        repository_root=Path("."),
    )
