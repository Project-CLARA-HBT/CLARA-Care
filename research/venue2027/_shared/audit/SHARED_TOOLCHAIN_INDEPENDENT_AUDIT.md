# Shared Toolchain — Independent Adversarial Audit (AUDIT-shared_toolchain)

- **Auditor**: independent verifier (no manifest task; adversarial mandate)
- **Date**: 2026-11-15
- **Base commit audited**: `7ebdbbf0740e87ffebe3538d6893a53eaccf2216`
- **Own worktree**: `/dev/shm/clara_worktrees/v27_audit_shared` (branch `research/venue2027/audit/shared-toolchain`)
- **Method**: read every tool end-to-end, then wrote *new* defeat probes (`research/venue2027/_shared/audit/test_independent_shared_audit.py`, 52 tests) rather than re-running the authors' suites. Probes that confirmed a real defect assert the CURRENT (defective) behaviour so the suite stays green; the defect is documented here and the program-level report is `status=FAIL`.
- **Adversarial-suite result**: `52 passed` (exit 0) · **existing author suites**: `39 passed` (exit 0) · **ruff**: clean.

## Verdict summary

| # | Tool | Positive claim real? | Negative controls fail closed? | Verdict |
|---|------|----------------------|-------------------------------|---------|
| 1 | `repo_fingerprint.py` | Yes — clean/anchored repo → stable deterministic digest | **Yes** (dirty tree, missing anchor, no HEAD, non-git all refused) | **PASS** |
| 2 | `agent_protocol.py` | Yes — well-formed PASS validates; both proof reports re-validate today (exit 0) | **No** — 3 defeats (F1, F2, F3) | **FAIL (defeated)** |
| 3 | `worktree_policy.py` | Partial — deterministic allocation, same-registry conflict works | **No** — 2 defeats (F4, F5) + in-process-only registry | **FAIL (defeated)** |
| 4 | `source_reference_map.py` | Yes — classification works; verified-but-absent → `MISSING_REQUIRED` | **No** — 1 defeat (F8) | **FAIL (defeated)** |
| 5 | `claim_overlap.py` | Yes — salami pair & exact archive reuse BLOCK | **No** — 1 defeat (F6) | **FAIL (defeated)** |
| 6 | `literature_ledger.py` | Partial — classification & `reproduced`-without-code gate work | **No** — 1 defeat (F7/F7b) | **FAIL (defeated)** |
| 7 | `research_ethics.py` | Yes — synthetic-only policy enforced | **Yes** under all probed attacks | **PASS** |
| 8 | `r4_regression.py` | Yes — trace `reproduced=true` is independently re-derived from the raw log (failing ids, immutability reason, `4 failed, 57 passed`) | **Yes** (forged logs without the exact reason / with missing ids do not count as reproduced) | **PASS** |

**Program verdict: FAIL** — 5 of 8 tools have at least one guard that an adversarial probe defeated. No defect was hidden; each is reproduced by a test in the audit suite.

## Confirmed defects (guards defeated)

### F1 — agent_protocol: artifact hash binding escapes the repo (`HIGH`)
`validate_report` resolves `artifacts_sha256` keys against the repo root with no confinement (agent_protocol.py:201-206). A report declaring `../outside.txt` is satisfied by any host file:
```
artifacts_sha256 = {"../outside.txt": <sha256 of file outside repo>}  → ValidationResult(ok=True, OK)
```
Evidence binding can therefore be fabricated from files the repository never contained. Probe: `test_f1_ap_artifact_hash_path_escape_defeats_hash_binding`.

### F2 — agent_protocol: boolean `exit_code` bypasses the zero-exit gate (`MEDIUM`)
The check `c.get("exit_code") != 0` (agent_protocol.py:174) uses `==` semantics: `False == 0` → a command recorded as `{"argv": ..., "exit_code": false}` passes as green. (`"0"` string and absent key are correctly refused.) Probe: `test_f2_ap_exit_code_boolean_false_bypasses_zero_exit_check`, `test_f2b_ap_exit_code_string_refused`.

### F3 — agent_protocol: `log_path` is never checked (`MEDIUM`)
The module docstring states "Assertions without logs are rejected", but a PASS whose only command cites `log_path: "logs/never_written.log"` (file does not exist) validates with `ok=True`. Probe: `test_f3_ap_pass_with_nonexistent_log_path_accepted`.

### F4 — worktree_policy: `..` traversal into protected production paths (`HIGH`)
`assert_writable` matches the `research/` prefix BEFORE any path normalization (worktree_policy.py:107-119). `research/venue2027/../../services/api/src/clara_api/db/models.py` is accepted, and `PathLockRegistry.claim()` will then register that production path as locked by the calling agent. Probe: `test_f4_wp_parent_traversal_claims_protected_path`.

### F5 — worktree_policy: dot-segment lock split (`LOW`)
Lock keys are computed from `p.strip().lstrip("./")` before normalization (worktree_policy.py:132), so `research/venue2027/compsac/./x.py` and `research/venue2027/compsac/x.py` become two different locks; a second agent double-claims the same file. Probe: `test_f5_wp_dot_segment_lock_split_documented`.

### F6 — claim_overlap: archive-name variant evasion (`MEDIUM`)
Archive reuse is exact string membership (claim_overlap.py:121-122): `E15_E22_FROZEN`, `" e15_e22_frozen "`, and `e15_e22_frozen_v2` all evade `ARCHIVE_REUSE_AS_NEW`. (Note the contrast: the salami check normalizes case/whitespace; the archive check does not.) Probe: `test_f6_co_archive_name_variant_evasion`.

### F7 — literature_ledger: documented `VERIFIED_WITHOUT_CODE` gate not implemented (`LOW`)
Docstring (literature_ledger.py:21-23) promises `ok=False` / `VERIFIED_WITHOUT_CODE` for any `VERIFIED_BASELINE` without a code URL. No such branch exists; `verify_sources` returns `ok=True`, and a whitespace-only `code_url` even counts as runnable code (`VERIFIED_BASELINE`). The classification itself (cannot claim a runnable baseline) does work. Probes: `test_f7_ll_documented_verified_without_code_gate_is_not_implemented`, `test_f7b_ll_whitespace_code_url_counts_as_runnable_code`.

### F8 — source_reference_map: `..` in verified anchors resolves outside the repo (`LOW`)
`_classify` does `(root / path).is_file()` without confinement (source_reference_map.py:93-97), so a `source_verified.json` entry `../outside.txt` is reported `VERIFIED_EXISTING` with `ok=True` even though the file is outside the checkout. Probe: `test_f8_srm_parent_traversal_resolves_outside_repo`.

## Guards that held under attack (asserted refused)

- **agent_protocol**: empty `commands` → `NO_COMMANDS`; absent `exit_code` → `NONZERO_EXIT`; `source_sha_after="deadbeef"` / foreign sha → `SHA_NOT_IN_REPO` (7-char real prefix is accepted — acceptable, git-resolvable); swapped hash → `ARTIFACT_HASH_MISMATCH`; missing artifact → `ARTIFACT_MISSING`; foreign `task_id` → `TASK_MISMATCH`; unsatisfied dependency → `DEPENDENCIES_UNSATISFIED`; bogus status → `SCHEMA_INVALID`.
- **worktree_policy**: GLHS path, `db/models.py`, absolute `/etc/passwd`, `../README.md`, `services/...` → refused; same path twice in one registry → `LockConflict`; `_shared/` prefix is single-owner; invalid slug → `INVALID_SLUG`.
- **research_ethics**: `clinical_claim_allowed=True` → blocked; PHI with `synthetic_verifiable=False` (all three provenances) → blocked; non-synthetic provenance (incl. case-variant `Generated_Synthetic`) → blocked; empty/whitespace license → blocked; provider gate without ack → blocked; real-data provenance is never laundered by other flags.
- **claim_overlap**: identical normalized question+endpoint → `SALAMI_SAME_QUESTION_AND_ENDPOINT` (BLOCK); exact archive id → BLOCK.
- **repo_fingerprint**: dirty tree → `DIRTY_WORKTREE` (and dirty+missing-anchor never returns ok); repo with commits but zero anchors → `MISSING_REQUIRED_FILE` (all 8 reported); no HEAD → `NO_HEAD`; non-git dir → `NOT_A_GIT_REPO`; digest deterministic.
- **r4_regression**: trace JSON's `reproduced=true` independently re-derived from `proof/logs/SH-incident_repro.log` — exact expected failing ids, immutability reason present (8 occurrences), `4 failed, 57 passed in 66.86s`, exit code 1, listener anchor still raises the documented reason at `db/models.py`. Forged-log controls (wrong reason string / missing failing id) do not count as reproduced.

## Proof reports re-validation (run today)

```
python3 research/venue2027/_shared/tools/agent_protocol.py validate research/venue2027/proof/SH-repo_fingerprint.json --repo . --task SH-repo_fingerprint
→ exit 0, ok=true (log: research/venue2027/proof/logs/AUDIT-revalidate-SH-repo_fingerprint.log)

python3 research/venue2027/_shared/tools/agent_protocol.py validate research/venue2027/proof/SH-agent_protocol.json --repo . --task SH-agent_protocol
→ exit 0, ok=true (log: research/venue2027/proof/logs/AUDIT-revalidate-SH-agent_protocol.log)
```
Both reports' artifact hashes and source SHAs match this checkout — the prior work is real, not fabricated.

## Residual risks (not defects, but unenforced)

1. **`PathLockRegistry` is in-process memory.** Two agent *processes* each get their own registry and can both "claim" the same path. Real exclusivity must come from git worktree/branch allocation (git refuses duplicates); the registry is advisory. Test `test_wp_same_path_two_registries_are_independent` documents this.
2. **`repo_fingerprint --allow-dirty`** exists as an escape hatch; fine, since `ok` stays honest and the flag is explicit.
3. **`agent_protocol` FAIL/BLOCKED statuses skip command/artifact hard checks** by design (only PASS carries weight); a FAIL report with no evidence is accepted. Program process should treat FAIL/BLOCKED as needing human review anyway.
4. **`mark_task` state file is plain JSON** with no locking/signature; concurrent `mark_task` invocations can last-write-win.

## Recommended fixes (for the tool owners, smallest first)

1. F2: require `isinstance(exit_code, int) and not isinstance(exit_code, bool) and c["exit_code"] == 0`.
2. F3: if `log_path` present, assert `(root / log_path).is_file()` for PASS reports.
3. F4/F1/F8: normalize with `posixpath.normpath()` and refuse any result starting with `../` or being absolute before prefix checks (shared helper across the three tools).
4. F5: build lock keys from `posixpath.normpath()` output.
5. F6: normalize archive ids (`_normalize()`) before membership, and consider prefix/`_frozen` suffix matching.
6. F7: implement the documented `VERIFIED_WITHOUT_CODE` violation and strip `code_url` before truthiness.

## Reproduction

```bash
python3 -m pytest -q research/venue2027/_shared/audit/test_independent_shared_audit.py   # 52 passed, exit 0
ruff check research/venue2027/_shared/audit/                                            # clean
python3 research/venue2027/_shared/tools/agent_protocol.py validate \
  research/venue2027/proof/SH-repo_fingerprint.json --repo . --task SH-repo_fingerprint # exit 0
python3 research/venue2027/_shared/tools/agent_protocol.py validate \
  research/venue2027/proof/SH-agent_protocol.json --repo . --task SH-agent_protocol     # exit 0
```

---

## Remediation addendum (post-audit, same checkout lineage)

All eight confirmed defeats (F1–F8) were repaired and re-verified with the
auditor's own probes, which were flipped from "assert the defect" to "assert the
refusal". The independent audit suite now passes (52 probes) alongside the author
suite.

| Defect | Fix | Verified |
|---|---|---|
| F1 artifact path escape | `_confined_path()` resolves inside repo root; absolute/`..`/symlink escape refused (`ARTIFACT_MISSING`) | yes |
| F2 bool exit code | `exit_code` must be an `int` and not `bool` (`NONZERO_EXIT`) | yes |
| F3 missing log | every PASS command needs a non-empty on-disk `log_path` (`MISSING_LOG`) | yes |
| F4 `..` traversal to protected path | `_normalize_path()` + protected/membership checks on the normalized form | yes |
| F5 `./` lock split | lock keys built from the normalized path | yes |
| F6 archive variant evasion | archive ids canonicalized (case/whitespace/suffix) before matching | yes |
| F7 false verified-baseline claim | explicit `claims_verified_baseline` with no code URL fails closed; honest code-absence stays `PRIMARY_READ_CODE_ABSENT` | yes |
| F8 source-map escape | manifest paths confined to repo root; escape → `MISSING_REQUIRED` | yes |

Residual, documented risk (unchanged by design): `PathLockRegistry` is
in-memory, so cross-process exclusivity relies on real git worktrees, not the
class.
