"""Structural gate for DSN-prior (literature_matrix.csv).

Purpose
-------
Machine-checks task ``DSN-prior`` (venue ``dsn``, phase ``P01``) against the
deliverable contract: ``research/venue2027/dsn/literature_matrix.csv`` must be
a valid comparator matrix under the SHARED validator
``research/venue2027/_shared/tools/comparator_matrix.py`` (imported, not
reimplemented), and must additionally carry the crash-consistency framing the
DSN novelty contract and blueprint fix:

- the **strong-baseline arms** of the blueprint as B-prefixed rows:
  B0 single-write transactional commit with fire-and-forget side effect
  (weak control), B1 PostgreSQL atomic write + transactional outbox +
  idempotent consumer (mandatory strong practical baseline), B2 durable
  workflow/saga with compensation and stable operation IDs (strong
  operational baseline), B3/fsync-durability reference and the ARIES
  write-ahead-log recovery reference, plus the two journal arms: candidate
  B4 reconciliation safety journal and internal control B5 monotonic
  single journal;
- the **registry comparators** named by the novelty contract claim table:
  ``elle20`` (independent black-box history oracle), ``silo13``
  (single-store serializable CC boundary), ``ct9162`` (append-only log
  integrity is not reconciliation);
- **tri-state recoverability framing (the contribution class)**: the
  recoverable-outcome function returns COMMITTED, REJECTED, or INDETERMINATE
  across the *joint* clinical row + decision receipt + side-effect record.
  The tests assert the framing language and the pre-registered falsification
  rule (a fully engineered B1/B2 at equal invariants and cost withdraws the
  superiority claim), that no row asserts an observed empirical value, and
  that the matrix consumes no frozen E15-E22 archive, no COMPSAC contention
  results and no IFIP replay evidence (cross-study firewall).

Adversarial controls (executed against the shared validator, not copies of
it): an unknown/fabricated comparator id, a missing source link, a thin
``mechanism_analysis``, an ``available_code=yes`` row without ``code_url``,
an ``ORIGINAL_UPSTREAM`` row without code, and a ``FAITHFUL_PORT`` row
without ``code_url`` must all fail loudly with the shared validator's stable
reason codes - citing a nonexistent implementation must never pass silently.

Allowed input
-------------
Read-only access to the matrix CSV, ``MANIFESTS/literature_registry.json``,
``_shared/baselines/registry.yaml``, the DSN novelty contract and in-memory
CSV strings used as positive/adversarial controls for the shared validator.
No network, no database, no provider calls, no randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``DSN_PRIOR_``; pytest reports the failing check directly. The shared
validator itself is never modified by these tests.

Version
-------
``DSN_PRIOR_TEST_VERSION = "1.0.0"``
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

DSN_PRIOR_TEST_VERSION = "1.0.0"

DSN_DIR = pathlib.Path(__file__).resolve().parents[1]
MATRIX = DSN_DIR / "literature_matrix.csv"
NOVELTY_CONTRACT = DSN_DIR / "novelty_contract.md"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

# Registry comparators that MUST appear as real registry rows.
REQUIRED_REGISTRY_IDS = (
    "ct9162",  # append-only log integrity is not reconciliation
    "elle20",  # independent black-box transaction-history oracle
    "silo13",  # single-store serializable CC boundary (no joint semantics)
)

# Blueprint arms + journal candidate/control arms that MUST appear as B rows.
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B4-", "B5-")

# Shared-baseline-registry arm entries backing the B-prefixed rows.
REQUIRED_ARM_REGISTRY_NAMES = (
    "db-transaction-fire-and-forget",  # B0
    "postgres-outbox-idempotent-consumer",  # B1
    "durable-workflow-saga-compensation",  # B2
)


def _load_matrix_text() -> str:
    assert MATRIX.is_file(), f"DSN_PRIOR_MISSING_MATRIX: {MATRIX}"
    return MATRIX.read_text(encoding="utf-8")


def _load_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(_load_matrix_text())))
    for index, row in enumerate(rows, start=2):
        missing = [c for c in cm.REQUIRED_COLUMNS if row.get(c) is None]
        assert not missing, f"DSN_PRIOR_ROW_{index}_MISSING_VALUES:{missing}"
    return rows


def _literature_registry() -> dict[str, object]:
    assert LITERATURE_REGISTRY.is_file(), f"DSN_PRIOR_MISSING_REGISTRY: {LITERATURE_REGISTRY}"
    payload = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "DSN_PRIOR_REGISTRY_SHAPE"
    return payload


def _baseline_registry_names() -> set[str]:
    assert BASELINE_REGISTRY.is_file(), f"DSN_PRIOR_MISSING_BASELINE_REGISTRY: {BASELINE_REGISTRY}"
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
    assert result.ok, f"DSN_PRIOR_VALIDATOR_FAILED: {result.to_dict()}"
    assert result.reason_codes == (), "DSN_PRIOR_REASON_CODES_NONEMPTY"
    assert result.violations == (), "DSN_PRIOR_VIOLATIONS_NONEMPTY"
    assert result.row_count >= 8, f"DSN_PRIOR_TOO_FEW_ROWS: {result.row_count}"


def test_matrix_carries_exactly_the_required_columns() -> None:
    reader = csv.DictReader(io.StringIO(_load_matrix_text()))
    columns = tuple(reader.fieldnames or ())
    assert columns == cm.REQUIRED_COLUMNS, f"DSN_PRIOR_COLUMNS_MISMATCH: {columns}"


def test_required_registry_ids_present() -> None:
    ids = {row["comparator_id"] for row in _load_rows()}
    for lit_id in REQUIRED_REGISTRY_IDS:
        assert lit_id in ids, f"DSN_PRIOR_MISSING_LITERATURE_ROW:{lit_id}"


def test_all_blueprint_and_journal_arms_present() -> None:
    ids = [row["comparator_id"] for row in _load_rows()]
    for prefix in REQUIRED_ARM_PREFIXES:
        assert any(cid.startswith(prefix) for cid in ids), f"DSN_PRIOR_MISSING_ARM:{prefix}"


def test_wal_and_fsync_reference_rows_present() -> None:
    ids = {row["comparator_id"] for row in _load_rows()}
    wal_rows = [cid for cid in ids if "aries" in cid.lower() or "wal" in cid.lower()]
    fsync_rows = [cid for cid in ids if "fsync" in cid.lower() or "durability" in cid.lower()]
    assert wal_rows, "DSN_PRIOR_WAL_REFERENCE_ABSENT"
    assert fsync_rows, "DSN_PRIOR_FSYNC_REFERENCE_ABSENT"


def test_comparator_ids_are_registry_ids_or_b_arms() -> None:
    literature = set(_literature_registry().keys())
    for row_ in _load_rows():
        cid = row_["comparator_id"]
        assert cid in literature or cid.startswith("B"), f"DSN_PRIOR_FABRICATED_COMPARATOR_ID:{cid}"


def test_arm_rows_map_to_shared_baseline_registry_entries() -> None:
    registry_names = _baseline_registry_names()
    for arm_name in REQUIRED_ARM_REGISTRY_NAMES:
        assert arm_name in registry_names, f"DSN_PRIOR_REGISTRY_ANCHOR_MISSING:{arm_name}"


def test_registry_rows_cite_their_registered_locator() -> None:
    registry = _literature_registry()
    for row_ in _load_rows():
        entry = registry.get(row_["comparator_id"])
        if not isinstance(entry, dict):
            continue
        registered = str(entry.get("url", "")).strip()
        cited = row_["doi_or_url"].strip()
        assert (
            cited == registered
        ), f"DSN_PRIOR_LOCATOR_MISMATCH:{row_['comparator_id']}:{cited!r}!={registered!r}"


def test_every_row_has_mechanism_analysis() -> None:
    for row_ in _load_rows():
        analysis = (row_["mechanism_analysis"] or "").strip()
        assert (
            len(analysis) >= cm.MIN_MECHANISM_CHARS
        ), f"DSN_PRIOR_THIN_MECHANISM:{row_['comparator_id']}"


def test_no_row_labeled_weak_without_mechanism_reasoning() -> None:
    for row_ in _load_rows():
        text = (row_["mechanism_analysis"] or "").lower()
        assert (
            "strong" in text or "candidate" in text or "anchor" in text or "control" in text
        ), f"DSN_PRIOR_WEAK_LABEL_WITHOUT_MECHANISM:{row_['comparator_id']}"


def test_available_code_yes_rows_cite_verified_upstream_code() -> None:
    for row_ in _load_rows():
        if row_["available_code"] == "yes":
            url = row_["code_url"].strip()
            assert url.startswith(
                ("http://", "https://")
            ), f"DSN_PRIOR_AVAILABLE_WITHOUT_URL:{row_['comparator_id']}"
            assert (
                row_["fidelity_status"] == "ORIGINAL_UPSTREAM"
            ), f"DSN_PRIOR_YES_NOT_ORIGINAL_UPSTREAM:{row_['comparator_id']}"


def test_unavailable_baselines_are_marked_not_run() -> None:
    for row_ in _load_rows():
        if row_["available_code"] == "UNAVAILABLE":
            assert (
                row_["fidelity_status"] == "UNAVAILABLE_NOT_RUN"
            ), f"DSN_PRIOR_UNAVAILABLE_NOT_MARKED_NOT_RUN:{row_['comparator_id']}"


def test_arm_rows_do_not_claim_original_upstream_without_external_code() -> None:
    # In-project blueprint arms (B0/B4/B5) point at this repository; they must
    # never be dressed up as runnable upstream comparators. This invariant is
    # about CSV claims, not about whether any package directory happens to
    # exist in a given checkout (later DSN tasks legitimately create
    # evaluation/venue2027/dsn), so assert on the rows only.
    for row_ in _load_rows():
        cid = row_["comparator_id"]
        if cid.startswith(("B0-", "B4-", "B5-")):
            assert (
                row_["available_code"] != "yes"
            ), f"DSN_PRIOR_IN_PROJECT_ARM_CLAIMS_RUNNABLE:{cid}"
            assert (
                row_["fidelity_status"] == "UNAVAILABLE_NOT_RUN"
            ), f"DSN_PRIOR_IN_PROJECT_ARM_NOT_MARKED_NOT_RUN:{cid}"


# ---------------------------------------------------------------------------
# Crash-consistency framing: joint tri-state recoverability, not a new toy.
# ---------------------------------------------------------------------------


def test_joint_tri_state_framing_language_present_in_matrix() -> None:
    text = _load_matrix_text().lower()
    for required in (
        "committed",
        "rejected",
        "indeterminate",
        "joint",
        "crash window",
        "falsif",
    ):
        assert required in text, f"DSN_PRIOR_TRI_STATE_FRAMING_MISSING:{required}"


def test_matrix_declares_hypothesis_not_measured_superiority() -> None:
    # The candidate must be phrased as a claim under test; observed outcomes
    # enter only via artifacts/venue2027/dsn/<run_id>/manifest.json later.
    text = _load_matrix_text().lower()
    assert "candidate" in text, "DSN_PRIOR_CANDIDATE_LANGUAGE_ABSENT"
    for forbidden in (
        "we introduce a new mechanism that outperforms",
        "state-of-the-art recovery",
        "beats all baselines",
        "proven superior",
    ):
        assert forbidden not in text, f"DSN_PRIOR_MECHANISM_CLAIM_FOUND:{forbidden}"


def test_candidate_arm_declared_falsifiable_not_superior() -> None:
    candidate = [r for r in _load_rows() if r["comparator_id"].startswith("B4-")]
    assert len(candidate) == 1, "DSN_PRIOR_CANDIDATE_ARM_COUNT"
    row_ = candidate[0]
    assert row_["available_code"] != "yes", (
        "DSN_PRIOR_CANDIDATE_CLAIMS_AVAILABLE_CODE: candidate must not be "
        "presented as a runnable external comparator"
    )
    text = (row_["mechanism_analysis"] + " " + row_["supported_guarantee"]).lower()
    assert "falsif" in text, "DSN_PRIOR_CANDIDATE_NOT_FALSIFIABLE"
    assert "candidate" in text, "DSN_PRIOR_CANDIDATE_NOT_LABELLED"
    for forbidden in ("superior to", "outperforms", "beats"):
        assert forbidden not in text, f"DSN_PRIOR_CANDIDATE_SUPERIORITY_CLAIM:{forbidden}"


def test_strong_baselines_declared_mandatory_not_stubbed() -> None:
    # Novelty contract C2: B1 is a mandatory full implementation under equal
    # budget; the matrix must record it as runnable upstream, never as a stub.
    b1 = [r for r in _load_rows() if r["comparator_id"].startswith("B1-")]
    assert len(b1) == 1, "DSN_PRIOR_B1_ARM_COUNT"
    assert b1[0]["available_code"] == "yes", "DSN_PRIOR_B1_NOT_RUNNABLE_UPSTREAM"
    assert b1[0]["fidelity_status"] == "ORIGINAL_UPSTREAM", "DSN_PRIOR_B1_NOT_ORIGINAL_UPSTREAM"
    text = _load_matrix_text().lower()
    assert "equal budget" in text, "DSN_PRIOR_EQUAL_BUDGET_CLAUSE_ABSENT"


def test_oracle_independence_recorded() -> None:
    # The Elle oracle row must record that the oracle side is independent of
    # the candidate implementation (blueprint independence rule).
    elle = [r for r in _load_rows() if r["comparator_id"] == "elle20"]
    assert len(elle) == 1, "DSN_PRIOR_ELLE_ROW_COUNT"
    text = (elle[0]["mechanism_analysis"] + " " + elle[0]["limitations_vs_candidate"]).lower()
    assert "oracle" in text, "DSN_PRIOR_ELLE_NOT_ORACLE"
    assert (
        "not reuse candidate code" in text or "independent" in text
    ), "DSN_PRIOR_ELLE_INDEPENDENCE_NOT_RECORDED"


def test_pinned_upstream_revisions_recorded_for_runnable_arms() -> None:
    for row_ in _load_rows():
        if row_["available_code"] == "yes":
            combined = row_["supported_guarantee"] + " " + row_["mechanism_analysis"]
            assert any(
                tok in combined for tok in ("commit", "tag", "revision", "pinned")
            ), f"DSN_PRIOR_NO_PINNED_REVISION:{row_['comparator_id']}"


def test_no_empirical_values_asserted_in_matrix() -> None:
    # Design-time ledger: no observed violation counts, no RTO percentiles, no
    # measured fsync costs - outcomes enter only via run manifests later.
    text = _load_matrix_text()
    for forbidden in ("rto p99 =", "p99 =", "violations observed =", "measured at "):
        assert forbidden not in text.lower(), f"DSN_PRIOR_EMPIRICAL_VALUE_ASSERTED:{forbidden}"
    import re

    assert not re.search(
        r"\b\d+\.\d+\s*(ms|us|μs|percent|%)\b", text
    ), "DSN_PRIOR_NUMERIC_RESULT_FOUND"


def test_cross_study_firewall_declared() -> None:
    # Per DSN-overlap: the study consumes no frozen E15-E22 archive, no
    # COMPSAC contention results and no IFIP replay evidence, and the journal
    # arm must never be presented as evidence for a sibling study.
    candidate = [r for r in _load_rows() if r["comparator_id"].startswith("B4-")]
    assert candidate, "DSN_PRIOR_CANDIDATE_ARM_ABSENT"
    text = (candidate[0]["mechanism_analysis"]).lower()
    for required in ("e15-e22", "compsac", "ifip"):
        assert required in text, f"DSN_PRIOR_FIREWALL_CLAUSE_MISSING:{required}"


def test_governing_contract_keeps_go_declaration() -> None:
    # The standing declarations live in the DSN novelty contract; this ledger
    # must not silently drift away from them.
    assert NOVELTY_CONTRACT.is_file(), f"DSN_PRIOR_CONTRACT_MISSING: {NOVELTY_CONTRACT}"
    lowered = NOVELTY_CONTRACT.read_text(encoding="utf-8").lower()
    assert "decision: go" in lowered, "DSN_PRIOR_CONTRACT_GO_DECLARATION_ABSENT"
    assert "reconciliation safety journal" in lowered, "DSN_PRIOR_CONTRACT_JOURNAL_ABSENT"
    assert "indeterminate" in lowered, "DSN_PRIOR_CONTRACT_TRI_STATE_ABSENT"
    assert "48 crash windows" in lowered, "DSN_PRIOR_CONTRACT_FAULT_DESIGN_ABSENT"


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
        '"Strong comparator retained as a control for the recovery surface."',
    ]
    return "\n".join([header, *rows]) + "\n"


def _mutate(control: str, old: str, new: str) -> str:
    assert old in control, "DSN_PRIOR_CONTROL_MUTATION_MISS"
    return control.replace(old, new, 1)


def test_adversarial_fabricated_comparator_id_fails() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    bad = _mutate(_good_control_csv(), "B2-arm", "totally-made-up-aries-paper")
    result = cm.validate_matrix(bad, known_registry_ids=known)
    assert result.ok is False, "DSN_PRIOR_FABRICATED_ID_UNEXPECTEDLY_PASSED"
    assert (
        "UNKNOWN_COMPARATOR_ID" in result.reason_codes
    ), f"DSN_PRIOR_FABRICATED_ID_CODES:{result.reason_codes}"


def test_adversarial_missing_source_link_fails() -> None:
    bad = _mutate(_good_control_csv(), "https://example.org/c", "")
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DSN_PRIOR_MISSING_LINK_UNEXPECTEDLY_PASSED"
    assert (
        "MISSING_SOURCE_LINK" in result.reason_codes
    ), f"DSN_PRIOR_MISSING_LINK_CODES:{result.reason_codes}"


def test_adversarial_thin_mechanism_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "Strong comparator retained as a control for the recovery surface.",
        "weak",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DSN_PRIOR_THIN_MECH_UNEXPECTEDLY_PASSED"
    assert (
        "MECHANISM_ANALYSIS_MISSING" in result.reason_codes
    ), f"DSN_PRIOR_THIN_MECH_CODES:{result.reason_codes}"


def test_adversarial_available_code_yes_without_url_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "https://example.org/b,,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
        ",,class,guarantee,limitation,yes,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DSN_PRIOR_CODE_WITHOUT_URL_UNEXPECTEDLY_PASSED"
    assert (
        "AVAILABLE_CODE_WITHOUT_URL" in result.reason_codes
    ), f"DSN_PRIOR_CODE_WITHOUT_URL_CODES:{result.reason_codes}"


def test_adversarial_upstream_without_code_fails() -> None:
    bad = _mutate(
        _good_control_csv(),
        "limitation,yes,ORIGINAL_UPSTREAM",
        "limitation,no,ORIGINAL_UPSTREAM",
    )
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DSN_PRIOR_UPSTREAM_WITHOUT_CODE_UNEXPECTEDLY_PASSED"
    assert (
        "UPSTREAM_WITHOUT_CODE" in result.reason_codes
    ), f"DSN_PRIOR_UPSTREAM_WITHOUT_CODE_CODES:{result.reason_codes}"


def test_adversarial_faithful_port_without_code_url_fails() -> None:
    # Build a control matrix via the csv writer so quoting is canonical, then
    # declare a FAITHFUL_PORT row whose code_url is stripped: the shared
    # validator must refuse it with PORT_WITHOUT_CODE.
    import io as _io

    buf = _io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(cm.REQUIRED_COLUMNS)
    writer.writerow(
        [
            "B1-port",
            "T",
            "V",
            "https://example.org/b",
            "https://example.org/port",
            "class",
            "guarantee",
            "limitation",
            "yes",
            "FAITHFUL_PORT",
            "Strong comparator with a port pinned at a verified revision for fidelity review.",
        ]
    )
    writer.writerow(
        [
            "B2-arm",
            "T",
            "V",
            "https://example.org/c",
            "",
            "class",
            "guarantee",
            "limitation",
            "no",
            "UNAVAILABLE_NOT_RUN",
            "Strong comparator retained as a control for the recovery surface.",
        ]
    )
    writer.writerow(
        [
            "B0-arm",
            "T",
            "V",
            "https://example.org/a",
            "",
            "class",
            "guarantee",
            "limitation",
            "no",
            "UNAVAILABLE_NOT_RUN",
            "Strong comparator because the mechanism differs on the isolated boundary.",
        ]
    )
    control = buf.getvalue()
    bad = _mutate(control, ",https://example.org/port,", ",,")
    result = cm.validate_matrix(bad)
    assert result.ok is False, "DSN_PRIOR_PORT_WITHOUT_CODE_UNEXPECTEDLY_PASSED"
    assert (
        "PORT_WITHOUT_CODE" in result.reason_codes
    ), f"DSN_PRIOR_PORT_WITHOUT_CODE_CODES:{result.reason_codes}"
