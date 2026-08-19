# R3 Release Gate Follow-up

**Audit date:** 2026-08-19  
**Branch:** `codex/commitloop-phase-a`  
**Audited HEAD:** `92f29479`  
**Decision:** `BLOCKED`

This follow-up supersedes the stale working-tree observations in
`R3_RELEASE_GATE_REPORT.md`. Historical seals remain unchanged. A passing test
or protocol is not promoted to claim-eligible evidence without the required
freeze, raw-result inventory, and seal.

## Completed Since Prior Audit

| Gate | Verified evidence | Status |
|---|---|---|
| B | `fa3ea429`; immutable inference-to-THSS binding, migration, commit-time root re-read; 87 focused tests passed, plus 38 lineage tests in agent validation | PARTIAL: isolated PostgreSQL migration/regression gate remains |
| C | `aa82a756`; `GLHS-BINDING-ABLATION-20260819-01`; 320 schedules, 640 PostgreSQL executions, raw stream and seal | DONE for the matched ablation |
| D malformed audit | `00c5a31b`; checksums 49/49, available artifact had 0/360 malformed cells | PARTIAL: not the missing 384-subject raw artifact |
| F W8 reporting | `afd2126f`; deterministic renderer and all 25 survivor classifications | PARTIAL: W9 human review/execution and equal-budget run remain |
| H | `7c64ef84`; `FHIR-CONFORMANCE-V1-20260819`, validator 6.9.12, 33 tests, machine seal | PARTIAL: H-009 manual fields and documented semantic gaps remain |
| I | `f3a00573`, `92f29479`; claim synchronization and current-HEAD release metadata | PARTIAL: PDF source/build preflight is unavailable |

## Verified Results

- Exact-binding ablation: no-binding accepted `256/256` invalid commits;
  exact-binding accepted `0/256`; both arms accepted `64/64` valid controls;
  exact McNemar `p=1.727233711018889e-77`, paired risk difference `1.0`.
- GLHS production lineage focused tests: `87 passed`; ruff clean for the
  changed GLHS scope. Full API suite was attempted but timed out at 42% without
  a reported failure; isolated PostgreSQL migration upgrade remains blocked by
  the existing local database state.
- FHIR machine seal: 6 positive and 10 negative fixtures; structural and
  application layers are reported separately. Temporal, provenance, replay,
  and version-mismatch gaps remain explicit rather than hidden.
- v7 development run: last durable observation was `9,760/19,008` cells,
  scientific `N=192`; Gemini complete, Claude partial. The volatile raw run
  directory was lost on host reboot, so no v7 accuracy or final-holdout claim
  is made.

## Open Blockers

1. GLHS v2 12-schedule raw artifact is byte-verified but has frozen observation
   mismatches (`TOCTOU-V2-05/-09`); it is not claim-eligible until a new run is
   correctly frozen and sealed.
2. GLHS repeated interleavings require a real isolated PostgreSQL execution
   with commit-order evidence; the protocol is frozen but execution is pending.
3. The repository lacks the immutable 384-subject raw run/seal needed for the
   reported 220-malformed-output decomposition.
4. GovRed 30-60 schedule holdout and repeated ordering run require independent
   human authorship and isolated execution; final-003 remains immutable.
5. GovMut W9 requires blinded independent human non-equivalence review before
   denominator promotion, then separate execution/seal and equal-budget data.
6. CareGuard remains `RESULT-INCOMPLETE` pending an authorized current Vietnam
   identity frame and human mapping review; no benchmark was run.
7. FHIR support-letter/signature/advisor/milestone fields are human gates;
   the machine seal records them as `MANUAL_GATE`.
8. No tracked manuscript PDF sources or PDF build tools are available, so the
   final PDF/render/package gate cannot be marked done.

## Integrity Rules Confirmed

- No old GovRed final-003, GovMut W8, GLHS v1/v2 protocol seal, or prior null
  result was overwritten.
- No evaluation-only exact-binding branch is imported by production and no
  production `disable_binding` flag exists.
- Repetitions, retries, model-condition cells, and lost v7 execution cells
  were not counted as scientific subjects or schedules.
- CareGuard was not executed and no independent human authorship was claimed.
- GovRed RIVF and GovMut SOICT remain the primary archival routes; second venues
  remain extension-only until material new evidence exists.
