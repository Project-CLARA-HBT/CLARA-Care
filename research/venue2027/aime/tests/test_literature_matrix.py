"""Structural gate for AIME-prior (literature_matrix.csv).

Purpose
-------
Validate ``research/venue2027/aime/literature_matrix.csv`` through the shared
program validator ``validate_matrix() -> MatrixResult`` from
``research/venue2027/_shared/tools/comparator_matrix.py`` (task
``AIME-prior``, phase ``P01``, venue ``aime``). The real matrix must pass the
shared validator with every blueprint arm and the clinical-AI comparator
classes present; adversarial variants (fabricated comparator id, missing
source link, thin mechanism analysis, ``available_code=yes`` without a code
URL, ``ORIGINAL_UPSTREAM`` without runnable code) must fail with their stable
reason codes. The matrix must assert the clinical-venue claim discipline: no
clinical efficacy claim is made anywhere in the ledger, and the governing
novelty contract keeps the mandatory standing language (no real PHI, synthetic
vignettes only, blinded independent clinician review, synthetic action
correctness is NOT clinical efficacy).

Allowed input
-------------
Read-only access to the matrix CSV, the literature registry
(``MANIFESTS/literature_registry.json``), the shared baseline registry
(``_shared/baselines/registry.yaml``), the AIME novelty contract and
in-memory CSV strings used as positive/adversarial controls for the shared
validator. No network, no DB, no provider calls, no randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``AIME_PRIOR_``; pytest reports the failing check directly. The shared
validator itself is never modified by these tests.

Version
-------
``AIME_PRIOR_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SHARED_TOOLS = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import comparator_matrix as cm  # noqa: E402

AIME_PRIOR_TEST_VERSION = "1.0.0"

AIME_DIR = pathlib.Path(__file__).resolve().parents[1]
MATRIX = AIME_DIR / "literature_matrix.csv"
NOVELTY_CONTRACT = AIME_DIR / "novelty_contract.md"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

# Blueprint arms B0-B3 plus the candidate (B4) and the consent-agnostic
# retrieval reference (B5). Registry baseline names each arm maps to.
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B3-", "B4-", "B5-")
REQUIRED_ARM_REGISTRY_NAMES = (
    "full-authorized-history-single-snapshot",
    "full-per-step-refresh-current-policy-filter",
    "healthbench-medhelm-rubric",
    "static-model-output-post-filter",
)

# Clinical-AI comparator classes that must appear as real registry rows.
REQUIRED_LITERATURE_IDS = (
    "medhelm2026",  # strong clinical benchmark suite (MedHELM)
    "healthbench25",  # strong clinical benchmark suite (HealthBench)
    "amie2026",  # longitudinal conversational clinical AI (Amie)
    "cse2026",  # physician-consensus evaluation quality baseline
    "tauben25",  # policy-following tool-agent workflow benchmark
    "fhir5",  # consent structure vocabulary (claim M3 surface)
    "who21",  # clinical governance claim boundary (claim M5)
)


def _load_matrix_text() -> str:
    assert MATRIX.is_file(), f"AIME_PRIOR_MISSING_MATRIX: {MATRIX}"
    return MATRIX.read_text(encoding="utf-8")


def _load_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(_load_matrix_text())))
    for index, row in enumerate(rows, start=2):
        missing = [c for c in cm.REQUIRED_COLUMNS if row.get(c) is None]
        assert not missing, f"AIME_PRIOR_ROW_{index}_MISSING_VALUES:{missing}"
    return rows


def _literature_registry() -> dict[str, object]:
    assert LITERATURE_REGISTRY.is_file(), f"AIME_PRIOR_MISSING_REGISTRY: {LITERATURE_REGISTRY}"
    payload = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "AIME_PRIOR_REGISTRY_SHAPE"
    return payload


def _baseline_registry_names() -> set[str]:
    assert BASELINE_REGISTRY.is_file(), f"AIME_PRIOR_MISSING_BASELINE_REGISTRY: {BASELINE_REGISTRY}"
    names: set[str] = set()
    for line in BASELINE_REGISTRY.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("name:"):
            names.add(stripped.split("name:", 1)[1].strip().strip('"'))
    return names


def test_real_matrix_passes_shared_validator() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    result = cm.validate_matrix(_load_matrix_text(), known_registry_ids=known)
    assert result.ok, f"AIME_PRIOR_VALIDATOR_FAILED: {result.to_dict()}"
    assert result.reason_codes == (), "AIME_PRIOR_REASON_CODES_NONEMPTY"
    assert result.violations == (), "AIME_PRIOR_VIOLATIONS_NONEMPTY"
    assert result.row_count >= 3, "AIME_PRIOR_TOO_FEW_ROWS"


def test_matrix_carries_exactly_the_required_columns() -> None:
    reader = csv.DictReader(io.StringIO(_load_matrix_text()))
    columns = tuple(reader.fieldnames or ())
    assert columns == cm.REQUIRED_COLUMNS, f"AIME_PRIOR_COLUMNS_MISMATCH: {columns}"


def test_all_blueprint_arms_present() -> None:
    ids = [row["comparator_id"] for row in _load_rows()]
    for prefix in REQUIRED_ARM_PREFIXES:
        assert any(cid.startswith(prefix) for cid in ids), f"AIME_PRIOR_MISSING_ARM:{prefix}"


def test_required_literature_ids_present() -> None:
    ids = {row["comparator_id"] for row in _load_rows()}
    for lit_id in REQUIRED_LITERATURE_IDS:
        assert lit_id in ids, f"AIME_PRIOR_MISSING_LITERATURE_ROW:{lit_id}"


def test_comparator_ids_are_registry_ids_or_arms() -> None:
    literature = set(_literature_registry().keys())
    for row in _load_rows():
        cid = row["comparator_id"]
        assert cid in literature or cid.startswith("B"), (
            f"AIME_PRIOR_FABRICATED_COMPARATOR_ID:{cid}"
        )


def test_arm_rows_map_to_shared_baseline_registry_names() -> None:
    registry_names = _baseline_registry_names()
    for arm_name in REQUIRED_ARM_REGISTRY_NAMES:
        assert arm_name in registry_names, f"AIME_PRIOR_REGISTRY_ANCHOR_MISSING:{arm_name}"


def test_registry_rows_cite_their_registered_locator() -> None:
    registry = _literature_registry()
    for row in _load_rows():
        entry = registry.get(row["comparator_id"])
        if not isinstance(entry, dict):
            continue
        registered = str(entry.get("url", "")).strip()
        cited = row["doi_or_url"].strip()
        assert cited == registered, (
            f"AIME_PRIOR_LOCATOR_MISMATCH:{row['comparator_id']}:{cited!r}!={registered!r}"
        )


def test_every_row_has_mechanism_analysis() -> None:
    for row in _load_rows():
        analysis = (row["mechanism_analysis"] or "").strip()
        assert len(analysis) >= cm.MIN_MECHANISM_CHARS, (
            f"AIME_PRIOR_THIN_MECHANISM:{row['comparator_id']}"
        )


def test_no_row_labeled_weak_without_mechanism_reasoning() -> None:
    for row in _load_rows():
        text = (row["mechanism_analysis"] or "").lower()
        assert "strong" in text or "candidate" in text or "ablation" in text or "anchor" in text, (
            f"AIME_PRIOR_WEAK_LABEL_WITHOUT_MECHANISM:{row['comparator_id']}"
        )


def test_candidate_arm_declared_falsifiable_not_superior() -> None:
    rows = _load_rows()
    candidate = [r for r in rows if r["comparator_id"].startswith("B4-")]
    assert len(candidate) == 1, "AIME_PRIOR_CANDIDATE_ARM_COUNT"
    text = (candidate[0]["mechanism_analysis"] + candidate[0]["supported_guarantee"]).lower()
    assert "falsif" in text, "AIME_PRIOR_CANDIDATE_NOT_FALSIFIABLE"
    for forbidden in ("superior", "outperform", "beats"):
        assert forbidden not in text, f"AIME_PRIOR_CANDIDATE_SUPERIORITY_CLAIM:{forbidden}"


def test_unavailable_baselines_are_marked_not_run() -> None:
    for row in _load_rows():
        if row["available_code"] == "UNAVAILABLE":
            assert row["fidelity_status"] == "UNAVAILABLE_NOT_RUN", (
                f"AIME_PRIOR_UNAVAILABLE_NOT_MARKED_NOT_RUN:{row['comparator_id']}"
            )


def _good_control_csv() -> str:
    header = ",".join(cm.REQUIRED_COLUMNS)
    rows = [
        "B0-arm,T,V,https://example.org/a,,class,guarantee,limitation,no,UNAVAILABLE_NOT_RUN,"
        '"Strong comparator because the mechanism differs on the isolated axis."',
        "B1-arm,T,V,https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM,"
        '"Strong comparator with runnable upstream code pinned at a verified revision."',
        "B2-arm,T,V,https://example.org/c,,class,guarantee,limitation,no,UNAVAILABLE_NOT_RUN,"
        '"Strong comparator retained as an anchor for the ablation surface."',
    ]
    return "\n".join([header, *rows]) + "\n"


def _mutate(control: str, old: str, new: str) -> str:
    assert old in control, "AIME_PRIOR_CONTROL_MUTATION_MISS"
    return control.replace(old, new, 1)


def test_adversarial_fabricated_comparator_id_fails() -> None:
    bad = _mutate(_good_control_csv(), "B2-arm", "totally-made-up-paper")
    result = cm.validate_matrix(bad, known_registry_ids=set())
    assert result.ok is False, "AIME_PRIOR_FABRICATED_ID_UNEXPECTEDLY_PASSED"
    assert "UNKNOWN_COMPARATOR_ID" in result.reason_codes, (
        f"AIME_PRIOR_FABRICATED_ID_CODES:{result.reason_codes}"
    )


def test_adversarial_missing_source_link_fails() -> None:
    bad = _mutate(_good_control_csv(), "https://example.org/c", "")
    result = cm.validate_matrix(bad)
    assert result.ok is False, "AIME_PRIOR_MISSING_LINK_UNEXPECTEDLY_PASSED"
    assert "MISSING_SOURCE_LINK" in result.reason_codes, (
        f"AIME_PRIOR_MISSING_LINK_CODES:{result.reason_codes}"
    )


def test_adversarial_thin_mechanism_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "Strong comparator retained as an anchor for the ablation surface.",
        "weak",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "AIME_PRIOR_THIN_MECH_UNEXPECTEDLY_PASSED"
    assert "MECHANISM_ANALYSIS_MISSING" in result.reason_codes, (
        f"AIME_PRIOR_THIN_MECH_CODES:{result.reason_codes}"
    )


def test_adversarial_available_code_yes_without_url_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
        ",,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "AIME_PRIOR_CODE_WITHOUT_URL_UNEXPECTEDLY_PASSED"
    assert "AVAILABLE_CODE_WITHOUT_URL" in result.reason_codes, (
        f"AIME_PRIOR_CODE_WITHOUT_URL_CODES:{result.reason_codes}"
    )


def test_adversarial_upstream_without_code_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "limitation,yes,ORIGINAL_UPSTREAM",
        "limitation,no,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "AIME_PRIOR_UPSTREAM_WITHOUT_CODE_UNEXPECTEDLY_PASSED"
    assert "UPSTREAM_WITHOUT_CODE" in result.reason_codes, (
        f"AIME_PRIOR_UPSTREAM_WITHOUT_CODE_CODES:{result.reason_codes}"
    )


def test_no_clinical_efficacy_claim_in_matrix() -> None:
    text = _load_matrix_text()
    lowered = text.lower()
    # The matrix makes only systems-level workflow-safety claims; it must
    # reference the blinded clinician-review requirement rather than efficacy.
    assert "blinded independent clinician review" in lowered, (
        "AIME_PRIOR_BLINDED_REVIEW_ANCHOR_ABSENT"
    )
    for forbidden in (
        "clinically effective",
        "proves clinical efficacy",
        "improves patient outcomes",
        "diagnostic accuracy of",
        "clinical trial",
    ):
        assert forbidden not in lowered, f"AIME_PRIOR_FORBIDDEN_EFFICACY_PHRASE:{forbidden}"
    # No invented empirical numbers: no percentage or p-value style results.
    assert not re.search(r"\b\d+(\.\d+)?%", text), "AIME_PRIOR_PERCENTAGE_FOUND"
    assert not re.search(r"\bp\s*[<>=]", text, flags=re.IGNORECASE), "AIME_PRIOR_PVALUE_FOUND"


def test_governing_contract_keeps_no_efficacy_standing_language() -> None:
    # The standing declarations live in the AIME novelty contract; this ledger
    # must not silently drift away from them.
    assert NOVELTY_CONTRACT.is_file(), f"AIME_PRIOR_CONTRACT_MISSING: {NOVELTY_CONTRACT}"
    lowered = NOVELTY_CONTRACT.read_text(encoding="utf-8").lower()
    assert "no real phi" in lowered, "AIME_PRIOR_CONTRACT_NO_REAL_PHI_ABSENT"
    assert "synthetic vignettes only" in lowered, "AIME_PRIOR_CONTRACT_SYNTHETIC_ONLY_ABSENT"
    assert "blinded independent clinician review" in lowered, (
        "AIME_PRIOR_CONTRACT_BLINDED_REVIEW_ABSENT"
    )
    assert "synthetic action correctness is not clinical efficacy" in lowered, (
        "AIME_PRIOR_CONTRACT_NO_EFFICACY_STATEMENT_ABSENT"
    )
