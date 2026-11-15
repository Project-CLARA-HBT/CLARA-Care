"""CLARA-Care 2027 shared task SH-unified_ci: unified CI gate routing policy.

Purpose
-------
Single executable policy table mapping changed paths ("change classes") to the
CI gates that must run before the change may be merged, plus a fail-closed
auditor that refuses any policy entry referencing a workflow, script or
Makefile target that does not exist in the repository. The prose contract is
``research/venue2027/_shared/ci_policy.md``; this module is the enforced code.

Core contract (MANIFESTS/tasks.json, SH-unified_ci.signature)
------------------------------------------------------------
``choose_gate(change_set) -> Checks`` maps a change set to required/optional
gates. Never raises on bad input: every refusal is a stable ``reason_code``
carried on the returned object. A change class that can derive a research
claim (research evidence, shared research infrastructure, frozen release
data, gate configuration) is structurally routed to the full R4 gate
(secret_scan, chronology, r4_pytest, claim_lint, e22_offline) and can never
be routed to a trivial check instead; ``audit_policy`` refuses such a policy
with ``RESEARCH_CLASS_MISSING_R4_GATE``.

Allowed input
-------------
- ``change_set``: repo-relative POSIX path or iterable of them; empty/None
  allowed (no-op). Pure function: no file, clock, network or randomness.
- ``event``: one of ``pull_request | push | schedule | workflow_dispatch | tag``
  (run modes: PR contract tests, nightly light smoke, controlled dispatch for
  heavy PG/LLM runs, signed-tag-only frozen full campaign).
- ``audit_policy``: a sequence of :class:`PolicyEntry` (default: the embedded
  table built from this module's catalog) plus a repository root; existence is
  checked read-only with ``Path.is_file``.

Failure semantics (fail-closed, never a silent pass)
----------------------------------------------------
- Frozen release data (``research/glhs_journal/q4_r4/``) on auto events is
  refused with ``FROZEN_RELEASE_DATA_AUTO_RUN``; allowed only on
  ``workflow_dispatch`` or a signed release tag (which adds the release gate).
- Heavy gates on the nightly schedule are refused with
  ``HEAVY_GATE_ON_SCHEDULE`` (nightly is light smoke only).
- Unknown events fail closed with ``UNKNOWN_EVENT`` and no claimed gates.
- ``audit_policy`` refusals: ``MISSING_GATE_WORKFLOW``,
  ``MISSING_GATE_SCRIPT``, ``UNKNOWN_CHANGE_CLASS``, ``POLICY_ENTRY_INVALID``,
  ``POLICY_EMPTY``, ``RESEARCH_CLASS_MISSING_R4_GATE``.
- ``assert_r4_gate_green`` verifies the recorded R4 gate evidence
  (``research/venue2027/_shared/green_gate.json``); no research claim may be
  derived unless it reports PASS with ``R4_EVIDENCE_OK``.

Version
-------
``CI_POLICY_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from pathlib import Path

CI_POLICY_VERSION = "1.0.0"

GREEN_GATE_PATH = "research/venue2027/_shared/green_gate.json"

R4_WORKFLOW = ".github/workflows/glhs-r4-novelty-gate.yml"
CI_WORKFLOW = ".github/workflows/ci.yml"
NIGHTLY_WORKFLOW = ".github/workflows/active-eval.yml"
RELEASE_WORKFLOW = ".github/workflows/release.yml"
MOBILE_WORKFLOW = ".github/workflows/mobile-apk.yml"

R4_PYTEST_ARGV = (
    "cd services/api && DATABASE_URL=sqlite+pysqlite:////tmp/clara_gate.db "
    "AUTH_AUTO_PROVISION_USERS=true AUTH_BOOTSTRAP_ADMIN_ENABLED=true "
    "GLHS_RESEARCH_COMPARATORS_ENABLED=true PYTHONPATH=src:../ml/src:. uv run pytest -q "
    "tests/test_glhs_immutable_projection_contract.py tests/test_glhs_r4_admission.py "
    "tests/test_glhs_r4_comparators.py tests/test_glhs_comparator_policies.py "
    "tests/test_glhs_current_state_insufficiency.py tests/test_glhs_inference_envelope.py "
    "tests/test_glhs_reason_codes.py tests/test_glhs_attestation_receipts.py "
    "tests/test_inference_attestation.py tests/test_glhs_grwc_lineage.py "
    "tests/test_glhs_mandatory_thss_binding.py"
)

SECRET_SCAN_ARGV = (
    "python3 (inline GitHub Actions secret scan: FORBIDDEN_PATTERNS aura_prod_x7k9m2, "
    "sk-[a-zA-Z0-9]{32,}; walks .py/.json/.md/.csv/.yml/.yaml excluding "
    ".git/.venv/node_modules)"
)


@dataclasses.dataclass(frozen=True)
class GateCheck:
    """One concrete gate job, grounded in a real workflow (and optional script)."""

    job_id: str
    workflow: str
    job: str
    argv: str
    script: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "job_id": self.job_id,
            "workflow": self.workflow,
            "job": self.job,
            "argv": self.argv,
            "script": self.script,
        }


@dataclasses.dataclass(frozen=True)
class GateRefusal:
    reason_code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"reason_code": self.reason_code, "detail": self.detail}


@dataclasses.dataclass(frozen=True)
class PolicyEntry:
    """One policy row: a change class selects a gate job (blocking or optional)."""

    change_class: str
    job_id: str
    workflow: str
    job: str
    argv: str
    blocking: bool
    script: str | None = None


GATE_CATALOG: dict[str, GateCheck] = {
    "secret_scan": GateCheck(
        job_id="secret_scan",
        workflow=R4_WORKFLOW,
        job="secret-scan",
        argv=SECRET_SCAN_ARGV,
    ),
    "chronology": GateCheck(
        job_id="chronology",
        workflow=R4_WORKFLOW,
        job="chronology-audit",
        argv=(
            "PYTHONPATH=services/api/src:services/ml/src:. python3 "
            "research/glhs_journal/q4_r4/chronology_validator_r4.py"
        ),
        script="research/glhs_journal/q4_r4/chronology_validator_r4.py",
    ),
    "r4_pytest": GateCheck(
        job_id="r4_pytest",
        workflow=R4_WORKFLOW,
        job="r4-admission-and-comparator-tests",
        argv=R4_PYTEST_ARGV,
    ),
    "claim_lint": GateCheck(
        job_id="claim_lint",
        workflow=R4_WORKFLOW,
        job="r4-claim-lint",
        argv="python3 scripts/ci/r4_claim_lint.py",
        script="scripts/ci/r4_claim_lint.py",
    ),
    "e22_offline": GateCheck(
        job_id="e22_offline",
        workflow=R4_WORKFLOW,
        job="offline-reproducibility-sweep",
        argv="python3 reproduce_q4_r4.py",
        script="reproduce_q4_r4.py",
    ),
    "quality": GateCheck(
        job_id="quality",
        workflow=CI_WORKFLOW,
        job="quality",
        argv="bash scripts/docs/check-docs-links.sh && ruff check && mypy",
        script="scripts/docs/check-docs-links.sh",
    ),
    "scripts_syntax": GateCheck(
        job_id="scripts_syntax",
        workflow=CI_WORKFLOW,
        job="scripts-syntax",
        argv="bash -n <each scripts/**/*.sh>",
    ),
    "artifact_safety_policy": GateCheck(
        job_id="artifact_safety_policy",
        workflow=CI_WORKFLOW,
        job="artifact-safety-policy",
        argv="python3 scripts/security/check_ci_artifact_policy.py",
        script="scripts/security/check_ci_artifact_policy.py",
    ),
    "api_tests": GateCheck(
        job_id="api_tests",
        workflow=CI_WORKFLOW,
        job="api-tests",
        argv="cd services/api && uv sync --frozen --extra dev --no-editable && "
        ".venv/bin/python -m pytest -q tests",
    ),
    "ml_tests": GateCheck(
        job_id="ml_tests",
        workflow=CI_WORKFLOW,
        job="ml-tests",
        argv="cd services/ml && uv sync --frozen --extra dev --no-editable && "
        ".venv/bin/python -m pytest -q tests",
    ),
    "web_lint_build": GateCheck(
        job_id="web_lint_build",
        workflow=CI_WORKFLOW,
        job="web-lint-build",
        argv="cd apps/web && npm ci && npm run lint && npm run build",
    ),
    "web_unit_tests": GateCheck(
        job_id="web_unit_tests",
        workflow=CI_WORKFLOW,
        job="web-unit-tests",
        argv="cd apps/web && npm ci && npm run test",
    ),
    "web_e2e": GateCheck(
        job_id="web_e2e",
        workflow=CI_WORKFLOW,
        job="web-e2e",
        argv="cd apps/web && npm ci && npx playwright install --with-deps chromium "
        "&& npm run test:e2e",
    ),
    "security_audit": GateCheck(
        job_id="security_audit",
        workflow=CI_WORKFLOW,
        job="security-audit",
        argv="pip-audit --progress-spinner=off --ignore-vuln GHSA-wj6h-64fc-37mp && "
        "npm audit --omit=dev --audit-level=high && "
        "python3 scripts/ops/check_dependency_integrity.py",
        script="scripts/ops/check_dependency_integrity.py",
    ),
    "container_scan": GateCheck(
        job_id="container_scan",
        workflow=CI_WORKFLOW,
        job="container-scan",
        argv="trivy image --severity HIGH,CRITICAL --ignore-unfixed <api|ml|web>",
    ),
    "eval_smoke": GateCheck(
        job_id="eval_smoke",
        workflow=CI_WORKFLOW,
        job="clara-eval-vn-smoke",
        argv="python -m evaluation.clara_eval.run --config evaluation/configs/smoke.yaml",
        script="evaluation/clara_eval/run.py",
    ),
    "nightly_smoke": GateCheck(
        job_id="nightly_smoke",
        workflow=NIGHTLY_WORKFLOW,
        job="run-active-eval",
        argv="python -m evaluation.clara_eval.run --config evaluation/configs/nightly.yaml",
        script="evaluation/clara_eval/run.py",
    ),
    "eval_release_gate": GateCheck(
        job_id="eval_release_gate",
        workflow=RELEASE_WORKFLOW,
        job="clara-eval-release-gate",
        argv="python -m evaluation.clara_eval.run --config evaluation/configs/release.yaml",
        script="evaluation/clara_eval/run.py",
    ),
    "mobile_apk": GateCheck(
        job_id="mobile_apk",
        workflow=MOBILE_WORKFLOW,
        job="build-apk",
        argv="gradle assembleRelease (apps/mobile release APK)",
    ),
}

R4_GATE_JOB_IDS: frozenset[str] = frozenset(
    {"secret_scan", "chronology", "r4_pytest", "claim_lint", "e22_offline"}
)

CHANGE_CLASSES: frozenset[str] = frozenset(
    {
        "docs",
        "unclassified",
        "manifests",
        "production_api",
        "production_ml",
        "production_web",
        "production_mobile",
        "gate_config",
        "research_infra",
        "research_evidence",
        "frozen_release_data",
    }
)

R4_BEARING_CLASSES: frozenset[str] = frozenset(
    {"research_infra", "research_evidence", "frozen_release_data", "gate_config"}
)

CLASS_REQUIRED: dict[str, tuple[str, ...]] = {
    "docs": ("quality",),
    "unclassified": ("secret_scan",),
    "manifests": ("secret_scan", "eval_smoke"),
    "production_api": ("quality", "api_tests"),
    "production_ml": ("quality", "ml_tests"),
    "production_web": ("quality", "web_lint_build", "web_unit_tests", "web_e2e"),
    "production_mobile": ("mobile_apk",),
    "gate_config": (
        "secret_scan",
        "chronology",
        "r4_pytest",
        "claim_lint",
        "e22_offline",
        "quality",
        "scripts_syntax",
        "artifact_safety_policy",
    ),
    "research_infra": (
        "secret_scan",
        "chronology",
        "r4_pytest",
        "claim_lint",
        "e22_offline",
        "artifact_safety_policy",
    ),
    "research_evidence": (
        "secret_scan",
        "chronology",
        "r4_pytest",
        "claim_lint",
        "e22_offline",
        "artifact_safety_policy",
        "eval_smoke",
    ),
    "frozen_release_data": (
        "secret_scan",
        "chronology",
        "r4_pytest",
        "claim_lint",
        "e22_offline",
        "artifact_safety_policy",
    ),
}

CLASS_OPTIONAL: dict[str, tuple[str, ...]] = {
    "docs": (),
    "unclassified": (),
    "manifests": (),
    "production_api": ("security_audit", "container_scan"),
    "production_ml": ("security_audit", "container_scan"),
    "production_web": ("security_audit", "container_scan"),
    "production_mobile": (),
    "gate_config": ("security_audit",),
    "research_infra": ("quality",),
    "research_evidence": ("quality",),
    "frozen_release_data": (),
}

_PREFIX_RULES: tuple[tuple[str, str], ...] = (
    ("research/glhs_journal/q4_r4/", "frozen_release_data"),
    ("research/venue2027/_shared/", "research_infra"),
    (".github/workflows/", "gate_config"),
    ("scripts/ci/", "gate_config"),
    ("scripts/security/", "gate_config"),
    ("scripts/ops/", "gate_config"),
    ("scripts/docs/", "gate_config"),
    ("scripts/release/", "gate_config"),
    ("Makefile", "gate_config"),
    (".github/requirements-quality.txt", "gate_config"),
    (".github/requirements-security-audit.txt", "gate_config"),
    ("ruff.toml", "gate_config"),
    ("services/api/", "production_api"),
    ("services/ml/", "production_ml"),
    ("apps/web/", "production_web"),
    ("apps/mobile/", "production_mobile"),
    ("contracts/consumer-terminology/", "manifests"),
    ("evaluation/clara_eval/datasets/", "manifests"),
    ("research/", "research_evidence"),
    ("evaluation/", "research_evidence"),
    ("datasets/", "research_evidence"),
    ("docs/", "docs"),
)

_RUN_MODE_BY_EVENT: dict[str, str] = {
    "pull_request": "pull_request",
    "push": "push",
    "schedule": "nightly",
    "workflow_dispatch": "controlled_dispatch",
    "tag": "signed_tag_release",
}

_AUTO_EVENTS: frozenset[str] = frozenset({"pull_request", "push", "schedule"})

_NIGHTLY_ALLOWED_JOB_IDS: frozenset[str] = frozenset({"eval_smoke", "secret_scan"})


def _normalize_path(raw: object) -> str:
    text = str(raw).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _classify_path(path: str) -> str:
    for prefix, change_class in _PREFIX_RULES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return change_class
    if path.endswith(".md"):
        return "docs"
    return "unclassified"


def _classify_change_set(change_set: Sequence[str] | str | None) -> tuple[str, ...]:
    if change_set is None:
        return ()
    if isinstance(change_set, str):
        items: tuple[object, ...] = (change_set,)
    else:
        items = tuple(change_set)
    return tuple(
        sorted(
            {
                _classify_path(normalized)
                for item in items
                if (normalized := _normalize_path(item)) != ""
            }
        )
    )


def _catalog_job(job_id: str) -> GateCheck:
    return GATE_CATALOG[job_id]


@dataclasses.dataclass(frozen=True)
class Checks:
    """Result of :func:`choose_gate`; JSON-serializable via :meth:`to_dict`."""

    change_class: str
    event: str
    run_mode: str
    required_jobs: tuple[GateCheck, ...]
    optional_jobs: tuple[GateCheck, ...]
    refusals: tuple[GateRefusal, ...]

    @property
    def required_job_ids(self) -> tuple[str, ...]:
        return tuple(job.job_id for job in self.required_jobs)

    @property
    def optional_job_ids(self) -> tuple[str, ...]:
        return tuple(job.job_id for job in self.optional_jobs)

    @property
    def requires_r4_gate(self) -> bool:
        return "r4_pytest" in self.required_job_ids

    @property
    def refusal_codes(self) -> tuple[str, ...]:
        return tuple(refusal.reason_code for refusal in self.refusals)

    @property
    def ok_to_auto_run(self) -> bool:
        return not self.refusals

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_version": CI_POLICY_VERSION,
            "change_class": self.change_class,
            "event": self.event,
            "run_mode": self.run_mode,
            "requires_r4_gate": self.requires_r4_gate,
            "ok_to_auto_run": self.ok_to_auto_run,
            "required_jobs": [job.to_dict() for job in self.required_jobs],
            "optional_jobs": [job.to_dict() for job in self.optional_jobs],
            "refusals": [refusal.to_dict() for refusal in self.refusals],
        }


def choose_gate(
    change_set: Sequence[str] | str | None,
    *,
    event: str = "pull_request",
) -> Checks:
    """Map a change set to the gates that must pass for the given trigger event."""

    if event not in _RUN_MODE_BY_EVENT:
        return Checks(
            change_class="none",
            event=str(event),
            run_mode="none",
            required_jobs=(),
            optional_jobs=(),
            refusals=(
                GateRefusal(
                    "UNKNOWN_EVENT",
                    f"event {event!r} not recognized; refusing to claim any gate",
                ),
            ),
        )

    classes = _classify_change_set(change_set)
    if not classes:
        return Checks(
            change_class="none",
            event=event,
            run_mode="none",
            required_jobs=(),
            optional_jobs=(),
            refusals=(),
        )

    required_ids: list[str] = []
    optional_ids: list[str] = []
    for change_class in classes:
        for job_id in CLASS_REQUIRED[change_class]:
            if job_id not in required_ids:
                required_ids.append(job_id)
        for job_id in CLASS_OPTIONAL[change_class]:
            if job_id not in optional_ids and job_id not in required_ids:
                optional_ids.append(job_id)

    refusals: list[GateRefusal] = []
    if "frozen_release_data" in classes and event in _AUTO_EVENTS:
        refusals.append(
            GateRefusal(
                "FROZEN_RELEASE_DATA_AUTO_RUN",
                "frozen release data (research/glhs_journal/q4_r4/) changed on an auto "
                "run; a frozen heavy full campaign is allowed only on workflow_dispatch "
                "or a signed release tag",
            )
        )
    if event == "tag" and "frozen_release_data" in classes:
        if "eval_release_gate" not in required_ids:
            required_ids.append("eval_release_gate")
    if event == "schedule":
        heavy = [jid for jid in required_ids if jid not in _NIGHTLY_ALLOWED_JOB_IDS]
        if heavy:
            refusals.append(
                GateRefusal(
                    "HEAVY_GATE_ON_SCHEDULE",
                    "nightly is light smoke only "
                    f"(active-eval.yml); heavy jobs {sorted(heavy)} must run on "
                    "pull_request or controlled dispatch",
                )
            )

    required_jobs = tuple(_catalog_job(job_id) for job_id in required_ids)
    optional_jobs = tuple(
        _catalog_job(job_id) for job_id in optional_ids if job_id not in required_ids
    )
    return Checks(
        change_class="+".join(classes),
        event=event,
        run_mode=_RUN_MODE_BY_EVENT[event],
        required_jobs=required_jobs,
        optional_jobs=optional_jobs,
        refusals=tuple(refusals),
    )


def _default_policy_table() -> tuple[PolicyEntry, ...]:
    entries: list[PolicyEntry] = []
    for change_class, job_ids in CLASS_REQUIRED.items():
        for job_id in job_ids:
            gate = GATE_CATALOG[job_id]
            entries.append(
                PolicyEntry(
                    change_class=change_class,
                    job_id=gate.job_id,
                    workflow=gate.workflow,
                    job=gate.job,
                    argv=gate.argv,
                    blocking=True,
                    script=gate.script,
                )
            )
    for change_class, job_ids in CLASS_OPTIONAL.items():
        for job_id in job_ids:
            gate = GATE_CATALOG[job_id]
            entries.append(
                PolicyEntry(
                    change_class=change_class,
                    job_id=gate.job_id,
                    workflow=gate.workflow,
                    job=gate.job,
                    argv=gate.argv,
                    blocking=False,
                    script=gate.script,
                )
            )
    return tuple(entries)


DEFAULT_POLICY_TABLE: tuple[PolicyEntry, ...] = _default_policy_table()


@dataclasses.dataclass(frozen=True)
class AuditResult:
    ok: bool
    reason_codes: tuple[str, ...]
    errors: tuple[str, ...]
    entries_audited: int

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
            "errors": list(self.errors),
            "entries_audited": self.entries_audited,
            "policy_version": CI_POLICY_VERSION,
        }


def audit_policy(
    policy: Sequence[PolicyEntry] | None = None,
    *,
    repo: str | Path = ".",
) -> AuditResult:
    """Fail-closed audit of a policy table against the repository on disk.

    Every referenced workflow must exist under ``.github/workflows/`` and every
    referenced script must exist; a research-claim-bearing change class must be
    routed to the R4 gate (``r4_pytest``), never to a trivial check.
    """

    entries = tuple(DEFAULT_POLICY_TABLE if policy is None else policy)
    if not entries:
        return AuditResult(False, ("POLICY_EMPTY",), ("policy table is empty",), 0)

    root = Path(repo)
    codes: list[str] = []
    errors: list[str] = []

    def refuse(code: str, detail: str) -> None:
        if code not in codes:
            codes.append(code)
        errors.append(f"{code}: {detail}")

    for index, entry in enumerate(entries):
        label = f"entry[{index}] {entry.change_class}/{entry.job_id}"
        if entry.change_class not in CHANGE_CLASSES:
            refuse("UNKNOWN_CHANGE_CLASS", f"{label}: unknown change class")
        if not isinstance(entry.argv, str) or not entry.argv.strip():
            refuse("POLICY_ENTRY_INVALID", f"{label}: argv must be a non-empty string")
        workflow = entry.workflow
        if (
            not isinstance(workflow, str)
            or not workflow.startswith(".github/workflows/")
            or not workflow.endswith((".yml", ".yaml"))
            or not (root / workflow).is_file()
        ):
            refuse(
                "MISSING_GATE_WORKFLOW",
                f"{label}: workflow {workflow!r} does not exist under "
                ".github/workflows/ in this repository",
            )
        if entry.script is not None and not (root / entry.script).is_file():
            refuse(
                "MISSING_GATE_SCRIPT",
                f"{label}: script {entry.script!r} does not exist in this repository",
            )

    class_blocking: dict[str, set[str]] = {}
    for entry in entries:
        if entry.blocking:
            class_blocking.setdefault(entry.change_class, set()).add(entry.job_id)
    for change_class in sorted(R4_BEARING_CLASSES):
        if change_class not in {entry.change_class for entry in entries}:
            continue
        blocking_jobs = class_blocking.get(change_class, set())
        if "r4_pytest" not in blocking_jobs:
            refuse(
                "RESEARCH_CLASS_MISSING_R4_GATE",
                f"change class {change_class!r} can derive a research claim but is "
                f"routed only to {sorted(blocking_jobs)}; the full R4 gate "
                "(r4_pytest) is mandatory and a trivial check is not acceptable",
            )

    if not codes:
        return AuditResult(True, ("OK",), (), len(entries))
    return AuditResult(False, tuple(codes), tuple(errors), len(entries))


def assert_r4_gate_green(repo: str | Path = ".") -> tuple[bool, str]:
    """Verify the recorded R4 gate evidence is green (read-only).

    No research claim may be derived unless the recorded gate run
    (``research/venue2027/_shared/green_gate.json``) reports ``overall_status``
    PASS with every required job passing at exit code 0.
    """

    path = Path(repo) / GREEN_GATE_PATH
    if not path.is_file():
        return False, "R4_EVIDENCE_MISSING"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False, "R4_EVIDENCE_UNPARSEABLE"
    if data.get("overall_status") != "PASS":
        return False, "R4_GATE_NOT_GREEN"
    jobs = {job.get("job_id"): job for job in data.get("jobs", [])}
    for job_id in data.get("required_jobs", []):
        job = jobs.get(job_id)
        if job is None or job.get("status") != "PASS" or job.get("exit_code") != 0:
            return False, f"R4_JOB_NOT_GREEN:{job_id}"
    return True, "R4_EVIDENCE_OK"
