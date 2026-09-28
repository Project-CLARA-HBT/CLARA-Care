# GLHS R3 Protocol Literature & Novelty Audit Report

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Artifact Path:** `research/glhs_journal/q3_r3/protocol_literature_audit.md`  
**Author / Role:** Agent A — Literature & Novelty  
**Phase:** Phase 4 — Master Prospective Protocol Literature & Novelty Audit  
**Status:** Frozen Prospective Protocol Audit & Baseline Validation  
**Date:** 2026-09-29  
**Primary Target Venue:** Q1–Q3 Health Informatics / Systems Journal (*Journal of Medical Systems* → *Methods of Information in Medicine* → *Health Information Science and Systems*)

---

## 1. Executive Summary & Audit Mandate

In Phase 4 of the GLHS R3 research program, Agent A (Literature & Novelty) conducted a comprehensive, hostile literature and baseline audit of all 15 prospective experiment protocol specifications (**E00 through E14**). The master specification is established in `GLHS_R3_MASTER_SPEC.md` (§7), `GLHS_R3_EXPERIMENT_AND_STATISTICS_PLAN.md`, `PACKAGE_MANIFEST.json`, `research/glhs_journal/q3_r3/novelty_contract.md`, `research/glhs_journal/q3_r3/claim_budget.json`, and `research/glhs_journal/q3_r3/protocols/MASTER_STATISTICAL_FREEZE.json`.

### 1.1 Core Audit Mandate
The objective of this audit is to ensure that:
1. **Literature Anchoring:** Every protocol is explicitly anchored against established peer-reviewed literature across database systems, usage control, capability tokens, provenance, health informatics, dynamic consent, and persistent agent memory.
2. **Surrendered Non-Novelty:** No protocol attempts to claim novelty for established mechanisms (OCC, SSI, PBAC, PCFS/Macaroons, W3C PROV, dynamic consent, hash canonicalization, or temporal snapshots).
3. **Competitive Baseline Integrity (E03):** The minimal token comparator (`MIN_READSET_TOKEN`) is constructed as a fair, competitive systems baseline modeled on Macaroons (Birgisson et al., NDSS 2014) and Amazon DynamoDB conditional check writes, rather than an artificial strawman.
4. **Backend Truthfulness (E04 & E09):** Real PostgreSQL ACID transaction execution is strictly separated from in-memory simulations. The Python `SimulatedPartitionCoordinator` and thread-lock mocks from R2 are completely prohibited from supporting headline PostgreSQL claims.
5. **Real Provider Accounting (E11 & E12):** Model utility and error sensitivity protocols strictly enforce immutable provider accounting ledgers (recording requested model IDs, reported model IDs, tokens, latencies, and request IDs), prohibiting mock or synthetic runs from masquerading as provider evidence.
6. **Clinical Claim Isolation (E13):** Synthetic task evaluations (e.g., Synthea) and retrospective cohort mappings (eICU, MIMIC-IV) are strictly isolated from human clinical efficacy or diagnostic claims.
7. **Strict Claim Budget Adherence:** Every protocol adheres to the strict Claim Budget defined in `claim_budget.json`, eliminating all forbidden keywords ("first", "TOCTOU eliminated", "tamper-proof", "formally proven secure", "clinically safe", "doctor replacement", "THSS uniquely necessary", "independent peer review by internal agents").

---

## 2. Core Integrity & Baseline Mandates Audit

### 2.1 Mandate 1: E03 Competitive Baseline (`MIN_READSET_TOKEN`) vs Artificial Strawman
A frequent failure mode in systems research is testing against a hobbled baseline to manufacture artificial superiority. Agent A audited the E03 comparator specification to verify that `MIN_READSET_TOKEN` is a strong, defensible, and literature-grounded alternative.

```
+--------------------------------------------------------------------------------------------------+
|                                    COMPARATOR ARCHITECTURE IN E03                                |
+------------------------------------+-----------------------------------+-------------------------+
| Baseline Variant                   | Literature Foundation             | Mechanism Properties    |
+------------------------------------+-----------------------------------+-------------------------+
| GLHS Full GRWC                     | Master Spec §2, GRWC Invariant    | Two-digest server-bound |
|                                    | (Kung & Robinson 1981, MemTX 2026)| Lineage + Revalidation  |
+------------------------------------+-----------------------------------+-------------------------+
| MIN_READSET_TOKEN (Unsigned)       | Amazon DynamoDB Conditional Writes| Compact read-set vector |
|                                    | (Sivasubramanian 2012)            | Key-version pairs       |
+------------------------------------+-----------------------------------+-------------------------+
| HMAC_READSET_TOKEN (Symmetric)     | Proof-Carrying File System        | Tamper-evident digest   |
|                                    | (Garg et al., IEEE S&P 2010)      | Server-signed read-set  |
+------------------------------------+-----------------------------------+-------------------------+
| MACAROON_CAVEAT_TOKEN (Delegated)  | Macaroons: Cookies with Caveats   | HMAC chain with context |
|                                    | (Birgisson et al., NDSS 2014)     | caveats & attenuation   |
+------------------------------------+-----------------------------------+-------------------------+
```

* **Literature Grounding:**
  - *Macaroons (Birgisson et al., NDSS 2014)*: Contextual authorization tokens carrying attenuated caveats. In E03, Macaroons represent a direct capability-based alternative where the read-set versions, purpose, and snapshot expiration are chained into cryptographic caveats.
  - *DynamoDB Conditional Writes (Sivasubramanian, 2012)*: Unsigned/compact attribute-version predicates sent at write time to enforce optimistic consistency.
  - *PCFS (Garg et al., IEEE S&P 2010)*: Proof-carrying access tokens checked at storage admission.
* **Fairness Verification:**
  - `MIN_READSET_TOKEN` is **not** a hollow mock; it carries the full entity key and version vector observed during data retrieval and evaluates conditional matches within the commit transaction.
  - `HMAC_READSET_TOKEN` prevents client tampering with the read-set predicate using standard symmetric cryptography.
  - `MACAROON_CAVEAT_TOKEN` supports first-party caveats for actor, role, purpose, and time-to-live.
* **Trade-Off & Equivalence Policy:**
  - E03 explicitly measures serialized payload size (bytes), validation CPU time ($\mu\text{s}$), database read/write IOPS, and lineage reconstructability.
  - **Equivalence Gate Rule:** If `MIN_READSET_TOKEN` or `MACAROON_CAVEAT_TOKEN` achieves identical safety against race conditions and invalid admissions with lower byte/CPU overhead, GLHS R3 commits to **publishing the equivalence prominently** and narrowing its scientific contribution to the formalization of the GRWC invariant and its operational semantics, explicitly disclaiming mechanism superiority.

### 2.2 Mandate 2: E04 & E09 Live PostgreSQL Execution vs In-Memory Simulation Boundary
In the prior R2 iteration, concurrency benchmarks and TOCTOU evaluations utilized an in-memory `SimulatedPartitionCoordinator` with Python `threading.Lock` primitives. Agent A verified the complete replacement of simulated backends for all headline PostgreSQL claims.

* **Literature Grounding:**
  - *Serializable Snapshot Isolation in PostgreSQL (Cahill et al., SIGMOD 2008; Ports & Grittner, PVLDB 2012)*: PostgreSQL's production SSI engine detects read-write anti-dependency cycles (rw-antidependencies) via `SIREAD` locks.
* **Audit Verifications:**
  - **E04 (Generated TOCTOU):** The protocol specifies live PostgreSQL 16 server sessions with the production `PostgresCommitKernel`, executing actual SQL transactions (`BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE`, row-level `SELECT ... FOR UPDATE`, and transactional version checks). It mandates $N = 1,024$ unique logical schedules.
  - **E09 (Write Contention & Concurrency):** Multi-worker write benchmarks run against real PostgreSQL database instances across a worker grid ($W \in \{1, 2, 4, 8, 16, 32, 64\}$) under 10 clinical workload contention patterns.
  - **Simulation Labeling (NFR-08, Gate G1):** Python-based thread lock simulations are strictly relegated to local unit smoke tests. Any artifact or table derived from simulation is explicitly labeled `SIMULATION_NOT_PRODUCTION` and cannot support manuscript claims regarding PostgreSQL throughput, latency, or concurrency.

### 2.3 Mandate 3: E11 & E12 Real Provider Accounting & Sensitivity
To prevent the misrepresentation of synthetic or local LLM completions as commercial provider benchmarks, Agent A verified the strict provider accounting rules governing E11 and E12.

* **Literature Grounding:**
  - *LongMemEval (ICLR 2025)* & *FUTURE-AI (BMJ 2025)*: Benchmark utility and governance evaluation in foundation models.
* **Audit Verifications:**
  - **Immutable Provider Ledger:** E11 mandates persistence of an immutable `provider_ledger.jsonl` recording `requested_model_id`, `reported_model_id`, provider request ID, exact prompt tokens, completion tokens, latency, and raw response bytes.
  - **Prohibition of Mock Data (Gate G2):** Synthetic completion generators (e.g., local Markov or random text generators) are strictly prohibited from generating provider comparison metrics. If live provider execution is unavailable due to credentials or budget, E11 is marked `NOT_RUN`, and no provider utility claim is made.
  - **Equivalence Testing Rigor:** E11 implements Schuirmann's Two One-Sided Tests (TOST) with a prospective equivalence margin ($\delta = 0.02$, $\alpha = 0.05$, $N = 384$ paired subjects, power $\ge 80\%$). It forbids asserting equivalence from non-significant $p$-values ($p > 0.05$).
  - **E12 Error Taxonomy:** Directly consumes the raw response ledger from E11 across 12 mutually exclusive error classes (`invalid_json`, `schema_mismatch`, `truncation`, `refusal`, `empty_response`, `provider_error`, `wrong_model`, `timeout`, `content_format_violation`, `semantic_failure`, `rate_limit`, `unclassified`), reporting Intention-To-Treat (ITT) R0 primary failure rates alongside R1 (repair), R2 (retry), and R3 (fallback) recovery pipelines.

### 2.4 Mandate 4: E13 Synthetic Task Isolation & Clinical Claim Isolation
Agent A audited E13 to verify that external cohort validation remains strictly within descriptive systems engineering boundaries and does not claim medical efficacy.

* **Literature Grounding:**
  - *MIMIC-IV (Johnson et al., Sci Data 2023)*, *eICU-CRD (Pollard et al., Sci Data 2018)*, *Synthea (Walonoski et al., JAMIA 2018)*.
* **Audit Verifications:**
  - **Descriptive Systems Scope:** E13 evaluates schema canonicalization, snapshot reconstruction completeness, and dependency vector extraction across 4 heterogeneous datasets (eICU demo, Synthea synthetic cohort, MIMIC-IV ICU demo, Diabetes 130-US Hospitals).
  - **Synthetic Isolation:** Synthea data is explicitly designated `SYNTHETIC_COHORT_NOT_HUMAN_CLINICAL`.
  - **Clinical Non-Efficacy Invariant:** E13 is strictly forbidden from asserting clinical safety, diagnostic precision, treatment efficacy, or clinician replacement (complying with Claim Budget Category `CLINICAL_EFFICACY`).
  - **Human Review Gate:** Any human clinician evaluation requires actual human expert panels; in their absence, human review is marked `NOT_RUN_HUMAN_UNAVAILABLE`. Internal LLM subagents are labeled internal verification tooling, never independent human reviewers.

---

## 3. Protocol-by-Protocol Detailed Literature & Novelty Audit (E00–E14)

```
====================================================================================================
GLHS R3 EXPERIMENT PROTOCOL AUDIT MATRIX (E00–E14)
====================================================================================================
```

### E00 — Literature, Claim Budget, and Code Contract Freeze
* **Priority / Backend:** P0 / Static Audit Ledger
* **Primary Research Question:** What is actually novel, and is the manuscript claim budget fully synchronized with codebase implementation capabilities?
* **Prior Art & Literature Anchors:**
  - Kung & Robinson (*ACM TODS 1981*): Optimistic Concurrency Control.
  - Cahill et al. (*ACM SIGMOD 2008*) / Ports & Grittner (*PVLDB 2012*): Serializable Snapshot Isolation.
  - Agrawal et al. (*VLDB 2002*): Hippocratic Databases.
  - Birgisson et al. (*NDSS 2014*): Macaroons Contextual Capabilities.
  - Green et al. (*PODS 2007*): Provenance Semirings.
  - MemTX / MemTxn (*arXiv 2026*): Transactional Agent Memory.
* **Novelty Boundary & Differentiation:** Establishes the formal boundary of GRWC. Confirms that GLHS R3 surrenders all standalone claims to OCC, SSI, PBAC, PCFS, PROV, dynamic consent, hash commitments, and bitemporality.
* **Claim Budget Verification:** Verified compliant. Enforces the prospective freeze of `novelty_contract.md` and `claim_budget.json`.
* **Audit Status:** **APPROVED (P0 Core)**

---

### E01 — Inference Consumption Integrity Protocol
* **Priority / Backend:** P0 / Production Path + PostgreSQL 16
* **Primary Research Question:** Was the claimed governed disclosure projection actually supplied to the inference pass that generated the proposal lineage?
* **Prior Art & Literature Anchors:**
  - Bates et al. (*USENIX Security 2015*): Linux Provenance Modules (LPM).
  - Wang et al. (*ACL 2025*): Evaluating and mitigating privacy leakage in LLM agent memory.
  - LongMemEval (*ICLR 2025*): Evaluating long-term memory retrieval in language agents.
* **Novelty Boundary & Differentiation:** Traditional agent memory checks whether cited facts exist in a global knowledge base. E01 evaluates whether a persistent write proposal descends from an inference context that received the *exact* model-visible projection digest ($\mathcal{H}_{\text{proj}}$) and request envelope digest ($\mathcal{H}_{\text{env}}$), rejecting unconsumed snapshots, snapshot substitutions, and prompt drift across 10 adversarial attack families ($N = 640$ adversarial, $N = 128$ clean controls).
* **Claim Budget Verification:** Verified compliant. Target invalid-admission rate is $0.0$ (projected Clopper-Pearson 95% UCB $\le 0.578\%$). No claims of "tamper-proof" or "unhackable" systems.
* **Audit Status:** **APPROVED (P0 Headline Novelty)**

---

### E02 — Binding Component Factorial Ablation
* **Priority / Backend:** P0 / PostgreSQL 16
* **Primary Research Question:** Which specific components of the GRWC binding are necessary to enforce exact-disclosure admission within the tested threat model?
* **Prior Art & Literature Anchors:**
  - Box, Hunter & Hunter (*Statistics for Experimenters*, Wiley 2005): Full Factorial Designs.
  - Agrawal et al. (*VLDB 2002*): Attribute-level privacy disclosure.
* **Novelty Boundary & Differentiation:** Evaluates a $2^4$ factorial design across 4 discrete components: (1) Snapshot Identity, (2) Projection Digest, (3) Disclosed Evidence Membership, and (4) Inference Binding Continuity ($N = 352$ schedules). Confirms that a component is designated "necessary" if and only if its isolated ablation exposes a targeted counterexample while clean controls remain $100\%$ admissible.
* **Claim Budget Verification:** Verified compliant. No claims of "optimal" or "unique" architecture.
* **Audit Status:** **APPROVED (P0 Rigor)**

---

### E03 — Minimal Token / Capability Comparator Baseline
* **Priority / Backend:** P0 / PostgreSQL 16
* **Primary Research Question:** Could a simpler mechanism (e.g., minimal unsigned token, HMAC, or Macaroon) satisfy the read-to-write continuity invariant under identical schedule replay?
* **Prior Art & Literature Anchors:**
  - Birgisson et al. (*NDSS 2014*): Macaroons: Cookies with Contextual Caveats for Decentralized Authorization.
  - Garg et al. (*IEEE S&P 2010*): A Proof-Carrying File System (PCFS).
  - Sivasubramanian (*ACM TOS 2012*): Amazon DynamoDB: A Scalable, Highly Available NoSQL Database Service (Conditional Writes).
* **Novelty Boundary & Differentiation:** Directly contrasts GLHS full GRWC against 3 competitive capability baselines: (1) `MIN_READSET_TOKEN`, (2) `HMAC_READSET_TOKEN`, and (3) `MACAROON_CAVEAT_TOKEN` ($N = 352$ schedules). Evaluates trade-offs across serialized bytes, validation CPU, database IOPS, and lineage reconstructability.
* **Claim Budget Verification:** Verified compliant. Explicitly commits to reporting equivalence prominently if the minimal token matches GLHS safety guarantees.
* **Audit Status:** **APPROVED (P0 Competitive Baseline)**

---

### E04 — Generated TOCTOU & Transactional Kernel Assurance
* **Priority / Backend:** P0 / Live PostgreSQL 16 (Serializable)
* **Primary Research Question:** Does the PostgreSQL commit kernel strictly reject stale governance/state in tested schedules under live serializable execution?
* **Prior Art & Literature Anchors:**
  - Cahill et al. (*ACM SIGMOD 2008*): Serializable Snapshot Isolation in PostgreSQL.
  - Ports & Grittner (*PVLDB 2012*): Serializable Snapshot Isolation in PostgreSQL.
  - Bishop & Dilger (*ACM Computing Surveys 1996*): Checking for Race Conditions in File Systems (TOCTOU).
* **Novelty Boundary & Differentiation:** Exercises live PostgreSQL 16 connections under Serializable isolation and row-level locking across $N = 1,024$ unique logical race schedules. Evaluates race conditions where clinical state, consent directives, or system policies mutate between inference dispatch ($t_1$) and write admission ($t_3$).
* **Claim Budget Verification:** Verified compliant. Mandates reporting $0/1024$ with Clopper-Pearson 1-sided 95% UCB ($\le 0.292\%$). Strict prohibition against stating "TOCTOU eliminated" or "race conditions impossible".
* **Audit Status:** **APPROVED (P0 Concurrency Assurance)**

---

### E05 — Dependency Completeness & Mutation Analysis
* **Priority / Backend:** P0 / PostgreSQL 16
* **Primary Research Question:** Are semantically required dependencies strictly derived and enforced at commit time, prohibiting omission-corrupted dependency vectors while admitting conservative supersets with zero false-stale aborts?
* **Prior Art & Literature Anchors:**
  - Fekete et al. (*ACM TODS 2005*): Making snapshot isolation serializable (Write-Skew Analysis).
  - DeMillo, Lipton & Sayward (*IEEE Computer 1978*): Hints on Test Data Selection: The Theory of Mutation Analysis.
* **Novelty Boundary & Differentiation:** Enforces operation-derived semantic dependency contracts $D(P)$. Evaluates $N = 312$ execution runs across 9 mutation classes (M1: omit entity, M2: add irrelevant, M3: mutate key, M4: mutate access, M5: mutate version, M6: write-skew, M7: unrelated replace, M8: omit evidence, M9: omit governance) alongside clean baseline and conservative superset controls ($N = 108$ valid, $N = 204$ invalid).
* **Claim Budget Verification:** Verified compliant. Statistical bounds: Invalid admission Clopper-Pearson UCB $\le 1.46\%$; Valid superset false-stale aborts $= 0.0$.
* **Audit Status:** **APPROVED (P0 Semantic Rigor)**

---

### E06 — Anti-Downgrade & Lineage Anti-Laundering Protocol
* **Priority / Backend:** P0 / API Service + PostgreSQL 16
* **Primary Research Question:** Can bound lineage be laundered or downgraded across audited routes and frozen attack patterns?
* **Prior Art & Literature Anchors:**
  - Saltzer & Schroeder (*IEEE Proceedings 1975*): The Protection of Information in Computer Systems (Complete Mediation).
  - Birgisson et al. (*NDSS 2014*): Capability attenuation and non-bypassable caveat verification.
* **Novelty Boundary & Differentiation:** Audits all API gateway and internal service endpoints against 11 attack patterns ($N = 250$ adversarial laundering attempts, $N = 50$ positive controls), verifying that human clinician review or post-processing cannot strip the root inference binding ID to route writes through a weak base-only path.
* **Claim Budget Verification:** Verified compliant. Target invalid laundering admission rate $= 0.0$ (Wilson UCB $\le 1.07\%$). Claims bounded strictly to audited routes.
* **Audit Status:** **APPROVED (P0 Anti-Laundering)**

---

### E07 — Canonicalization & Cross-Runtime Serialization Protocol
* **Priority / Backend:** P0 / Python 3.12 + Node.js (RFC 8785)
* **Primary Research Question:** Are JSON canonicalization commitments ($\mathcal{H}_{\text{proj}}$ and $\mathcal{H}_{\text{env}}$) deterministic and bit-for-bit identical across Python and JavaScript runtimes?
* **Prior Art & Literature Anchors:**
  - Rundgren, Jordan & Erdtman (*RFC 8785, 2020*): JSON Canonicalization Scheme (JCS).
  - Merkle (*IEEE S&P 1980*): Protocols for Public Key Cryptosystems.
* **Novelty Boundary & Differentiation:** Verifies cross-runtime deterministic serialization across $N = 35$ standard RFC 8785 and edge-case vectors (floats, negative zero `-0.0`, Unicode UTF-8 multi-byte sequences, nested key order, surrogate pairs).
* **Claim Budget Verification:** Verified compliant. Zero bit-drift allowed ($100\%$ concordance).
* **Audit Status:** **APPROVED (P0 Determinism)**

---

### E08 — Formal Bounded Assurance & State Space Exploration
* **Priority / Backend:** P0 / TLA+ Model Checker (TLC)
* **Primary Research Question:** Are all formal state invariants counterexample-free within bounded BFS exploration depth?
* **Prior Art & Literature Anchors:**
  - Lamport (*Specifying Systems*, Addison-Wesley 2002): The TLA+ Language and Tools for Hardware and Software Engineers.
  - Newcombe et al. (*Communications of the ACM 2015*): How Amazon Web Services Uses Formal Methods.
* **Novelty Boundary & Differentiation:** Extends the formal specification (`GLHS_GSA.tla`) with explicit inference binding states and evaluates invariants $I_{01}$ through $I_{15}$ across Depth 5 ($21,475$ states) and Depth 6 ($69,120$ states).
* **Claim Budget Verification:** Verified compliant. Explicitly phrased as "bounded exhaustive exploration through depth $d=6$". Strict prohibition against claiming "universal mathematical proof" or "formally proven secure".
* **Audit Status:** **APPROVED (P0 Formal Assurance)**

---

### E09 — Concurrency & Write Contention Benchmark
* **Priority / Backend:** P1 / PostgreSQL 16 Server
* **Primary Research Question:** What contention, latency, and false-stale abort behavior occurs under multi-worker clinical write workloads?
* **Prior Art & Literature Anchors:**
  - Gray & Reuter (*Transaction Processing*, Morgan Kaufmann 1993): Concurrency Control and Recovery.
  - Ports & Grittner (*PVLDB 2012*): Serializable Snapshot Isolation Performance in PostgreSQL.
* **Novelty Boundary & Differentiation:** Benchmarks live PostgreSQL 16 transactions across a 7-point worker grid ($W \in \{1, 2, 4, 8, 16, 32, 64\}$) under 10 clinical workload contention patterns ($N = 350$ trials, 5 replications per cell), evaluating transactions committed per second (TPS), latency quantiles (p50, p95, p99), and advisory lock wait times.
* **Claim Budget Verification:** Verified compliant. Prohibits Python thread-lock mocks. Requires live database instance attestation.
* **Audit Status:** **APPROVED (P1 Systems Performance)**

---

### E10 — Full-Stack System Performance & Latency Cost
* **Priority / Backend:** P1 / HTTP REST + PostgreSQL 16
* **Primary Research Question:** What is the end-to-end full-stack latency and payload overhead of GRWC commitment checking over HTTP?
* **Prior Art & Literature Anchors:**
  - Fielding (*PhD Dissertation, UC Irvine 2000*): Architectural Styles and the Design of Network-based Software Architectures (REST).
* **Novelty Boundary & Differentiation:** Measures end-to-end HTTP request-response latency and serialized payload expansion across 6 core REST operations ($N = 600$ requests, 100 per class), isolating HTTP transport, RBAC middleware, and PostgreSQL commitment checking overhead.
* **Claim Budget Verification:** Verified compliant. Purely descriptive latency profile reporting.
* **Audit Status:** **APPROVED (P1 Systems Performance)**

---

### E11 — Two-Model Clinical Utility & Governance Equivalence
* **Priority / Backend:** P1 / Real LLM Providers (DeepSeek Pro / Flash)
* **Primary Research Question:** Does strict governed context preserve benchmark clinical utility compared to un-governed full authorized history?
* **Prior Art & Literature Anchors:**
  - LongMemEval (*ICLR 2025*): Evaluating memory retrieval and reasoning in long-context models.
  - Schuirmann (*Journal of Pharmacokinetics and Biopharmaceutics 1987*): A comparison of the Two One-Sided Tests (TOST) Procedure and the Power Approach for Assessing the Equivalence of Average Bioavailability.
* **Novelty Boundary & Differentiation:** Prospectively powered TOST equivalence design ($N = 384$ paired subjects, equivalence margin $\delta = \pm 0.02$, $\alpha = 0.05$, power $\ge 80\%$) comparing strict governed context (THSS snapshot bound) against unbounded authorized profile history.
* **Claim Budget Verification:** Verified compliant. Mandates immutable provider ledger recording `requested_model_id` and `reported_model_id`. Strictly forbids inferring equivalence from non-significant $p$-values. If provider run is omitted, marked `NOT_RUN`.
* **Audit Status:** **APPROVED (P1 Model Utility)**

---

### E12 — Malformed Response Sensitivity & Error Taxonomy Protocol
* **Priority / Backend:** P1 / Actual E11 Response Ledger
* **Primary Research Question:** How do real LLM response failures impact clinical utility estimates under ITT vs prespecified recovery?
* **Prior Art & Literature Anchors:**
  - FUTURE-AI (*BMJ 2025*): Guiding principles for trustworthy clinical artificial intelligence.
  - Schulz et al. (*CONSORT-AI / SPIRIT-AI*, *Nature Medicine 2020*): Reporting guidelines for clinical trial protocols for AI interventions (Intention-To-Treat analysis).
* **Novelty Boundary & Differentiation:** Evaluates $N = 768$ model completions from the actual E11 ledger across a 12-class error taxonomy, measuring primary ITT failure rates (R0) and deterministic recovery success across R1 (JSON repair), R2 (single retry), and R3 (fallback escalation).
* **Claim Budget Verification:** Verified compliant. Prohibits simulated 10% error injections for headline claims; requires derivation from real provider ledger.
* **Audit Status:** **APPROVED (P1 Error Sensitivity)**

---

### E13 — External Cohort Generalizability & Source-Disjoint Validation
* **Priority / Backend:** P2 / External Cohort Datasets (eICU, Synthea, MIMIC-IV, Diabetes)
* **Primary Research Question:** Does snapshot reconstruction and GRWC governance generalize across source-disjoint external cohorts?
* **Prior Art & Literature Anchors:**
  - Johnson et al. (*Scientific Data 2023*): MIMIC-IV, a freely accessible electronic health record dataset.
  - Pollard et al. (*Scientific Data 2018*): The eICU Collaborative Research Database.
  - Walonoski et al. (*JAMIA 2018*): Synthea: An approach, method, and software mechanism for generating realistic synthetic patients.
* **Novelty Boundary & Differentiation:** Evaluates schema mapping fidelity, snapshot reconstruction completeness, and dependency vector extraction across 4 external datasets ($N = 4$ cohorts).
* **Claim Budget Verification:** Verified compliant. Synthea explicitly designated synthetic. Strictly prohibits clinical diagnostic or medical safety claims. If human clinician review is absent, designated `NOT_RUN_HUMAN_UNAVAILABLE`.
* **Audit Status:** **APPROVED (P2 Generalizability)**

---

### E14 — Reproduction Audit & SHA-256 Hash Verification
* **Priority / Backend:** P0 / Fresh Checkout Environment
* **Primary Research Question:** Can an independent third party recover and reproduce every central paper claim from a fresh repository checkout?
* **Prior Art & Literature Anchors:**
  - ACM Artifact Review and Badging Version 1.1 (*Association for Computing Machinery 2020*): Artifact Available, Functional, and Replicated standards.
  - Peng (*Science 2011*): Reproducible Research in Computational Science.
* **Novelty Boundary & Differentiation:** Implements automated verification of 100% SHA-256 hashes of prospective protocol definitions, table/figure generation scripts, raw byte availability, and claim budget linter checks.
* **Claim Budget Verification:** Verified compliant. Gate fails if any claim wording violates `claim_budget.json` or if raw artifact bytes are unavailable.
* **Audit Status:** **APPROVED (P0 Reproducibility Gate)**

---

## 4. Cross-Cutting Claim Budget & Forbidden Terms Verification

Agent A executed a comprehensive regex and policy check against all 15 protocol definitions and their corresponding specification documents, verifying compliance with the 7 forbidden categories in `claim_budget.json`:

```
+---------------------------------------------------------------------------------------------------+
|                              CLAIM BUDGET REGEX COMPLIANCE AUDIT                                  |
+--------------------------------+--------------------------------------+---------------------------+
| Forbidden Category             | Target Prohibited Patterns           | Audit Finding / Status    |
+--------------------------------+--------------------------------------+---------------------------+
| 1. PRIORITY_OR_FIRST           | "first provenance-aware",            | ZERO MATCHES              |
|                                | "first transactional agent memory",  | PASS (All claims bounded) |
|                                | "pioneering governed architecture"   |                           |
+--------------------------------+--------------------------------------+---------------------------+
| 2. ABSOLUTE_SECURITY           | "TOCTOU eliminated", "tamper-proof", | ZERO MATCHES              |
|                                | "formally proven secure",            | PASS (Statistical UCB     |
|                                | "unhackable", "bulletproof"          | and bounded BFS used)     |
+--------------------------------+--------------------------------------+---------------------------+
| 3. CLINICAL_EFFICACY           | "clinically safe", "fda approved",   | ZERO MATCHES              |
|                                | "doctor replacement", "proven safe"  | PASS (Systems invariant)  |
+--------------------------------+--------------------------------------+---------------------------+
| 4. MECHANISM_UNIQUENESS        | "THSS is uniquely necessary",        | ZERO MATCHES              |
|                                | "only viable architecture"           | PASS (E03 comparator open)|
+--------------------------------+--------------------------------------+---------------------------+
| 5. UNBACKED_PROVIDER_CLAIM     | Unbacked provider efficacy or        | ZERO MATCHES              |
|                                | equivalence without provider ledger  | PASS (Provider ledger req)|
+--------------------------------+--------------------------------------+---------------------------+
| 6. SIMULATION_AS_PRODUCTION    | Simulated thread-locks presented as  | ZERO MATCHES              |
|                                | live PostgreSQL performance          | PASS (PostgreSQL live req)|
+--------------------------------+--------------------------------------+---------------------------+
| 7. INTERNAL_AGENT_ADJUDICATION | Internal LLM agents described as     | ZERO MATCHES              |
|                                | "independent human peer reviewers"  | PASS (Internal tooling)   |
+--------------------------------+--------------------------------------+---------------------------+
```

---

## 5. Summary Matrix & Audit Verdicts

```
+-----+-----------------------------------+----------+--------------------+--------------------------------+------------------+
| ID  | Experiment Title                  | Priority | Backend            | Primary Literature Anchor      | Audit Verdict    |
+-----+-----------------------------------+----------+--------------------+--------------------------------+------------------+
| E00 | Literature & Claim Freeze         | P0       | Static Audit       | Kung 1981, Cahill 2008, MemTX  | APPROVED         |
| E01 | Inference Consumption Integrity   | P0       | Live PG + Kernel   | LPM (2015), LongMemEval (2025) | APPROVED         |
| E02 | Binding Factorial Ablation        | P0       | PostgreSQL 16      | Box et al. (2005), Agrawal     | APPROVED         |
| E03 | Minimal Token Comparator          | P0       | PostgreSQL 16      | Macaroons (2014), DynamoDB     | APPROVED (EQUIV) |
| E04 | Generated TOCTOU Assurance        | P0       | Live PG (SSI)      | Cahill 2008, Ports 2012        | APPROVED         |
| E05 | Dependency Completeness           | P0       | PostgreSQL 16      | Fekete (2005), DeMillo (1978)  | APPROVED         |
| E06 | Anti-Downgrade & Anti-Laundering  | P0       | API + PG 16        | Saltzer (1975), Macaroons      | APPROVED         |
| E07 | Canonicalization (RFC 8785)       | P0       | Python + Node.js   | RFC 8785 (2020), Merkle (1980) | APPROVED         |
| E08 | Formal Bounded Model Checking     | P0       | TLA+ (TLC)         | Lamport (2002), Newcombe 2015  | APPROVED (BOUND) |
| E09 | Write Contention Concurrency      | P1       | Live PG 16 Server  | Gray & Reuter (1993), Ports    | APPROVED         |
| E10 | Full-Stack HTTP Performance       | P1       | HTTP REST + PG 16  | Fielding (2000) REST           | APPROVED         |
| E11 | Two-Model Clinical Utility        | P1       | Real Providers     | LongMemEval, Schuirmann TOST   | APPROVED (LEDGER)|
| E12 | Malformed Response Sensitivity    | P1       | Actual E11 Ledger  | FUTURE-AI (2025), CONSORT-AI   | APPROVED         |
| E13 | External Cohort Validation        | P2       | eICU/MIMIC/Synthea | MIMIC-IV, eICU, Synthea        | APPROVED (DESCR) |
| E14 | Public Reproduction Audit         | P0       | Fresh Checkout     | ACM Artifact Badging (2020)    | APPROVED         |
+-----+-----------------------------------+----------+--------------------+--------------------------------+------------------+
```

---

## 6. Phase 4 Literature & Novelty Sign-Off

### 6.1 Formal Declaration
Agent A (Literature & Novelty) hereby certifies that:
1. All 15 experiment protocols (E00–E14) in `MASTER_STATISTICAL_FREEZE.json` and `research/glhs_journal/q3_r3/protocols/` are rigorously grounded in established database systems, security capability, usage control, clinical provenance, and agent memory literature.
2. The core novelty boundary is strictly and conservatively confined to **Governed Read-to-Write Continuity (GRWC)** / **Exact-Disclosure Admission**.
3. All baseline comparators (especially E03 `MIN_READSET_TOKEN` and Macaroon caveat tokens) are fair, competitive, and literature-derived.
4. Live PostgreSQL execution, real provider accounting ledgers, and descriptive external cohort boundaries are strictly enforced.
5. All protocol descriptions are 100% free of forbidden claims, priority assertions, absolute security wording, and clinical efficacy overclaims.

### 6.2 Downstream Directives for Phase 5 Execution
- **Agent B (Systems / Formal):** Ensure implementation contracts strictly match the formal invariants ($I_{01}-I_{15}$) verified in E00 and E08.
- **Agent C (Experiment / Statistics):** Enforce exact Clopper-Pearson / Wilson upper confidence bounds and TOST equivalence rules during Phase 5 execution.
- **Agent D (Implementation / Reproducibility):** Maintain bit-for-bit SHA-256 seal verification and ensure all raw execution bytes are stored in publicly retrievable artifact directories.
- **Agent E (Hostile Reviewer):** Continue enforcing automated claim budget linting (`scripts/ops/lint_glhs_claims.py`) on all derived manuscript text and figures.

```text
[PASS] Protocol literature and novelty audit completed successfully.
[PASS] All 15 protocols (E00-E14) validated against literature anchors.
[PASS] E03 Macaroon/DynamoDB competitive baseline certified fair and non-strawman.
[PASS] E04/E09 live PostgreSQL backend truthfulness certified.
[PASS] E11/E12 real provider accounting ledger invariants certified.
[PASS] E13 synthetic task isolation and clinical non-efficacy certified.
[PASS] Zero claim budget violations across all protocol definitions.
```
