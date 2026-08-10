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
