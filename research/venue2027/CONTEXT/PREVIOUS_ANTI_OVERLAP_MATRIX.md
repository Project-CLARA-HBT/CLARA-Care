# Nine-paper non-overlap and independent-evidence matrix

## Mandatory rule

Each paper must pass a 5-part distinction test: (1) different precise research question, (2) different scientific primary endpoint, (3) independently frozen evaluation design, (4) material new contribution beyond GLHS/HEALTHINF/GovRed/GovMut, (5) candid citation to closest related published or accepted papers. Sharing the repository and background methods is acceptable, but repackaging the same primary experiment is not. If any two proposed studies cannot pass these conditions, treat them as alternate target venues for ONE manuscript, not two papers.

| Venue | New primary endpoint | Novel proposed artifact | Conflict to check |
|---|---|---|---|
| DSN | duplicate/lost durable effect after crashes | crash journal and recovery fault scheduler | COMPSAC commit correctness vs recoverability |
| PoPETs | future revoked-attribute redisclosure and linkability | consent-aware prompt/cache invalidator | PST log privacy (different data surface) |
| IFIP SEC | cross-actor/purpose/tenant replay admission | context-bound receipt replay threat corpus | GLHS R4 E15 (high overlap risk) |
| ACNS SoK | taxonomy coverage / inter-rater disagreement | systematic literature dataset and counterexamples | IFIP security mechanism (avoid same evaluation) |
| COMPSAC | false-stale rejection and throughput under contention | dependency-scope PostgreSQL benchmark | GLHS R3/R4 concurrency evidence |
| AIME | task-level clinical workflow eligibility and unnecessary refusal | independently reviewed synthetic vignettes | HEALTHINF systems mechanism (avoid same endpoint) |
| SACMAT | cross-implementation policy decision conformance | PolicyTrace purpose/delegation corpus | GovMut mutation benchmark (avoid same corpus) |
| DIMVA | attack-campaign detection PR-AUC at fixed FPR | telemetry detector and synthetic campaign set | IFIP rejection vs detection distinction |
| PST | audit reconstructability vs metadata inference | minimized forensic receipts and insider attack dataset | PoPETs prompt/cache privacy distinction |

**If enough time/resources for only 3 independent papers:** COMPSAC (systems), AIME (medical workflow), and PoPETs (privacy). Prioritize the one with genuinely verified results and affordable attendance. SACMAT Dataset/Tool and PST short are possible after new evidence, not cheap guaranteed accepts.

## Venue-specific conflict controls

- DSN/COMPSAC: Do not reuse the same concurrency schedule as two independent primary studies. DSN needs crash cut-points; COMPSAC needs benign-contention and dependency scope.
- PoPETs/PST: Distinguish *future prompt redisclosure after consent revocation* from *post hoc audit-event inference and retention*. Different public artifacts and threat models.
- IFIP/ACNS: One is replay-resistant admission, one is SoK bibliographic taxonomy; literature SoK must be independent of self-referential performance results.
- IFIP/DIMVA: One prevents invalid tokens at verification, one detects campaigns over time, measured on independent detectors and event streams.
- SACMAT/GovMut: PolicyTrace measures authorization semantic conformance and portability. GovMut measures testing strategies' fault-detection mutation scores. None of the W8 45-mutant scores can be new PolicyTrace results.
- AIME/HEALTHINF: AIME clinical workflow task validity, not resubmitting co-versioned governance protocol or prior synthetic correctness numbers.

## Publication status and prerequisite

The user's previous conversation indicates HEALTHINF #97 has been accepted. The current repository publication registry distinguishes RIVF GovRed and SOICT GovMut as independent primary routes; no evidence is available here that these candidates have since appeared in proceedings. Before any simultaneous submission, audit accepted/published/preprint/submitted states and conflicts with policy. Preserve dates and actual statuses. Do not guess proceedings or journal publication.
