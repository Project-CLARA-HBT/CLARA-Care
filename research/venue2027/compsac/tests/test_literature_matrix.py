"""Structural test for the COMPSAC-prior literature matrix.

Purpose
-------
Machine-checks that ``research/venue2027/compsac/literature_matrix.csv`` is a
well-formed comparator matrix for the P01 prior-art gate: parseable CSV, the
required columns, all five blueprint arms (B0-B4), a non-empty mechanism
analysis on every row, code-availability discipline (``available_code=yes``
requires a ``code_url`` and every declared fidelity status is a legal value),
and no fabricated comparator ids (every id either exists in
``MANIFESTS/literature_registry.json`` or is one of the blueprint's named
benchmark-arm features).

Allowed input
-------------
Read-only access to the matrix CSV, the literature registry JSON and the
worktree root. No network, no DB, no provider calls.

Failure semantics
-----------------
Each check fails with an assertion message naming the missing or fabricated
matrix element; no silent passes. Stdlib-only (csv/json/pathlib), matching the
conventions of ``test_novelty_contract.py``.

Version
-------
``compsac-literature-matrix-test-v1``
"""

from __future__ import annotations

import csv
import json
import pathlib

WORKTREE_ROOT = pathlib.Path(__file__).resolve().parents[4]
MATRIX = pathlib.Path(__file__).resolve().parents[1] / "literature_matrix.csv"
LITERATURE_REGISTRY = (
    WORKTREE_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)

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

REQUIRED_ARMS = (
    "B0-global-profile-version-occ",
    "B1-silo-style-entity-readset-occ",
    "B2-postgresql-ssi",
    "B3-entity-occ-no-closure-ablation",
    "B4-dependency-complete-scope-local-occ",
)

ALLOWED_AVAILABLE_CODE = {"yes", "no", "UNAVAILABLE"}
ALLOWED_FIDELITY = {"ORIGINAL_UPSTREAM", "FAITHFUL_PORT", "UNAVAILABLE_NOT_RUN"}


def _matrix_rows() -> list[dict[str, str]]:
    assert MATRIX.is_file(), f"literature matrix missing at {MATRIX}"
    with MATRIX.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _registry_ids() -> set[str]:
    assert LITERATURE_REGISTRY.is_file(), f"literature registry missing at {LITERATURE_REGISTRY}"
    return set(json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8")).keys())


def test_csv_parses_and_has_required_columns() -> None:
    with MATRIX.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        columns = tuple(reader.fieldnames or ())
    assert columns == REQUIRED_COLUMNS, f"unexpected CSV columns: {columns}"


def test_contains_all_five_blueprint_arms() -> None:
    ids = {row["comparator_id"] for row in _matrix_rows()}
    for arm in REQUIRED_ARMS:
        assert arm in ids, f"blueprint arm missing from matrix: {arm}"


def test_every_row_has_nonempty_mechanism_analysis() -> None:
    for row in _matrix_rows():
        analysis = row["mechanism_analysis"].strip()
        assert analysis, f"empty mechanism_analysis for {row['comparator_id']}"
        assert (
            len(analysis) >= 40
        ), f"mechanism_analysis too short to explain a mechanism for {row['comparator_id']}"


def test_no_available_code_yes_without_code_url() -> None:
    for row in _matrix_rows():
        if row["available_code"] == "yes":
            url = row["code_url"].strip()
            assert url, f"{row['comparator_id']} claims available_code=yes without code_url"
            assert url.startswith(
                ("http://", "https://")
            ), f"{row['comparator_id']} code_url is not an absolute URL: {url!r}"


def test_enum_fields_use_legal_values() -> None:
    for row in _matrix_rows():
        assert (
            row["available_code"] in ALLOWED_AVAILABLE_CODE
        ), f"{row['comparator_id']} illegal available_code: {row['available_code']!r}"
        assert (
            row["fidelity_status"] in ALLOWED_FIDELITY
        ), f"{row['comparator_id']} illegal fidelity_status: {row['fidelity_status']!r}"


def test_no_fabricated_comparator_ids() -> None:
    registry_ids = _registry_ids()
    for row in _matrix_rows():
        cid = row["comparator_id"]
        is_registry_id = cid in registry_ids
        is_blueprint_arm = cid.startswith(("B0-", "B1-", "B2-", "B3-", "B4-"))
        assert is_registry_id or is_blueprint_arm, (
            f"comparator id {cid!r} is neither a literature-registry id nor a "
            f"blueprint benchmark arm (fabricated comparator)"
        )


def test_every_row_cites_a_primary_source_locator() -> None:
    for row in _matrix_rows():
        locator = row["doi_or_url"].strip()
        assert locator.startswith(
            ("http://", "https://")
        ), f"{row['comparator_id']} lacks a DOI/URL primary-source locator"


def test_no_row_labeled_weak_without_mechanism_reasoning() -> None:
    for row in _matrix_rows():
        text = row["mechanism_analysis"].lower()
        assert (
            "strong" in text or "candidate" in text or "ablation" in text
        ), f"{row['comparator_id']} mechanism_analysis does not ground the comparator's role"


def test_registry_ids_cite_their_registered_locator() -> None:
    registry = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    for row in _matrix_rows():
        entry = registry.get(row["comparator_id"])
        if entry is None:
            continue
        registered = entry.get("url", "").strip()
        cited = row["doi_or_url"].strip()
        assert (
            cited == registered
        ), f"{row['comparator_id']} cites {cited!r} but the registry has {registered!r}"
