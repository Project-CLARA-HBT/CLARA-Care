# GLHS independent evidence program ExecPlan

## Purpose and constraints

Extend the current working GST/THSS/GLHS implementation without redesigning it.
All clinical, human, real-EHR, provider, full-stack, and security claims fail
closed until their raw frozen artifacts exist. Structural Q2/Q3 remains
developer-authored conformance evidence.

## Checkpoint — 2026-08-09

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
6. Audit every completion criterion, clean the worktree, tag the exact source,
   and rerun the final protocol.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-08-09 | Comparator remains mechanism-mapped, not called faithful Zhao. | Zhao et al. KnowFM 2026 is mapped, but semantic classifier, refinement merger, calibrated data and constraint implementation are unavailable. |
| 2026-08-09 | Human and external endpoints remain NOT RUN. | No qualified reviewers, lawful full-EHR attestation, or frozen oracle is present. |
| 2026-08-09 | Synthetic Q2/Q3 is retained only as structural evidence. | Developer authorship/oracle prevents independent clinical inference. |
| 2026-08-09 | MIMIC Demo run is sealed as non-headline. | Subject split and source timestamps are measurable, but curator independence and clinician adjudication are absent by user direction. |
