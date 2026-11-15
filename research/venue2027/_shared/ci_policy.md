# Unified CI policy — gate routing, security and research-claim separation

> Generated from the executable policy in
> `research/venue2027/_shared/tools/ci_policy.py` (version `1.0.0`).
> The prose below describes enforced code, not a substitute for it. Every
> workflow, job and script named here was verified to exist in this
> repository at task time (`test -f`); the auditor `audit_policy(...)`
> re-checks existence mechanically and refuses the policy otherwise.

## 1. Objective and core rule

One shared program-level CI contract for all nine 2027 studies:

**No research claim may be derived, recorded or updated unless the R4 gate
(evidence: `research/venue2027/_shared/green_gate.json`, task
`SH-r4_ci_gate`, overall status PASS, every required job exit code 0) has
passed on the source state the claim is derived from.** The check
`assert_r4_gate_green(repo)` refuses derivation with a stable reason code
(`R4_EVIDENCE_MISSING`, `R4_EVIDENCE_UNPARSEABLE`, `R4_GATE_NOT_GREEN`,
`R4_JOB_NOT_GREEN:<job_id>`) when the recorded evidence is absent, stale or
non-green.

The **artifact/SUT separation** is structural:

- Contract tests (unit-level, hermetic) run on every pull request.
- Heavy PG/LLM runs run only on an explicit controlled workflow
  (`workflow_dispatch`) or the nightly `schedule` light smoke — never
  auto-selected for an unrelated change class.
- Frozen heavy full campaigns run on a signed release tag only
  (`release.yml` job `clara-eval-release-gate` + tag creation job
  `create-semver-tag`).

## 2. Change classes and gate routing

`choose_gate(change_set, event=...) -> Checks` classifies each changed path
and unions the required gates. Routing table (blocking jobs only; optional
hardening jobs in parentheses):

| Change class | Trigger examples | Required gates | Optional |
|---|---|---|---|
| `docs` | `docs/**`, any `*.md` outside classed prefixes | `quality` (`ci.yml` job `quality`: docs-check + ruff + mypy) | — |
| `unclassified` | anything not matched below | `secret_scan` | — |
| `manifests` | `contracts/consumer-terminology/**`, `evaluation/clara_eval/datasets/**` | `secret_scan`, `eval_smoke` (`ci.yml` job `clara-eval-vn-smoke`) | — |
| `production_api` | `services/api/**` | `quality`, `api_tests` | (`security_audit`, `container_scan`) |
| `production_ml` | `services/ml/**` | `quality`, `ml_tests` | (same) |
| `production_web` | `apps/web/**` | `quality`, `web_lint_build`, `web_unit_tests`, `web_e2e` | (same) |
| `production_mobile` | `apps/mobile/**` | `mobile_apk` (`mobile-apk.yml` job `build-apk`) | — |
| `gate_config` | `.github/workflows/**`, `scripts/{ci,security,ops,docs,release}/**`, `Makefile`, `ruff.toml`, `.github/requirements-*.txt` | full R4 gate + `quality`, `scripts_syntax`, `artifact_safety_policy` | (`security_audit`) |
| `research_infra` | `research/venue2027/_shared/**` | full R4 gate + `artifact_safety_policy` | (`quality`) |
| `research_evidence` | `research/**`, `evaluation/**`, `datasets/**` | full R4 gate + `artifact_safety_policy`, `eval_smoke` | (`quality`) |
| `frozen_release_data` | `research/glhs_journal/q4_r4/**` | full R4 gate + `artifact_safety_policy` | — |

The **full R4 gate** is the five-job set recorded green in
`green_gate.json`, all in `.github/workflows/glhs-r4-novelty-gate.yml`:

| Job id | Workflow job | Command (as recorded) |
|---|---|---|
| `secret_scan` | `secret-scan` | inline scan for `aura_prod_x7k9m2` / `sk-[a-zA-Z0-9]{32,}` over `.py/.json/.md/.csv/.yml/.yaml` (excl. `.git/.venv/node_modules`) |
| `chronology` | `chronology-audit` | `PYTHONPATH=services/api/src:services/ml/src:. python3 research/glhs_journal/q4_r4/chronology_validator_r4.py` |
| `r4_pytest` | `r4-admission-and-comparator-tests` | `pytest -q` over the 10 R4 admission/comparator test files (+ `test_glhs_immutable_projection_contract.py` per recorded gate run), SQLite-only, auto-provisioned auth |
| `claim_lint` | `r4-claim-lint` | `python3 scripts/ci/r4_claim_lint.py` |
| `e22_offline` | `offline-reproducibility-sweep` | `python3 reproduce_q4_r4.py` (hermetic, sockets blocked) |

## 3. Trigger-event rules (run modes)

| Event | Run mode | Rule |
|---|---|---|
| `pull_request` / `push` | PR contract tests | Auto-runnable; SUT suites + contract tests only. No heavy PG/LLM claim runs. |
| `schedule` | nightly light smoke | Light smoke only (`active-eval.yml` job `run-active-eval`, CLARA-Eval VN `evaluation/configs/nightly.yaml`). Any heavy required gate is refused: `HEAVY_GATE_ON_SCHEDULE`. |
| `workflow_dispatch` | controlled dispatch | The only auto-class allowed to run the frozen heavy full campaign on demand (`R4_EVIDENCE_OK` still required for claims). |
| `tag` | signed-tag release | Frozen campaign allowed; `release.yml` `clara-eval-release-gate` + `create-semver-tag` are added when frozen release data is in the change set. |

**Adversarial control (fail-closed):** an auto run (`pull_request`, `push`,
`schedule`) whose change set touches frozen release data
(`research/glhs_journal/q4_r4/`) is refused with
`FROZEN_RELEASE_DATA_AUTO_RUN` — auto-runs must never change frozen release
data silently. An unknown event yields `UNKNOWN_EVENT` with **no** claimed
gates (never a permissive fallback).

## 4. Security policy (every change class)

1. **Secret scan** (`secret_scan`, also `ci.yml` hardening via
   `research-evidence.yml` job `secret-scan` for `research/` +
   `evaluation/`): forbidden credential patterns; any match fails the gate.
2. **Artifact safety**: `ci.yml` job `artifact-safety-policy` runs
   `scripts/security/check_ci_artifact_policy.py` — unsafe diagnostic
   artifact paths are rejected; failure diagnostics are sanitized via
   `scripts/security/check_ci_artifact_safety.py` before upload.
3. **Dependency integrity**: `ci.yml` job `security-audit` runs pip-audit
   (blocking on default branch; carried advisory must be recorded in
   `docs/security/accepted-findings.md`), `npm audit --omit=dev
   --audit-level=high`, and `scripts/ops/check_dependency_integrity.py`
   with an SBOM via `scripts/ops/generate_sbom.py`.
4. **Upload rule**: checksums and logs only — never PHI, secrets, provider
   keys, raw transcripts or benchmark-only flags. Research worktrees use
   the isolated PG cluster (`infra/research/venue2027/docker-compose.pg.yaml`,
   enforced by `research/venue2027/_shared/tools/pg_guard.py`); SQLite is
   never claimed as PostgreSQL evidence.
5. **Protected paths**: `.github/workflows/`, `services/api/alembic/versions/`,
   `services/api/src/clara_api/glhs/`, `services/api/src/clara_api/db/models.py`,
   `apps/web/app/` are never writable by research agents
   (`research/venue2027/_shared/worktree_policy.md`).

## 5. Policy audit (fail-closed, machine-checked)

`audit_policy(policy=None, repo=.)` audits the embedded routing table
(`DEFAULT_POLICY_TABLE`) — or any proposed table — against the repository:

| Refusal code | Meaning |
|---|---|
| `MISSING_GATE_WORKFLOW` | referenced file does not exist under `.github/workflows/` (or is not `.yml`/`.yaml`) |
| `MISSING_GATE_SCRIPT` | referenced script does not exist in the repository |
| `UNKNOWN_CHANGE_CLASS` | change class not in the catalog |
| `POLICY_ENTRY_INVALID` | empty/blank argv or malformed entry |
| `POLICY_EMPTY` | empty policy table |
| `RESEARCH_CLASS_MISSING_R4_GATE` | a research-claim-bearing class (`research_infra`, `research_evidence`, `frozen_release_data`, `gate_config`) is routed without blocking `r4_pytest` — the R4 gate cannot be downgraded to a trivial check |

A change class that can derive a research claim is *structurally* bound to
the R4 gate: no policy variant that swaps it for a lint/docs check audits
clean, and `choose_gate` itself routes those classes to the five-job gate on
every event.

## 6. Required vs optional summary

- **Required everywhere**: `secret_scan` (or the full R4 gate for any
  research/gate-bearing class), plus the per-class SUT suites above.
- **Optional hardening** (advisory on PRs, blocking on default branch /
  dispatch per `ci.yml` `required-ci-gates` policy mode): `security_audit`,
  `container_scan`.
- **Nightly**: light smoke only. **Signed tag**: frozen heavy full campaign
  plus release gate.
- Docs-only changes skip every heavy run and never change recorded prior
  claim status (`green_gate.json` is not rewritten by docs routing).

## 7. Verification evidence for this policy

- Positive/adversarial contract tests:
  `research/venue2027/_shared/tests/test_ci_policy.py` (22 tests).
- Recorded R4 gate evidence: `research/venue2027/_shared/green_gate.json`
  (all five jobs PASS, exit 0, first green SHA `152c89116069072bcb82678702c7b0d70a0fccfb`).
- Phase gate context: `research/venue2027/GATES/PHASE_GATE_MATRIX.md` (P08).
