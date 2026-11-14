"""Structural gate for POPETS-prior (literature_matrix.csv).

Purpose
-------
Stdlib-only checks for task ``POPETS-prior`` (venue ``popets``, phase ``P01``).
It validates ``research/venue2027/popets/literature_matrix.csv`` against the
deliverable contract:

- the CSV parses and carries every required column;
- all blueprint arms / claim-matrix comparators are present (B0-B3 arms and
  the full-cache-refresh, purpose-bound keying, macaroon/capability, and
  Zanzibar-consistency reference classes);
- every comparator_id is either a real id from
  ``research/venue2027/MANIFESTS/literature_registry.json`` or a named
  blueprint/registry reference (arms B0-B3, purpose-bound keying reference);
- every row has a non-empty mechanism_analysis (positive control: no
  competing method labeled weak without mechanism analysis);
- ``available_code=yes`` requires a non-empty code_url, and matrix
  ``fidelity_status`` values use the shared registry vocabulary
  (ORIGINAL_UPSTREAM / FAITHFUL_PORT / UNAVAILABLE_NOT_RUN).

Adversarial controls: unknown comparator ids, empty mechanism analyses,
available_code=yes without code_url, and nonexistent registry ids must fail
loudly with stable reason codes, never pass silently.

Allowed input: the matrix CSV, the literature registry JSON and the baseline
registry YAML in this repository only. No network access, no randomness.

Version: 1.0.0
"""

from __future__ import annotations

import csv
import json
import pathlib

POPETS_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = POPETS_DIR.parents[2]

MATRIX = POPETS_DIR / "literature_matrix.csv"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

REQUIRED_COLUMNS = (
    "comparator_id",
    "title",
    "venue",
    "doi_or_url",
    "code_url",
    "algorithm_class",
    "supported_guarantee",
    "limitations_vs_candidate",
    "available_code",
    "fidelity_status",
    "mechanism_analysis",
)

ALLOWED_FIDELITY = ("ORIGINAL_UPSTREAM", "FAITHFUL_PORT", "UNAVAILABLE_NOT_RUN")
ALLOWED_AVAILABLE_CODE = ("yes", "no", "UNAVAILABLE")

# Blueprint baseline arms (B4 is the candidate itself, not a comparator).
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B3-")

# Claim-matrix literature ids that must appear as rows (novelty contract C1-C5).
REQUIRED_LITERATURE_IDS = (
    "zanzibar19",  # C1: Zanzibar-consistency reference
    "macaroons14",  # C5: macaroon / attenuated capability reference
    "muse",  # C2: unlearning boundary
    "openfga",  # C1/C3: executable Zanzibar-consistency reference
    "fhir5",  # C4: purpose-bound structure reference
)

# Named blueprint references beyond literature ids.
REQUIRED_NAMED_REFERENCES = ("blueprint-purpose-bound-cache-keying",)

# Blueprint arm labels that must exist in the shared baseline registry.
REQUIRED_ARM_REGISTRY_NAMES = (
    "ttl-only-cache",
    "coarse-cache-purge-on-revocation",
    "always-recompute-authorized-projection",
    "zanzibar-like-consistency-token-cache",
)


def _load_matrix() -> list[dict[str, str]]:
    if not MATRIX.is_file():
        raise AssertionError(f"MISSING_MATRIX: expected {MATRIX}")
    with MATRIX.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _literature_ids() -> set[str]:
    if not LITERATURE_REGISTRY.is_file():
        raise AssertionError(f"MISSING_REGISTRY: expected {LITERATURE_REGISTRY}")
    data = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    return set(data)


def _baseline_registry_names() -> set[str]:
    if not BASELINE_REGISTRY.is_file():
        raise AssertionError(f"MISSING_BASELINE_REGISTRY: expected {BASELINE_REGISTRY}")
    names: set[str] = set()
    for line in BASELINE_REGISTRY.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("name:"):
            names.add(stripped.split("name:", 1)[1].strip().strip('"'))
    return names


def test_csv_parses_with_required_columns() -> None:
    rows = _load_matrix()
    assert rows, "MATRIX_EMPTY"
    for column in REQUIRED_COLUMNS:
        assert column in rows[0], f"MISSING_COLUMN:{column}"
    for index, row in enumerate(rows):
        missing = [c for c in REQUIRED_COLUMNS if row.get(c) is None]
        assert not missing, f"ROW_{index}_MISSING_VALUES:{missing}"


def test_all_arms_present() -> None:
    ids = [row["comparator_id"] for row in _load_matrix()]
    for prefix in REQUIRED_ARM_PREFIXES:
        assert any(cid.startswith(prefix) for cid in ids), f"MISSING_ARM:{prefix}"


def test_required_literature_and_named_references_present() -> None:
    ids = {row["comparator_id"] for row in _load_matrix()}
    for lit_id in REQUIRED_LITERATURE_IDS:
        assert lit_id in ids, f"MISSING_LITERATURE_ROW:{lit_id}"
    for ref in REQUIRED_NAMED_REFERENCES:
        assert ref in ids, f"MISSING_NAMED_REFERENCE:{ref}"


def test_comparator_ids_are_real_registry_ids_or_blueprint_references() -> None:
    literature = _literature_ids()
    registry_names = _baseline_registry_names()
    for row in _load_matrix():
        cid = row["comparator_id"]
        if cid in literature:
            continue
        arm, _, name = cid.partition("-")
        is_arm = arm in {"B0", "B1", "B2", "B3"} and name in registry_names
        is_named_ref = cid.startswith("blueprint-")
        assert is_arm or is_named_ref, f"UNKNOWN_COMPARATOR_ID:{cid}"


def test_every_row_has_mechanism_analysis() -> None:
    for row in _load_matrix():
        analysis = (row["mechanism_analysis"] or "").strip()
        assert len(analysis) >= 40, f"MECHANISM_ANALYSIS_MISSING_OR_THIN:{row['comparator_id']}"


def test_available_code_yes_requires_code_url() -> None:
    for row in _load_matrix():
        available = row["available_code"]
        assert available in ALLOWED_AVAILABLE_CODE, (
            f"INVALID_AVAILABLE_CODE:{row['comparator_id']}:{available}"
        )
        if available == "yes":
            code_url = (row["code_url"] or "").strip()
            assert code_url.startswith(("http://", "https://")), (
                f"AVAILABLE_CODE_WITHOUT_CODE_URL:{row['comparator_id']}"
            )


def test_fidelity_status_uses_registry_vocabulary() -> None:
    for row in _load_matrix():
        status = row["fidelity_status"]
        assert status in ALLOWED_FIDELITY, (
            f"UNKNOWN_FIDELITY_STATUS:{row['comparator_id']}:{status}"
        )
        if status in ("ORIGINAL_UPSTREAM", "FAITHFUL_PORT") and row["available_code"] == "yes":
            assert (row["code_url"] or "").strip(), (
                f"VERIFIED_FIDELITY_WITHOUT_CODE_URL:{row['comparator_id']}"
            )


def test_registries_still_contain_referenced_anchors() -> None:
    registry_names = _baseline_registry_names()
    for arm_name in REQUIRED_ARM_REGISTRY_NAMES:
        assert arm_name in registry_names, f"REGISTRY_ANCHOR_MISSING:{arm_name}"
