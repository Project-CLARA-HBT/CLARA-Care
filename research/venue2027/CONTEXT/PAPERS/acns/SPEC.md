# SoK: What Can Inference Attestation Prove About AI-Visible Context?

**Venue:** ACNS 2027 | **Rank target:** B | **Deadline:** 2027-01-21 cycle 2 full

**Official CFP:** https://acns2027.isg.rhul.ac.uk/calls/papers/

**Research status:** PROSPECTIVE / NOT SUBMISSION READY (2026-11-14)

**Source snapshot:** `research/glhs-r4-novelty-hardening` at `bce92340e190c62208a24aa3304f188080f6fd58`. Frozen historical evidence SHA `9006ac5c5379ead2620e47bc2c924ab4f7d45373`.

## 0. One-page decision

**Core question.** Terms such as provenance, attestation, auditability and model use are frequently conflated. A systematic knowledge synthesis should separate evidence that bytes were assembled, dispatched, delivered, processed or semantically used, and explain which claims each mechanism can actually support.

**Unique contribution.** A reproducible literature selection protocol, a trust-boundary taxonomy with falsifiable proof obligations, and reference adversarial witnesses distinguishing dispatch, provider and semantic claims.

**Track strategy.** Systematization of Knowledge (SoK), if chosen under official guidelines

**Publication cost and mobility.** General (non-student) registration and in-person presentation mandatory; best student award EUR 1,500 is an award, not pre-acceptance funding.

**Funding plan.** Seek affiliated university co-author support or corporate underwriting for registration and UK travel.

**Submission formatting.** ACNS Springer LNCS official format, anonymous submission.

**Hard stop.** Do not submit while the latest GLHS R4 release check fails or if novelty and dataset boundaries overlap an already accepted/submitted manuscript. This specification is a development plan; it is not evidence that an experiment has run.

## 1. Scientific hypotheses, boundaries, falsification

**Goal.** Terms such as provenance, attestation, auditability and model use are frequently conflated. A systematic knowledge synthesis should separate evidence that bytes were assembled, dispatched, delivered, processed or semantically used, and explain which claims each mechanism can actually support.

**Design hypothesis.** Classify claims into ordered evidence strata: reconstruction provenance, server-side assembly, egress bytes, transport delivery, provider-side attestation, and internal semantic use. Specify which transitions require third-party evidence or are unprovable by systems-level receipts alone.

**Pre-registered questions**
1. **RQ1:** Which precise inference-context assertions are evidenced by current software receipts, transport attestations or trusted hardware?
2. **RQ2:** How often do published approaches equate model-visible supply with neural semantic use?
3. **RQ3:** Which adversarial counterexamples invalidate common informal claims under explicit trust assumptions?

**Falsification and negative-result policy.** If claimed strata cannot be distinguished reliably by two independent coders, revise taxonomy and report ambiguity rather than declare consensus. A null effect, lost advantage to a capable baseline, or a counterexample is a valid publication outcome; never filter away unfavorable trials.

**Novelty/overlap firewall.** This is a literature SoK, not a new GLHS deployment or another attestation performance paper. Must include competitors and negative findings; cannot rely primarily on CLARA self-citations. Begin with a full textual comparison against HEALTHINF #97, GLHS R4, GovRed/RIVF, GovMut/SOICT and all other pending 2027 manuscripts. Same underlying code is permitted but same primary contribution or evidence reused as a new study is not. Publish positive and negative overlap findings in the internal `overlap_audit.md`.

## 2. Concrete code and architecture integration

**Design change.** Implement a transparent review dataset of bibliographic metadata, citation trails, double-coded evidence sentences, claim classes, counterexamples and disagreement adjudications. A small proof-of-concept reproduces selected counterexamples against CLARA but is not the paper's central novelty.

**Source areas to inspect; these are pointers, not proof all APIs still exist at HEAD:**
- `research/glhs_journal/q4_r4/literature_matrix_r4.json`
- `research/glhs_journal/q4_r4/novelty_contract_r4.md`
- `research/glhs_journal/q4_r4/theorems_r4.md`
- `docs/formal/`

Implementation artifacts must be additive and isolated to `research/venue2027/04_acns_2027/`, `evaluation/venue2027/04_acns_2027/`, `tests/venue2027/04_acns_2027/`, and `artifacts/venue2027/04_acns_2027/{run_id}/` until their security review passes. Never modify production patient data, never add a research-only bypass flag to deployed pathways, and never put provider credentials in artifacts. Configuration and migrations are reviewed before integration.

**Code integrity prerequisites:** Fix the `GlhsClinicalCommitmentProposal` immutable row update conflict without disabling the immutability event handler. Root error at `services/api/src/clara_api/db/models.py` near line 3040; latest R4 CI had four failing tests and failed the E22 hermetic reproduction. Run a pinned clean-checkout repair verification and record the first green CI SHA. Historical E15--E19 results ran on an SQLite memory backend; do not label these as PostgreSQL benchmarks.

### Proposed module layout

```text
research/venue2027/04_acns_2027/
  README.md                 # scope, protocol links, claimed originality
  novelty_contract.md       # claimed + surrendered mechanisms
  literature_matrix.csv     # prior studies and exact comparison questions
  claim_ledger.csv          # each sentence -> run / endpoint / exclusions
  freeze/                   # frozen preregistration, git SHAs and seeds
  analysis/                 # fixed estimands + review notes
  release/                  # checked PDF, raw-artifact manifest and checksums
evaluation/venue2027/04_acns_2027/
  generate_cohort.py        # deterministic, source-licensed synthetic generator
  run_baselines.py         # matched study arms, isolated DB
  collect_events.py        # immutable observation & backend provenance
  analyze.py               # preregistered, no post-hoc denominator changes
  reproduce.py             # clean-checkout and negative-control verification
tests/venue2027/04_acns_2027/
  test_oracle.py            # positive and negative controls
  test_no_leak.py           # PHI, credentials, canary
  test_replay.py            # freeze and raw checksums
  test_faults.py            # adversarial cases and failure classifications
```

## 3. Threat or challenge family matrix

The following classes must each include a controlled negative, legitimate operation, deterministic seed, stable label, and a complete expected/observed trace.

| Family | Setup and oracle | Required evidence |
|---|---|---|
| F01 | Server constructs context but does not transmit it | raw schedule, expected decision, observed decision, run manifest, hash |
| F02 | Transport retry changes payload after receipt creation | raw schedule, expected decision, observed decision, run manifest, hash |
| F03 | Provider receives content but ignores it | raw schedule, expected decision, observed decision, run manifest, hash |
| F04 | Audit receipt lacks actor or purpose semantics | raw schedule, expected decision, observed decision, run manifest, hash |
| F05 | Provider claims are unverified self-reports | raw schedule, expected decision, observed decision, run manifest, hash |

The control labels must be authored and locked independently from the detector/validator being evaluated. If the oracle cannot decide ground truth, mark `INDETERMINATE`, not false positive or true negative.

## 4. Dataset contract and provenance

**Population and scope.** Public papers identified through a recorded multi-database query and citation snowballing; no pretend corpus size. Synthetic witnesses only for adversarial demonstrations.

**Unit of analysis:** a distinct publication for review statistics; a distinct claim sentence for codebook annotations, clustered within publication.

**Generation pipeline:** (a) produce a versioned synthetic source fixture; (b) derive task-scoped independent units before any model or algorithm executes; (c) lock train/validation/test if supervised; (d) serialize expected decisions separately from tested code; (e) sign manifest checksums and blinded assignment. Never claim that 1,000 correlated retry events are 1,000 independent patients.

**Minimum run manifest fields** (`manifest.json`): `study_id`, `source_sha`, `harness_sha`, `analyzer_sha`, `git_status`, `backend`, `postgres_version`, `isolation_level`, `hardware`, `python_version`, `seed`, `cohort_sha256`, `protocol_sha256`, `start_utc`, `end_utc`, `observed_errors`, `primary_n_unique`, `secondary_n_retries`, `excluded_with_reason`, `test_mode`, `license`, `ethics`, `result_status`.

**Legal/privacy:** Synthetic patient IDs only, no real clinical prompts, no live credentials, no unauthorized web corpus. When referencing standards or open public datasets, log URLs and redistribution rights. An open public healthcare corpus is NOT automatically unrestricted redistribution.

## 5. Prespecified comparator implementations

Use matched data, identical time budgets, pinned source versions and explicit unit-level pairing. Do not benchmark a toy comparator against production code unless matching feature coverage is documented.

| Arm | Implementation requirements | Non-inferiority/safety control |
|---|---|---|
| B0 | Unstructured narrative survey; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B1 | Single-coder classification; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B2 | Two-coder protocol with prespecified taxonomy and adjudication; pin its implementation and configuration | positive legitimate controls + all challenge classes |
| B3 | Public counterexample suite; pin its implementation and configuration | positive legitimate controls + all challenge classes |

**Fairness:** Where a signed capability or classic OCC baseline provides the same primary decision safety as the proposed method, explicitly surrender any claimed superiority for that endpoint. Confirm baseline authorship/implementation and do not present stub methods as peer systems.

## 6. Execution and measurement plan

**Primary and secondary outcomes:**
1. number of screened/eligible papers (after search).
2. inter-rater agreement.
3. taxonomy coverage.
4. replicability of counterexample witnesses.
5. unresolved disagreements.

**Analysis:** Publish inclusion flow, preregistered exclusion reasons, Cohen's kappa with confidence interval, per-stratum claim counts and sensitivity to ambiguous coding.

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

**STOP condition:** If claimed strata cannot be distinguished reliably by two independent coders, revise taxonomy and report ambiguity rather than declare consensus.

**Risks and mitigations:** Missing search corpus and genuinely independent coder(s); cryptographic novelty is not claimed. Literature coverage must be deep enough for ACNS reviewers.

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

**Default decision:** draft-only while experiments are pending. Seek affiliated university co-author support or corporate underwriting for registration and UK travel.

**Format migration:** ACNS Springer LNCS official format, anonymous submission.

**Official source:** https://acns2027.isg.rhul.ac.uk/calls/papers/. Use the official CFP and author guide again immediately before submission, because fee schedules, anonymization rules and presentation policies can change.



## PSC evaluation extension: to be implemented, not assumed

**Candidate:** PSC-EvidenceLattice — A Systematization of Assurance Evidence for Agent-Executed Health Actions.

**RQ1:** Which claims are distinguishable from signed inputs, dispatch receipts, model-output lineage and actual commit-time witnesses?

**Strongest fair comparator:** RATS RFC 9334 claim/evidence/attestation roles; simple checklist review; PROV lineage; independent security reviewer annotations.

**Primary:** auditor classification accuracy on blind independently authored claim corpus. **Utility/coverage:** inter-annotator agreement and abstention/calibration.

**Do-not-claim gate:** If ordinary RATS terminology and a clear checklist give equivalent classification agreement, present as replication/SoK rather than algorithm novelty.

See `PSC_METHOD_EXTENSION.md` for explicit shadow A/B, certificate, model-ablation and 7 file-level contracts. This is a scientific method proposal, not a certified result.
