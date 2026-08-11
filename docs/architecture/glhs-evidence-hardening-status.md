# GLHS evidence and contract hardening status

Updated: 2026-08-12. This register is publication-target agnostic. `COMPLETE`
means implementation plus executable repository evidence exists; it does not
mean clinical validity. External evidence remains fail-closed.

| Requirement | Status | Implementation | Tests | Artifact | Blocker |
| --- | --- | --- | --- | --- | --- |
| Repository/safety constraints | COMPLETE | API-owned GST/THSS boundary; safety gates unchanged | Focused API suites | This register | None |
| Dataset registry/data isolation | IN_PROGRESS | Registry plus gitignored raw/normalized roots; fail-closed list/inspect/verify/fetch/freeze tools | Dataset-tool tests | `datasets/registry.yaml` | Canonical checksums/acquisition timestamps remain missing for most sources |
| Common longitudinal evidence interface | IN_PROGRESS | Noncanonical common record plus FHIR-NDJSON, Diabetes, eICU-offset and nested-FHIR adapters | Provenance/time/missingness/minimization adapter tests | Local gitignored normalized outputs | OMOP and MEPS adapters pending; full SyntheticMass execution pending |
| SyntheticMass FHIR v1 local source | IN_PROGRESS | Nested-tar FHIR-bundle adapter and nested-integrity verifier implemented; outer archive is 30,878,003,109 bytes | Outer SHA-256/gzip/tar pass plus minimized nested-adapter fixtures | Source/license record; root operator archive remains untracked; outer SHA-256 `c913774ac42f9c68a3f18e24e579e55a8b1a380bebe403b68cc67ff7226de127` | Rerun new verifier across every nested chunk, then full compressed normalization/metrics and clean-SHA freeze |
| Synthea FHIR STU3 May 2017 local source | IN_PROGRESS | Registered local candidate, 22,339,056,743 bytes | Presence inspection only | Root operator archive, untracked | Full hash/archive verification and normalization pending |
| MIMIC-IV Demo FHIR adapter execution | PARTIAL | Streaming ZIP/NDJSON/GZIP adapter emitted 927,109 records for 100 subjects without estimated time | Local integrity, frozen-manifest verifier and six data-tool/adapter tests | Tracked clean-SHA manifest; gitignored normalized output; source SHA-256 `372997394c1f94fe7a8a1d7a064b5dc75e3e5db6d29a6283515d6f330f206542` | Provider-supplied canonical checksum and source-derived evaluation rerun pending; non-headline demo only |
| Diabetes-130 external real-data adapter execution | PARTIAL | Streaming ZIP/CSV adapter emitted 2,768,244 records from 101,766 encounters and 71,518 subjects; all unavailable temporal coordinates remain unknown | Archive-member verification, frozen-manifest verification and adapter provenance/time tests | License record, clean-SHA source manifest and gitignored normalized output; source SHA-256 `f82ac129da2ddd2299391ff6fbae3a6a58b3edcf59ac9d7bd480c00fe453112a` | Cohort/task freeze and source-derived structural evaluation pending; not clinical gold |
| eICU Demo acquisition/adapter | PARTIAL | Resumable atomic fetch, provider-SHA256 verifier and offset-preserving selected-table adapter emitted 540,237 records from 1,841 subjects/2,520 stays | All 33 packaged checksums plus resume/partial/provider-tamper/adapter tests | Source/license record and gitignored normalized output; archive SHA-256 `8e33a1094945d6ba07cf613b15b2fe4d98f6b3324601d026e80d445bd5b8b865` | Clean-SHA manifest, operational-metrics rerun and source-derived task evaluation pending |
| Synthea OMOP 2.8M source | NOT_RUN | Fail-closed registry entry | `NOT_AVAILABLE` path tested | None | Canonical distribution and local archive unresolved |
| Tracked primary master specification | COMPLETE | Exact-content tracked copy at the declared primary path | Byte/hash comparison plus docs check | `docs/architecture/glhs-evidence-hardening-master-spec.md` | None |
| Active naming is target agnostic | PARTIAL | Legacy evaluators archived; active naming guard exists | `evaluation/property_assurance/test_naming_migration.py` | Historical archives | Existing active structural documentation still contains legacy protocol IDs; guard expansion pending |
| Explicit proposal target/base/actor/role/purpose/task | COMPLETE | `GlhsClinicalCommitmentProposal`; commitment gateway | `test_commitloop_gateway.py` | Migration 0055 | None |
| Snapshot-bound proposal path | COMPLETE | `propose_bound_commitment_transition`; `validate_bound_proposal_context` | Coordinate and endpoint tests | Proposal/manifest consistency fingerprints | None |
| Base-version-only proposal path | COMPLETE | `propose_base_commitment_transition`; `validate_base_proposal_context` | Base-only commit test | Transition ledger | None |
| Full same-context binding | COMPLETE | Manifest validation checks profile, actor, role, purpose, task, base, ID and digest | One-coordinate-at-a-time rejection test | Stable reason codes | None |
| Atomic profile transition | COMPLETE | PostgreSQL profile-row `FOR UPDATE`; idempotency recheck after lock | Opt-in PostgreSQL race contract passed | Rootless PostgreSQL 16.14, random isolated schemas | None for N=4 atomic safety contract |
| N writers / unrelated slots | COMPLETE | Profile-global serialization exercised for same and unrelated semantic slots | Four simultaneous writers per workload: one commit and three stale rejects | PostgreSQL test output, synthetic/no-PHI | This is safety conformance, not the version-granularity performance study |
| Snapshot canonicalization contract | COMPLETE | `canonical_json.py`; schema/profile/algorithm metadata | Canonical ordering, Unicode, dates, non-finite rejection | Migration 0055 | None |
| Legacy snapshot reconstruction | COMPLETE | Profile-dispatched legacy fingerprint validation | Legacy v2 reconstruction test | Stored legacy payload | None |
| Bitemporal cutoffs | COMPLETE | Explicit valid/knowledge cutoff columns and payload coordinates | THSS/reconstruction tests | Snapshot manifest v3 | None |
| Late-evidence/conflict boundary matrix | PARTIAL | Bitemporal replay and conflict retention implemented | Existing gateway/reconciliation tests | Structural fixtures | Equality-cross-product expansion pending |
| Standards-composed mechanism baseline | COMPLETE | Bitemporal resolution, version-aware write, current authorization, provenance and audit composition; exact disclosure binding intentionally absent | Five focused temporal/write/manifest/tamper tests | Hash-frozen manifest, method card, source mapping and deviations | None for mechanism isolation; this is not a FHIR server/product claim |
| Contract-clause ablation | COMPLETE | Seven incremental clause variants over one identical 16-case matrix | Five runner/grid/checksum/freeze/tamper tests | Hash-frozen experiment manifest; 112-cell raw/aggregate output validates | None for developer-authored structural evidence; no external or clinical adjudication |
| Structural conformance | COMPLETE | Developer-authored suites retained as conformance only | Structural/property suites plus frozen clause matrix | Recomputable raw and aggregate structural output | Limited to enumerated synthetic mechanisms; not clinical validity |
| Independent annotation export/import/adjudication | PARTIAL | Evidence-program validators/scaffolds exist | Validator tests | Annotation guide | Genuine two-annotator plus independent-adjudicator inputs absent |
| Independent THSS utility/minimization | BLOCKED_EXTERNAL | Utility grid validator exists | Validator tests | Protocol scaffold | Qualified independent oracle and provider outputs absent |
| Model execution manifests | PARTIAL | Existing CommitLoop manifests/checksums | Evaluator tests | Frozen historical runs | New contract replication not frozen or executed |
| Confirmatory replication power | PARTIAL | Conservative tied paired-design calculator exists | Power tests | Draft analysis plan | New protocol is not frozen; no provider execution authorized |
| Concurrency/version granularity study | PARTIAL | Production profile-global path runs 1/2/4/8/16; resource/dependency alternatives are deterministic mechanism models only | 310 raw attempts, 50 independent profile races, grid/checksum/tamper validation | Clean-SHA contention artifact with raw/summary/model/checksums | No PostgreSQL performance implementation of alternatives, consent/policy/mixed workloads or retry-success study |
| Full-stack operational evaluation | PARTIAL | Alembic-backed service-layer runner covers seven real paths and fails closed on nonempty DB/output reuse | Validator/checksum/tamper tests plus clean-SHA PostgreSQL run | Saved v2 metrics/manifest/checksum and systems report | HTTP, source-revocation and concurrent-transition paths explicitly remain gaps |
| Governance adversarial boundary | PARTIAL | Tamper/expiry/stale/cross-context tests at service/API boundary | Focused gateway/endpoint tests | Local test evidence | Deployment/cache-boundary run and operator labels absent |
| Audit reconstruction | COMPLETE | Exact stored payload, proposal coordinates, digest contract and snapshot-specific transition reconstruction | Tamper/legacy/unrelated-transition tests | Ledger rows | None for implementation conformance; external audit remains separate |
| External lawful-data validation | BLOCKED_EXTERNAL | Fail-closed manifests/validators | Validator tests | Demo-only non-headline artifacts | Lawful holdout, curator attestation and independent oracle absent |
| Statistical contract | PARTIAL | Subject-clustered paired statistics, failure handling, deterministic clause matrix and descriptive false-stale estimand | Evaluator tests and contention validator | Existing analysis plans, frozen clause ablation and contention manifest | No inferential contention plan or external confirmatory execution |
| Unique-run artifact contract | PARTIAL | Seal/checksum/validation tooling exists | Evidence-program tests | Clean-SHA systems sub-run plus existing sealed artifacts | Program-wide hardening artifact and final evidence inventory remain pending |
| Manuscript evidence map | COMPLETE | Claim-to-evidence register | Docs check pending | `glhs-manuscript-evidence-map.md` | None |
| Manuscript revision guidance | NOT_RUN | No manuscript prose changed | None | None | Generate only after verified evidence stabilizes |
| Workstream A — contract hardening | COMPLETE | Context/digest/bitemporal/immutability and atomic transition contract implemented | Focused/full API plus actual PostgreSQL concurrency pass | Migration 0055 and isolated-schema race output | Complete as engineering conformance, not clinical evidence |
| Workstream B — novelty isolation | COMPLETE | Strong standards-composed mechanism comparator plus incremental clause engine | Ten focused tests; identical 16-case matrix across seven variants | Hash-frozen comparator/experiment manifests; validated 112-cell raw/aggregate run | Complete only as developer-authored structural evidence |
| Workstream C — systems evidence | PARTIAL | PostgreSQL atomic race, seven-operation service-layer runner and clean false-stale grid | PostgreSQL race plus full-stack/contention artifact validators pass | Clean systems and contention evidence | HTTP/source revocation/concurrent full-stack, deployed adversarial matrix and alternative-strategy PostgreSQL performance remain |
| Workstream D — independent evidence | BLOCKED_EXTERNAL | Import/validation scaffolds only | Validator tests | NOT_RUN protocols | Independent people/data/provider inputs absent |
| Workstream E — reproducibility/release | PARTIAL | Locks, CI edits, seals and checksums | Local validators | Existing reproducibility index | Clean SHA, naming cleanup and final evidence inventory pending |
| No clinical/publication overclaim | COMPLETE | Docs label synthetic/developer-authored limits | Release gates | This register | None |

## Current validation checkpoint

- Focused contract suite: 34 passed and one environment-gated PostgreSQL test
  skipped in the default run on 2026-08-11; Ruff and focused mypy passed.
- PostgreSQL concurrency contract was then explicitly enabled on 2026-08-12
  against rootless PostgreSQL 16.14. It passed both N=4 same-slot and unrelated-
  slot workloads: one atomic winner and three stale rejects in each workload.
  JUnit SHA-256: `046c3a1399027894617f8781919e8990efb79b8de944b6851ac26d2711e3abfb`.
- Full API suite: 1,369 passed, 2 skipped, exit 0 on 2026-08-11; JUnit SHA-256
  `7248d7130865e12c42ca827929d3eb3dc9a2f3756e31121bfff47775c5119f11`.
- Validated GLHS implementation commit: `7c968673df7bb30c3fa2f7ca0d881a92f643a22f`;
  latest pushed checkpoint before systems-runner edits:
  `c76a3d5ae94313a0a21d50911b56c1669857b2fa`.
- Evaluator/property assurance: 84 passed; comparator/evidence/adversarial/
  full-stack validators: 20 passed; release/status/seal validators: 10 passed.
- Network-free local assurance smoke: 8 synthetic transitions, zero external
  calls, checksum verified. This is local SQLite engineering evidence only.
- Workstream-B novelty isolation: frozen standards-composed manifest validates;
  five comparator tests and five clause-ablation tests pass. A fresh network-free
  run validated all 112 cells (16 identical cases x 7 variants), its aggregates
  and its SHA-256 inventory; external calls were zero.
- Full-stack v2 clean-SHA run: PostgreSQL 16.14 at Alembic revision
  `20260811_0055`, history depth 50, 30 repetitions for each of seven
  service-layer operations, implementation `36642787931e5ce429f73e8087c6a2ef66e71307`
  and checksum inventory SHA-256
  `75115757d7acec428d9291c567e12a2477f909990627d3f10e8bce40a8911336`.
  HTTP, actual source revocation and concurrent transition remain declared gaps;
  failed/developmental attempts are recorded in `glhs-systems-evidence-report.md`.
- Contention clean-SHA run: five independent profile races at each workload ×
  concurrency level (1/2/4/8/16), yielding 310 writer attempts and no database
  errors. In unrelated-slot races, profile-global false-stale rejection rates
  were 0, 0.5, 0.75, 0.875 and 0.9375 respectively; same-dependency losses
  were true stale. The saved artifact's checksum inventory SHA-256 is
  `a98c8c8b256b12b62d82bdd2ab73e24de4ccd7765444ce4daedcbc11de5f5f94`.
- Provider/model calls: zero for this hardening checkpoint.
- MIMIC-IV Demo FHIR local-integrity metadata was frozen from clean source SHA
  `1e74492f131779bcbc1af6304c3dcac036417912`; manifest payload SHA-256 is
  `e5257d01f07024cfc965f0f263484c49fac2c5728539de3d030db8b0eadec738`.
  The verifier rehashed the current source inventory and confirmed the source
  commit exists. Canonical checksum status remains explicitly `NOT_PROVIDED`.
- Diabetes-130 full-source normalization processed 101,766 unique encounters
  from 71,518 subjects into 2,768,244 source-linked records. The 2,988,916,669-
  byte JSONL rehashed to
  `9962c20af14eab834680aa1a3d4c2beae784752ed48b63ca0e6a567613e78760`;
  the adapter created zero estimated temporal coordinates. This proves adapter
  execution and structural counts only, not a clinical oracle or outcome.
- Diabetes-130 local-integrity metadata was frozen from clean source SHA
  `8793df4dbebc88bf906e6b9c414e680f5503752d`; manifest payload SHA-256 is
  `0d8bdbd621e0e54a4acd15ec7461de5edcceb8376f4f413a2f2f125c64992ec8`.
  Registry/source/self-hash verification passes; provider checksum status
  remains `NOT_PROVIDED`.
- eICU Demo verification matched all 33 official `SHA256SUMS.txt` entries and
  the outer ZIP SHA-256 is
  `8e33a1094945d6ba07cf613b15b2fe4d98f6b3324601d026e80d445bd5b8b865`.
  Selected-table normalization emitted 540,237 records (787,134,348 bytes) for
  1,841 subjects and 2,520 ICU stays; output SHA-256 is
  `68b25539c09e64aca75ce1010b51787c7ba179ad5d0fffb7f961b9e242310756`.
  All knowledge timestamps remain unknown and no estimated time was created.
