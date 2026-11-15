"""Structural gate for DIMVA-prior (literature_matrix.csv).

Purpose
-------
Machine-checks task ``DIMVA-prior`` (venue ``dimva``, phase ``P01``) against
the deliverable contract: ``research/venue2027/dimva/literature_matrix.csv``
must be a valid comparator matrix under the SHARED validator
``research/venue2027/_shared/tools/comparator_matrix.py`` (imported, not
reimplemented), and must additionally carry the comparators the DIMVA novelty
contract names:

- the minimal-event probing-detection framing: the ledger is a *detection*
  study (campaign-level AUCPR at a fixed false-positive budget over event
  streams) and must never drift into prevention/admission language for its own
  endpoint (that boundary belongs to the IFIP SEC sibling study);
- anomaly-detection baseline ``sommer10`` (environmental-memorization anchor),
  agent tool-use benchmarks ``agentdojo24``/``toolemu24``/``tauben25``/
  ``injecagent24``, verification-time authorization boundaries
  ``zanzibar19``/``macaroons14``;
- every blueprint arm ``B0``-``B4`` (B4 = candidate, recorded for falsification
  transparency, never presented as an external comparator).

Adversarial controls (executed against the shared validator, not copies of
it): a fabricated comparator id, an ``available_code=yes`` row without a
``code_url``, a thin ``mechanism_analysis``, and an ``ORIGINAL_UPSTREAM`` row
without code must all fail loudly with the shared validator's stable reason
codes - citing a nonexistent implementation must never pass silently.

Allowed input
-------------
Read-only access to the matrix CSV, ``MANIFESTS/literature_registry.json``,
``_shared/baselines/registry.yaml``, ``research/publication_registry.yaml``
(archive study id ``glhs-journal``) and the shared tools directory. No
network, no database, no provider calls, no randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``DIMVA_PRIOR_``; pytest reports the failing check directly. The shared
validator itself is never modified by these tests.

Version
-------
``DIMVA_PRIOR_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SHARED_TOOLS = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import comparator_matrix as cm  # noqa: E402

DIMVA_PRIOR_TEST_VERSION = "1.0.0"

DIMVA_DIR = pathlib.Path(__file__).resolve().parents[1]
MATRIX = DIMVA_DIR / "literature_matrix.csv"
NOVELTY_CONTRACT = DIMVA_DIR / "novelty_contract.md"
THREAT_MODEL = DIMVA_DIR / "threat_model.md"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"
PUBLICATION_REGISTRY = REPO_ROOT / "research" / "publication_registry.yaml"

# Novelty-contract claim matrix (C1-C7) anchors that MUST appear as rows.
REQUIRED_LITERATURE_IDS = (
    "agentdojo24",  # C1: agent attack benchmark; independent multi-stage traces
    "toolemu24",  # C2: LM-emulated sandbox; simulated outcomes != persisted events
    "tauben25",  # C3: final-state policy scoring; no temporal detection endpoint
    "injecagent24",  # C4: injection threat families for cross-family holdout
    "sommer10",  # C5: environmental memorization / label-leakage warning
    "zanzibar19",  # C6: verification-time authorization, no telemetry surface
    "macaroons14",  # C7: caveat tokens prevent, they do not detect over time
)

# Blueprint arms (B4 is the candidate itself, still required as a row).
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B3-", "B4-")

# Shared-baseline-registry arm entries backing the B-prefixed rows.
REQUIRED_ARM_REGISTRY_NAMES = (
    "static-threshold-denied-per-window",
    "temporal-rule-sequence-signature",
    "isolation-forest-privacy-minimized",
    "gradient-boosted-trees-controlled-features",
)


def _load_matrix_text() -> str:
    assert MATRIX.is_file(), f"DIMVA_PRIOR_MISSING_MATRIX: {MATRIX}"
    return MATRIX.read_text(encoding="utf-8")


def _load_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(_load_matrix_text())))
    for index, row in enumerate(rows, start=2):
        missing = [c for c in cm.REQUIRED_COLUMNS if row.get(c) is None]
        assert not missing, f"DIMVA_PRIOR_ROW_{index}_MISSING_VALUES:{missing}"
    return rows


def _literature_registry() -> dict[str, object]:
    assert LITERATURE_REGISTRY.is_file(), f"DIMVA_PRIOR_MISSING_REGISTRY: {LITERATURE_REGISTRY}"
    payload = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "DIMVA_PRIOR_REGISTRY_SHAPE"
    return payload


def _baseline_registry_names() -> set[str]:
    assert BASELINE_REGISTRY.is_file(), (
        f"DIMVA_PRIOR_MISSING_BASELINE_REGISTRY: {BASELINE_REGISTRY}"
    )
    names: set[str] = set()
    for line in BASELINE_REGISTRY.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("name:"):
            names.add(stripped.split("name:", 1)[1].strip().strip('"'))
    return names


def _validate_shared() -> cm.MatrixResult:
    """Run the shared comparator-matrix validator over the real CSV."""
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    return cm.validate_matrix(_load_matrix_text(), known_registry_ids=known)


# ---------------------------------------------------------------- structure


def test_real_matrix_passes_shared_validator() -> None:
    result = _validate_shared()
    assert result.ok, f"DIMVA_PRIOR_VALIDATOR_FAILED: {result.to_dict()}"
    assert result.reason_codes == (), "DIMVA_PRIOR_REASON_CODES_NONEMPTY"
    assert result.violations == (), "DIMVA_PRIOR_VIOLATIONS_NONEMPTY"
    assert result.row_count >= len(REQUIRED_LITERATURE_IDS) + len(REQUIRED_ARM_PREFIXES), (
        f"DIMVA_PRIOR_TOO_FEW_ROWS: {result.row_count}"
    )


def test_matrix_carries_exactly_the_required_columns() -> None:
    reader = csv.DictReader(io.StringIO(_load_matrix_text()))
    columns = tuple(reader.fieldnames or ())
    assert columns == cm.REQUIRED_COLUMNS, f"DIMVA_PRIOR_COLUMNS_MISMATCH: {columns}"


def test_required_literature_ids_present() -> None:
    ids = {row["comparator_id"] for row in _load_rows()}
    for lit_id in REQUIRED_LITERATURE_IDS:
        assert lit_id in ids, f"DIMVA_PRIOR_MISSING_LITERATURE_ROW:{lit_id}"


def test_all_blueprint_arms_present() -> None:
    ids = [row["comparator_id"] for row in _load_rows()]
    for prefix in REQUIRED_ARM_PREFIXES:
        assert any(cid.startswith(prefix) for cid in ids), f"DIMVA_PRIOR_MISSING_ARM:{prefix}"


def test_comparator_ids_are_registry_ids_or_arms() -> None:
    literature = set(_literature_registry().keys())
    for row in _load_rows():
        cid = row["comparator_id"]
        assert cid in literature or cid.startswith("B"), (
            f"DIMVA_PRIOR_FABRICATED_COMPARATOR_ID:{cid}"
        )


def test_arm_rows_map_to_shared_baseline_registry_names() -> None:
    registry_names = _baseline_registry_names()
    for arm_name in REQUIRED_ARM_REGISTRY_NAMES:
        assert arm_name in registry_names, f"DIMVA_PRIOR_REGISTRY_ANCHOR_MISSING:{arm_name}"


def test_registry_rows_cite_their_registered_locator() -> None:
    registry = _literature_registry()
    for row in _load_rows():
        entry = registry.get(row["comparator_id"])
        if not isinstance(entry, dict):
            continue
        registered = str(entry.get("url", "")).strip()
        cited = row["doi_or_url"].strip()
        assert cited == registered, (
            f"DIMVA_PRIOR_LOCATOR_MISMATCH:{row['comparator_id']}:{cited!r}!={registered!r}"
        )


def test_available_code_yes_rows_cite_http_code_url() -> None:
    for row in _load_rows():
        if row["available_code"] == "yes":
            url = row["code_url"].strip()
            assert url.startswith(("http://", "https://")), (
                f"DIMVA_PRIOR_AVAILABLE_CODE_WITHOUT_URL:{row['comparator_id']}"
            )
            assert row["fidelity_status"] in cm.FIDELITY_STATUSES


def test_every_row_has_mechanism_analysis() -> None:
    for row in _load_rows():
        analysis = (row["mechanism_analysis"] or "").strip()
        assert len(analysis) >= cm.MIN_MECHANISM_CHARS, (
            f"DIMVA_PRIOR_THIN_MECHANISM:{row['comparator_id']}"
        )


def test_unavailable_baselines_are_marked_not_run() -> None:
    for row in _load_rows():
        if row["available_code"] == "UNAVAILABLE":
            assert row["fidelity_status"] == "UNAVAILABLE_NOT_RUN", (
                f"DIMVA_PRIOR_UNAVAILABLE_NOT_MARKED_NOT_RUN:{row['comparator_id']}"
            )


def test_candidate_arm_declared_falsifiable_not_superior() -> None:
    rows = _load_rows()
    candidate = [r for r in rows if r["comparator_id"].startswith("B4-")]
    assert len(candidate) == 1, "DIMVA_PRIOR_CANDIDATE_ARM_COUNT"
    text = (candidate[0]["mechanism_analysis"] + candidate[0]["supported_guarantee"]).lower()
    assert "falsif" in text, "DIMVA_PRIOR_CANDIDATE_NOT_FALSIFIABLE"
    for forbidden in ("superior", "outperform", "beats"):
        assert forbidden not in text, f"DIMVA_PRIOR_CANDIDATE_SUPERIORITY_CLAIM:{forbidden}"


# ------------------------------------------------------------ detection framing


def test_primary_framing_is_detection_not_prevention() -> None:
    """The DIMVA endpoint is detection over event streams, never admission."""
    contract = NOVELTY_CONTRACT.read_text(encoding="utf-8").lower()
    assert "campaign-level pr-auc" in contract or "campaign-level probing detection" in contract, (
        "DIMVA_PRIOR_DETECTION_ENDPOINT_ABSENT"
    )
    assert "detection" in contract and "prevention" in contract, (
        "DIMVA_PRIOR_DETECTION_VS_PREVENTION_LANGUAGE_ABSENT"
    )
    # The four-part boundary against the IFIP SEC prevention sibling must hold.
    assert "one prevents invalid tokens at verification, one detects campaigns over time" in (
        contract.replace("\n", " ")
    ), "DIMVA_PRIOR_IFIP_BOUNDARY_STATEMENT_ABSENT"


def test_matrix_rows_keep_detection_framing() -> None:
    for row in _load_rows():
        cid = row["comparator_id"]
        if cid.startswith("B4-"):
            # The candidate row must claim a detection endpoint, not an
            # admission/prevention endpoint.
            blob = (row["algorithm_class"] + " " + row["supported_guarantee"]).lower()
            assert "detect" in blob or "detection" in blob, (
                f"DIMVA_PRIOR_CANDIDATE_NOT_DETECTION_FRAMED:{cid}"
            )
        if cid.startswith(("B0-", "B1-")):
            # The competing baselines must be framed as detectors too.
            blob = (row["algorithm_class"] + " " + row["supported_guarantee"]).lower()
            assert "detect" in blob or "detector" in blob or "alarm" in blob, (
                f"DIMVA_PRIOR_BASELINE_NOT_DETECTION_FRAMED:{cid}"
            )


def test_matrix_makes_no_prevention_or_admission_claim() -> None:
    lowered = _load_matrix_text().lower()
    for forbidden in (
        "prevents replay",
        "prevents unauthorized",
        "admission decision",
        "our detector prevents",
        "blocks the request",
    ):
        assert forbidden not in lowered, f"DIMVA_PRIOR_PREVENTION_CLAIM:{forbidden}"


def test_threat_model_keeps_detection_boundary() -> None:
    assert THREAT_MODEL.is_file(), f"DIMVA_PRIOR_THREAT_MODEL_MISSING: {THREAT_MODEL}"
    lowered = THREAT_MODEL.read_text(encoding="utf-8").lower()
    assert "detection" in lowered, "DIMVA_PRIOR_THREAT_MODEL_NOT_DETECTION_FRAMED"
    assert "no dimva artifact decides or strengthens a single request's admission" in lowered, (
        "DIMVA_PRIOR_THREAT_MODEL_ADMISSION_BOUNDARY_ABSENT"
    )


def test_archive_refusal_is_recorded_not_cannibalized() -> None:
    """glhs-journal is background only; the contract must refuse it as evidence."""
    assert PUBLICATION_REGISTRY.is_file(), (
        f"DIMVA_PRIOR_PUBLICATION_REGISTRY_MISSING: {PUBLICATION_REGISTRY}"
    )
    pub_registry = PUBLICATION_REGISTRY.read_text(encoding="utf-8")
    assert "id: glhs-journal" in pub_registry, "DIMVA_PRIOR_ARCHIVE_STUDY_UNREGISTERED"
    contract = NOVELTY_CONTRACT.read_text(encoding="utf-8").lower()
    assert "refus" in contract, "DIMVA_PRIOR_ARCHIVE_REFUSAL_LANGUAGE_ABSENT"
    assert "no e15" in contract and "may be re-labeled" in contract, (
        "DIMVA_PRIOR_ARCHIVE_RELABEL_BAN_ABSENT"
    )


# ------------------------------------------- adversarial controls (shared validator)


def _good_control_csv() -> str:
    header = ",".join(cm.REQUIRED_COLUMNS)
    rows = [
        "B0-arm,T,V,https://example.org/a,,class,guarantee,limitation,no,UNAVAILABLE_NOT_RUN,"
        '"Strong comparator because the mechanism differs on the isolated axis."',
        "B1-arm,T,V,https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM,"
        '"Strong comparator with runnable upstream code pinned at a verified revision."',
        "B2-arm,T,V,https://example.org/c,,class,guarantee,limitation,no,UNAVAILABLE_NOT_RUN,"
        '"Strong comparator retained as an anchor for the holdout surface."',
    ]
    return "\n".join([header, *rows]) + "\n"


def _mutate(control: str, old: str, new: str) -> str:
    assert old in control, "DIMVA_PRIOR_CONTROL_MUTATION_MISS"
    return control.replace(old, new, 1)


def test_adversarial_fabricated_comparator_id_fails() -> None:
    bad = _mutate(_good_control_csv(), "B2-arm", "made-up-probing-detector-2049")
    result = cm.validate_matrix(bad, known_registry_ids=set())
    assert result.ok is False, "DIMVA_PRIOR_FABRICATED_ID_UNEXPECTEDLY_PASSED"
    assert "UNKNOWN_COMPARATOR_ID" in result.reason_codes, (
        f"DIMVA_PRIOR_FABRICATED_ID_CODES:{result.reason_codes}"
    )


def test_adversarial_missing_source_link_fails() -> None:
    bad = _mutate(_good_control_csv(), "https://example.org/c", "")
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DIMVA_PRIOR_MISSING_LINK_UNEXPECTEDLY_PASSED"
    assert "MISSING_SOURCE_LINK" in result.reason_codes, (
        f"DIMVA_PRIOR_MISSING_LINK_CODES:{result.reason_codes}"
    )


def test_adversarial_thin_mechanism_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "Strong comparator retained as an anchor for the holdout surface.",
        "weak",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DIMVA_PRIOR_THIN_MECH_UNEXPECTEDLY_PASSED"
    assert "MECHANISM_ANALYSIS_MISSING" in result.reason_codes, (
        f"DIMVA_PRIOR_THIN_MECH_CODES:{result.reason_codes}"
    )


def test_adversarial_available_code_yes_without_url_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
        ",,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DIMVA_PRIOR_CODE_WITHOUT_URL_UNEXPECTEDLY_PASSED"
    assert "AVAILABLE_CODE_WITHOUT_URL" in result.reason_codes, (
        f"DIMVA_PRIOR_CODE_WITHOUT_URL_CODES:{result.reason_codes}"
    )


def test_adversarial_upstream_without_code_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "limitation,yes,ORIGINAL_UPSTREAM",
        "limitation,no,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DIMVA_PRIOR_UPSTREAM_WITHOUT_CODE_UNEXPECTEDLY_PASSED"
    assert "UPSTREAM_WITHOUT_CODE" in result.reason_codes, (
        f"DIMVA_PRIOR_UPSTREAM_WITHOUT_CODE_CODES:{result.reason_codes}"
    )


def test_adversarial_tampering_of_the_real_matrix_is_detected() -> None:
    """Mutating one real row must flip the shared validator to not-ok."""
    text = _load_matrix_text()
    target = "https://github.com/scikit-learn/scikit-learn,https://github.com/scikit-learn/scikit-learn,Unsupervised anomaly detection"
    assert target in text, "DIMVA_PRIOR_TAMPER_TARGET_ABSENT"
    tampered = text.replace(
        target,
        ",https://github.com/scikit-learn/scikit-learn,Unsupervised anomaly detection",
        1,
    )
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    result = cm.validate_matrix(tampered, known_registry_ids=known)
    assert result.ok is False, "DIMVA_PRIOR_TAMPERED_MATRIX_PASSED"
    assert "MISSING_SOURCE_LINK" in result.reason_codes, (
        f"DIMVA_PRIOR_TAMPER_CODES:{result.reason_codes}"
    )


def test_shared_validator_version_is_pinned() -> None:
    assert cm.COMPARATOR_MATRIX_VERSION == "1.0.0", "DIMVA_PRIOR_VALIDATOR_VERSION_DRIFT"
