# GLHS independent evidence program ExecPlan

## Purpose and constraints

Extend the current working GST/THSS/GLHS implementation without redesigning it.
All clinical, human, real-EHR, provider, full-stack, and security claims fail
closed until their raw frozen artifacts exist. Structural-conformance evidence remains
developer-authored conformance evidence.

## Checkpoint — 2026-08-10

Completed scaffolding:
- a standalone mechanism-mapped bitemporal comparator with operator tests;
- external-cohort, annotation, and utility manifest validators that reject
  missing freezes, sealed partition, independence, or two model families;
- draft policies for medication, allergy/adverse reaction, and diagnosis/problem;
- explicit NOT RUN protocols for human, governance, and full-stack work;
- root reproducibility index and property-assurance inventory.
- a headline artifact seal that rejects incomplete raw output inventories and a
  downstream utility CSV validator that rejects an incomplete task/model/context grid.
- result validators for human review, isolated application-boundary adversarial
  runs, and the PostgreSQL→GST→GLHS→THSS→API benchmark path.
- an opt-in adversarial transport harness that records only response hashes and
  requires operator classification before any security outcome is reported.
- a curator-owned external preparer that requires preselected deidentified
  JSONL, validates development/test subject disjointness, and rejects synthetic
  oracle fields without downloading credentialed EHR data.
- a sealed non-headline MIMIC Demo run with 31/69 subject-disjoint split,
  6,741 source-derived tasks over medication, diagnosis/problem and lab state,
  plus 34/34 API/GST/THSS assurance tests.
- active evaluation paths are functional rather than reviewer-round labels;
  historical structural bytes are under `evaluation/archives/` with a naming CI guard.
- persistent proposals carry their base state version; transitions and THSS
  manifests record the consent version. A stale proposal cannot activate after
  state advances.
- a proposal may carry its source THSS snapshot ID; a cross-profile, expired,
  stale, or digest-mismatched source snapshot fails closed before persistence.
- GST checks the required profile-scope action and cached-grant expiry itself,
  so a caller cannot bypass route-level authorization with a constructed scope.
- THSS persists a canonical payload digest for decision reconstruction and now
  carries task-critical coverage, freshness, evidence-sufficiency and conflict
  assessment. `risk_aware` returns `ABSTAIN_ESCALATE` when any critical input is
  insufficient.
- `docs/architecture/glhs-risk-aware-thss.md` records the distinct medication,
  allergy/adverse-reaction, diagnosis/problem, and lab/chronic-state policies.
- VISTA and LongMedBench are recorded as asset-gated reference points only;
  their public runnable assets are not present, so no faithful comparator or
  benchmark claim is emitted.
- Decision reconstruction only returns transitions linked to the exact source
  THSS snapshot; an unrelated transition ID fails closed. Risk-aware snapshots
  persist policy-derived escalation reasons alongside coverage, freshness,
  evidence, and conflict assessments.
- Headline readiness now requires a frozen independent release attestation;
  sealed files and protocol inventory alone cannot enable headline claims.

Not completed / cannot be inferred:
- lawful full-MIMIC access and an independently curated sealed cohort (Demo-only
  developer-prepared evidence now exists but is not headline eligible);
- qualified independent annotations and adjudication;
- source-reviewed faithful BTSA mapping;
- provider executions across two model families;
- real API-boundary adversarial exercise;
- PostgreSQL-to-API operational measurements;
- a clean tagged final SHA and final reruns.

## Checkpoint — 2026-08-12 external-evidence specification restart

The operator-supplied evidence-hardening master specification broadens the
program beyond the earlier CommitLoop confirmatory path. Gate 1 now starts with
a repository-owned dataset registry and a fail-closed local data layer before
any new headline experiment.

Implemented in this checkpoint:

- `datasets/registry.yaml` records source, access, evidence class, schema,
  temporal/provenance semantics, limitations, local candidates and output paths;
- raw and normalized records are gitignored while metadata/license/manifests
  remain eligible for review;
- list, inspect, verify, fetch, normalize and freeze commands distinguish
  `NOT_AVAILABLE`, `ACCESS_REQUIRED`, presence, local integrity, normalization
  and evaluation rather than collapsing them into one availability flag;
- a common longitudinal evidence record preserves source subject/record,
  encounter, original value, valid time, knowledge time, precision, provenance,
  payload pointer/hash, uncertainty and missingness;
- the FHIR-NDJSON ZIP adapter leaves absent knowledge time unknown and creates
  no estimated timestamp.

Local read-only inspection found SyntheticMass FHIR v1 (30,878,003,109 bytes),
Synthea FHIR STU3 May 2017 (22,339,056,743 bytes), and MIMIC-IV Demo on FHIR
2.1.0 (51,859,726 bytes). These are presence observations, not canonical
checksum validation. Synthea OMOP 2.8M remains `NOT_AVAILABLE` because no local
archive or verified canonical distribution was found.

The MIMIC-FHIR Demo archive passed local ZIP integrity and was normalized into
the gitignored common interface: 927,109 records over 100 source subjects,
with 0 estimated timestamps. All 927,109 records lack `meta.lastUpdated`, so
knowledge time remains explicitly unknown. This is adapter execution on an
open real-data demo, not an independent oracle or clinical validation.

Its local-integrity manifest was subsequently frozen from clean source SHA
`1e74492f131779bcbc1af6304c3dcac036417912` and verified against its self-hash,
registry hash, extant Git commit, and current source inventory. The provider did
not supply a pinned checksum through this workflow, so canonical authenticity
remains unproven and the manifest says `NOT_PROVIDED` rather than upgrading the
claim.

The open CC-BY-4.0 Diabetes-130 archive was fetched from the registered UCI
endpoint, checked for ZIP integrity and expected members, and normalized without
extraction. The full source yielded 101,766 unique encounters from 71,518
subjects and 2,768,244 common-interface records. Because the source supplies no
event or recorded timestamps, every temporal coordinate remains explicitly
unknown and `estimated_times_created` is zero. This is real external-data
adapter/structural execution, not clinical gold or temporal-outcome validation.
Its source/license record and local-integrity manifest are tracked; the latter
was frozen from clean source SHA
`8793df4dbebc88bf906e6b9c414e680f5503752d` and passes the manifest verifier.
No provider-pinned archive checksum was exposed by the inspected UCI metadata,
so canonical authenticity remains a declared limitation.

The eICU Demo path now pins the official ZIP filename/endpoint, retains
resumable atomic partial downloads, and rejects a directory containing only a
partial as unavailable. Its verifier checks the packaged `SHA256SUMS.txt`
entries rather than relying only on ZIP CRC. A selected-table adapter preserves
documented minute offsets relative to ICU-unit admission without fabricating
absolute datetimes or knowledge timestamps. Full archive verification and
adapter execution remain `IN_PROGRESS` until the throttled official transfer
finishes; no partial counts are reported as evidence.

The transfer subsequently completed at the expected 136,773,541 bytes. The
outer ZIP and all 33 provider SHA-256 entries passed. Full selected-table
normalization produced 540,237 records across 1,841 subjects and 2,520 ICU
stays, with zero estimated timestamps. The clean-SHA instrumented rerun was
byte-identical and measured 24.764845 seconds, 21,814.67 records/second, peak
RSS 65,016 KiB and 5.7550x storage amplification on this host. The source
manifest is frozen; source-derived task execution remains pending, so this
stays `PARTIAL`.

The normalized aggregate was then frozen from clean SHA
`cd973c83f93e31ed472abaf16d3e46bd7a19ae34`. Its verifier rehashed the complete
gitignored record file, checked 540,237 physical lines against the recorded
count, and bound it to the provider-verified source manifest. Payload SHA-256 is
`44f0e9253599d07fcf10f741c8d1f4db2325c3827b6a97eed9bae17cf5f56850`.

The eICU task preparer is implemented with a deterministic subject split before
task selection, same-stay/same-slot offset comparisons, explicit tie/missing
exclusions, no knowledge-time imputation, and a strong valid-offset parity
reference. Task rows remain local and only their aggregate/hash manifest is
tracked.

The clean-revision run froze 59,513 tasks with 343,537 events across 1,413
represented evaluation subjects. The validator rehashed all task rows, enforced
unique latest-offset targets, verified upstream source/normalization bindings,
and rejected raw identity fields. The task SHA-256 is
`0b125b72c9327450ad21b199b7e48482d918a1d06a1ec7a962edf6c32ddc31e4`.
The subsequently frozen execution processed every task unchanged. Production
GLHS reconstruction and the strong valid-offset parity reference each selected
59,513/59,513 targets; input order selected 17,160/59,513, with zero missing
outputs and an empty error taxonomy. The tracked sanitized result payload is
`31a8cd13a2697e403bcb30c92c37ed5186049b7b854ef3caa139c5e7a21eecf1`.
This is source-offset structural mechanics through in-process SQLite production
primitives, not clinical correctness or deployment-boundary performance.

The source-offset runner is now frozen against implementation SHA
`87249453ae26871c99ddeac06927b3b32599d67d`, the exact cohort/task hashes, the
strong valid-offset parity reference, input-order baseline and production
`record_evidence -> propose_assertion -> apply_transition -> reconstruct_state`
path. Protocol payload SHA-256 is
`3a29d0c02357ae2cc708284f7e0aff2f76474489ae73c25f1dd0111674beea65`.
It declares SQLite/in-process scope, a source-subject analysis unit, missing or
invalid output as failure, and unavailable absolute/knowledge time without
estimation. The full execution is complete and its local ignored raw outputs
revalidate against their tracked aggregate/hash freeze. Provider calls remained
zero.

SyntheticMass v1 full nested verification passed for the local
30,878,003,109-byte archive. Two complete traversals each found 11 nested
archives, 1,307,771 FHIR bundles and 2,711,037 nested members with zero unsafe
members. The clean-SHA source manifest payload is
`384e9fc5669aceea0070cb6a11ee621f9e63f298a87893312bffe4073c8443cd`.
The adapter minimizes away Patient demographics and writes deterministic gzip
common records, but full normalization and metrics remain pending. The provider
did not supply a pinned checksum through this workflow, so this is frozen local
integrity for a synthetic archive, not canonical authenticity or validation.

The newly supplied SynPUF OMOP directories are registered as distinct 100K and
approximately 2.3M distributions rather than pooled. The 100K gzip streams
pass a local codec check. The larger directory contains one corrupt
temporary-suffix LZO object, so the repository verifier fails closed before a
29GB hash pass; it is not frozen or called complete. Synthea Coherent is also
registered from its bundled CC BY 4.0 README and local ZIP identity. Its
central directory contains 2,488 entries (2,484 files); source freeze and
minimized FHIR normalization now pass, while cross-modality linkage remains
pending. A newly supplied Diabetes-130 archive is
byte-identical to the already used UCI ZIP and is treated only as a duplicate.

The SynPUF OMOP 100K source was then frozen and normalized through the new
streaming adapter. Seventeen gzip tables (914,865,701 source bytes) produced
39,573,534 common records over 90,217 source subjects. Valid source dates or
datetimes were preserved, knowledge time stayed unknown, and no timestamp was
estimated. The normalized output and aggregate freeze are tracked by hash;
the evidence remains synthetic source/adapter execution, not clinical truth.

Synthea Coherent likewise passed the full local ZIP freeze and the minimized
FHIR Bundle adapter. It emitted 1,297,901 records from 1,278 subject bundles;
CSV/DICOM/DNA members were counted but not copied into normalized evidence.
Knowledge time stayed unknown and no time was estimated. The source and
normalization aggregate manifests are tracked by SHA-256; provider checksum
and cross-modality semantic linkage remain open gates.

The specification is now tracked at its declared primary path,
`docs/architecture/glhs-evidence-hardening-master-spec.md`, as a byte-identical
content copy apart from the final newline. The operator-provided root copy
remains untracked and untouched.

## Next gates

1. A lawful data steward freezes an external real-EHR manifest and proves
   subject disjointness from development.
2. Qualified reviewers approve/freeze the guide, label independently, and
   produce the adjudicated oracle.
3. A methods reviewer supplies the BTSA source mapping or retains the
   comparator as mechanism-only.
4. Freeze all task/model/domain/statistical manifests before comparative runs.
5. Execute the protocol on real deployment boundaries, write raw artifacts to
   `artifacts/evidence-program/<run-id>/`, then generate every reported table
   from those artifacts.
6. An independent release authority freezes
   `artifacts/evidence-program/headline-release-attestation.json` only after
   each external-cohort, adjudication, two-model utility, adversarial, and
   PostgreSQL full-stack gate is complete. The readiness audit rejects all
   headline claims without this approved attestation.
7. Audit every completion criterion, clean the worktree, tag the exact source,
   and rerun the final protocol.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-08-09 | Comparator remains mechanism-mapped, not called faithful Zhao. | Zhao et al. KnowFM 2026 is mapped, but semantic classifier, refinement merger, calibrated data and constraint implementation are unavailable. |
| 2026-08-09 | Human and external endpoints remain NOT RUN. | No qualified reviewers, lawful full-EHR attestation, or frozen oracle is present. |
| 2026-08-09 | Synthetic structural runs are retained only as structural evidence. | Developer authorship/oracle prevents independent clinical inference. |
| 2026-08-10 | Risk-aware THSS is a governed abstention mechanism, not a clinical-safety claim. | Thresholds and domain policies need independent clinical review before any safety inference. |
| 2026-08-09 | MIMIC Demo run is sealed as non-headline. | Subject split and source timestamps are measurable, but curator independence and clinician adjudication are absent by user direction. |
| 2026-08-11 | Separate snapshot-bound and base-version-only proposal validation. | An optional snapshot inside one ambiguous rule could not state or test the exact admissibility contract. |
| 2026-08-11 | Version snapshot fingerprints as `sha-256` plus `clara.canonical-json.v1`, retaining a legacy validator. | Deterministic hashing needs an explicit encoding contract; an unkeyed digest is only a trusted-store consistency check. |
| 2026-08-11 | Keep PostgreSQL atomicity evidence `NOT_RUN` on this host. | The implementation and opt-in isolated-schema test exist, but no acknowledged PostgreSQL URL or Docker runtime is available. |
| 2026-08-12 | Bind dataset freezes to both the registry file and the selected entry. | Adding an unrelated dataset must not invalidate immutable evidence; legacy manifests are verified from their exact historical Git registry, while any change to their own entry still fails closed. |
| 2026-08-12 | Keep each SynPUF OMOP distribution separate and reject the corrupt temporary LZO object. | A 100K development sample cannot stand in for the full distribution, and local presence cannot override failed codec integrity. |
| 2026-08-12 | Freeze only sanitized aggregate eICU results while hashing ignored raw outputs. | Subject/task rows remain local; the tracked evidence is independently revalidated without exposing identifiers or widening the clinical claim. |
