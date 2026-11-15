"""Structural gate for ACNS-prior (literature_matrix.csv).

Purpose
-------
Machine-checks task ``ACNS-prior`` (venue ``acns``, phase ``P01``) against the
deliverable contract: ``research/venue2027/acns/literature_matrix.csv`` must be
a valid comparator matrix under the SHARED validator
``research/venue2027/_shared/tools/comparator_matrix.py`` (imported, not
reimplemented), and must additionally carry the SoK framing the ACNS novelty
contract and blueprint fix:

- attestation/provenance **evidence-boundary** coverage as registry rows:
  ``rats9334`` (RFC 9334/RATS normative evidence taxonomy, baseline B0),
  ``ct9162`` (RFC 9162 Certificate Transparency: verifiable logs are not
  processing/execution proof), ``macaroons14`` (context-bound authority is not
  attestation), ``zanzibar19`` (verification-time consistency boundary),
  ``agentdojo24``/``toolemu24``/``tauben25`` (agent-benchmark observability
  categories, baseline B2), ``fhir5`` (retrospective lineage, baseline B1);
- every blueprint arm ``B0``-``B3`` (B3 is the candidate dual-human-coded
  taxonomy, recorded for falsification transparency, never presented as an
  external comparator);
- **SoK framing (the contribution class)**: this is a Systematization of
  Knowledge - the deliverable is an evidence-boundary coverage matrix over the
  published literature, NOT a new mechanism. The tests below assert the
  framing language (taxonomy/coverage/lattice/corpus coding) is present, that
  no row claims a novel attestation primitive, enforcement mechanism, or
  runnable benchmark, that the candidate arm is declared falsifiable, and that
  the matrix consumes no frozen E15-E22 archive, no IFIP mechanism inputs and
  no DIMVA telemetry (cross-study firewall).

Adversarial controls (executed against the shared validator, not copies of
it): an unknown/fabricated comparator id, a missing source link, a thin
``mechanism_analysis``, an ``available_code=yes`` row without ``code_url``,
and an ``ORIGINAL_UPSTREAM`` row without code must all fail loudly with the
shared validator's stable reason codes - citing a nonexistent implementation
must never pass silently.

Allowed input
-------------
Read-only access to the matrix CSV, ``MANIFESTS/literature_registry.json``,
``_shared/baselines/registry.yaml``, the ACNS novelty contract and in-memory
CSV strings used as positive/adversarial controls for the shared validator.
No network, no database, no provider calls, no randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``ACNS_PRIOR_``; pytest reports the failing check directly. The shared
validator itself is never modified by these tests.

Version
-------
``ACNS_PRIOR_TEST_VERSION = "1.0.0"``
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

ACNS_PRIOR_TEST_VERSION = "1.0.0"

ACNS_DIR = pathlib.Path(__file__).resolve().parents[1]
MATRIX = ACNS_DIR / "literature_matrix.csv"
NOVELTY_CONTRACT = ACNS_DIR / "novelty_contract.md"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

# Evidence-boundary comparators that MUST appear as real registry rows.
REQUIRED_REGISTRY_IDS = (
    "rats9334",  # B0 source: normative RATS attester/evidence/verifier boundary
    "ct9162",  # transparency: verifiable logs != processing/execution proof
    "macaroons14",  # context-bound authority != attestation evidence
    "zanzibar19",  # verification-time consistency boundary (staleness)
    "agentdojo24",  # B2 source: agent benchmark observability categories
    "toolemu24",  # B2 source: emulated sandbox evidence below L2
    "tauben25",  # harness-internal database-state outcome evidence
    "fhir5",  # B1 companion: retrospective consent/audit/provenance lineage
)

# Blueprint arms B0-B3 (B3 is the candidate SoK arm itself).
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B3-")

# Shared-baseline-registry arm entries backing the B-prefixed rows.
REQUIRED_ARM_REGISTRY_NAMES = (
    "rats-rfc9334-framework",
    "w3c-prov-provenance-audit",
    "agentdojo-attack-observability",
    "toolemu-risk-emulation",
)


def _load_matrix_text() -> str:
    assert MATRIX.is_file(), f"ACNS_PRIOR_MISSING_MATRIX: {MATRIX}"
    return MATRIX.read_text(encoding="utf-8")


def _load_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(_load_matrix_text())))
    for index, row in enumerate(rows, start=2):
        missing = [c for c in cm.REQUIRED_COLUMNS if row.get(c) is None]
        assert not missing, f"ACNS_PRIOR_ROW_{index}_MISSING_VALUES:{missing}"
    return rows


def _literature_registry() -> dict[str, object]:
    assert LITERATURE_REGISTRY.is_file(), f"ACNS_PRIOR_MISSING_REGISTRY: {LITERATURE_REGISTRY}"
    payload = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "ACNS_PRIOR_REGISTRY_SHAPE"
    return payload


def _baseline_registry_names() -> set[str]:
    assert BASELINE_REGISTRY.is_file(), f"ACNS_PRIOR_MISSING_BASELINE_REGISTRY: {BASELINE_REGISTRY}"
    names: set[str] = set()
    for line in BASELINE_REGISTRY.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("name:"):
            names.add(stripped.split("name:", 1)[1].strip().strip('"'))
    return names


def _validate_shared() -> cm.MatrixResult:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    return cm.validate_matrix(_load_matrix_text(), known_registry_ids=known)


# ---------------------------------------------------------------------------
# Positive controls: the real matrix must satisfy the shared validator.
# ---------------------------------------------------------------------------


def test_real_matrix_passes_shared_validator() -> None:
    result = _validate_shared()
    assert result.ok, f"ACNS_PRIOR_VALIDATOR_FAILED: {result.to_dict()}"
    assert result.reason_codes == (), "ACNS_PRIOR_REASON_CODES_NONEMPTY"
    assert result.violations == (), "ACNS_PRIOR_VIOLATIONS_NONEMPTY"
    assert result.row_count >= len(REQUIRED_REGISTRY_IDS) + len(REQUIRED_ARM_PREFIXES), (
        f"ACNS_PRIOR_TOO_FEW_ROWS: {result.row_count}"
    )


def test_matrix_carries_exactly_the_required_columns() -> None:
    reader = csv.DictReader(io.StringIO(_load_matrix_text()))
    columns = tuple(reader.fieldnames or ())
    assert columns == cm.REQUIRED_COLUMNS, f"ACNS_PRIOR_COLUMNS_MISMATCH: {columns}"


def test_required_registry_ids_present() -> None:
    ids = {row["comparator_id"] for row in _load_rows()}
    for lit_id in REQUIRED_REGISTRY_IDS:
        assert lit_id in ids, f"ACNS_PRIOR_MISSING_LITERATURE_ROW:{lit_id}"


def test_all_blueprint_arms_present() -> None:
    ids = [row["comparator_id"] for row in _load_rows()]
    for prefix in REQUIRED_ARM_PREFIXES:
        assert any(cid.startswith(prefix) for cid in ids), f"ACNS_PRIOR_MISSING_ARM:{prefix}"


def test_comparator_ids_are_registry_ids_or_b_arms() -> None:
    literature = set(_literature_registry().keys())
    for row_ in _load_rows():
        cid = row_["comparator_id"]
        assert cid in literature or cid.startswith("B"), (
            f"ACNS_PRIOR_FABRICATED_COMPARATOR_ID:{cid}"
        )


def test_arm_rows_map_to_shared_baseline_registry_entries() -> None:
    registry_names = _baseline_registry_names()
    for arm_name in REQUIRED_ARM_REGISTRY_NAMES:
        assert arm_name in registry_names, f"ACNS_PRIOR_REGISTRY_ANCHOR_MISSING:{arm_name}"


def test_registry_rows_cite_their_registered_locator() -> None:
    registry = _literature_registry()
    for row_ in _load_rows():
        entry = registry.get(row_["comparator_id"])
        if not isinstance(entry, dict):
            continue
        registered = str(entry.get("url", "")).strip()
        cited = row_["doi_or_url"].strip()
        assert cited == registered, (
            f"ACNS_PRIOR_LOCATOR_MISMATCH:{row_['comparator_id']}:{cited!r}!={registered!r}"
        )


def test_every_row_has_mechanism_analysis() -> None:
    for row_ in _load_rows():
        analysis = (row_["mechanism_analysis"] or "").strip()
        assert len(analysis) >= cm.MIN_MECHANISM_CHARS, (
            f"ACNS_PRIOR_THIN_MECHANISM:{row_['comparator_id']}"
        )


def test_no_row_labeled_weak_without_mechanism_reasoning() -> None:
    for row_ in _load_rows():
        text = (row_["mechanism_analysis"] or "").lower()
        assert "strong" in text or "candidate" in text or "anchor" in text or "baseline" in text, (
            f"ACNS_PRIOR_WEAK_LABEL_WITHOUT_MECHANISM:{row_['comparator_id']}"
        )


def test_available_code_yes_rows_cite_verified_upstream_code() -> None:
    for row_ in _load_rows():
        if row_["available_code"] == "yes":
            url = row_["code_url"].strip()
            assert url.startswith(("http://", "https://")), (
                f"ACNS_PRIOR_AVAILABLE_WITHOUT_URL:{row_['comparator_id']}"
            )
            assert row_["fidelity_status"] == "ORIGINAL_UPSTREAM", (
                f"ACNS_PRIOR_YES_NOT_ORIGINAL_UPSTREAM:{row_['comparator_id']}"
            )


def test_unavailable_baselines_are_marked_not_run() -> None:
    for row_ in _load_rows():
        if row_["available_code"] == "UNAVAILABLE":
            assert row_["fidelity_status"] == "UNAVAILABLE_NOT_RUN", (
                f"ACNS_PRIOR_UNAVAILABLE_NOT_MARKED_NOT_RUN:{row_['comparator_id']}"
            )


# ---------------------------------------------------------------------------
# SoK framing: evidence-boundary coverage, not a new mechanism.
# ---------------------------------------------------------------------------


def test_sok_framing_language_present_in_matrix() -> None:
    text = _load_matrix_text().lower()
    for required in (
        "evidence-to-claim lattice",
        "coverage matrix",
        "corpus",
        "falsification",
    ):
        assert required in text, f"ACNS_PRIOR_SOK_FRAMING_MISSING:{required}"


def test_matrix_declares_coverage_not_new_mechanism() -> None:
    # The SoK's object is the published literature's claim-evidence structure:
    # coding/systematizing language must appear, and the matrix must not claim
    # to introduce a deployable artifact.
    text = _load_matrix_text().lower()
    assert "systemat" in text, "ACNS_PRIOR_SYSTEMATIZATION_LANGUAGE_ABSENT"
    for forbidden in (
        "we introduce a new mechanism",
        "novel cryptographic primitive",
        "we propose a new protocol",
        "state-of-the-art detector",
    ):
        assert forbidden not in text, f"ACNS_PRIOR_MECHANISM_CLAIM_FOUND:{forbidden}"


def test_candidate_arm_declared_falsifiable_not_superior() -> None:
    candidate = [r for r in _load_rows() if r["comparator_id"].startswith("B3-")]
    assert len(candidate) == 1, "ACNS_PRIOR_CANDIDATE_ARM_COUNT"
    row_ = candidate[0]
    assert row_["available_code"] != "yes", (
        "ACNS_PRIOR_CANDIDATE_CLAIMS_AVAILABLE_CODE: candidate must not be "
        "presented as a runnable external comparator"
    )
    text = (row_["mechanism_analysis"] + " " + row_["supported_guarantee"]).lower()
    assert "falsif" in text, "ACNS_PRIOR_CANDIDATE_NOT_FALSIFIABLE"
    assert "candidate" in text, "ACNS_PRIOR_CANDIDATE_NOT_LABELLED"
    for forbidden in ("superior", "outperform", "beats"):
        assert forbidden not in text, f"ACNS_PRIOR_CANDIDATE_SUPERIORITY_CLAIM:{forbidden}"


def test_evidence_boundary_classes_covered() -> None:
    # The six lattice classes must be covered by the matrix's framing rows:
    # assembly/egress and execution (B0/RATS), transport and receipt boundary
    # (transparency/replay comparators), semantic consumption (tau-bench,
    # gap G3), lineage (B1/PROV-FHIR), and agent-benchmark observability (B2).
    text = _load_matrix_text().lower()
    for concept in (
        "execution trace",
        "semantic consumption",
        "lineage",
        "observability",
        "receipt",
        "verification-time",
    ):
        assert concept in text, f"ACNS_PRIOR_EVIDENCE_BOUNDARY_CLASS_MISSING:{concept}"


def test_no_empirical_values_asserted_in_matrix() -> None:
    # Design-time ledger: no observed kappa, no reproduction rates, no
    # percentages - empirical outcomes enter only via run manifests later.
    text = _load_matrix_text()
    for forbidden in ("kappa =", "κ =", "reproduction rate of", "agreement of 0."):
        assert forbidden not in text.lower(), f"ACNS_PRIOR_EMPIRICAL_VALUE_ASSERTED:{forbidden}"
    assert "0." not in text.replace("0.1.35", "").replace("v0.13.0", ""), (
        "ACNS_PRIOR_NUMERIC_RESULT_FOUND"
    )


def test_cross_study_firewall_declared() -> None:
    # Per ACNS-scope section 5: the SoK consumes no frozen E15-E22 archive, no
    # IFIP mechanism inputs and no DIMVA telemetry, and its coverage matrix
    # must not be presented as evidence for either sibling study.
    candidate = [r for r in _load_rows() if r["comparator_id"].startswith("B3-")]
    assert candidate, "ACNS_PRIOR_CANDIDATE_ARM_ABSENT"
    text = (candidate[0]["mechanism_analysis"]).lower()
    for required in ("e15-e22", "ifip", "dimva"):
        assert required in text, f"ACNS_PRIOR_FIREWALL_CLAUSE_MISSING:{required}"


def test_governing_contract_keeps_sok_declaration() -> None:
    # The standing declarations live in the ACNS novelty contract; this ledger
    # must not silently drift away from them.
    assert NOVELTY_CONTRACT.is_file(), f"ACNS_PRIOR_CONTRACT_MISSING: {NOVELTY_CONTRACT}"
    lowered = NOVELTY_CONTRACT.read_text(encoding="utf-8").lower()
    assert "systematization of knowledge (sok)" in lowered, (
        "ACNS_PRIOR_CONTRACT_SOK_DECLARATION_ABSENT"
    )
    assert "no new mechanism" in lowered, "ACNS_PRIOR_CONTRACT_NO_MECHANISM_ABSENT"
    assert "coverage matrix" in lowered, "ACNS_PRIOR_CONTRACT_COVERAGE_MATRIX_ABSENT"
    assert "counterexample witnesses" in lowered, "ACNS_PRIOR_CONTRACT_WITNESSES_ABSENT"


# ---------------------------------------------------------------------------
# Adversarial controls: the SHARED validator must reject each tampered matrix.
# ---------------------------------------------------------------------------


def _good_control_csv() -> str:
    header = ",".join(cm.REQUIRED_COLUMNS)
    rows = [
        "B0-arm,T,V,https://example.org/a,,class,guarantee,limitation,no,UNAVAILABLE_NOT_RUN,"
        '"Strong comparator because the mechanism differs on the isolated boundary."',
        "B1-arm,T,V,https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM,"
        '"Strong comparator with runnable upstream code pinned at a verified revision."',
        "B2-arm,T,V,https://example.org/c,,class,guarantee,limitation,no,UNAVAILABLE_NOT_RUN,"
        '"Strong comparator retained as an anchor for the boundary surface."',
    ]
    return "\n".join([header, *rows]) + "\n"


def _mutate(control: str, old: str, new: str) -> str:
    assert old in control, "ACNS_PRIOR_CONTROL_MUTATION_MISS"
    return control.replace(old, new, 1)


def test_adversarial_fabricated_comparator_id_fails() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    bad = _mutate(_good_control_csv(), "B2-arm", "totally-made-up-rats-paper")
    result = cm.validate_matrix(bad, known_registry_ids=known)
    assert result.ok is False, "ACNS_PRIOR_FABRICATED_ID_UNEXPECTEDLY_PASSED"
    assert "UNKNOWN_COMPARATOR_ID" in result.reason_codes, (
        f"ACNS_PRIOR_FABRICATED_ID_CODES:{result.reason_codes}"
    )


def test_adversarial_missing_source_link_fails() -> None:
    bad = _mutate(_good_control_csv(), "https://example.org/c", "")
    result = cm.validate_matrix(bad)
    assert result.ok is False, "ACNS_PRIOR_MISSING_LINK_UNEXPECTEDLY_PASSED"
    assert "MISSING_SOURCE_LINK" in result.reason_codes, (
        f"ACNS_PRIOR_MISSING_LINK_CODES:{result.reason_codes}"
    )


def test_adversarial_thin_mechanism_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "Strong comparator retained as an anchor for the boundary surface.",
        "weak",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "ACNS_PRIOR_THIN_MECH_UNEXPECTEDLY_PASSED"
    assert "MECHANISM_ANALYSIS_MISSING" in result.reason_codes, (
        f"ACNS_PRIOR_THIN_MECH_CODES:{result.reason_codes}"
    )


def test_adversarial_available_code_yes_without_url_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
        ",,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "ACNS_PRIOR_CODE_WITHOUT_URL_UNEXPECTEDLY_PASSED"
    assert "AVAILABLE_CODE_WITHOUT_URL" in result.reason_codes, (
        f"ACNS_PRIOR_CODE_WITHOUT_URL_CODES:{result.reason_codes}"
    )


def test_adversarial_upstream_without_code_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "limitation,yes,ORIGINAL_UPSTREAM",
        "limitation,no,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "ACNS_PRIOR_UPSTREAM_WITHOUT_CODE_UNEXPECTEDLY_PASSED"
    assert "UPSTREAM_WITHOUT_CODE" in result.reason_codes, (
        f"ACNS_PRIOR_UPSTREAM_WITHOUT_CODE_CODES:{result.reason_codes}"
    )
