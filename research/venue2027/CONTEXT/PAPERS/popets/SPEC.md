# Revocation-Aware Context Caches: Limiting Future Disclosures in Longitudinal Health Agents

**Venue:** PoPETs/PETS 2027 | **Rank target:** A | **Deadline:** 2026-11-30 issue 3 / 2027-02-28 issue 4

**Official CFP:** https://petsymposium.org/authors-2027.php

**Research status:** PROSPECTIVE / NOT SUBMISSION READY (2026-11-14)

**Source snapshot:** `research/glhs-r4-novelty-hardening` at `bce92340e190c62208a24aa3304f188080f6fd58`. Frozen historical evidence SHA `9006ac5c5379ead2620e47bc2c924ab4f7d45373`.

## 0. One-page decision

**Core question.** A consent revocation cannot retract a disclosure already delivered to an external model. It can, however, prevent future replay or reassembly of forbidden attributes. We study this precise prospective privacy boundary and its performance/utility trade-offs.

**Unique contribution.** Revocation-conditioned selective cache invalidation, a future-disclosure noninterference property, and a measured privacy--availability trade-off under synthetic longitudinal histories.

**Track strategy.** PoPETs journal-style paper, issue 4 preferred

**Publication cost and mobility.** Verified $0 submission fees and $0 APC; physical attendance not strictly necessary for publication.

**Funding plan.** Zero-fee publication is the preferred route; in-person travel entirely optional for publication. Apply for meeting bursaries only if participating.

**Submission formatting.** MANDATORY PoPETs 2027 acmart+popets LaTeX template and required ethics/open-science/AI-use sections; NOT arXiv style for submission.

**Hard stop.** Do not submit while the latest GLHS R4 release check fails or if novelty and dataset boundaries overlap an already accepted/submitted manuscript. This specification is a development plan; it is not evidence that an experiment has run.

## 1. Scientific hypotheses, boundaries, falsification

**Goal.** A consent revocation cannot retract a disclosure already delivered to an external model. It can, however, prevent future replay or reassembly of forbidden attributes. We study this precise prospective privacy boundary and its performance/utility trade-offs.

**Design hypothesis.** Model contexts as a labeled directed acyclic graph from consent grants and purpose to prompt components, embeddings and cache entries. Revocation event r invalidates every future dispatch whose dependency closure contains a revoked label; historical receipt records remain immutable but are access-filtered. Explicitly exclude the impossible promise of erasing an already observed external-model input.

**Pre-registered questions**
1. **RQ1:** Can selective invalidation prevent post-revocation redisclosure across cache and retry paths?
2. **RQ2:** How much sensitive-attribute linkability survives metadata and retrieval traces after minimization?
3. **RQ3:** What authorized context is unnecessarily removed by coarse invalidation versus selective invalidation?

**Falsification and negative-result policy.** If TTL-only and selective invalidation yield statistically indistinguishable future-disclosure outcomes at similar utility, no superiority claim; identify the actual trade-off. A null effect, lost advantage to a capable baseline, or a counterexample is a valid publication outcome; never filter away unfavorable trials.

**Novelty/overlap firewall.** Independent privacy outcome is prompt redisclosure and inference leakage after consent revocation; never recycle the GLHS commit-admission experiments. PST concerns audit retention, not prompt caches. Begin with a full textual comparison against HEALTHINF #97, GLHS R4, GovRed/RIVF, GovMut/SOICT and all other pending 2027 manuscripts. Same underlying code is permitted but same primary contribution or evidence reused as a new study is not. Publish positive and negative overlap findings in the internal `overlap_audit.md`.

## 2. Concrete code and architecture integration

**Design change.** Build a consent-aware projection index and cache invalidator for query, RAG, prefetch, retry and fallback paths; instrument the eventual bytes sent to providers, not only intermediate record eligibility.

**Source areas to inspect; these are pointers, not proof all APIs still exist at HEAD:**
- `services/api/src/clara_api/glhs/`
- `services/ml/src/`
- `evaluation/governance_adversarial/`
- `evaluation/clinical_utility/`
- `docs/security/`

Implementation artifacts must be additive and isolated to `research/venue2027/02_popets_2027/`, `evaluation/venue2027/02_popets_2027/`, `tests/venue2027/02_popets_2027/`, and `artifacts/venue2027/02_popets_2027/{run_id}/` until their security review passes. Never modify production patient data, never add a research-only bypass flag to deployed pathways, and never put provider credentials in artifacts. Configuration and migrations are reviewed before integration.

**Code integrity prerequisites:** Fix the `GlhsClinicalCommitmentProposal` immutable row update conflict without disabling the immutability event handler. Root error at `services/api/src/clara_api/db/models.py` near line 3040; latest R4 CI had four failing tests and failed the E22 hermetic reproduction. Run a pinned clean-checkout repair verification and record the first green CI SHA. Historical E15--E19 results ran on an SQLite memory backend; do not label these as PostgreSQL benchmarks.

### Proposed module layout

```text
research/venue2027/02_popets_2027/
  README.md                 # scope, protocol links, claimed originality
  novelty_contract.md       # claimed + surrendered mechanisms
  literature_matrix.csv     # prior studies and exact comparison questions
  claim_ledger.csv          # each sentence -> run / endpoint / exclusions
  freeze/                   # frozen preregistration, git SHAs and seeds
  analysis/                 # fixed estimands + review notes
  release/                  # checked PDF, raw-artifact manifest and checksums
evaluation/venue2027/02_popets_2027/
  generate_cohort.py        # deterministic, source-licensed synthetic generator
  run_baselines.py         # matched study arms, isolated DB
  collect_events.py        # immutable observation & backend provenance
  analyze.py               # preregistered, no post-hoc denominator changes
  reproduce.py             # clean-checkout and negative-control verification
tests/venue2027/02_popets_2027/
  test_oracle.py            # positive and negative controls
  test_no_leak.py           # PHI, credentials, canary
  test_replay.py            # freeze and raw checksums
  test_faults.py            # adversarial cases and failure classifications
```

## 3. Threat or challenge family matrix

The following classes must each include a controlled negative, legitimate operation, deterministic seed, stable label, and a complete expected/observed trace.

| Family | Setup and oracle | Required evidence |
|---|---|---|
| F01 | Cross-purpose cache key collision | raw schedule, expected decision, observed decision, run manifest, hash |
| F02 | Revoked attribute reappearing in retry prompts | raw schedule, expected decision, observed decision, run manifest, hash |
| F03 | Prefetch race against consent revocation | raw schedule, expected decision, observed decision, run manifest, hash |
| F04 | Cross-session embedding reuse | raw schedule, expected decision, observed decision, run manifest, hash |
| F05 | Inference of sensitive category from retained log metadata | raw schedule, expected decision, observed decision, run manifest, hash |

The control labels must be authored and locked independently from the detector/validator being evaluated. If the oracle cannot decide ground truth, mark `INDETERMINATE`, not false positive or true negative.

## 4. Dataset contract and provenance

**Population and scope.** Generate entirely synthetic medication, allergy and family-history attributes with multiple revocation epochs; no patient identifiers or clinical provenance from real users.

**Unit of analysis:** independent synthetic patient-purpose-history tuple; each has a fixed event schedule and controlled revocation time.

**Generation pipeline:** (a) produce a versioned synthetic source fixture; (b) derive task-scoped independent units before any model or algorithm executes; (c) lock train/validation/test if supervised; (d) serialize expected decisions separately from tested code; (e) sign manifest checksums and blinded assignment. Never claim that 1,000 correlated retry events are 1,000 independent patients.

**Minimum run manifest fields** (`manifest.json`): `study_id`, `source_sha`, `harness_sha`, `analyzer_sha`, `git_status`, `backend`, `postgres_version`, `isolation_level`, `hardware`, `python_version`, `seed`, `cohort_sha256`, `protocol_sha256`, `start_utc`, `end_utc`, `observed_errors`, `primary_n_unique`, `secondary_n_retries`, `excluded_with_reason`, `test_mode`, `license`, `ethics`, `result_status`.

**Legal/privacy:** Synthetic patient IDs only, no real clinical prompts, no live credentials, no unauthorized web corpus. When referencing standards or open public datasets, log URLs and redistribution rights. An open public healthcare corpus is NOT automatically unrestricted redistribution.

## 5. Prespecified comparator implementations

Use matched data, identical time budgets, pinned source versions and explicit unit-level pairing. Do not benchmark a toy comparator against production code unless matching feature coverage is documented.

| Arm | Implementation requirements | Non-inferiority/safety control |
|---|---|---|
| B0 | TTL-only cache expiry; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B1 | Profile-wide flush; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B2 | Grant-level selective invalidation; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B3 | Selective invalidation plus disclosure-minimizing logging; pin its implementation and configuration | positive legitimate controls + all challenge classes |

**Fairness:** Where a signed capability or classic OCC baseline provides the same primary decision safety as the proposed method, explicitly surrender any claimed superiority for that endpoint. Confirm baseline authorship/implementation and do not present stub methods as peer systems.

## 6. Execution and measurement plan

**Primary and secondary outcomes:**
1. post-revocation forbidden-disclosure rate.
2. attribute-inference advantage of audited attack model.
3. over-redaction of authorized content.
4. cache hit rate and latency.
5. residual sensitive bytes and retention time.

**Analysis:** Report per-patient clustered confidence intervals, attack success vs chance under prespecified priors, and separate privacy leakage from harmless denial. Zero leaks only bounds the tested schedules.

**Prespecified experiment grid:**

1. Smoke: 5 independent units per family to establish the oracle and instrumentation, labeled development-only.
2. Baseline validity: positive and negative controls for every arm; no unequal permissions or silent retries.
3. Prospective freeze: version the finalized cohort, workloads, power/sample calculation, primary estimand and family-specific denominators.
4. Confirmatory test: execute every frozen arm on each independent schedule; choose N by a documented power / confidence-bound calculation, not a cosmetic round number.
5. Stress/ablation: run additional conditions separately from confirmatory denominator and identify the exact difference from the base mechanism.
6. Reproduce: run with empty output directory; hash byte-equivalent (or document numerical tolerance for randomized provider outputs), validate chronology and deliberate negative tampering.
7. Publish: anonymized artifacts, README, licenses, no user health data and exact code-to-claim crosswalk.

**Prohibited analyses:** No imputation of NOT_RUN to zero; no cherry-picked provider seed; no uncorrected multiple comparisons presented as planned primary; no test leakage; no post-hoc freeze; no mixing SQLite and PostgreSQL latency evidence.

**Mandatory tables/figures:** architecture diagram; challenge-family coverage; baseline primary metric with confidence interval; cost/performance plot; ablation or falsifying counterexample; limitations/validity map. All generated by code and tied to manifest/run SHA.

## 7. Release gates and reviewer-grade acceptance tests

- [ ] **G0 novelty:** 20+ relevant prior works (or systematic SoK search corpus), cited and checked; two independent reviewers approve distinct main claim; overlaps with every other venue documented.
- [ ] **G1 code:** latest branch root regression addressed without weakening append-only database invariants; relevant CI passes and release commit pinned.
- [ ] **G2 oracle:** independently curated outcomes, complete family coverage, synthetic licensing and patient-data non-ingestion verified.
- [ ] **G3 backend:** PostgreSQL work actually runs on PostgreSQL 16 with appropriate isolation/locking attestation; non-DB experiments state their true backend.
- [ ] **G4 negative controls:** deliberately corrupted receipts/dependencies and missing artifacts fail closed; reason codes agree with frozen truth.
- [ ] **G5 statistics:** no pseudoreplication; every estimate has correct denominator, uncertainty interval and prespecified hypothesis/multiple-testing policy.
- [ ] **G6 reproducibility:** clean checkout, artifact SHA-256, environment manifest and offline reanalysis pass; evidence source SHA matches manuscript.
- [ ] **G7 manuscript:** all claims supported; tables and figures are actual; original literature checked by humans; no broad clinical efficacy/security assurances.
- [ ] **G8 venue policy:** select official template, author anonymity, page limit, AI-use disclosure, originality, author-registration, and presentation requirements confirmed.
- [ ] **G9 funding:** cost and presentation feasibility confirmed before a nonrefundable registration commitment.

**STOP condition:** If TTL-only and selective invalidation yield statistically indistinguishable future-disclosure outcomes at similar utility, no superiority claim; identify the actual trade-off.

**Risks and mitigations:** A straightforward cache invalidation system may not reach PoPETs novelty standards; requires real privacy adversary and threat-model-driven privacy measurements.

## 8. Work allocation (ten independent subagents)

| Agent | Concrete output | Acceptance criterion |
|---|---|---|
| A1 literature | bibliography + claim comparison | no invented or uncited prior work |
| A2 theory | definitions, theorem/checkable invariant | falsifiable claim with counterexample |
| A3 architecture | isolated adapter implementation | passes integration and security review |
| A4 datasets | independent synthetic cohort + provenance | generator reproducible with locked seeds |
| A5 baselines | genuinely capable comparators | fairness audit and negative controls |
| A6 adversarial | challenge family runner | every family includes clean control |
| A7 statistics | preregistered estimand and analyzer | reanalysis recovers all computed numbers |
| A8 reproducibility | fresh-checkout CI + checksum | failure injection and no-network check pass |
| A9 manuscript | figure and table plumbing, LaTeX conversion | no placeholders in actual submission |
| A10 hostile review | overlap, clinical, ethics and fees audit | independent written GO/NO-GO |

The 10 agents may work in parallel in separate branches, but the principal investigator must review and merge sequentially with CI protection. An LLM agent is NOT a clinician, independent ethical adjudicator or substitute for evidence.

## 9. Publication decisions and funding

**Default decision:** draft-only while experiments are pending. Zero-fee publication is the preferred route; in-person travel entirely optional for publication. Apply for meeting bursaries only if participating.

**Format migration:** MANDATORY PoPETs 2027 acmart+popets LaTeX template and required ethics/open-science/AI-use sections; NOT arXiv style for submission.

**Official source:** https://petsymposium.org/authors-2027.php. Use the official CFP and author guide again immediately before submission, because fee schedules, anonymization rules and presentation policies can change.



## PSC evaluation extension: to be implemented, not assumed

**Candidate:** PSC-Revoke — Prospective Purpose-Specific Revocation with Cache and Egress Attestation.

**RQ1:** What information can a revocation-aware system prevent from being re-disclosed after time t_r, given that prior model disclosure cannot be retracted?

**Strongest fair comparator:** Per-request policy re-evaluation with no cache; selectively invalidating cache; macaroons with shortened TTL; Zanzibar-style consistency checks.

**Primary:** forbidden post-revocation future disclosure per patient-purpose-history. **Utility/coverage:** authorized disclosure coverage at fixed leakage bound and p95 latency.

**Do-not-claim gate:** If an always-recompute per-request permission gate provides equal privacy protection with acceptable latency, do not claim privacy novelty.

See `PSC_METHOD_EXTENSION.md` for explicit shadow A/B, certificate, model-ablation and 7 file-level contracts. This is a scientific method proposal, not a certified result.
