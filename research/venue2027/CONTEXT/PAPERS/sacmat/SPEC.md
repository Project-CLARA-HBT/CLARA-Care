# PolicyTrace: A Reproducible Conformance Corpus for Purpose-Scoped Consent Delegation

**Venue:** SACMAT 2027 | **Rank target:** C | **Deadline:** 2027-02-12 cycle 2

**Official CFP:** https://www.sacmat.org/2027/call-for-papers.php

**Research status:** PROSPECTIVE / NOT SUBMISSION READY (2026-11-14)

**Source snapshot:** `research/glhs-r4-novelty-hardening` at `bce92340e190c62208a24aa3304f188080f6fd58`. Frozen historical evidence SHA `9006ac5c5379ead2620e47bc2c924ab4f7d45373`.

## 0. One-page decision

**Core question.** Purpose-based health information access changes through family delegation, temporary clinical roles, revocations and policy hierarchy. A portable conformance suite can reveal divergence among policy engines without conflating this with model accuracy.

**Unique contribution.** A formal decision oracle, controlled synthetic policy-history generator and implementation-independent conformance corpus with reproducible policy decision point adapters.

**Track strategy.** Dataset/Tool track (5 pages + 1 bibliography/appendix) or main research if stronger

**Publication cost and mobility.** Potential ACM 2027 APC USD 500 (member) or USD 750 (nonmember) absent institutional coverage/waiver PLUS full author registration and in-person presentation.

**Funding plan.** Check ACM Open membership and discretionary APC waiver first; ask host organizers about high-school student support. Avoid assuming waiver approval.

**Submission formatting.** ACM acmart sigconf double-blind; track labels/limits mandatory.

**Hard stop.** Do not submit while the latest GLHS R4 release check fails or if novelty and dataset boundaries overlap an already accepted/submitted manuscript. This specification is a development plan; it is not evidence that an experiment has run.

## 1. Scientific hypotheses, boundaries, falsification

**Goal.** Purpose-based health information access changes through family delegation, temporary clinical roles, revocations and policy hierarchy. A portable conformance suite can reveal divergence among policy engines without conflating this with model accuracy.

**Design hypothesis.** Define authorization judgments PDP(s, actor, purpose, resource, time) in {PERMIT, DENY, INDETERMINATE}, with precedence rules for explicit revocation and time-bounded delegation. Generate histories with a reference oracle and metamorphic properties such as revocation monotonicity where applicable.

**Pre-registered questions**
1. **RQ1:** Can a compact policy calculus encode precedence between emergency role, delegation expiry, purpose and consent?
2. **RQ2:** Which categories of policy-engine disagreement arise under identical request attributes and history?
3. **RQ3:** Does the generator cover semantic transitions missing from static one-request policy test suites?

**Falsification and negative-result policy.** If a strong existing ABAC conformance suite covers the same transition classes, publish as incremental tool only if portability/usability advantages are evidenced. A null effect, lost advantage to a capable baseline, or a counterexample is a valid publication outcome; never filter away unfavorable trials.

**Novelty/overlap firewall.** GovMut studies testing-strategy mutant adequacy. PolicyTrace studies semantic conformance between authorization policy engines and delegated consent timelines; no recycled W8 mutant scores. Begin with a full textual comparison against HEALTHINF #97, GLHS R4, GovRed/RIVF, GovMut/SOICT and all other pending 2027 manuscripts. Same underlying code is permitted but same primary contribution or evidence reused as a new study is not. Publish positive and negative overlap findings in the internal `overlap_audit.md`.

## 2. Concrete code and architecture integration

**Design change.** Implement policytrace-generator, a JSON schema, deterministic seeds, interpreters for CLARA PDP and a small XACML-style adapter, plus a policy-diff viewer independent of AI providers.

**Source areas to inspect; these are pointers, not proof all APIs still exist at HEAD:**
- `services/api/src/clara_api/glhs/`
- `docs/security/`
- `research/assurance_soict/`
- `contracts/`
- `evaluation/governance_adversarial/`

Implementation artifacts must be additive and isolated to `research/venue2027/07_sacmat_2027/`, `evaluation/venue2027/07_sacmat_2027/`, `tests/venue2027/07_sacmat_2027/`, and `artifacts/venue2027/07_sacmat_2027/{run_id}/` until their security review passes. Never modify production patient data, never add a research-only bypass flag to deployed pathways, and never put provider credentials in artifacts. Configuration and migrations are reviewed before integration.

**Code integrity prerequisites:** Fix the `GlhsClinicalCommitmentProposal` immutable row update conflict without disabling the immutability event handler. Root error at `services/api/src/clara_api/db/models.py` near line 3040; latest R4 CI had four failing tests and failed the E22 hermetic reproduction. Run a pinned clean-checkout repair verification and record the first green CI SHA. Historical E15--E19 results ran on an SQLite memory backend; do not label these as PostgreSQL benchmarks.

### Proposed module layout

```text
research/venue2027/07_sacmat_2027/
  README.md                 # scope, protocol links, claimed originality
  novelty_contract.md       # claimed + surrendered mechanisms
  literature_matrix.csv     # prior studies and exact comparison questions
  claim_ledger.csv          # each sentence -> run / endpoint / exclusions
  freeze/                   # frozen preregistration, git SHAs and seeds
  analysis/                 # fixed estimands + review notes
  release/                  # checked PDF, raw-artifact manifest and checksums
evaluation/venue2027/07_sacmat_2027/
  generate_cohort.py        # deterministic, source-licensed synthetic generator
  run_baselines.py         # matched study arms, isolated DB
  collect_events.py        # immutable observation & backend provenance
  analyze.py               # preregistered, no post-hoc denominator changes
  reproduce.py             # clean-checkout and negative-control verification
tests/venue2027/07_sacmat_2027/
  test_oracle.py            # positive and negative controls
  test_no_leak.py           # PHI, credentials, canary
  test_replay.py            # freeze and raw checksums
  test_faults.py            # adversarial cases and failure classifications
```

## 3. Threat or challenge family matrix

The following classes must each include a controlled negative, legitimate operation, deterministic seed, stable label, and a complete expected/observed trace.

| Family | Setup and oracle | Required evidence |
|---|---|---|
| F01 | Expired delegate role | raw schedule, expected decision, observed decision, run manifest, hash |
| F02 | Policy inheritance conflict | raw schedule, expected decision, observed decision, run manifest, hash |
| F03 | Revoke then regrant with ordering | raw schedule, expected decision, observed decision, run manifest, hash |
| F04 | Purpose mismatch across nested grants | raw schedule, expected decision, observed decision, run manifest, hash |
| F05 | Emergency override with absent approval obligation | raw schedule, expected decision, observed decision, run manifest, hash |

The control labels must be authored and locked independently from the detector/validator being evaluated. If the oracle cannot decide ground truth, mark `INDETERMINATE`, not false positive or true negative.

## 4. Dataset contract and provenance

**Population and scope.** New synthetic policy-delegation histories, not GovMut's 45 mutants or GLHS R4 E15 corpus; source and oracle available under a permissive license.

**Unit of analysis:** unique policy-state history and request pair, with generation seed retained.

**Generation pipeline:** (a) produce a versioned synthetic source fixture; (b) derive task-scoped independent units before any model or algorithm executes; (c) lock train/validation/test if supervised; (d) serialize expected decisions separately from tested code; (e) sign manifest checksums and blinded assignment. Never claim that 1,000 correlated retry events are 1,000 independent patients.

**Minimum run manifest fields** (`manifest.json`): `study_id`, `source_sha`, `harness_sha`, `analyzer_sha`, `git_status`, `backend`, `postgres_version`, `isolation_level`, `hardware`, `python_version`, `seed`, `cohort_sha256`, `protocol_sha256`, `start_utc`, `end_utc`, `observed_errors`, `primary_n_unique`, `secondary_n_retries`, `excluded_with_reason`, `test_mode`, `license`, `ethics`, `result_status`.

**Legal/privacy:** Synthetic patient IDs only, no real clinical prompts, no live credentials, no unauthorized web corpus. When referencing standards or open public datasets, log URLs and redistribution rights. An open public healthcare corpus is NOT automatically unrestricted redistribution.

## 5. Prespecified comparator implementations

Use matched data, identical time budgets, pinned source versions and explicit unit-level pairing. Do not benchmark a toy comparator against production code unless matching feature coverage is documented.

| Arm | Implementation requirements | Non-inferiority/safety control |
|---|---|---|
| B0 | Static ABAC request corpus; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B1 | Random policy transitions without semantic coverage; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B2 | Mutation-oriented GovMut benchmark as separate related work, not data source; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B3 | PolicyTrace semantic transition corpus; pin its implementation and configuration | positive legitimate controls + all challenge classes |

**Fairness:** Where a signed capability or classic OCC baseline provides the same primary decision safety as the proposed method, explicitly surrender any claimed superiority for that endpoint. Confirm baseline authorship/implementation and do not present stub methods as peer systems.

## 6. Execution and measurement plan

**Primary and secondary outcomes:**
1. decision disagreement by semantic class.
2. semantic transition coverage.
3. oracle adjudication completeness.
4. generation/replay runtime.
5. cross-implementation portability.

**Analysis:** Report coverage by independently defined semantic class with Wilson intervals where meaningful; disagreements are inspected, not automatically counted as security breaches.

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

**STOP condition:** If a strong existing ABAC conformance suite covers the same transition classes, publish as incremental tool only if portability/usability advantages are evidenced.

**Risks and mitigations:** Dataset/tool distinctness must be demonstrated; ACM APC and in-person costs may be prohibitive without coverage.

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

**Default decision:** draft-only while experiments are pending. Check ACM Open membership and discretionary APC waiver first; ask host organizers about high-school student support. Avoid assuming waiver approval.

**Format migration:** ACM acmart sigconf double-blind; track labels/limits mandatory.

**Official source:** https://www.sacmat.org/2027/call-for-papers.php. Use the official CFP and author guide again immediately before submission, because fee schedules, anonymization rules and presentation policies can change.



## PSC evaluation extension: to be implemented, not assumed

**Candidate:** PSC-PolicyTrace — Twin-Trace Certification for Temporal Purpose-Based Authorization.

**RQ1:** Can a trace-relative oracle distinguish same-state policy histories that produce different authorized actions?

**Strongest fair comparator:** Cedar policy engine; OpenFGA ReBAC; OPA/Rego; XACML MC/DC mutation tests; pairwise configuration testing.

**Primary:** detected true temporal authorization faults per independently verified mutant family. **Utility/coverage:** false-positive rate, unique coverage per query, oracle runtime.

**Do-not-claim gate:** If equal-budget MC/DC or property-based mutation testing finds the same mutants, no improved test-effectiveness claim.

See `PSC_METHOD_EXTENSION.md` for explicit shadow A/B, certificate, model-ablation and 7 file-level contracts. This is a scientific method proposal, not a certified result.
