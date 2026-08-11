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
manifest is frozen; the normalized-metrics artifact and task protocol remain
pending, so this stays `PARTIAL`.

SyntheticMass v1 outer SHA-256/gzip/tar verification passed for the local
30,878,003,109-byte archive. The source is twelve outer members containing
nested tar.gz chunks; an adapter and verifier now stream those chunks, minimize
away Patient demographics, reject links/traversal, and write deterministic
gzip common records. Full nested verification and normalization have not yet
run, so the outer-only result cannot be frozen as complete source acceptance.

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
