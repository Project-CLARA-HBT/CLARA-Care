# Comparator v2 notes (W3 comparator registry / W10 estimand registry)

Scope: this workstream maintains the published-system comparator registry
(`evaluation/comparator_studies/published_systems.yaml`), the estimand registry
(`research/evidence_upgrade/estimands.yaml`), the prior-work comparison table
(`research/evidence_upgrade/final/PRIOR_WORK_COMPARISON.csv`), and this note.
No git commits, no CareGuard changes, no remote VPS work, and no SOICT run are
part of this workstream.

## The standards-composed baseline is `STANDARDS_COMPOSED_SEMANTIC`

`evaluation/comparator_studies/registry.yaml` records the `standards_composed`
method with fidelity `semantic_mechanism_baseline_not_fhir_server`. Its engine
(`evaluation.comparator_studies.standards_composed_baseline.engine:
StandardsComposedState`) is a **mechanism-isolation baseline, not an actual
FHIR server**:

- It composes version-aware writes, current authorization, provenance, and audit
  to isolate the exact THSS disclosure-context binding as the mechanism under
  test. It intentionally omits that binding.
- It is never labelled as, and does not claim to be, a faithful FHIR server or a
  production-grade governed state store.
- Any comparison against it is a **semantic mechanism isolation** comparison,
  reported as `STANDARDS_COMPOSED_SEMANTIC`, and may not be dressed up as a
  "FHIR baseline" result.

## Faithful external comparators require fidelity gates

No nearest-neighbor system in `published_systems.yaml` is an automatic direct
GLHS/RIVF baseline: none has a same-task mapping at freeze time. A system can
only be classified `DIRECTLY_COMPARABLE` when, per row, its fidelity tests pass:

1. **Same-task mapping preserves published semantics.** The mapping must run the
   system's own published read/write/authorization/concurrency semantics against
   the same frozen logical cases as GLHS/RIVF, not a rewritten local proxy.
2. **Asset availability + license.** A runnable, license-compatible artifact
   must exist and be pinned (`code_source`, `pinned_version`, `license` no longer
   `UNVERIFIED`), with a verified source checkout.
3. **Adapter contract compliance.** The adapter must implement the comparator
   contract used for the frozen runs and must not be replaced with project-local
   code that changes the mechanism under test.
4. **Authorization-gate parity / concurrency parity.** Semantics that drive the
   endpoint (authorization gates, concurrency/ordering rules) must be mapped
   without weakening them; otherwise the system is at most
   `MECHANISM_REFERENCE_ONLY`.

Until those gates pass, the honest classification is `ASSET_GATED` (mapping or
assets unverified) or `MECHANISM_REFERENCE_ONLY` / `TASK_MISMATCH` (reference
only, no same-task benchmark). MemTX, MemTxn, and CommitGuard are recorded with
an explicit **upgrade path to `DIRECTLY_COMPARABLE`** — but only once the gates
above are actually met. A citation alone never licenses a numerical comparison.

## Estimands and the comparison table

`research/evidence_upgrade/estimands.yaml` pins the target quantity behind every
headline metric (unit, numerator, denominator, inclusion, exclusion, missing
handling, clustering, comparison family). `PRIOR_WORK_COMPARISON.csv` records
only comparisons backed by a same-task benchmark:

- RIVF final-003 arm contrasts use the honest frozen numbers (strict 0.143 vs
  UNBOUND 0.571 primary; secondary endpoints 0/270 in every arm) with paired
  McNemar support where reported.
- GLHS concurrency uses the five-schedule matrix and keeps TOCTOU-03
  `INDETERMINATE`.
- Where no same-task benchmark exists (all external nearest-neighbor systems,
  and the not-run SOICT mutation score), rows are marked `NOT_COMPARABLE` and no
  result is fabricated.
