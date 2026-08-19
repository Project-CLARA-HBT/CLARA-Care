# R3 Evidence Registry Final Audit

**Audit date:** 2026-08-19
**Audited HEAD:** `a9cefc314de302446a28d949f13419d211b717e4`
**Branch:** `codex/commitloop-phase-a`
**Decision:** `BLOCKED`; the registry routing is coherent, but the R3 evidence set is not fully sealed and several historical claim ledgers remain stale or disagree with the canonical pointers.

This is an evidence audit only. `research/publication_registry.yaml` and manuscript
files were not modified. The worktree was already dirty; conclusions below distinguish
the current filesystem from committed `HEAD`. Only this report is owned by this
workstream.

## Audit Rules

- A path is verified only when it exists and its declared SHA-256 recomputes exactly.
- A protocol, freeze, derived table, smoke run, design artifact, or unsealed working-tree output is not a sealed result.
- `NOT_RUN`, `PENDING`, and `UNRESOLVED` are retained unless the required result and seal exist.
- The canonical GLHS pointer is the 12-schedule v2 artifact, not the historical 5-schedule v1 artifact.
- Existing W8 GovMut evidence does not close the separate F workstream extension gates.

## Registry And Hashes

The registry itself is unchanged and hash-verified:

| Item | Path | SHA-256 / disposition | Finding |
|---|---|---|---|
| A registry | `research/publication_registry.yaml` | `39c1cb7f37f53d57bdcc44e6a5951bdc79d6ac35abdad4c3fe5a56aa7500a6aa` | Exists; GovRed/GovMut primary vs held-extension routing is explicit. |
| A baseline | `research/R3_BASELINE_AUDIT.json` | `55118a5ef7ebfb958f9c95b16f97f0a33085a695c6965af507c4d66c1c091d64` | Byte-valid historical baseline; records baseline commit `0a6c5940`, not current HEAD. |
| A report | `research/R3_WORKSTREAM_A_REPORT.md` | `85ae4b911c152bb0ccb382abebbf2d8d768e0997a468ea721dcb2d05243c27e8` | Byte-valid historical reconciliation; its clean-tree snapshot is no longer current. |
| E GovRed analysis | `research/govred_rivf/results/final-003-analysis-v2.json` | `098d4c3b14593b7a32e52c929d4cde7c3770e051063dd1c05c7ae83ef18d014c` | Exists and matches the canonical registry/run pointer. |
| E three-state derivation | `research/govred_rivf/results/final-003-three-state-primary.json` | `64a05d9551e22e6f48430a1d18146d07b9230183fee928d6b926c5ee823efb3e` | Exists and is derived from final-003; not a new execution. |
| E locked manifest | `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json` | `f5b20de13854a1d47f5496e4e4c3052f235c416bf4a4df6909c8091da8939378` | Exists and matches the registry's GovRed frozen-manifest path. |
| G statistics freeze | `research/careguard_vn/statistics_plan_freeze.json` | `09b4fbdf42a1755b08a49f38e36c433a423c24f46420a67d8262ea7de640a508` | Exists and is planning evidence only. |
| D/GLHS v2 seal | `research/glhs_journal/protocol_v2/artifact-sha256.json` | `b7f254304a929eb1d9d3534644e4b499780ae0295f16e50a027f871432f04b06` | Exists; all 4 declared child hashes pass. |
| GLHS v2 raw run | `research/glhs_journal/protocol_v2/run_v2_raw.json` | `ae8932f69b87e825b3ec942a453aa97b60156581c90a694f9ccdfc79b19c3d8d` | Exists and is byte-verified, but not claim-eligible. |

The registry's GovMut path also exists: the sealed analysis, run, and preflight
recompute to `e3ab1832c42be2a745ddae4ab960697143688302f78f6f4c08e82ef379278a67`,
`c59768dced443bb9cde6ba78762b728522cc9f581e30556b008f4b054e7cb6ce`, and
`432bd2ab66b707fd3de01d0ef5ce2830e0501c10801c21c51321a04f62b97db0` respectively.
The registry's CareGuard entry remains `NOT_RUN`/`NOT_RUN`; it has no benchmark
manifest or headline run to verify.

## Workstream Findings

### A: Baseline And Registry

The routing reconciliation is correct at the current registry hash. GovRed points to
run `2026-08-17-rivf-final-003`; GovMut points to
`govmut-soict-2026-final-v2`; GLHS points to the v2 raw artifact and
`CANONICAL_TOCTOU_EVIDENCE.md`; BigData Healthcare and BigData ML remain
`held_extension_only` with the material-extension rule.

A is not a current clean-baseline seal. `R3_BASELINE_AUDIT.json` records
`baseline_commit: 0a6c5940...`, while HEAD is `a9cefc31...` and the worktree has
many tracked and untracked changes. The prior release report audited HEAD
`3263d011`; subsequent commits `00c5a31b`, `f3a00573`, `afd2126f`, and
`d9dd3349`, the merge `460a850b`, and `a9cefc31` are outside that snapshot.

### E: GovRed

The final-003 primary evidence is present and hash-verified. The three-state output
reports, for `GLHS_STRICT`, `CONFIRMED_INVALID=0`, `INDETERMINATE=30`,
`CONFIRMED_SAFE_OR_REJECTED=180`, and `OPERATIONAL_FAILURE=0`; the 30 concurrent
residuals remain indeterminate and were not relabeled as confirmed violations.

This supports the registry's limited executable-primary status, not completion of E:

- The 30-scenario/50-repeat protocol is frozen but `PENDING EXECUTION`; no isolated PostgreSQL result or seal exists.
- The 39-schedule holdout is `FROZEN - NOT EXECUTED - MANUAL AUTHORSHIP GATE OPEN`; it has no authored oracle expectations or outcomes.
- The 180 `NOT_RUN` cases per arm remain excluded from denominators and are not zero failures.
- E-005 capability drivers are implementation/capability evidence, not executions.

### G: CareGuard

The statistics plan and supporting protocols are hash-verified, but Gate G is not
passed. `SOURCE_GATE_CHECKLIST.md` says the official/current DAV identity frame is
`NOT ACQUIRED`; the four-role source set therefore fails validation. RxNorm, DDInter,
and the five-record DailyMed subset are source-role evidence only. There is no DAV
mapping review, frozen identity frame, split, Mode A/Mode B run, or CareGuard seal.

`CGVN-RESULT-001` and `CGVN-RESULT-002` remain `NOT_RUN`. No false-clear, identity
accuracy, Vietnam coverage, specificity, or clinical-coverage result is permitted.

### D And Existing GLHS v2

The four v2 seal entries all pass:

| Sealed child | Recomputed SHA-256 |
|---|---|
| `postgres_toctou_protocol_v2.json` | `c10836f3e25c29cd83ade06cf104f67d97484397ec037809a36482685830798d` |
| `statistics_plan_v2.json` | `46a7e270f067769a3c43dc643dd448a2a25bdfffe74597c2d3b399b073af4fa7` |
| `run_v2_raw.json` | `ae8932f69b87e825b3ec942a453aa97b60156581c90a694f9ccdfc79b19c3d8d` |
| `analysis_v2.json` | `39efc4c7632e305eaea6b7ea12c339752266a901ad931fda806e58f207d95990` |

The v2 run has 12 schedules, 10 rejected outcomes, 2 committed outcomes, 0
forbidden commits, and 2 frozen classification mismatches:

- `TOCTOU-V2-05`: expected `indeterminate_ordering`, observed `rejected_after_or_during_governance_race`.
- `TOCTOU-V2-09`: expected `indeterminate_ordering`, observed `rejected_during_or_before_governance_race`.

The raw status is `EXECUTED_V2_OBSERVATION_MISMATCH`; the protocol result rule makes
the run not claim-eligible despite all hashes passing. The v1 five-schedule result is
historical only and is not the registry's canonical headline.

The new D artifacts do not close this blocker:

- `research/glhs_journal/concurrency_repetition_v1/FREEZE.md` is `NOT EXECUTED - PENDING`; its manifest hash is `4b66c774bb8f16bbb697d0efc1c1da69953ffbb2b7521602cae9accd12a5e62e` and no repeat raw/analysis result exists.
- `research/glhs_journal/malformed_audit_v1/malformed_audit.json` hashes to `2dbaa91196e501910435e97ec614f9ab30b318854a1c6723f7bd5a3c37f081bf`, but audits only 360 local cells with 2 source subjects and 0 malformed outputs.
- The reported v5-batch5 384-subject/220-malformed raw output is not present or sealed in this repository.
- `research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2_1.json` exists with hash `0b36ec3af7d1e9c43c92d6d825922d2f7364772dfdd2decf42126e0d6fe425c4`, but is not listed in the v2 seal and is not canonical evidence.
- The new `research/evidence_upgrade/v7_final_status/DEVELOPMENT_RUN_STATUS.md` is explicitly `INCOMPLETE, UNSEALED`; its last checkpoint was `9,760 / 19,008` development cells and the raw checkpoint/seal files do not survive on disk. It correctly adds no claim-eligible v7 result.

## B/C/F/H: Explicitly Pending

| Workstream | Status | Evidence boundary and blocker |
|---|---|---|
| B, mandatory THSS lineage | `PENDING` | Current implementation, migration, and tests are dirty working-tree candidates. No immutable B code/freeze/test identity or sealed PostgreSQL regression evidence exists. |
| C, exact-binding matched ablation | `PENDING` | The 320-schedule freeze and arm-diff checks exist, but `GLHS-BA-006` and `GLHS-BA-007` are `PENDING_POSTGRES_EXECUTION`; SQLite smoke is explicitly not final evidence and no PostgreSQL result/analysis seal exists. |
| F, GovMut extension | `PENDING` for R3 extension | W8 itself is sealed and hash-verified. The new W8 renderers/classification and W9 design inputs are not a W9 execution seal: human non-equivalence review, W9 execution/seal, and equal-budget evidence are absent. W8 cannot be used to mark the extension complete. |
| H, FHIR application evidence | `PENDING` | Current run output exists but is unsealed, has two structural mismatches, and lacks `evaluation/fhir_conformance/seal/artifact-sha256.json`, `analysis.json`, and `seal.json`. |

## Exact Stale Entries And Mismatches

These are the entries that must not be treated as current claim authority:

| Exact entry | Problem | Required interpretation |
|---|---|---|
| `research/evidence_upgrade/final/CLAIM_TO_EVIDENCE.csv:2-5,7` | These rows embed `CURRENT_EVIDENCE_STATUS.json:6aa8d9e4...`; current file hash is `907b75c8...`. Row 4 (`GLHS-CONCURRENCY-001`) is correctly marked `historical_not_canonical`, while rows 2, 3, 5, and 7 still carry the old cross-reference. | Historical/current cross-references are stale. Refresh the embedded hash or explicitly bind each row to a retained historical snapshot; do not treat the old hash as the current status file. |
| `research/govred_rivf/claim_to_evidence.csv:16-17` (`RIVF-RESULT-001/-002`) | Still anchors the study-level result claims to v1 `research/govred_rivf/results/analysis.json`. | Pointer mismatch. The registry and global ledger use canonical `final-003-analysis-v2.json`; v1 is historical and has the old underflow-prone analysis representation. |
| `research/R3_BASELINE_AUDIT.json:5` | `baseline_commit` is `0a6c5940...`, not current HEAD. | Historical metadata, not a current baseline. |
| `research/R3_RELEASE_GATE_REPORT.md:7` | Prior gate report audited HEAD `3263d011`. | Superseded audit metadata; it predates the GLHS D, registry-sync, GovMut follow-up, and follow-up-validation commits. |
| `research/release_r3/BUILD_INFO.json:44` and `research/release_r3/EVIDENCE_MANIFEST.json:1467` | The generated package records `source_commit: 00c5a31b`, while audited HEAD is `d9dd3349`. | Treat the package as an older snapshot, not a live synchronization guarantee; regenerate/bind it to the exact audited commit before release. |

Commit `f3a00573` correctly demoted `GLHS-TOCTOU-001` to
`historical_not_canonical`, added `GLHS-TOCTOU-V2-001` as
`byte_verified_not_claim_eligible`, corrected `PROGRAM_MANIFEST.json`, and
changed the evidence-upgrade v1 row to historical wording. Those corrections are
committed; the remaining embedded hash mismatch and package source-commit
mismatch above are still open.

The read-only ledger audit script reports 125 claims: 118 verified anchors, 7
explicit `NOT_RUN` claims, and 0 missing anchors. This confirms path/hash coverage;
it does not promote a claim whose status is pending, historical, or unresolved.

## Blockers

1. GLHS v2 claim eligibility is blocked by the two frozen classification mismatches; a new run ID/reseal or formally reconciled frozen result is required.
2. D still lacks 50-repeat concurrency output, the immutable 384-subject raw output/seal, and independent human contract holdout evidence.
3. E still lacks repetition execution, independent human-authored holdout outcomes, and a new confirmatory freeze; 180 `NOT_RUN` cases remain excluded.
4. G lacks the authorized current DAV identity frame and human mapping review, so no CareGuard benchmark may run.
5. B and C have no sealed evidence for the required production-lineage regression and isolated PostgreSQL matched ablation.
6. F has sealed W8 plus unsealed W8-derived/W9 design artifacts; the required W9 human/equal-budget extension remains pending.
7. H has an unsealed run with structural mismatches and no machine seal/analysis artifact.
8. Historical baseline/release metadata and the stale v1 GLHS evidence-upgrade entries must be reconciled before a synchronized package can be called final.

## Checks Run

- SHA-256 recomputation passed for the registry, A artifacts, E artifacts, G statistics freeze, GovMut seal entries, and all 4 GLHS v2 seal entries.
- `synchronize_r3.py` read-only functions: 118 verified anchors, 7 declared `NOT_RUN`, 0 missing anchors; registry overlap tokens passed.
- API virtualenv tests passed: GovRed 46, CareGuard 18, GLHS repetition/malformed 41, binding-only ablation 23, and current GovMut follow-up tests 27. Current `ruff check evaluation/property_assurance` also passes.
- System Python could not run pytest because `pytest` is not installed there; the repository API virtualenv supplied the passing test environment.
- Release preflight reports no tracked-source omissions, but no tracked PDF source and no PDF build tools are available.
