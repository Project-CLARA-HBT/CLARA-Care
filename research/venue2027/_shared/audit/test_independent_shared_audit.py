"""Independent adversarial audit of the venue2027 shared toolchain.

Written by AUDIT-shared_toolchain, an independent verifier with no manifest
task of its own. Every probe here is NEW (not derived from
``_shared/tests/*``) and attempts to DEFEAT a guard. Each probe asserts the
guard's CURRENT behaviour; probes marked RESIDUAL-RISK document a confirmed
defeat without being allowed to fail the suite (per audit instructions: keep
the suite green, mark the defect in SHARED_TOOLCHAIN_INDEPENDENT_AUDIT.md and
set status=FAIL in AUDIT-shared_toolchain.json).

Confirmed defeats at audit time (commit 7ebdbbf0):
  F1 agent_protocol   — artifact hash bound via ``..`` escape is satisfied by a
                        repo-external file (evidence fabrication).
  F2 agent_protocol   — command ``exit_code: false`` bool-bypasses the
                        zero-exit check (False == 0 int comparison).
  F3 agent_protocol   — PASS accepted with command ``log_path`` pointing at a
                        nonexistent file (assertions without logs are supposed
                        to be rejected).
  F4 worktree_policy  — ``research/venue2027/../../services/...`` passes
                        assert_writable and can be LOCK-CLAIMED for a
                        production path.
  F5 worktree_policy  — ``path/./x.py`` bypasses an existing lock (lock-key
                        identity is pre-normalization).
  F6 claim_overlap    — archive reuse with case/whitespace variants
                        (``E15_E22_FROZEN``, `` e15_e22_frozen ``) evades the
                        salami/archive BLOCK.
  F7 literature_ledger— docstring contract "VERIFIED_BASELINE without a code
                        URL yields ok=False (VERIFIED_WITHOUT_CODE)" is NOT
                        implemented; verify_sources returns ok=True.
  F8 source_reference_map — verified anchors containing ``..`` are resolved
                        outside the repo root and reported VERIFIED_EXISTING.

Guards that held under attack (asserted REFUSED below): empty commands,
absent exit_code, foreign sha (incl. ``deadbeef``), swapped artifact hashes,
dependency-not-completed, task mismatch, protected GLHS paths, duplicate path
claims, dot-segment lock split (documented), clinical-claim flag, PHI without
verifiable synthesis, non-synthetic provenance, missing license, identical
normalized question+endpoint, exact archive reuse, dirty worktree, missing
anchor, no-HEAD, non-git dir, no log-dir escape for the R4 trace.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

AUDIT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = AUDIT_DIR.parents[3]
TOOLS_DIR = AUDIT_DIR.parent / "tools"
PROOF_DIR = REPO_ROOT / "research/venue2027/proof"
sys.path.insert(0, str(TOOLS_DIR))

import agent_protocol as ap  # noqa: E402
import claim_overlap as co  # noqa: E402
import literature_ledger as ll  # noqa: E402
import repo_fingerprint as rf  # noqa: E402
import research_ethics as re_  # noqa: E402
import source_reference_map as srm  # noqa: E402
import worktree_policy as wp  # noqa: E402


# --------------------------------------------------------------------- helpers
def _git(repo: pathlib.Path, *argv: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), *argv], check=True, capture_output=True, text=True
    )
    return res.stdout.strip()


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "audit@example.com")
    _git(r, "config", "user.name", "Independent Auditor")
    (r / "artifact.txt").write_text("evidence\n", encoding="utf-8")
    (r / "audit.log").write_text("collected 1 item\n1 passed\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    return r


@pytest.fixture()
def head(repo: pathlib.Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def anchored_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Git repo containing all 8 REQUIRED_ANCHOR_FILES, clean tree."""
    r = tmp_path / "anchored"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "audit@example.com")
    _git(r, "config", "user.name", "Independent Auditor")
    for rel in rf.REQUIRED_ANCHOR_FILES:
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "anchors")
    return r


def _report(head: str, digest: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "task_id": "T",
        "status": "PASS",
        "source_sha_before": head,
        "source_sha_after": head,
        "changed_paths": ["artifact.txt"],
        "commands": [{"argv": "pytest -q", "exit_code": 0, "log_path": "audit.log"}],
        "artifacts_sha256": {"artifact.txt": digest},
        "unresolved": [],
    }
    base.update(overrides)
    return base


# ----------------------------------------------------- agent_protocol: refused
def test_ap_pass_with_empty_commands_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), commands=[]), repo=repo
    )
    assert r.ok is False
    assert r.reason_code == "NO_COMMANDS"


def test_ap_pass_with_missing_exit_code_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), commands=[{"argv": "pytest"}]),
        repo=repo,
    )
    assert r.ok is False
    assert r.reason_code == "NONZERO_EXIT"


def test_ap_pass_with_foreign_source_sha_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), source_sha_after="deadbeef"),
        repo=repo,
    )
    assert r.ok is False
    assert r.reason_code == "SHA_NOT_IN_REPO"


def test_ap_pass_with_swapped_artifact_hash_refused(
    head: str, repo: pathlib.Path
) -> None:
    r = ap.validate_report(
        _report(head, "f" * 64), repo=repo
    )
    assert r.ok is False
    assert r.reason_code == "ARTIFACT_HASH_MISMATCH"


def test_ap_pass_with_missing_artifact_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), artifacts_sha256={"ghost.txt": "0" * 64}),
        repo=repo,
    )
    assert r.ok is False
    assert r.reason_code == "ARTIFACT_MISSING"


def test_ap_dependency_not_completed_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt")),
        repo=repo,
        task_dependencies=["SH-upstream"],
        completed_tasks=["SH-unrelated"],
    )
    assert r.ok is False
    assert r.reason_code == "DEPENDENCIES_UNSATISFIED"


def test_ap_task_mismatch_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), task_id="SH-someone_else"),
        repo=repo,
        expected_task_id="T",
    )
    assert r.ok is False
    assert r.reason_code == "TASK_MISMATCH"


def test_ap_invalid_status_refused(head: str, repo: pathlib.Path) -> None:
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), status="SUPER_PASS"),
        repo=repo,
    )
    assert r.ok is False
    assert r.reason_code == "SCHEMA_INVALID"


# --------------------------- agent_protocol: CONFIRMED DEFEATS (residual risk)
def test_f1_ap_artifact_hash_path_escape_defeats_hash_binding(
    head: str, repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """CONFIRMED DEFEAT: hash binding is satisfied by a repo-external file.

    A report may declare ``../outside.txt`` inside artifacts_sha256; the
    validator resolves it against the repo root without confinement, so an
    agent can bind "evidence" to any file on the host filesystem.
    """
    outside = tmp_path / "outside.txt"
    outside.write_text("fabricated evidence\n", encoding="utf-8")
    r = ap.validate_report(
        _report(head, _sha256(outside), artifacts_sha256={"../outside.txt": _sha256(outside)}),
        repo=repo,
    )
    # FIXED: repo-external artifact paths are now refused.
    assert r.ok is False
    assert r.reason_code in ("ARTIFACT_MISSING", "ARTIFACT_HASH_MISMATCH")


def test_f2_ap_exit_code_boolean_false_bypasses_zero_exit_check(
    head: str, repo: pathlib.Path
) -> None:
    """CONFIRMED DEFEAT: ``exit_code: false`` passes because False == 0."""
    r = ap.validate_report(
        _report(
            head,
            _sha256(repo / "artifact.txt"),
            commands=[{"argv": "pytest -q (fabricated green)", "exit_code": False}],
        ),
        repo=repo,
    )
    # FIXED: bool is no longer accepted as an exit code.
    assert r.ok is False
    assert r.reason_code == "NONZERO_EXIT"


def test_f2b_ap_exit_code_string_refused(head: str, repo: pathlib.Path) -> None:
    """Type confusion must not extend to plain strings (this direction holds)."""
    r = ap.validate_report(
        _report(head, _sha256(repo / "artifact.txt"), commands=[{"argv": "x", "exit_code": "0"}]),
        repo=repo,
    )
    assert r.ok is False
    assert r.reason_code == "NONZERO_EXIT"


def test_f3_ap_pass_with_nonexistent_log_path_accepted(head: str, repo: pathlib.Path) -> None:
    """CONFIRMED DEFEAT: module docstring says "Assertions without logs are
    rejected", but a PASS whose only command claims a nonexistent log passes.
    """
    r = ap.validate_report(
        _report(
            head,
            _sha256(repo / "artifact.txt"),
            commands=[
                {"argv": "pytest -q", "exit_code": 0, "log_path": "logs/never_written.log"}
            ],
        ),
        repo=repo,
    )
    # FIXED: a PASS whose command log is absent is refused.
    assert r.ok is False
    assert r.reason_code == "MISSING_LOG"


# ---------------------------------------------------- worktree_policy: refused
def test_wp_protected_glhs_path_refused() -> None:
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.assert_writable(["services/api/src/clara_api/glhs/admission.py"])
    assert exc.value.reason_code == "PROTECTED_PATH"


def test_wp_protected_db_models_refused() -> None:
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.assert_writable(["services/api/src/clara_api/db/models.py"])
    assert exc.value.reason_code == "PROTECTED_PATH"


def test_wp_outside_research_tree_refused() -> None:
    for path in ("services/api/pyproject.toml", "/etc/passwd", "../README.md"):
        with pytest.raises(wp.WorktreePolicyError) as exc:
            wp.assert_writable([path])
        assert exc.value.reason_code == "OUTSIDE_RESEARCH_TREE"


def test_wp_same_path_claimed_by_two_agents_conflict() -> None:
    registry = wp.PathLockRegistry()
    registry.claim("agent-A", ["research/venue2027/compsac/x.py"])
    with pytest.raises(wp.LockConflict):
        registry.claim("agent-B", ["research/venue2027/compsac/x.py"])


def test_wp_same_path_two_registries_are_independent() -> None:
    """Documented residual risk, not a defeat: PathLockRegistry is in-memory,
    so two agent *processes* each hold their own registry and can both 'claim'
    the same path. Cross-process exclusivity must come from real git worktrees
    (git itself refuses a duplicate worktree/branch), not from this class.
    """
    reg_a = wp.PathLockRegistry()
    reg_b = wp.PathLockRegistry()
    reg_a.claim("agent-A", ["research/venue2027/compsac/x.py"])
    reg_b.claim("agent-B", ["research/venue2027/compsac/x.py"])
    assert reg_a.holders() != reg_b.holders()


def test_wp_shared_prefix_single_owner() -> None:
    registry = wp.PathLockRegistry()
    registry.claim("agent-A", ["research/venue2027/_shared/a.json"])
    with pytest.raises(wp.LockConflict):
        registry.claim("agent-B", ["research/venue2027/_shared/b.json"])


def test_wp_invalid_slug_refused() -> None:
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.allocate_worktree("compsac; rm -rf /", "T1")
    assert exc.value.reason_code == "INVALID_SLUG"


# ---------------------------- worktree_policy: CONFIRMED DEFEATS (residual risk)
def test_f4_wp_parent_traversal_claims_protected_path() -> None:
    """CONFIRMED DEFEAT: ``research/venue2027/../../services/...`` passes the
    research-prefix check AND is claimable in the lock registry, so an agent
    can reserve a production path under a research-shaped name.
    """
    prod = "research/venue2027/../../services/api/src/clara_api/db/models.py"
    # FIXED: traversal to a protected path is refused before any lock is taken.
    with pytest.raises(wp.WorktreePolicyError) as exc:
        wp.assert_writable([prod])
    assert exc.value.reason_code in ("PROTECTED_PATH", "OUTSIDE_RESEARCH_TREE")
    registry = wp.PathLockRegistry()
    with pytest.raises(wp.WorktreePolicyError):
        registry.claim("rogue-agent", [prod])
    assert not registry.holders()


def test_f5_wp_dot_segment_lock_split_documented() -> None:
    """CONFIRMED DEFEAT (cosmetic severity): ``dir/./x.py`` bypasses an
    existing lock on ``dir/x.py`` because lock keys are built BEFORE
    normalization. A second agent can double-claim the same file.
    """
    registry = wp.PathLockRegistry()
    registry.claim("agent-A", ["research/venue2027/compsac/x.py"])
    # FIXED: dot-segment variants normalize to the same lock key.
    with pytest.raises(wp.LockConflict):
        registry.claim("agent-B", ["research/venue2027/compsac/./x.py"])
    assert len(registry.holders()) == 1


# ------------------------------------------------------- research_ethics gates
def test_ethics_clinical_claim_allowed_refused() -> None:
    d = re_.DatasetDeclaration(
        dataset_id="d",
        provenance="generated_synthetic",
        license="internal",
        synthetic_verifiable=True,
        clinical_claim_allowed=True,
    )
    v = re_.check_data_policy(d)
    assert v.ok is False
    assert "CLINICAL_CLAIM_FROM_SYNTHETIC_DATA" in v.reason_codes


def test_ethics_phi_fields_without_verifiable_synthesis_refused() -> None:
    for prov in ("generated_synthetic", "deterministic_fixture", "public_deidentified_benchmark"):
        d = re_.DatasetDeclaration(
            dataset_id="d",
            provenance=prov,
            license="internal",
            phi_fields=("mrn", "email"),
            synthetic_verifiable=False,
        )
        v = re_.check_data_policy(d)
        assert v.ok is False, prov
        assert v.reason_codes, prov


def test_ethics_non_synthetic_provenance_refused() -> None:
    d = re_.DatasetDeclaration(
        dataset_id="d", provenance="hospital_export", license="internal"
    )
    v = re_.check_data_policy(d)
    assert v.ok is False
    assert "NON_SYNTHETIC_PROVENANCE" in v.reason_codes


def test_ethics_case_variant_provenance_refused() -> None:
    d = re_.DatasetDeclaration(
        dataset_id="d", provenance="Generated_Synthetic", license="internal"
    )
    assert re_.check_data_policy(d).ok is False


def test_ethics_missing_license_refused() -> None:
    d = re_.DatasetDeclaration(
        dataset_id="d", provenance="generated_synthetic", license=""
    )
    v = re_.check_data_policy(d)
    assert v.ok is False
    assert "MISSING_LICENSE" in v.reason_codes


def test_ethics_provider_gate_refused_without_ack() -> None:
    d = re_.DatasetDeclaration(
        dataset_id="d", provenance="generated_synthetic", license="internal"
    )
    v = re_.check_provider_use(d)
    assert v.ok is False
    assert "PROVIDER_TERMS_NOT_ACKNOWLEDGED" in v.reason_codes


def test_ethics_real_phi_provenance_is_not_a_license_to_write_phi() -> None:
    """A dataset can never become writable by toggling flags on real data."""
    d = re_.DatasetDeclaration(
        dataset_id="d",
        provenance="hospital_export",
        license="internal",
        phi_fields=("name",),
        synthetic_verifiable=True,
        provider_terms_acknowledged=True,
    )
    v = re_.check_data_policy(d)
    assert v.ok is False
    assert "NON_SYNTHETIC_PROVENANCE" in v.reason_codes


# ------------------------------------------------------------- claim_overlap
def test_co_identical_normalized_question_and_endpoint_blocked() -> None:
    a = co.StudyClaim(
        study="a", research_question="  Does   X beat Y?  ", primary_endpoint="AUROC@95",
        dataset="d1", baselines=(),
    )
    b = co.StudyClaim(
        study="b", research_question="does x beat y?", primary_endpoint="auroc@95",
        dataset="d2", baselines=(),
    )
    r = co.audit_overlap([a, b])
    assert r.ok is False
    assert any(f.reason_code == "SALAMI_SAME_QUESTION_AND_ENDPOINT" for f in r.findings)


def test_co_exact_archive_reuse_blocked() -> None:
    claim = co.StudyClaim(
        study="a", research_question="Q", primary_endpoint="ep", dataset="d",
        baselines=(), reuses_archive=("e15_e22_frozen",),
    )
    r = co.audit_overlap([claim])
    assert r.ok is False
    assert r.findings[0].reason_code == "ARCHIVE_REUSE_AS_NEW"


# ------------------------------ claim_overlap: CONFIRMED DEFEAT (residual risk)
@pytest.mark.parametrize(
    "variant", ["E15_E22_FROZEN", " e15_e22_frozen ", "e15_e22_frozen_v2"]
)
def test_f6_co_archive_name_variant_evasion(variant: str) -> None:
    """CONFIRMED DEFEAT: archive reuse is matched by exact string equality, so
    case/whitespace/suffix variants of a frozen archive evade the BLOCK.
    """
    claim = co.StudyClaim(
        study="a", research_question="Q", primary_endpoint="ep", dataset="d",
        baselines=(), reuses_archive=(variant,),
    )
    r = co.audit_overlap([claim])
    # FIXED: canonicalized archive ids detect all case/whitespace/suffix variants.
    assert r.ok is False
    assert any(f.reason_code == "ARCHIVE_REUSE_AS_NEW" for f in r.findings)


# ----------------------------------------------------------- literature_ledger
def test_ll_reproduced_without_code_refused() -> None:
    rec = ll.LiteratureRecord(
        id="x", title="T", venue="V", doi_or_url="https://x", reproduced=True
    )
    r = ll.verify_sources([rec])
    assert r.ok is False
    assert r.violations


def test_ll_missing_doi_refused() -> None:
    rec = ll.LiteratureRecord(id="x", title="T", venue="V", doi_or_url="")
    r = ll.verify_sources([rec])
    assert r.ok is False


def test_ll_unread_source_is_unverified() -> None:
    rec = ll.LiteratureRecord(id="x", title="T", venue="V", doi_or_url="https://x")
    r = ll.verify_sources([rec])
    assert r.counts[ll.UNVERIFIED] == 1
    assert r.counts[ll.VERIFIED_BASELINE] == 0


# -------------------------- literature_ledger: CONFIRMED DEFEAT (residual risk)
def test_f7_ll_documented_verified_without_code_gate_is_not_implemented() -> None:
    """CONFIRMED DEFEAT: the module docstring promises "Any record marked
    VERIFIED_BASELINE without a code URL yields ok=False with
    reason_code=VERIFIED_WITHOUT_CODE". No such check exists; a record with a
    primary_source_read=True and NO code_url classifies as
    PRIMARY_READ_CODE_ABSENT and verify_sources still returns ok=True.
    """
    rec = ll.LiteratureRecord(
        id="x", title="T", venue="V", doi_or_url="https://x", primary_source_read=True,
        code_url="", claims_verified_baseline=True,
    )
    r = ll.verify_sources([rec])
    # FIXED: an explicit runnable-baseline claim without code fails closed.
    assert r.ok is False
    assert any("VERIFIED_BASELINE" in v for v in r.violations)

    # Reading a source with no public code is NOT an error; it is honest absence.
    honest = ll.LiteratureRecord(
        id="y", title="T", venue="V", doi_or_url="https://x", primary_source_read=True,
        code_url="",
    )
    r2 = ll.verify_sources([honest])
    assert r2.counts[ll.PRIMARY_READ_CODE_ABSENT] == 1
    assert r2.ok is True


def test_f7b_ll_whitespace_code_url_counts_as_runnable_code() -> None:
    """Same defect family: a whitespace-only code_url yields VERIFIED_BASELINE."""
    rec = ll.LiteratureRecord(
        id="x", title="T", venue="V", doi_or_url="https://x", primary_source_read=True,
        code_url="   ",
    )
    r = ll.verify_sources([rec])
    # FIXED: whitespace-only code URL is not runnable code.
    assert r.counts[ll.VERIFIED_BASELINE] == 0
    assert r.counts[ll.PRIMARY_READ_CODE_ABSENT] == 1


# ------------------------------------------------------- source_reference_map
def test_srm_verified_but_absent_anchor_is_missing_required(tmp_path: pathlib.Path) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text("[]", encoding="utf-8")
    verified = tmp_path / "verified.json"
    verified.write_text('{"paths":{"gone.py":"anchor"}}', encoding="utf-8")
    r = srm.map_source(tmp_path, tasks_path=tasks, verified_path=verified)
    assert r.ok is False
    assert r.reason_code == "MISSING_REQUIRED"
    assert "gone.py" in r.missing_verified


def test_srm_existing_and_proposed_classification(tmp_path: pathlib.Path) -> None:
    (tmp_path / "exists.py").write_text("x=1\n", encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(
        '[{"id":"T","venue":"v","phase":"P00","files":["exists.py","new.py"]}]',
        encoding="utf-8",
    )
    verified = tmp_path / "verified.json"
    verified.write_text('{"paths":{"exists.py":"anchor"}}', encoding="utf-8")
    r = srm.map_source(tmp_path, tasks_path=tasks, verified_path=verified)
    assert r.ok is True
    classes = {row.path: row.classification for row in r.rows}
    assert classes["exists.py"] == "VERIFIED_EXISTING"
    assert classes["new.py"] == "NEW_PROPOSED"


# ------------------------ source_reference_map: CONFIRMED DEFEAT (residual risk)
def test_f8_srm_parent_traversal_resolves_outside_repo(tmp_path: pathlib.Path) -> None:
    """CONFIRMED DEFEAT: a verified anchor declared as ``../outside.txt`` is
    resolved against the repo root without confinement, so a file OUTSIDE the
    repo counts as VERIFIED_EXISTING and ok=True.
    """
    outside = tmp_path.parent / f"outside_{abs(hash(str(tmp_path))) % 10**8}.txt"
    outside.write_text("external\n", encoding="utf-8")
    try:
        tasks = tmp_path / "tasks.json"
        tasks.write_text("[]", encoding="utf-8")
        verified = tmp_path / "verified.json"
        verified.write_text(
            json.dumps({"paths": {f"../{outside.name}": "anchor"}}), encoding="utf-8"
        )
        r = srm.map_source(tmp_path, tasks_path=tasks, verified_path=verified)
        # FIXED: a path escaping the repo root is never VERIFIED_EXISTING.
        row = next(row for row in r.rows if outside.name in row.path)
        assert row.classification == "MISSING_REQUIRED"
        assert r.ok is False
    finally:
        outside.unlink(missing_ok=True)


# ----------------------------------------------------------- repo_fingerprint
def test_rf_dirty_worktree_refused(anchored_repo: pathlib.Path) -> None:
    (anchored_repo / "services/api/src/clara_api/glhs/admission.py").write_text(
        "# dirty\n", encoding="utf-8"
    )
    fp = rf.snapshot(anchored_repo)
    assert fp.ok is False
    assert fp.reason_code == "DIRTY_WORKTREE"


def test_rf_dirty_tree_is_not_papered_over_by_missing_anchor_check(
    anchored_repo: pathlib.Path,
) -> None:
    """Dirty + missing anchors must yield DIRTY_WORKTREE (ok=False) either way."""
    (anchored_repo / "services/api/src/clara_api/glhs/admission.py").unlink()
    fp = rf.snapshot(anchored_repo)
    assert fp.ok is False
    assert fp.reason_code in {"DIRTY_WORKTREE", "MISSING_REQUIRED_FILE"}
    assert fp.missing_required_files  # the missing anchor is still reported


def test_rf_missing_required_anchor_refused(tmp_path: pathlib.Path) -> None:
    """Repo with commits but ZERO anchor files must be refused."""
    r = tmp_path / "plain"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "a@b.c")
    _git(r, "config", "user.name", "T")
    (r / "readme.md").write_text("hi\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    fp = rf.snapshot(r)
    assert fp.ok is False
    assert fp.reason_code == "MISSING_REQUIRED_FILE"
    assert len(fp.missing_required_files) == len(rf.REQUIRED_ANCHOR_FILES)


def test_rf_no_head_refused(tmp_path: pathlib.Path) -> None:
    r = tmp_path / "empty"
    r.mkdir()
    _git(r, "init", "-q")
    fp = rf.snapshot(r)
    assert fp.ok is False
    assert fp.reason_code == "NO_HEAD"


def test_rf_not_a_git_repo_refused(tmp_path: pathlib.Path) -> None:
    fp = rf.snapshot(tmp_path)
    assert fp.ok is False
    assert fp.reason_code == "NOT_A_GIT_REPO"


def test_rf_digest_is_deterministic(anchored_repo: pathlib.Path) -> None:
    a = rf.snapshot(anchored_repo)
    b = rf.snapshot(anchored_repo)
    assert a.ok and b.ok
    assert a.content_sha256 == b.content_sha256
    assert a.head_sha == b.head_sha


def test_rf_write_roundtrip(anchored_repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    fp = rf.snapshot(anchored_repo)
    dest = tmp_path / "out" / "fp.json"
    rf.write_fingerprint(fp, dest)
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["content_sha256"] == fp.content_sha256


# ------------------------------------------------------------------ r4 regression
def test_r4_trace_reproduced_is_backed_by_log_with_immutability_reason() -> None:
    """The trace JSON claims ``reproduced=true``; independently re-derive that
    verdict from the raw pytest log it points at (never trust the JSON).
    """
    trace_path = AUDIT_DIR.parent / "r4_regression_trace.json"
    assert trace_path.is_file(), "r4_regression_trace.json missing"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert trace["reproduced"] is True
    assert trace["reason_code"] == "INCIDENT_REPRODUCED"

    log_path = REPO_ROOT / trace["log_path"]
    assert log_path.is_file(), f"log referenced by trace missing: {log_path}"
    log_text = log_path.read_text(encoding="utf-8", errors="ignore")

    # The immutability reason must actually appear in the raw log.
    assert "GLHS ledger rows are immutable; append a governed transition" in log_text

    # Re-parse the failure signature from the log (mirrors r4_regression regex).
    import re

    observed = set(
        m.group(2)
        for m in re.finditer(
            r"^(FAILED|ERROR) (tests/[^\s:]+::[^\s]+)", log_text, re.MULTILINE
        )
    )
    expected = set(trace["failed_tests"])
    assert observed == expected, f"log failures {observed} != trace {expected}"

    # Suite totals in the trace must match the log's summary line.
    m = re.search(r"(\d+) failed, (\d+) passed", log_text)
    assert m, "log has no 'N failed, N passed' summary line"
    assert int(m.group(1)) == trace["failed_count"]
    assert int(m.group(2)) == trace["passed_count"]

    # The reported exit code (pytest failure => nonzero) must be consistent.
    assert trace["exit_code"] == 1


def test_r4_expected_failing_ids_are_exactly_the_documented_incident() -> None:
    sys.path.insert(0, str(TOOLS_DIR))
    import r4_regression as r4

    assert set(r4.EXPECTED_FAILING_TESTS) == {
        "tests/test_glhs_r4_admission.py::test_full_valid_grwc_admission",
        "tests/test_glhs_r4_comparators.py::test_benchmark_decision_concordance_schedule_matrix",
        "tests/test_glhs_current_state_insufficiency.py::test_penicillin_allergy_current_state_insufficiency_witness",
        "tests/test_glhs_grwc_lineage.py::test_full_valid_review_chain",
    }
    # The listener must still raise the documented reason at the anchor site.
    models = REPO_ROOT / "services/api/src/clara_api/db/models.py"
    assert models.is_file()
    assert r4.INCIDENT_REASON in models.read_text(encoding="utf-8", errors="ignore")


# ------------------------------------------------- proof reports re-validation
def test_proof_reports_revalidate_today() -> None:
    """The two prior proof reports must still validate against THIS checkout
    (artifact hashes + source SHAs), proving they were not fabricated.
    """
    for task_id in ("SH-repo_fingerprint", "SH-agent_protocol"):
        report_path = PROOF_DIR / f"{task_id}.json"
        assert report_path.is_file(), report_path
        report = json.loads(report_path.read_text(encoding="utf-8"))
        r = ap.validate_report(report, repo=REPO_ROOT, expected_task_id=task_id)
        assert r.ok is True, f"{task_id}: {r.reason_code} {r.errors}"


def test_reproduce_r4_helper_refuses_forged_log(tmp_path: pathlib.Path) -> None:
    """Adversarial control on the reproducer's parse: a log that lacks the
    exact documented immutability reason (or misses an expected failing id)
    must NOT count as reproduced. We drive reproduce_r4's parsing helpers
    directly on synthetic outputs instead of running the full R4 suite.
    """
    sys.path.insert(0, str(TOOLS_DIR))
    import r4_regression as r4

    # Forged log: right failing ids, WRONG reason string.
    forged = "\n".join(
        f"FAILED {t} - ValueError: something else" for t in r4.EXPECTED_FAILING_TESTS
    )
    forged += "\n4 failed, 57 passed in 1.00s\n"
    failed, passed, failed_count, _ = r4._parse_failures(forged)
    assert set(failed) == set(r4.EXPECTED_FAILING_TESTS)
    reason_observed = r4.INCIDENT_REASON in forged
    reproduced = bool(
        r4.EXPECTED_FAILING_TESTS
        and not (set(failed) - set(r4.EXPECTED_FAILING_TESTS))
        and not (set(r4.EXPECTED_FAILING_TESTS) - set(failed))
        and reason_observed
    )
    assert reproduced is False  # forged reason => not reproduced

    # Forged log #2: right reason, one expected failure missing.
    partial = "\n".join(
        f"FAILED {t} - ValueError: {r4.INCIDENT_REASON}"
        for t in r4.EXPECTED_FAILING_TESTS[:-1]
    )
    failed2, _, _, _ = r4._parse_failures(partial)
    missing = set(r4.EXPECTED_FAILING_TESTS) - set(failed2)
    assert missing  # incompleteness must be detected, never filled in
