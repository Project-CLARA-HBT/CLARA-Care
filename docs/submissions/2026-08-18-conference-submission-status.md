# 2026 GLHS / CLARA-Care conference submission status

**Status date:** 2026-08-18  
**Evidence branch used:** `codex/commitloop-phase-a`  
**Purpose:** operational submission control. This document does not turn synthetic or structural evidence into clinical validation.

## Source-of-truth policy

1. Only sealed or repository-validated evidence may appear as a numerical result.
2. Developer-authored structural suites must be labelled **structural conformance**.
3. Controlled model-mediated cohorts must be labelled **synthetic software/mechanism evidence**, not clinical evidence.
4. `NOT_RUN`, `PARTIAL`, and `BLOCKED_EXTERNAL` evidence remains visible and may not be converted into positive claims.
5. The 2026-08-17 RIVF cache/audit development probe is **not a headline RIVF outcome**; it remains a development trace.
6. The exploratory CommitLoop Phase-B v4 run is not confirmatory evidence.
7. The later 384-subject Claude-only run is a material null result for strict THSS vs full authorized history and must not be hidden when making broad superiority claims.
8. Archival submissions must not be simultaneously under review at venues whose originality policy forbids concurrent consideration.

## Submission matrix

| Venue / package | Deadline | Current status | Evidence suitable now | Main blocker / action |
| --- | --- | --- | --- | --- |
| **IEEE RIVF 2026** — GLHS systems paper | 2026-08-31 | **YELLOW-GREEN — content can be finalized** | Structural conformance; exact PostgreSQL race; service-layer systems evidence; bounded 64-subject synthetic model-mediated cohort with limitations | Prior conference source/PDF is not tracked in this repo. Sync the off-repo IEEE source from the insertion map; do not use the Aug-17 development probe as a result. Once submitted, do not place the same archival GLHS paper under concurrent review elsewhere. |
| **SOICT 2026** — GovMut / broader governance-mutation study | Abstract 2026-09-09; full paper 2026-09-16 | **YELLOW-RED — methods ready, final endpoint not frozen** | 16-case × 7-variant clause ablation (112 structural cells) as precursor; existing GLHS contract evidence | The intended 45-mutant × 4-method × 5-seed study is not represented by a sealed final result in the tracked evidence inspected here. Do not invent/fill final Result tables. Also resolve archival overlap with IEEE BigData ML before submission. |
| **FMC 2026** — Vietnamese health-AI abstract | 2026-09-30 | **GREEN — scientific content ready** | Compact GLHS architecture + structural conformance + selected external-adapter scale; explicit non-clinical wording | Off-repo DOCX/PDF needs sync and final file-size check (submission form limit 1 MB). Keep claims accessible and avoid inferential superiority wording. |
| **IEEE BigData 2026 — Healthcare Data special session** — GovRed | 2026-08-29 | **YELLOW-RED — narrow systems paper possible; red-team headline not ready** | Current authorization/consent recheck, stale/expiry/context fail-closed tests, PostgreSQL race, audit reconstruction, contention trade-off | Deployment/cache-boundary adversarial matrix is not complete. A paper whose main claim is deployed adversarial security validation is not ready. A narrower governed-health-data systems paper can be finalized only if the off-repo manuscript already matches that claim. |
| **AMIA 2026 High School Scholars** — GLHS one-page manuscript | 2026-09-01 | **YELLOW-GREEN — research content ready, submission logistics remain** | 64-subject prospective controlled synthetic cohort; structural conformance; precise student contribution | Requires research mentor co-authorship/support materials and school/guardian information under AMIA rules. Keep synthetic/mechanism limits explicit. |
| **AMIA 2027 Amplify — Systems Demonstration** — CLARA-Care | 2026-09-03 | **GREEN — content ready** | Working GLHS implementation, exact snapshot/write binding, PostgreSQL atomicity, audit reconstruction, service-layer latency, FHIR ingestion scale | State deployment degree accurately as development/testing/prototype unless a real deployment artifact is separately verified. Do not present service-layer measurements as HTTP/production capacity. |
| **AMIA/HL7 FHIR App Competition 2026** — CLARA-Care | 2026-09-10 | **YELLOW-GREEN — technical application content ready** | FHIR ingestion/normalization evidence; SyntheticMass, MIMIC-IV Demo FHIR, eICU source processing; governed provenance/audit path | Student submission requires a support/attestation letter. Verify the exact FHIR release/resources and capability statement used by the app before form submission. |
| **IEEE BigData 2026 — Machine Learning on Big Data special session** — GovMut | 2026-09-30 | **YELLOW-RED — package shape ready, final study gate open** | 112-cell structural clause ablation and prior controlled mechanism evidence only | Do not substitute those precursor numbers for the planned mutation benchmark. If GovMut is materially the same archival study as SOICT, choose one active review path rather than simultaneous submission. |

## Recommended submission order as of 2026-08-18

1. **IEEE BigData Healthcare — 2026-08-29:** decide immediately whether GovRed is a narrow systems/governance paper that the existing evidence can support. If its title/abstract promises deployed red-team validation, hold it rather than overclaim.
2. **IEEE RIVF — 2026-08-31:** strongest near-term archival GLHS systems candidate. Freeze one evidence-consistent paper version and treat it as the active archival GLHS review.
3. **AMIA HSS — 2026-09-01:** complete mentor/support logistics while using the compact 64-subject controlled-synthetic result.
4. **AMIA Amplify — 2026-09-03:** submit CLARA-Care as a systems demonstration with truthful prototype/deployment wording.
5. **AMIA FHIR App — 2026-09-10:** finish student attestation and FHIR resource/capability details.
6. **SOICT — 2026-09-09 / 2026-09-16:** only proceed with GovMut if its final frozen study is available and it is not concurrently submitted as the same archival work elsewhere.
7. **FMC — 2026-09-30:** low scientific-content risk; compact Vietnamese abstract can use already verified evidence.
8. **IEEE BigData ML — 2026-09-30:** use as an alternative GovMut archival target, not a concurrent duplicate of SOICT.

## Current evidence gates

### Complete / usable with qualification

- Exact proposal/base/snapshot/context binding in the implemented contract.
- PostgreSQL profile-global atomic transition: in both tested four-writer same-slot and unrelated-slot races, one writer committed and three were stale-rejected.
- Standards-composed mechanism comparator and 16-case × 7-variant contract-clause ablation.
- Audit reconstruction of stored disclosure/proposal/decision linkage in focused implementation tests.
- Historical prospective controlled synthetic 64-subject model-mediated cohort.
- Clean single-process PostgreSQL service-layer latency artifact.
- External data adapters and source-processing artifacts where explicitly marked structural/demo/non-clinical.

### Partial / do not promote to headline completion

- Profile-global contention/version-granularity performance beyond the measured production profile-global path.
- Full-stack operational evaluation beyond service-layer, concurrency-one measurements.
- Governance adversarial boundary beyond local service/API contract tests.
- New model execution under the latest hardened contract.

### Blocked external

- Independent clinical adjudication / independent THSS clinical utility.
- Real-EHR clinical validity or efficacy.
- Lawful external holdout with qualified independent oracle.

## Artifact availability note

The exact prior RIVF/SOICT/FMC/AMIA/IEEE BigData conference `.tex`, `.docx`, and generated PDF packages discussed outside the repository are **not present in the branch inspected here**. Therefore this branch does not claim those PDFs were modified. `2026-08-18-venue-result-insertion-map.md` is the controlled, insertion-ready bridge for synchronizing those off-repo manuscripts without changing the scientific meaning of the evidence.

## Official venue references checked on 2026-08-18

- RIVF 2026 CFP: https://rivf2026.org/call-for-papers.html
- SOICT 2026 submission: https://soict.org/submission/paper-submission/
- FMC 2026: https://conference.pctu.edu.vn/home-english/
- IEEE BigData Healthcare Data: https://bigdataieee.org/BigData2026/calls/special-healthcare/
- IEEE BigData Machine Learning on Big Data: https://bigdataieee.org/BigData2026/calls/special-machine-learning/
- AMIA 2026 High School Scholars: https://amia.org/education-events/amia-2026-annual-symposium/high-school-scholars
- AMIA/HL7 FHIR App Competition: https://amia.org/education-events/amia-2026-annual-symposium/fhir
- AMIA 2027 Amplify proposal call: https://amia.org/education-events/2027-amplify-informatics-conference/summit-proposals
