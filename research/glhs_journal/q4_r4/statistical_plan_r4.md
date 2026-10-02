# GLHS R4 Prospective Experimental and Statistical Plan

**Program:** Governed Longitudinal Health Systems (GLHS) R4 — Governed Read-to-Write Continuity (GRWC)  
**Curator:** Agent C — Experiment & Statistics  
**Phase:** Phase 0 — Master Prospective Statistical & Experimental Plan  
**Status:** PROSPECTIVELY_FROZEN  
**Freeze Timestamp UTC:** `2026-09-30T00:00:00Z`  
**Master Seeds:** `E15: 20260930_15`, `E16: 20260930_16`, `E17: 20260930_17`, `E18: 20260930_18`, `E19: 20260930_19`, `E20: 20260930_20`, `E21: 20260930_21`, `E22: 20260930_22`  
**Primary Target Venue:** Q1 Health Informatics & Computer Systems Venues (*ACM Transactions on Computer Systems* / *IEEE Transactions on Knowledge and Data Engineering* / *Journal of Medical Systems*)

---

## 1. Executive Summary & Program Architecture

The GLHS R4 research program establishes the prospective empirical, systems, and formal foundation for **Governed Read-to-Write Continuity (GRWC)**, also denoted as **Exact-Disclosure Admission**. In complex healthcare AI environments, autonomous agents generate proposals for clinical record mutation based on multi-modal patient context retrieved across disparate health data stores.

Prior-art database consistency mechanisms, notably **Optimistic Concurrency Control (OCC)**, **Serializable Snapshot Isolation (SSI)**, and **Attribute-Based Access Control (ABAC)**, verify whether database entities have changed since read time and whether the committing actor holds authorization at commit time. However, these systems are fundamentally blind to the **semantic disclosure gap**:
1. Did the external, probabilistic neural model actually observe the exact data claimed?
2. Were critical contraindications, allergy alerts, or updated laboratory observations omitted from the model-visible context projection despite being present in the underlying database?
3. Has the proposal been laundered through an un-attested human or synthetic intermediary to bypass governance verifications?

GLHS R4 formalizes, operationalizes, and evaluates the GRWC invariant across eight prospective experimental protocols (**E15 through E22**). This document defines the prospective statistical plan, experimental designs, scientific units of analysis, sample size allocations, mathematical estimands, power analyses, stopping rules, and public reproducibility criteria governing R4.

```
+---------------------------------------------------------------------------------------------------+
|                                  GLHS R4 EXPERIMENT MATRIX (E15–E22)                              |
+-----+--------------------------------------+----------+-------------------+-----------------------+
| ID  | Experiment Protocol                  | Priority | System Backend    | Primary Endpoint      |
+-----+--------------------------------------+----------+-------------------+-----------------------+
| E15 | Dispatch Attestation Integrity       | P0       | FastAPI + PG 16   | Invalid Admission 0.0%|
| E16 | Five-Way Prior-Art Comparator        | P0       | PostgreSQL 16 SSI | Safety, Overhead, CPU |
| E17 | Current-State Insufficiency Witness  | P0       | Deterministic PG  | C0/C1 Failure Witness |
| E18 | Global vs. Disclosed Support         | P0       | PostgreSQL 16 SSI | Undisclosed Rejection |
| E19 | Transport Serialization Attacks      | P0       | HTTP Gateway      | Envelope Mismatch 100%|
| E20 | Optional Provider Receipt Study      | P2       | Provider Receipts | Attestation Parity    |
| E21 | Formal Novelty Model (I16–I24)       | P0       | Python Explorer / TLA+ | 0 Violations (d = 5)  |
| E22 | R4 Public Reproducibility Audit      | P0       | Fresh Checkout    | 100% Checksum Parity  |
+-----+--------------------------------------+----------+-------------------+-----------------------+
```

---

## 2. Global Experimental Integrity & Protocol Mandates

All experiments in GLHS R4 are subject to non-negotiable operational invariants:

1. **Protocol Freezing Prior to Execution:** No experiment runner may execute against claim-bearing schedules until its protocol specification, random seeds, test vectors, and analysis scripts are hashed and cryptographically sealed.
2. **Backend Truthfulness (Live PostgreSQL vs Simulation):** Headline systems claims must derive exclusively from live PostgreSQL 16.0 instances executing under Serializable Snapshot Isolation (SSI) with the production commit kernel (`PostgresCommitKernel`). In-memory locks or mock coordinators are restricted to unit test scaffolding and must be marked `SIMULATION_NOT_PRODUCTION`.
3. **Unit of Analysis Isolation:** The scientific unit of analysis is the **unique, independent logical schedule** or **paired witness scenario**. Microsecond jitter repetitions or TCP retry attempts within a schedule are treated strictly as secondary robustness probes; combining them into primary sample sizes is prohibited as pseudoreplication.
4. **Claim Budget Strict Enforcement:** Manuscripts and reports generated under R4 must strictly observe the frozen Claim Budget. Prohibited terminology includes:
   - "First system to solve medical AI safety"
   - "TOCTOU completely eliminated" (must state: "zero invalid admissions observed across $N$ tested schedules")
   - "Mathematically proven secure" (must state: "counterexample-free within bounded state exploration depth $d$")
   - "Clinically effective" or "Doctor replacement" (R4 is an engineering systems evaluation).
5. **Pre-specified Equivalence Policy (Gate 2):** If a simpler, capability-based comparator (e.g., `SIGNED_EXACT_DISCLOSURE_TOKEN`, C3) matches `FULL_GRWC` (C4) in safety and clean admissibility while incurring lower byte or CPU overhead, GLHS R4 commits to prominently reporting the equivalence and confining its novelty claim to the formulation of the GRWC invariant and its operational semantics.

---

## 3. Protocol Specifications (E15 through E22)

### 3.1 E15 — Dispatch Attestation Integrity Protocol

#### 3.1.1 Objective & Research Questions
E15 evaluates whether the GLHS dispatch attestation kernel prevents invalid write admissions when proposals are subjected to adversarial perturbations of their attestation tokens, context projections, and request envelopes.
- **Primary Question:** Does the dispatch attestation kernel achieve an invalid admission rate of exactly $0.0\%$ ($0/N$) across 16 prespecified attack classes (A01–A16)?
- **Secondary Question:** Does the clean-control admission rate maintain $100.0\%$ liveness ($224/224$) without false-stale aborts?

#### 3.1.2 Scientific Unit & Sample Size Allocation
- **Scientific Unit:** One unique logical adversarial dispatch attestation schedule executed against the production gateway and PostgreSQL commit kernel.
- **Total Sample Size:** $N = 1,024$ unique schedules.
  - **Adversarial Perturbation Arms:** 16 attack classes $\times$ 50 unique schedules per class = $800$ adversarial schedules.
  - **Clean Control Arm:** $224$ valid, unaltered dispatch attestation schedules.

#### 3.1.3 Taxonomy of 16 Adversarial Attack Classes (A01–A16)
```
+------------------------------------------------------------------------------------------------------+
|                                   TAXONOMY OF ATTACK CLASSES (E15)                                   |
+-----+--------------------------------------+---------------------------------------------------------+
| ID  | Attack Class Name                    | Expected Fail-Closed Error Code                         |
+-----+--------------------------------------+---------------------------------------------------------+
| A01 | snapshot_id_substitution             | proposal_snapshot_scope_forbidden                       |
| A02 | projection_digest_corruption         | proposal_manifest_digest_mismatch                       |
| A03 | request_envelope_digest_corruption   | proposal_envelope_digest_mismatch                       |
| A04 | undisclosed_evidence_injection       | proposal_evidence_not_disclosed                         |
| A05 | disclosed_evidence_stripping         | proposal_evidence_incomplete                            |
| A06 | cross_actor_credential_reuse         | attestation_actor_mismatch                              |
| A07 | cross_purpose_context_reuse          | attestation_purpose_mismatch                            |
| A08 | cross_task_context_reuse             | attestation_task_mismatch                               |
| A09 | historic_attestation_nonce_replay    | attestation_nonce_replayed                              |
| A10 | human_review_lineage_laundering      | commitment_lineage_base_only_forbidden                  |
| A11 | prompt_template_version_drift        | attestation_template_drift                              |
| A12 | unbound_provider_fallback            | attestation_fallback_unbound                            |
| A13 | stale_retry_context_mutation         | attestation_retry_stale                                 |
| A14 | cross_profile_projection_mismatch    | attestation_patient_mismatch                            |
| A15 | signature_hmac_tampering             | attestation_signature_invalid                           |
| A16 | malformed_attestation_payload        | attestation_payload_malformed                           |
+-----+--------------------------------------+---------------------------------------------------------+
```

#### 3.1.4 Primary & Secondary Estimands
1. **Invalid Admission Rate ($\theta_{\text{invalid}}$):**
   $$\theta_{\text{invalid}} = \frac{N_{\text{admitted, adversarial}}}{N_{\text{adversarial}}} = \frac{0}{800} = 0.0\%$$
   - **One-Sided Clopper-Pearson 95% Upper Confidence Bound (UCB):**
     $$\text{UCB}_{0.95} = 1 - (1 - 0.95)^{1/800} = 1 - (0.05)^{0.00125} \approx 0.00373 \quad (0.373\%)$$
   - Target: $\text{UCB} < 0.0050$ ($0.50\%$).
2. **Clean Control Liveness Rate ($\theta_{\text{clean}}$):**
   $$\theta_{\text{clean}} = \frac{N_{\text{admitted, clean}}}{N_{\text{clean}}} = \frac{224}{224} = 100.0\%$$
   - **One-Sided Wilson 95% Lower Confidence Bound (LCB):**
     $$\text{LCB}_{0.95} \approx 0.9866 \quad (98.66\%)$$

---

### 3.2 E16 — Five-Way Prior-Art Comparator Architecture Study

#### 3.2.1 Objective & Research Questions
E16 benchmarks GLHS Full GRWC against four representative prior-art paradigms across security, database concurrency, and provenance literature.
- **Primary Question:** Does any prior-art baseline (C0, C1, C2, C3) achieve equivalent safety against semantic disclosure and concurrency attacks while reducing systems overhead relative to C4?

#### 3.2.2 Comparator Arms Specification
```
+------------------------------------------------------------------------------------------------------+
|                                   FIVE COMPARATIVE ARMS (E16)                                        |
+-----+-------------------------------+-----------------------------------+----------------------------+
| Arm | Paradigm Name                 | Foundational Literature           | Core Mechanism             |
+-----+-------------------------------+-----------------------------------+----------------------------+
| C0  | CURRENT_STATE_ONLY            | Classical RDBMS Integrity Checks  | Re-checks DB predicates at |
|     |                               | (Date 2000, Stonebraker 2010)     | commit time only.          |
+-----+-------------------------------+-----------------------------------+----------------------------+
| C1  | OCC_READSET                   | Optimistic Concurrency Control    | Tracks entity key-version  |
|     |                               | (Kung & Robinson 1981, DynamoDB)  | read-set vectors.          |
+-----+-------------------------------+-----------------------------------+----------------------------+
| C2  | PROVENANCE_ONLY               | Retrospective Provenance          | Records W3C PROV graph     |
|     |                               | (Moreau et al. 2013, W3C PROV)    | after commit.              |
+-----+-------------------------------+-----------------------------------+----------------------------+
| C3  | SIGNED_EXACT_DISCLOSURE_TOKEN | Capability Tokens & Macaroons     | HMAC token holding exact   |
|     |                               | (Birgisson NDSS 2014, PCFS 2010)  | disclosure digest H_proj.  |
+-----+-------------------------------+-----------------------------------+----------------------------+
| C4  | FULL_GRWC                     | GLHS R4 Architecture              | Two-digest server binding, |
|     |                               | (Master Spec §2, GRWC Invariant)  | lineage & SSI commit locks.|
+-----+-------------------------------+-----------------------------------+----------------------------+
```

#### 3.2.3 Evaluated Estimands across All 5 Arms
Every schedule is evaluated across all five arms ($5 \times 500 = 2,500$ executions):
1. **Adversarial False Admission Rate (%):** Proportion of invalid/mutated proposals mistakenly committed.
2. **Clean False Rejection Rate (%):** Proportion of valid proposals improperly rejected.
3. **Decision Disagreement Rate vs C4 (%):** Proportion of schedules where arm decision differs from Full GRWC.
4. **Serialized Payload Overhead (Bytes):** Wire size of authorization and context metadata per proposal.
5. **Database IO Operations (IOPS):** Cumulative reads, writes, and lock acquisitions executed within the admission transaction.
6. **Validation CPU Time ($\mu\text{s}$):** Server-side wall-clock processing time spent in cryptographic and governance verification.
7. **Forensic Lineage Reconstructability Score (0–100):** Quantitative index measuring whether a third-party auditor can reconstruct the exact prompt projection and evidence sources from persisted audit trails:
   - $0$: No reconstruction possible (C0).
   - $20$: Entity version IDs only, prompt destroyed (C1).
   - $50$: Retrospective PROV graph without exact model projection bytes (C2).
   - $75$: Exact digest verified, but projection payload must be recovered off-line (C3).
   - $100$: Full bit-exact prompt, envelope, and evidence lineage directly reconstructible from server audit log (C4).

---

### 3.3 E17 — Current-State Insufficiency Witness Protocol

#### 3.3.1 Theoretical Formulation
The fundamental thesis of GRWC is that **verifying current database state is mathematically insufficient to govern AI-generated state mutations**.

Let the database state at time $t$ be $S_t \in \mathcal{S}$, and let the governance policy epoch be $G_t \in \mathcal{G}$. An AI model generates a mutation proposal $P$ based on observed disclosure $D \in \mathcal{D}$, denoted $P = \mathcal{M}(D)$.
- Under `CURRENT_STATE_ONLY` (C0), the admission predicate is $V_{\text{C0}}(P, S_{\text{commit}}, G_{\text{commit}}) \to \{\text{ADMIT}, \text{REJECT}\}$.
- Under `OCC_READSET` (C1), the admission predicate is $V_{\text{C1}}(P, R_{\text{readset}}, S_{\text{commit}}) \to \{\text{ADMIT}, \text{REJECT}\}$.

**Theorem (Current-State Insufficiency):** There exist deterministic proposal pairs $(P_{\text{good}}, P_{\text{substituted}})$ such that:
$$S_{\text{read}} = S_{\text{commit}}, \quad G_{\text{read}} = G_{\text{commit}}, \quad R_{\text{readset}}(P_{\text{good}}) = R_{\text{readset}}(P_{\text{substituted}})$$
yet $P_{\text{good}}$ is clinically aligned with patient safety while $P_{\text{substituted}}$ introduces severe patient harm, such that:
$$V_{\text{C0}}(P_{\text{substituted}}, S_{\text{commit}}, G_{\text{commit}}) = \text{ADMIT}$$
$$V_{\text{C1}}(P_{\text{substituted}}, R, S_{\text{commit}}) = \text{ADMIT}$$
$$V_{\text{C4}}(P_{\text{substituted}}, D_{\text{good}}, S_{\text{commit}}) = \text{REJECT}$$

#### 3.3.2 Concrete Clinical Witness Scenario
1. **Patient State:** Patient has documented severe anaphylaxis to Penicillin. In DB, `Observation(Allergy=Penicillin, version=1)`.
2. **Clean Execution ($P_{\text{good}}$):**
   - Context disclosure $D_{\text{good}}$ includes allergy record.
   - LLM proposes `MedicationRequest(Drug=Azithromycin 500mg, Ref=Obs#1)`.
   - Admitted safely under all paradigms.
3. **Substituted Adversarial Execution ($P_{\text{substituted}}$):**
   - Attacker or flawed retrieval drops allergy record, presenting $D_{\text{bad}}$.
   - LLM proposes `MedicationRequest(Drug=Amoxicillin 500mg, Ref=Obs#1)`.
   - At commit time, DB state is completely unchanged: `Allergy=Penicillin` is still version 1.
   - **C0 Evaluation:** Checks if patient exists and version is current $\to$ **ADMIT** (Severe Harm).
   - **C1 Evaluation:** Checks if read-set `Obs#1` is version 1 $\to$ **ADMIT** (Severe Harm).
   - **C4 (GRWC) Evaluation:** Computes $H_{\text{proj}}(D_{\text{good}}) \neq H_{\text{proj}}(D_{\text{bad}})$, detects mismatch with attested dispatch token $\to$ **REJECT** (`proposal_manifest_digest_mismatch`).

#### 3.3.3 Sample Size & Estimands
- $N = 100$ distinct clinical paired witness scenarios spanning antimicrobial stewardship, anticoagulation dosing, pediatric weight-based adjustments, and renal clearance adjustments.
- **Expected False Admission Rates:**
  - C0: $100.0\%$ ($100/100$)
  - C1: $100.0\%$ ($100/100$)
  - C3: $0.0\%$ ($0/100$)
  - C4: $0.0\%$ ($0/100$)

---

### 3.4 E18 — Global Source Support vs. Disclosed Support Protocol

#### 3.4.1 The Semantic Source-Support Fallacy
A common heuristic in retrieval-augmented clinical systems is **source verification**: if an LLM generates a claim citing evidence item $E^*$, the gateway checks whether $E^*$ exists in the EHR database. If $E^*$ is found, the proposal is deemed "grounded in truth."

E18 exposes the fatal flaw in this heuristic: **Global Source Presence $\neq$ Model Disclosure**.
If $E^*$ was never projected into the model's token context (e.g., due to top-$k$ retrieval truncation, relevance filtering, or prompt token limits), the model's assertion of $E^*$ is an ungrounded hallucination or an adversarial injection, even if $E^*$ happens to exist in the global database.

#### 3.4.2 Experimental Design
- **Schedules:**
  - $100$ schedules where evidence $E^*$ is present in PostgreSQL at version $v$, but deliberately omitted from prompt projection $\mathcal{P}$.
  - $100$ control schedules where $E^*$ is both present in PostgreSQL and included in prompt projection $\mathcal{P}$.
- **Comparator Behavior:**
  - **C1 (Source-Supported Validator):** Queries DB for $E^*$, finds it valid $\to$ **ADMIT** ($0.0\%$ omission detection).
  - **C4 (Full GRWC):** Evaluates evidence closure Invariant $I_{07} / I_{14}$:
    $$\mathcal{E}_{\text{asserted}} \subseteq \mathcal{E}_{\text{disclosed}}$$
    Since $E^* \notin \mathcal{E}_{\text{disclosed}}$, commit kernel rejects with `proposal_evidence_not_disclosed` ($100.0\%$ omission detection).

---

### 3.5 E19 — Transport Serialization Attacks Protocol

#### 3.5.1 The Two-Digest Security Invariant
GLHS separates the inference context binding into two orthogonal cryptographic hashes:
1. **Health Projection Digest ($H_{\text{proj}}$):** Canonical RFC 8785 JSON digest of model-visible clinical entities:
   $$H_{\text{proj}} = \text{SHA256}\left(\text{C14N}\left(P_{\text{health}}\right)\right)$$
2. **Request Envelope Digest ($H_{\text{env}}$):** Canonical digest of the complete transport envelope (HTTP headers, client metadata, routing options, model temperature, max tokens):
   $$H_{\text{env}} = \text{SHA256}\left(\text{C14N}\left(E_{\text{transport}}\right)\right)$$

#### 3.5.2 Mutation Taxonomy & Threat Vectors (8 Patterns, $N = 256$)
E19 subjects proposals to transport-level mutations executed after semantic envelope creation:
1. `envelope_whitespace_tampering`: Altering transport JSON formatting without changing logical values.
2. `json_key_reordering`: Permuting keys in transport envelope.
3. `transport_header_injection`: Injecting unauthorized tracing or proxy headers into the dispatch stream.
4. `proxy_parameter_mutation`: Mutating model sampling parameters (e.g., increasing `temperature` from 0.0 to 1.0).
5. `client_envelope_digest_substitution`: Replaying a valid envelope digest from a different request.
6. `cbor_canonicalization_tampering`: Mutating CBOR binary tags on wire.
7. `utf8_surrogate_injection`: Injecting unpaired Unicode surrogates into transport strings.
8. `float_precision_serialization_shift`: Altering floating point coordinates from IEEE 754 double to single precision.

#### 3.5.3 Estimands & Stopping Rule
- **Rejection Rate:** $100.0\%$ ($256/256$).
- **Rejection Reason Code:** `proposal_envelope_digest_mismatch`.
- **Stopping Rule:** Any successful admission of a transport-mutated envelope halts the experiment immediately.

---

### 3.6 E20 — Optional Provider Verifiable Receipt Study

#### 3.6.1 Capability Verification & Conditionality Rule
Emerging foundation model inference endpoints support hardware-based verifiable receipts (e.g., confidential computing hardware attestations, signed TPM completion tokens, cryptographic provenance headers).
- **Execution Rule:** E20 executes **only if** the active provider API in the test environment natively provides verifiable cryptographic receipts.
- **Fail-Safe Gate:** If live provider receipt capabilities are unavailable or return unsigned payloads, E20 is explicitly marked:
  $$\text{Status} = \text{NOT\_RUN\_PROVIDER\_ATTESTATION\_UNAVAILABLE}$$
- **Prohibition:** Generating mock or simulated vendor signatures is strictly forbidden.

---

### 3.7 E21 — Formal Novelty Model (Invariants $I_{16}$ through $I_{24}$)

#### 3.7.1 Bounded State-Space Verification Specification
E21 extends the formal verification model from R3 (which verified $I_{01}$–$I_{15}$) by introducing nine extended invariants ($I_{16}$–$I_{24}$) modeled in our canonical Python bounded state-space model checker (`explore_r4.py` / `model_r4.py`), with companion formal specification in TLA+ (`docs/formal/GLHS_GRWC_R4.tla`).
- **Exploration Tool:** Python Bounded State-Space Explorer (`explore_r4.py`).
- **Search Depth:** Exhaustive exploration through depth $d = 5$.
- **State-Space Scale:** Explores 162 distinct reachable states and 323 transitions.

#### 3.7.2 Extended Invariant Definitions ($I_{16}$–$I_{24}$)
```
+------------------------------------------------------------------------------------------------------+
|                                   FORMAL INVARIANTS MATRIX (I16–I24)                                 |
+-----+---------------------------------------------------+--------------------------------------------+
| ID  | Formal Invariant Name                             | Mathematical / Logical Invariant           |
+-----+---------------------------------------------------+--------------------------------------------+
| I16 | I16_current_state_insufficiency_counterexample    | \E P, P' \in Proposals: S(P) = S(P') /\    |
|     |                                                   | G(P) = G(P') /\ Valid(P) /\ \neg Valid(P') |
|     |                                                   | /\ C0_Admit(P') /\ \neg GRWC_Admit(P')     |
+-----+---------------------------------------------------+--------------------------------------------+
| I17 | I17_disclosed_vs_source_support_separation        | \A e \in AssertedEvidence:                 |
|     |                                                   | (e \in DB) \not\implies (e \in Disclosed)  |
+-----+---------------------------------------------------+--------------------------------------------+
| I18 | I18_two_digest_transport_independence             | \A p, e, e': (e \neq e') \implies          |
|     |                                                   | H_env(e) \neq H_env(e') /\                 |
|     |                                                   | (H_proj(p) unchanged)                      |
+-----+---------------------------------------------------+--------------------------------------------+
| I19 | I19_non_malleable_lineage_continuity              | \A p \in Proposals: Lineage(p).parent_id   |
|     |                                                   | = RootBinding(p).attestation_id            |
+-----+---------------------------------------------------+--------------------------------------------+
| I20 | I20_anti_laundering_human_gate                    | \A p \in AdaptedProposals:                 |
|     |                                                   | base_version_only(p) = FALSE               |
+-----+---------------------------------------------------+--------------------------------------------+
| I21 | I21_canonical_lock_hierarchy_deadlock_freedom     | LockOrder is strictly total;               |
|     |                                                   | Cycles(WaitForGraph) = \emptyset           |
+-----+---------------------------------------------------+--------------------------------------------+
| I22 | I22_dynamic_governance_precedence                 | Revoke(Consent) \prec Commit(Proposal)     |
|     |                                                   | \implies CommitResult = REJECT             |
+-----+---------------------------------------------------+--------------------------------------------+
| I23 | I23_deterministic_replay_parity                   | \A d: C14N(d) is unique and byte-identical |
+-----+---------------------------------------------------+--------------------------------------------+
| I24 | I24_clean_path_reachability                       | CleanValid(P) /\ Uncontended(S)            |
|     |                                                   | \implies CommitResult = ADMIT              |
+-----+---------------------------------------------------+--------------------------------------------+
```

---

### 3.8 E22 — R4 Public Reproducibility & Fresh Checkout Audit

#### 3.8.1 Hermetic Reproduction Pipeline
E22 operationalizes third-party auditability by verifying that the entire R4 experimental suite can be executed from a clean environment without manual intervention or network dependency:
1. **Repository Checksum Verification:** Validate SHA256 checksums of all frozen protocol definitions, schedule manifests, and seed configurations.
2. **Environment & Dependency Integrity:** Check Python virtual environment and system dependencies under fail-closed network isolation.
3. **Cryptographic & Merkle Chain Verification:** Validate SHA256 file checksums and Merkle hash chains of raw execution records for E15 through E21.
4. **Automated Computational Re-Execution:** Re-execute test runners for E15 through E21 against SUT kernel with master random seeds.
5. **Exact Concordance Verification:** Assert 100% concordant classification outcomes, zero invalid admissions, and bit-level identical audit records.

---

## 4. Sample Size Allocations and Power Analysis

### 4.1 Statistical Power for Zero-Failure Safety Endpoints (E15, E18, E19)
For safety-critical endpoints where the design target is zero failures ($k = 0$), statistical power corresponds to the probability of rejecting the null hypothesis $H_0: \theta \ge \theta_{\text{unacceptable}}$ in favor of $H_1: \theta = 0$.

Under the binomial distribution, the probability of observing 0 events in $N$ independent trials when the true failure rate is $\theta$ is:
$$P(k = 0 \mid \theta) = (1 - \theta)^N$$

To ensure that an observed result of $0/N$ bounds the true failure rate below $\theta_{\text{unacceptable}} = 0.005$ ($0.50\%$) at $\alpha = 0.05$ (equivalent to $95\%$ confidence):
$$(1 - 0.005)^N \le 0.05 \implies N \ln(0.995) \le \ln(0.05) \implies N \ge \frac{-2.9957}{-0.00501} \approx 598$$

- **E15 Allocation ($N = 800$ adversarial schedules):** Exceeds the 598-sample requirement, yielding a maximum 1-sided Clopper-Pearson 95% upper bound of:
  $$\text{UCB} = 1 - (0.05)^{1/800} \approx 0.00373 \quad (0.373\%)$$
  providing statistical power $> 98\%$ against a hypothesis of $\theta \ge 0.005$.
- **Clean Controls ($N = 224$ in E15):** Yields a 1-sided Wilson 95% lower bound $> 98.6\%$.

### 4.2 Power for Equivalence Testing in Comparator Overhead (E16)
For secondary continuous endpoints in E16 (Validation CPU Time, Serialized Bytes), equivalence between C3 and C4 is assessed via Schuirmann's Two One-Sided Tests (TOST) with an equivalence margin of $\delta = \pm 5\%$ of the mean:
$$H_{01}: \mu_{\text{C4}} - \mu_{\text{C3}} \le -\delta \quad \text{vs} \quad H_{11}: \mu_{\text{C4}} - \mu_{\text{C3}} > -\delta$$
$$H_{02}: \mu_{\text{C4}} - \mu_{\text{C3}} \ge +\delta \quad \text{vs} \quad H_{12}: \mu_{\text{C4}} - \mu_{\text{C3}} < +\delta$$

With $N = 500$ paired schedules per arm, assuming a coefficient of variation $CV = \sigma / \mu \le 0.25$, power to confirm equivalence within $\pm 5\%$ exceeds $90\%$ at $\alpha = 0.05$.

---

## 5. Pre-specified Validation Gates (Stop / Go Criteria)

Progression through Phase 0 and subsequent phases of GLHS R4 is governed by five mandatory Stop/Go validation gates:

```
+------------------------------------------------------------------------------------------------------+
|                                   GLHS R4 STOP / GO VALIDATION GATES                                 |
+--------+--------------------------+------------------------------------+-----------------------------+
| Gate   | Target Protocol          | Validation Condition               | Failure Action              |
+--------+--------------------------+------------------------------------+-----------------------------+
| Gate 1 | E15 (Dispatch Integrity) | 0 invalid admissions across A01–A16| STOP. Architecture defect;  |
|        |                          | (0 / 800).                         | block claim eligibility.    |
+--------+--------------------------+------------------------------------+-----------------------------+
| Gate 2 | E16 (Prior-Art Baseline) | If C3 matches C4 across all safety | Narrow novelty claim to     |
|        |                          | and utility metrics.               | invariant formalization.    |
+--------+--------------------------+------------------------------------+-----------------------------+
| Gate 3 | E17 / E18 (Insufficiency)| C0/C1 admit substituted proposal,  | STOP. Ineffective witness;  |
|        |                          | C4 strictly rejects.               | redesign clinical counterex.|
+--------+--------------------------+------------------------------------+-----------------------------+
| Gate 4 | E20 (Provider Receipts)  | Verifiable provider receipts       | Mark protocol as            |
|        |                          | available in test environment.     | NOT_RUN_PROVIDER_UNAVAIL.   |
+--------+--------------------------+------------------------------------+-----------------------------+
| Gate 5 | E22 (Reproducibility)    | 100% checksum and classification   | Disallow public manuscript  |
|        |                          | concordance on clean checkout.     | claim release.              |
+--------+--------------------------+------------------------------------+-----------------------------+
```

---

## 6. Public Release and Artifact Seal Specification

Following completion of execution runs, all generated artifacts must be packaged and sealed under `research/glhs_journal/q4_r4/` with the following structure:
- `experiments_plan_r4.json`: Prospective frozen experiment schema and parameters.
- `statistical_plan_r4.md`: Master prospective statistical design (this document).
- `manifest.json`: Full manifest of all logical schedule definitions and seed assignments.
- `raw/executions_E15.jsonl` through `raw/executions_E22.jsonl`: Bit-exact execution logs containing transaction IDs, timestamps, digests, error codes, and server PIDs.
- `derived/summary_E15.json` through `derived/summary_E22.json`: Aggregated statistical metrics, confidence intervals, and hypothesis test receipts.
- `seal/artifact-sha256.json`: Cryptographic SHA256 digest of every file in the release package.
- `REVERIFICATION_RECORD.md`: Independent reproduction audit log executing from a fresh git clone.

---

*This statistical plan is formally frozen under GLHS R4 Phase 0 governance. Any material alteration to sample sizes, attack taxonomies, equivalence margins, or stopping rules invalidates this freeze and requires a new revision identifier.*
