# Current repo audit summary - 2026-08-19

Repository reviewed through the connected GitHub app: `Project-CLARA-HBT/CLARA-Care`, branch `codex/commitloop-phase-a`.

## Highest-priority findings

1. **Mandatory binding is narrower than the R2 reviewer wording suggests.** The public commitment proposal API already requires snapshot ID/digest and invokes the bound proposal constructor. Generic assertion admission also has a regression lock against declared THSS-consuming downgrade. The unresolved gap is immutable inference-to-THSS lineage across internal/model/review paths: the internal base-version-only commitment constructor remains and current proposal lineage cannot independently prove that every descendant of a THSS-consuming model inference must remain bound.
2. **Production THSS/reconciliation hardening is substantially implemented already.** Current `commitment_thss.py` uses task-target/dependency selection, task-local conflicts, fact-level coverage, evidence minimization, domain freshness, and authorization-bounded expiry. Do not rebuild these from scratch.
3. **The existing `evaluation/contract_clause_ablation` is not the requested binding-only causal experiment.** It is a frozen developer-authored 16-case x 7 incremental-clause simulator. Preserve it, then add a separate matched same-production two-arm PostgreSQL ablation.
4. **GLHS evidence registry is inconsistent with the R2 manuscript.** The current canonical GLHS status materializes a five-schedule PostgreSQL run with one indeterminate ordering, while the R2 manuscript cites a 12-schedule v2 governance-TOCTOU run. The repository contains v2 executor/observer/writer machinery, but release provenance must be reconciled before submission.
5. **GovRed Not Run structure is already visible family-by-family.** The current matrix identifies which 30-case families were not executed. The next work is capability-gating/implementing feasible families, not merely adding another disclosure paragraph.
6. **GovMut W9 is already designed.** Eleven follow-up mutants target commitment gateway, governance-cache, and persistence-reconstruction blind spots, but W9 is not executed and still uses dual-model rather than human non-equivalence review. Extend W9 rather than inventing a separate holdout program.
7. **GovMut W8 already stores useful secondary evidence.** `final-analysis.json` contains per-mutant/method timing, seed-kill fraction/instability and the complete kill matrix. Build a reporting renderer before rerunning anything.
8. **CareGuard has three supporting source roles but no Vietnam identity frame.** RxNorm 2026-08-03, DDInter 2.0 and a small DailyMed current-SPL subset are acquired in controlled stores. No external benchmark is permitted until a current authorized Vietnam product source is obtained. Current statistics plan is still draft and lacks final sample-size/precision freeze.
9. **FHIR validation is partially implemented.** A checksum-pinned HL7 validator workflow exists, but currently validates one R4 fixture. Expand it into a frozen R4/STU3 + application-semantic matrix rather than claiming that validator evidence is absent.
10. **Publication registry is stale.** It still labels GovRed/GovMut headline runs as NOT_RUN/development despite later frozen artifacts. Registry/evidence reconciliation is a release blocker.

