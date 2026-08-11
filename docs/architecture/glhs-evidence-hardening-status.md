# GLHS evidence and contract hardening status

Updated: 2026-08-11. This register is publication-target agnostic. `COMPLETE`
means implementation plus executable repository evidence exists; it does not
mean clinical validity. External evidence remains fail-closed.

| Requirement | Status | Implementation | Tests | Artifact | Blocker |
| --- | --- | --- | --- | --- | --- |
| Repository/safety constraints | COMPLETE | API-owned GST/THSS boundary; safety gates unchanged | Focused API suites | This register | None |
| Active naming is target agnostic | PARTIAL | Legacy evaluators archived; active naming guard exists | `evaluation/property_assurance/test_naming_migration.py` | Historical archives | Existing active structural documentation still contains legacy protocol IDs; guard expansion pending |
| Explicit proposal target/base/actor/role/purpose/task | COMPLETE | `GlhsClinicalCommitmentProposal`; commitment gateway | `test_commitloop_gateway.py` | Migration 0055 | None |
| Snapshot-bound proposal path | COMPLETE | `propose_bound_commitment_transition`; `validate_bound_proposal_context` | Coordinate and endpoint tests | Proposal/manifest consistency fingerprints | None |
| Base-version-only proposal path | COMPLETE | `propose_base_commitment_transition`; `validate_base_proposal_context` | Base-only commit test | Transition ledger | None |
| Full same-context binding | COMPLETE | Manifest validation checks profile, actor, role, purpose, task, base, ID and digest | One-coordinate-at-a-time rejection test | Stable reason codes | None |
| Atomic profile transition | PARTIAL | PostgreSQL profile-row `FOR UPDATE`; idempotency recheck after lock | SQL compilation, local rollback, opt-in PostgreSQL race contract | JUnit/local results pending final checkpoint | PostgreSQL execution environment unavailable |
| N writers / unrelated slots | NOT_RUN | Opt-in isolated-schema test exists | `test_glhs_postgres_concurrency.py` skipped locally | None | Requires acknowledged PostgreSQL URL |
| Snapshot canonicalization contract | COMPLETE | `canonical_json.py`; schema/profile/algorithm metadata | Canonical ordering, Unicode, dates, non-finite rejection | Migration 0055 | None |
| Legacy snapshot reconstruction | COMPLETE | Profile-dispatched legacy fingerprint validation | Legacy v2 reconstruction test | Stored legacy payload | None |
| Bitemporal cutoffs | COMPLETE | Explicit valid/knowledge cutoff columns and payload coordinates | THSS/reconstruction tests | Snapshot manifest v3 | None |
| Late-evidence/conflict boundary matrix | PARTIAL | Bitemporal replay and conflict retention implemented | Existing gateway/reconciliation tests | Structural fixtures | Equality-cross-product expansion pending |
| Standards-composed mechanism baseline | PARTIAL | Bitemporal comparator exists | Comparator operator tests | Method card/deviations | Version-aware write, current authorization and audit composition not yet complete |
| Contract-clause ablation | NOT_RUN | Design specified only | None | None | Implementation and frozen case manifest required |
| Structural conformance | PARTIAL | Developer-authored suites retained as conformance only | Structural/property suites | Historical structural artifacts | New context-binding clauses not yet integrated into one frozen run |
| Independent annotation export/import/adjudication | PARTIAL | Evidence-program validators/scaffolds exist | Validator tests | Annotation guide | Genuine two-annotator plus independent-adjudicator inputs absent |
| Independent THSS utility/minimization | BLOCKED_EXTERNAL | Utility grid validator exists | Validator tests | Protocol scaffold | Qualified independent oracle and provider outputs absent |
| Model execution manifests | PARTIAL | Existing CommitLoop manifests/checksums | Evaluator tests | Frozen historical runs | New contract replication not frozen or executed |
| Confirmatory replication power | PARTIAL | Conservative tied paired-design calculator exists | Power tests | Draft analysis plan | New protocol is not frozen; no provider execution authorized |
| Concurrency/version granularity study | NOT_RUN | Definitions in master specification | Opt-in atomic safety test only | None | Benchmark implementation and PostgreSQL runtime required |
| Full-stack operational evaluation | NOT_RUN | PostgreSQL runner scaffold exists | Metric validators | NOT_RUN protocol | Isolated PostgreSQL deployment unavailable |
| Governance adversarial boundary | PARTIAL | Tamper/expiry/stale/cross-context tests at service/API boundary | Focused gateway/endpoint tests | Local test evidence | Deployment/cache-boundary run and operator labels absent |
| Audit reconstruction | COMPLETE | Exact stored payload, proposal coordinates, digest contract and snapshot-specific transition reconstruction | Tamper/legacy/unrelated-transition tests | Ledger rows | None for implementation conformance; external audit remains separate |
| External lawful-data validation | BLOCKED_EXTERNAL | Fail-closed manifests/validators | Validator tests | Demo-only non-headline artifacts | Lawful holdout, curator attestation and independent oracle absent |
| Statistical contract | PARTIAL | Subject-clustered paired statistics and failure handling | Evaluator tests | Existing analysis plans | Clause-ablation and contention estimands not frozen |
| Unique-run artifact contract | PARTIAL | Seal/checksum/validation tooling exists | Evidence-program tests | Existing sealed artifacts | New hardening run not yet sealed from a clean SHA |
| Manuscript evidence map | COMPLETE | Claim-to-evidence register | Docs check pending | `glhs-manuscript-evidence-map.md` | None |
| Manuscript revision guidance | NOT_RUN | No manuscript prose changed | None | None | Generate only after verified evidence stabilizes |
| Workstream A — contract hardening | PARTIAL | Core context/digest/bitemporal/immutability code implemented | Focused suites pass | Migration 0055 | PostgreSQL concurrency run and final full suite pending |
| Workstream B — novelty isolation | PARTIAL | Existing comparator foundation | Comparator tests | Method cards | Standards-composed baseline/ablation incomplete |
| Workstream C — systems evidence | NOT_RUN | Runners/scaffolds only | Validators | NOT_RUN manifests | PostgreSQL/deployed boundary absent |
| Workstream D — independent evidence | BLOCKED_EXTERNAL | Import/validation scaffolds only | Validator tests | NOT_RUN protocols | Independent people/data/provider inputs absent |
| Workstream E — reproducibility/release | PARTIAL | Locks, CI edits, seals and checksums | Local validators | Existing reproducibility index | Clean SHA, naming cleanup and final evidence inventory pending |
| No clinical/publication overclaim | COMPLETE | Docs label synthetic/developer-authored limits | Release gates | This register | None |

## Current validation checkpoint

- Focused contract suite: 34 passed and one PostgreSQL-only test skipped on
  2026-08-11; Ruff and focused mypy passed.
- PostgreSQL concurrency contract: present but skipped locally because no
  explicitly acknowledged PostgreSQL URL is installed.
- Full API suite: running; do not interpret this line as a pass until replaced
  with its completed exit status and JUnit path.
- Provider/model calls: zero for this hardening checkpoint.
