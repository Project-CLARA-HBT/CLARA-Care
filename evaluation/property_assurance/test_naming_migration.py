"""CI guard: active evidence paths must use functional names.

Historical bytes may retain their old protocol vocabulary only below the
explicit generalized archive root.  This guard is deliberately path-based so
that it cannot mistake a prose citation for an active executable protocol.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_ACTIVE_MARKERS = ("glhs_q2", "glhs_q3", "round1", "round2", "round3")
ARCHIVE_PARTS = {"archives", "archive", "historical"}


def test_active_evidence_paths_are_publication_target_agnostic() -> None:
    roots = (ROOT / "evaluation", ROOT / "scripts" / "evaluation")
    violations: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            parts = {part.lower() for part in relative.parts}
            if parts & (ARCHIVE_PARTS | {"__pycache__"}):
                continue
            lowered = "/".join(relative.parts).lower()
            if any(marker in lowered for marker in FORBIDDEN_ACTIVE_MARKERS):
                violations.append(str(relative))
    assert not violations, "publication/reviewer labels in active paths: " + ", ".join(
        sorted(violations)
    )


def test_functional_protocol_roots_exist() -> None:
    for name in (
        "structural_conformance",
        "external_validation",
        "comparator_studies",
        "clinical_adjudication",
        "clinical_utility",
        "governance_adversarial",
        "audit_reconstruction",
        "fullstack_benchmark",
        "property_assurance",
    ):
        assert (ROOT / "evaluation" / name).exists(), name
