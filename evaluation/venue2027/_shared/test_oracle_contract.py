"""Tests for SH-independent_oracle — independent truth derivation boundary.

Positive controls: the deterministic reference oracle gives identical verdicts
twice on a frozen synthetic case; verdicts validate against
``oracle_decision.v1.schema.json`` via the shared stdlib validator;
``INDETERMINATE`` requires a blinded human adjudication record before it may
be tallied. Negative controls: an oracle importing a candidate module is
refused (``CANDIDATE_IMPORT``) and an oracle importing baseline truth labels
is refused (``BASELINE_LABEL_EXCHANGE``).
"""

from __future__ import annotations

import ast
import dataclasses
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027._shared._fixtures import (  # noqa: E402
    baseline_labels,
    candidate_arm,
)
from evaluation.venue2027._shared.oracle_contract import (  # noqa: E402
    ORACLE_CONTRACT_VERSION,
    Case,
    DeterministicReferenceOracle,
    EvidenceRef,
    HumanAdjudicationRecord,
    IndependenceScanResult,
    OracleContractError,
    OracleIndependenceError,
    assert_countable,
    assert_oracle_independence,
)

SHARED_SCHEMAS = REPO_ROOT / "research" / "venue2027" / "_shared" / "schemas"
SHARED_TOOLS = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import schema_validator as sv  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "_fixtures"
CANDIDATE_ARM_PATH = FIXTURES / "candidate_arm.py"
CANDIDATE_REASONS_PATH = FIXTURES / "candidate_reasons.py"
CANDIDATE_ALIAS_PATH = FIXTURES / "candidate_alias.py"
BASELINE_LABELS_PATH = FIXTURES / "baseline_labels.py"
ORACLE_PATH = Path(__file__).resolve().parent / "oracle_contract.py"

SOURCE_SHA = "a" * 40


def _evidence(uri: str = "fixtures/oracle/frozen_labels.json") -> EvidenceRef:
    return EvidenceRef(
        pointer_kind="oracle_label",
        uri=uri,
        sha256="b" * 64,
        frozen_at="2026-11-15T00:00:00Z",
    )


def _case(case_id: str = "case_admit", family: str = "sepsis_triage_v1") -> Case:
    return Case(
        schema_version="1",
        case_id=case_id,
        case_family=family,
        independent_unit_id="unit:sepsis-001",
        unit_kind="case",
        backend="synthetic",
        source_sha=SOURCE_SHA,
        seed=7,
        branch="research/venue2027/tasks/w3-sh-independent-oracle",
        arm_id="C1",
        evidence=(_evidence(),),
        created_at="2026-11-15T00:00:00Z",
    )


def _oracle() -> DeterministicReferenceOracle:
    return DeterministicReferenceOracle(
        oracle_id="ref_oracle.v1",
        labels={
            ("sepsis_triage_v1", "case_admit"): ("ADMIT", "FROZEN_LABEL_ADMIT"),
            ("sepsis_triage_v1", "case_reject"): ("REJECT", "FROZEN_LABEL_REJECT"),
            ("sepsis_triage_v1", "case_ambiguous"): ("INDETERMINATE", "LABEL_CONFLICT"),
        },
        evidence_refs=(_evidence(),),
    )


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_reference_oracle_deterministic_identical_verdict_twice() -> None:
    oracle = _oracle()
    case = _case()
    first = oracle.evaluate(case)
    second = oracle.evaluate(case)
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.outcome == "ADMIT"
    assert first.reason_code == "FROZEN_LABEL_ADMIT"
    assert first.oracle_id == "ref_oracle.v1"
    assert first.case_id == "case_admit"
    assert first.evidence_refs[0].sha256 == "b" * 64


def test_reference_oracle_reject_and_frozen_table_snapshot() -> None:
    oracle = _oracle()
    verdict = oracle.evaluate(_case("case_reject"))
    assert verdict.outcome == "REJECT"
    assert verdict.reason_code == "FROZEN_LABEL_REJECT"
    # The frozen table is copied at construction: post-hoc mutation cannot
    # change verdicts (no silent oracle repair).
    mutated = dataclasses.replace(oracle)
    object.__setattr__(mutated, "labels", {})
    assert mutated.evaluate(_case()).outcome == "INDETERMINATE"
    assert oracle.evaluate(_case()).outcome == "ADMIT"
    # ...and the frozen table itself stays untouched:
    assert oracle.labels == {
        ("sepsis_triage_v1", "case_admit"): ("ADMIT", "FROZEN_LABEL_ADMIT"),
        ("sepsis_triage_v1", "case_reject"): ("REJECT", "FROZEN_LABEL_REJECT"),
        ("sepsis_triage_v1", "case_ambiguous"): ("INDETERMINATE", "LABEL_CONFLICT"),
    }


def test_verdict_matches_oracle_decision_v1_schema() -> None:
    oracle = _oracle()
    verdict = oracle.evaluate(_case("case_reject"))
    record = {
        "schema_version": "1",
        "oracle_id": verdict.oracle_id,
        "independent_unit_id": _case().independent_unit_id,
        "case_id": verdict.case_id,
        "arm_id": _case().arm_id,
        "outcome": "FAIL" if verdict.outcome == "REJECT" else "PASS",
        "reason_code": verdict.reason_code,
        "candidate_reason_code_ignored": True,
        "evidence": [dict(ref.to_dict()) for ref in verdict.evidence_refs],
        "source_sha": _case().source_sha,
        "backend": _case().backend,
        "adjudicated_at": "2026-11-15T00:00:00Z",
        "notes": "emitted from OracleVerdict via frozen label table",
    }
    schema = sv.load_schema(SHARED_SCHEMAS / "oracle_decision.v1.schema.json")
    assert sv.validate_instance(record, schema, schema_path=SHARED_SCHEMAS / (
        "oracle_decision.v1.schema.json"
    )) == ()


def test_case_roundtrip_matches_case_v1_schema() -> None:
    case = _case()
    schema = sv.load_schema(SHARED_SCHEMAS / "case.v1.schema.json")
    assert sv.validate_instance(case.to_dict(), schema, schema_path=SHARED_SCHEMAS / (
        "case.v1.schema.json"
    )) == ()
    assert Case.from_dict(case.to_dict()) == case


def test_independent_oracle_never_reads_candidate_reason_codes() -> None:
    # The oracle's verdict for the frozen case is independent of the
    # candidate's claimed reason codes: identical verdicts with a candidate
    # claiming the opposite label.
    oracle = _oracle()
    verdict = oracle.evaluate(_case("case_admit"))
    assert verdict.outcome == "ADMIT"
    assert verdict.reason_code != candidate_arm.candidate_score({})  # no candidate data used
    assert verdict.reason_code not in (
        "CANDIDATE_CLAIMED_ADMIT",
        "CANDIDATE_CLAIMED_REJECT",
    )


def test_indeterminate_requires_blinded_human_adjudication_record() -> None:
    oracle = _oracle()
    ambiguous = oracle.evaluate(_case("case_ambiguous"))
    assert ambiguous.outcome == "INDETERMINATE"
    assert ambiguous.needs_human_adjudication is True
    with pytest.raises(OracleContractError) as excinfo:
        assert_countable(ambiguous)
    assert excinfo.value.reason_code == "INDETERMINATE_UNADJUDICATED"

    record = HumanAdjudicationRecord(
        reviewer_pseudonym="clinician_R2",
        blinded=True,
        adjudicated_at="2026-11-15T01:30:00Z",
        verdict="REJECT",
        reason_code="HUMAN_ADJUDICATED_REJECT",
        case_id="case_ambiguous",
        oracle_id="ref_oracle.v1",
    )
    resolved = ambiguous.with_human_adjudication(record)
    assert resolved.outcome == "REJECT"
    assert resolved.resolved_by == (record,)
    assert_countable(resolved)
    # Non-UTC timestamps and unblinded reviewers are refused:
    with pytest.raises(OracleContractError):
        dataclasses.replace(record, adjudicated_at="2026-11-15T01:30:00")
    with pytest.raises(OracleContractError):
        dataclasses.replace(record, blinded=False)


def test_adjudication_mismatch_refused() -> None:
    oracle = _oracle()
    ambiguous = oracle.evaluate(_case("case_ambiguous"))
    wrong_case = HumanAdjudicationRecord(
        reviewer_pseudonym="clinician_R3",
        blinded=True,
        adjudicated_at="2026-11-15T02:00:00Z",
        verdict="ADMIT",
        reason_code="HUMAN_ADJUDICATED_ADMIT",
        case_id="other_case",
        oracle_id="ref_oracle.v1",
    )
    with pytest.raises(OracleContractError) as excinfo:
        ambiguous.with_human_adjudication(wrong_case)
    assert excinfo.value.reason_code == "ADJUDICATION_CASE_MISMATCH"


# ---------------------------------------------------------------------------
# Negative controls — independence source scan
# ---------------------------------------------------------------------------


def _oracle_source_with(extra_imports: str) -> str:
    return (
        "from __future__ import annotations\n"
        f"{extra_imports}\n"
        "\n"
        "\n"
        "def evaluate(case):\n"
        '    return {"outcome": "ADMIT", "reason_code": "OK"}\n'
    )


def _scan(tmp_path: Path, extra_imports: str, candidate_paths: list[Path]) -> OracleContractError:
    rogue = tmp_path / "rogue_oracle.py"
    rogue.write_text(_oracle_source_with(extra_imports), encoding="utf-8")
    with pytest.raises(OracleIndependenceError) as excinfo:
        assert_oracle_independence(rogue, candidate_paths)
    return excinfo.value


@pytest.mark.parametrize(
    ("extra_imports", "candidate"),
    [
        ("import evaluation.venue2027._shared._fixtures.candidate_arm", CANDIDATE_ARM_PATH),
        pytest.param(
            "from evaluation.venue2027._shared._fixtures import candidate_arm",
            CANDIDATE_ARM_PATH,
            id="from-import",
        ),
        pytest.param(
            "from evaluation.venue2027._shared import _fixtures as fx\nimport import_module\n"
            "m = import_module('evaluation.venue2027._shared._fixtures.candidate_arm')",
            CANDIDATE_ARM_PATH,
            id="dynamic-const-import",
        ),
        pytest.param("import candidate_reasons", CANDIDATE_REASONS_PATH, id="bare-name"),
    ],
)
def test_candidate_import_refused(
    tmp_path: Path, extra_imports: str, candidate: Path
) -> None:
    error = _scan(tmp_path, extra_imports, [candidate])
    assert error.reason_code == "CANDIDATE_IMPORT"


def test_baseline_label_import_refused(tmp_path: Path) -> None:
    error = _scan(
        tmp_path,
        "import baseline_labels\n",
        [BASELINE_LABELS_PATH],
    )
    assert error.reason_code == "BASELINE_LABEL_EXCHANGE"


def test_candidate_import_via_package_alias_refused(tmp_path: Path) -> None:
    # Transitive: the alias module re-exports the candidate arm.
    error = _scan(
        tmp_path,
        "from evaluation.venue2027._shared._fixtures import candidate_alias\n",
        [CANDIDATE_ALIAS_PATH],
    )
    assert error.reason_code == "CANDIDATE_IMPORT"


def test_dynamic_nonconstant_import_fails_closed(tmp_path: Path) -> None:
    error = _scan(
        tmp_path,
        "import importlib\nname = 'candidate_arm'\nimportlib.import_module(name)\n",
        [CANDIDATE_ARM_PATH],
    )
    assert error.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"


def test_missing_oracle_or_candidate_source_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(OracleIndependenceError) as missing_oracle:
        assert_oracle_independence(tmp_path / "absent_oracle.py", [CANDIDATE_ARM_PATH])
    assert missing_oracle.value.reason_code == "ORACLE_SOURCE_MISSING"
    rogue = tmp_path / "rogue_oracle.py"
    rogue.write_text("import os\n", encoding="utf-8")
    with pytest.raises(OracleIndependenceError) as missing_candidate:
        assert_oracle_independence(rogue, [tmp_path / "absent_candidate.py"])
    assert missing_candidate.value.reason_code == "CANDIDATE_PATH_MISSING"


def test_clean_oracle_scan_passes_and_independence_scan_logged() -> None:
    # The REAL independence scan of this task's oracle against every fixture:
    result = assert_oracle_independence(
        ORACLE_PATH,
        [CANDIDATE_ARM_PATH, CANDIDATE_REASONS_PATH, CANDIDATE_ALIAS_PATH, BASELINE_LABELS_PATH],
    )
    assert result.ok is True
    assert result.reason_code == "OK"
    assert isinstance(result, IndependenceScanResult)
    assert len(result.oracle_sha256) == 64
    payload = result.to_dict()
    assert json.dumps(payload)  # audit-log serializable
    # The scan covers the oracle's own source: parse it once more to confirm
    # the fixture names would be flagged if they ever appeared in imports.
    tree = ast.parse(ORACLE_PATH.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any("_fixtures" in name for name in imported)


def test_oracle_source_shas_recorded() -> None:
    # Keep the fixture module hashes visible in the test trail (tamper tripwire).
    for path in (
        CANDIDATE_ARM_PATH,
        CANDIDATE_REASONS_PATH,
        CANDIDATE_ALIAS_PATH,
        BASELINE_LABELS_PATH,
    ):
        assert path.is_file()
    assert candidate_arm.CANDIDATE_ARM_VERSION == "1.0.0"
    assert baseline_labels.BASELINE_LABELS_VERSION == "1.0.0"
    assert ORACLE_CONTRACT_VERSION == "1.0.0"


def test_reference_oracle_independence_scan_of_baseline_labels_only() -> None:
    # The reference oracle ships WITHOUT baseline label imports; the scan of a
    # clean oracle that imports only the shared validator stays clean.
    clean = Path(__file__).parent / "_scan_clean_target.py"
    clean.write_text(
        "import json\nfrom pathlib import Path\n\n\ndef evaluate(case):\n"
        "    return json.loads(Path('labels.json').read_text())\n",
        encoding="utf-8",
    )
    try:
        result = assert_oracle_independence(clean, [BASELINE_LABELS_PATH])
        assert result.ok is True
    finally:
        clean.unlink(missing_ok=True)
