"""Tests for the remaining SH P00/P01 shared tools.

Each tool is exercised with positive controls and adversarial controls that must
be refused (never silently treated as a clean/passing result).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import claim_overlap as co  # noqa: E402
import literature_ledger as ll  # noqa: E402
import research_ethics as re_  # noqa: E402
import source_reference_map as srm  # noqa: E402
import worktree_policy as wp  # noqa: E402


# ---------------------------------------------------------------- worktree policy
def test_allocate_worktree_is_deterministic() -> None:
    a = wp.allocate_worktree("compsac", "COMPSAC-oracle")
    b = wp.allocate_worktree("compsac", "COMPSAC-oracle")
    assert a.path == b.path
    assert a.branch == "research/venue2027/compsac/compsac-oracle"


def test_allocate_worktree_rejects_unsafe_slug() -> None:
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.allocate_worktree("compsac; rm -rf /", "x")
    assert exc.value.reason_code == "INVALID_SLUG"


def test_protected_path_refused() -> None:
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.assert_writable(["services/api/src/clara_api/glhs/admission.py"])
    assert exc.value.reason_code == "PROTECTED_PATH"


def test_outside_research_tree_refused() -> None:
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.assert_writable(["services/api/pyproject.toml"])
    assert exc.value.reason_code == "OUTSIDE_RESEARCH_TREE"


def test_concurrent_same_path_locks_conflict() -> None:
    registry = wp.PathLockRegistry()
    registry.claim("A01", ["research/venue2027/compsac/x.py"])
    with pytest.raises(wp.LockConflict):
        registry.claim("A02", ["research/venue2027/compsac/x.py"])
    registry.release("A01")
    registry.claim("A02", ["research/venue2027/compsac/x.py"])


def test_shared_prefix_lock_is_exclusive() -> None:
    registry = wp.PathLockRegistry()
    registry.claim("A01", ["research/venue2027/_shared/a.json"])
    with pytest.raises(wp.LockConflict):
        registry.claim("A02", ["research/venue2027/_shared/b.json"])


# -------------------------------------------------------------- source reference map
def test_source_map_classifies(tmp_path: pathlib.Path) -> None:
    (tmp_path / "exists.py").write_text("x=1\n", encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(
        '[{"id":"T","venue":"v","phase":"P00","files":["exists.py","new.py"],"signature":"f()"}]',
        encoding="utf-8",
    )
    verified = tmp_path / "verified.json"
    verified.write_text('{"paths":{"exists.py":"anchor"}}', encoding="utf-8")
    result = srm.map_source(tmp_path, tasks_path=tasks, verified_path=verified)
    assert result.ok is True
    classes = {(r.path, r.classification) for r in result.rows}
    assert ("exists.py", srm.VERIFIED_EXISTING) in classes
    assert ("new.py", srm.NEW_PROPOSED) in classes


def test_source_map_flags_missing_verified_anchor(tmp_path: pathlib.Path) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text("[]", encoding="utf-8")
    verified = tmp_path / "verified.json"
    verified.write_text('{"paths":{"gone.py":"anchor"}}', encoding="utf-8")
    result = srm.map_source(tmp_path, tasks_path=tasks, verified_path=verified)
    assert result.ok is False
    assert result.reason_code == "MISSING_REQUIRED"
    assert "gone.py" in result.missing_verified


# ------------------------------------------------------------------ claim overlap
def _claim(study: str, rq: str, ep: str) -> co.StudyClaim:
    return co.StudyClaim(
        study=study, research_question=rq, primary_endpoint=ep, dataset="d", baselines=()
    )


def test_distinct_studies_pass() -> None:
    claims = [_claim("a", "Q1?", "ep1"), _claim("b", "Q2?", "ep2")]
    assert co.audit_overlap(claims).ok is True


def test_same_question_and_endpoint_blocked() -> None:
    claims = [_claim("a", "Same Q?", "same ep"), _claim("b", " same q? ", "SAME EP")]
    result = co.audit_overlap(claims)
    assert result.ok is False
    assert any(f.reason_code == "SALAMI_SAME_QUESTION_AND_ENDPOINT" for f in result.findings)


def test_archive_reuse_as_new_blocked() -> None:
    claim = co.StudyClaim(
        study="a",
        research_question="Q?",
        primary_endpoint="ep",
        dataset="d",
        baselines=(),
        reuses_archive=("e15_e22_frozen",),
    )
    result = co.audit_overlap([claim])
    assert result.ok is False
    assert result.findings[0].reason_code == "ARCHIVE_REUSE_AS_NEW"


# --------------------------------------------------------------- literature ledger
def test_literature_verified_requires_code() -> None:
    rec = ll.LiteratureRecord(
        id="x", title="T", venue="V", doi_or_url="https://x", primary_source_read=True
    )
    result = ll.verify_sources([rec])
    assert result.counts[ll.PRIMARY_READ_CODE_ABSENT] == 1


def test_literature_unread_is_unverified() -> None:
    rec = ll.LiteratureRecord(id="x", title="T", venue="V", doi_or_url="https://x")
    result = ll.verify_sources([rec])
    assert result.counts[ll.UNVERIFIED] == 1


def test_literature_reproduced_without_code_violates() -> None:
    rec = ll.LiteratureRecord(
        id="x", title="T", venue="V", doi_or_url="https://x", reproduced=True
    )
    result = ll.verify_sources([rec])
    assert result.ok is False


def test_literature_missing_doi_violates() -> None:
    rec = ll.LiteratureRecord(id="x", title="T", venue="V", doi_or_url="")
    result = ll.verify_sources([rec])
    assert result.ok is False


# ------------------------------------------------------------------ research ethics
def _ds(**kw: object) -> re_.DatasetDeclaration:
    base = dict(
        dataset_id="d",
        provenance="generated_synthetic",
        license="internal",
        synthetic_verifiable=True,
    )
    base.update(kw)
    return re_.DatasetDeclaration(**base)  # type: ignore[arg-type]


def test_synthetic_dataset_passes() -> None:
    assert re_.check_data_policy(_ds()).ok is True


def test_real_patient_provenance_blocked() -> None:
    result = re_.check_data_policy(_ds(provenance="hospital_export"))
    assert result.ok is False
    assert "NON_SYNTHETIC_PROVENANCE" in result.reason_codes


def test_missing_license_blocked() -> None:
    result = re_.check_data_policy(_ds(license=""))
    assert result.ok is False


def test_phi_fields_require_verifiable_synthesis() -> None:
    result = re_.check_data_policy(
        _ds(phi_fields=("email",), synthetic_verifiable=False)
    )
    assert result.ok is False


def test_clinical_claim_from_synthetic_blocked() -> None:
    result = re_.check_data_policy(_ds(clinical_claim_allowed=True))
    assert result.ok is False
    assert "CLINICAL_CLAIM_FROM_SYNTHETIC_DATA" in result.reason_codes

def test_provider_terms_required() -> None:
    assert re_.check_provider_use(_ds()).ok is False
    assert re_.check_provider_use(_ds(provider_terms_acknowledged=True)).ok is True


# ------------------------------------------------------------------ threat model
import threat_model as tm  # noqa: E402


def _pair_rows() -> str:
    return "\n".join(
        f"| {f} | paired | a | c | clean: ok | adversarial: x | reject |"
        for f in tm.ATTACK_FAMILIES
    )


def _good_threat() -> str:
    return (
        "# Threat\n"
        "## Attacker and observer capabilities\nCAP\n"
        "## Trusted components\nTC\n"
        "## Excluded domains\nED\n"
        "## Attack family and control matrix\n"
        + _pair_rows()
        + "\n## Oracle and actor authority\nDefined: oracle X, actor Y.\n"
    )


def test_threat_model_complete_passes() -> None:
    assert tm.validate_threat(_good_threat()).ok is True


def test_threat_model_missing_section_refused() -> None:
    result = tm.validate_threat("# Threat\n## Attacker and observer capabilities\nx\n")
    assert result.ok is False
    assert "MISSING_SECTION" in result.reason_codes


def test_threat_model_family_without_pair_refused() -> None:
    text = "\n".join(
        line for line in _good_threat().splitlines() if "| replay |" not in line
    )
    result = tm.validate_threat(text)
    assert result.ok is False
    assert "replay" in result.families_without_pair


def test_threat_model_render_template_is_valid() -> None:
    template = (
        "# T\n## Attacker and observer capabilities\n## Trusted components\n"
        "## Excluded domains\n## Attack family and control matrix\n"
        + tm.render_matrix_template()
        + "\n## Oracle and actor authority\nDefined.\n"
    )
    assert tm.validate_threat(template).ok is True
