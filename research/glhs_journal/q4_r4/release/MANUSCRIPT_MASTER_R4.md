# GLHS: Governed Read-to-Write Continuity and Exact-Disclosure Admission for Longitudinal Health AI

**Authors:** Nguyen Ngoc Thien$^1$, Trinh Minh Quang$^1$  
$^1$ Hai Ba Trung High School, Hue, Vietnam  
**Date:** October 2026  
**Target Venue:** *ACM Transactions on Computer Systems* / *IEEE Transactions on Knowledge and Data Engineering* / *Journal of Medical Systems*  
**Artifact Archive:** `Project-CLARA-HBT/CLARA-Care` (`research/glhs_journal/q4_r4/`)  
**Release Identifier:** `GLHS-Q4-R4-RELEASE-20260930-V1`  

---

## Abstract

Persistent medical artificial intelligence (AI) systems execute multi-step non-deterministic inference over historical electronic health records (EHR) to generate structured mutation proposals—such as medication reconciliations, allergy updates, or dosage adjustments. This operational model introduces a fundamental systems vulnerability: between the moment a health state projection is compiled and disclosed for inference ($t_1$) and the moment a persistent write is requested ($t_3$), underlying clinical observations, lab results, or dynamic consent directives can silently drift ($t_2$).

While prior art separately provides optimistic concurrency control, purpose-based access control, W3C PROV lineage, dynamic consent, and capability tokens, existing systems leave a critical systems gap: they cannot verify whether a proposed persistent write remains continuous with the exact governed disclosure actually supplied to the inference instance that produced its lineage.

This paper formalizes, operationalizes, and evaluates **Governed Read-to-Write Continuity (GRWC)** (also denoted **Exact-Disclosure Admission**). Under GRWC, a persistent write proposal is admissible if and only if: (1) it descends from a server-attested inference binding proving the exact model-visible projection was consumed; (2) all declared evidence items were part of that exact disclosure; (3) schema-derived dependency requirements are fully satisfied; and (4) clinical state, dynamic consent, policy epochs, and actor permissions remain unviolated within the admission transaction under canonical database locks.

We operationalize GRWC in GLHS, an open-source clinical systems gateway featuring: a two-digest binding separating model-visible health projections ($H_{\text{proj}}$) from request transport envelopes ($H_{\text{env}}$); an immutable proposal lineage engine; and a six-phase atomic commit kernel executing over PostgreSQL 16.

We evaluate GLHS across eight prospective sealed experimental protocols (**E15–E22**). In dispatch attestation integrity evaluations ($N=1,024$ schedules), GLHS achieved $0.0\%$ invalid admission across 16 adversarial attack classes ($0/800$, Clopper-Pearson 95% UCB $< 0.005$) and $100.0\%$ clean control liveness ($224/224$). In a five-way comparator architecture study ($N=2,500$ executions), compact capability tokens (C3, `SIGNED_EXACT_DISCLOSURE_TOKEN`) matched full GLHS (C4) in static decision safety ($0$ decision disagreements across all schedules). Per our prespecified **Novelty Outcome Rule**, GLHS surrenders decision-safety superiority over compact capability tokens and restricts its core novelty claims strictly to lifecycle state-machine governance, server-attested two-digest dispatch receipts, tamper-evident non-downgradable proposal lineage, and bit-exact forensic audit reconstructability (reconstructability score $100$ vs $75$). In deterministic clinical witness evaluations (E17/E18), prior-art mechanisms C0/C1 suffered $100\%$ false admission on disclosure-substituted proposals, while GLHS achieved $0\%$ false admission ($p < 10^{-40}$). Bounded state-space exploration (E21) verified 9 target invariants across 64,890 reachable states to search depth $d=6$ with zero violations and $100\%$ formal mutant kill rate. All empirical datasets, execution traces, cryptographic seals, and offline reproduction routines (E22) are 100% reproducible.

**Keywords:** longitudinal health AI; governed read-to-write continuity; exact disclosure admission; two-digest attestation; prior-art comparator study; PostgreSQL serializability; forensic audit reconstructability.

---

## 1. Introduction

Longitudinal electronic health records (EHRs) are multi-source repositories of clinical observations, laboratory findings, diagnostic interpretations, and therapeutic orders. Autonomous medical AI agents consume patient context and emit mutation proposals back into clinical data stores.

However, the lifecycle of stateful health AI introduces a temporal consistency gap. An AI inference invocation is an asynchronous, multi-second cognitive process. Consequently, system execution splits into three temporal coordinates:

1. **Governed Read Compilation ($t_1$):** The clinical gateway evaluates access control, compiles patient observations, and generates a governed disclosure projection $H$.
2. **Inference and Proposal Generation ($t_2$):** The external AI model consumes $H$ and emits a structured mutation proposal $P$.
3. **Database Write Admission ($t_3$):** The proposal $P$ is submitted to the clinical storage engine for verification and durable persistence.

During the interval between $t_1$ and $t_3$, both the patient's clinical reality and their governing consent directives can undergo critical drift ($t_2$).

### 1.1 Surrendered Constituent Mechanisms & Novelty Demarcation

To eliminate unearned novelty claims, GLHS R4 explicitly surrenders 29 constituent mechanisms to prior art:

```
+----------------------------------------------------------------------------------------------------------+
|                                    SURRENDERED CONSTITUENT MECHANISMS (R4)                               |
+----+--------------------------------------------+--------------------------------------------------------+
| #  | Surrendered Constituent Mechanism          | Prior Art / Standard Boundary                          |
+----+--------------------------------------------+--------------------------------------------------------+
| 01 | Optimistic Concurrency Control (OCC)       | Kung & Robinson (ACM TODS 1981)                        |
| 02 | Serializable Snapshot Isolation (SSI)      | Cahill et al. (SIGMOD 2008); PostgreSQL 16             |
| 03 | W3C PROV Retrospective Lineage             | W3C PROV-DM Recommendation (2013)                      |
| 04 | Macaroon Capability Tokens                 | Birgisson et al. (NDSS 2014)                           |
| 05 | Proof-Carrying File Systems (PCFS)         | Garg et al. (2010)                                     |
| 06 | RFC 8785 JSON Canonicalization (JCS)        | RFC 8785 (IETF 2020)                                   |
| 07 | HMAC-SHA256 Authentication                 | FIPS PUB 198-1 / RFC 2104                              |
| 08 | Attribute-Based Access Control (ABAC)      | Hu et al. (NIST SP 800-162)                            |
| 09 | Purpose-Based Access Control (PBAC)        | Byun et al. (ACM TISS 2005)                            |
| 10 | Dynamic Patient Consent Management         | Coiera & Clarke (JAMI 2004)                            |
| 11 | Bitemporal Data Modeling                   | Snodgrass & Ahn (ACM TODS 1985)                        |
| 12 | Merkle Hash Chains                         | Merkle (IEEE S&P 1987)                                 |
| 13 | Two-Phase Locking (2PL)                    | Eswaran et al. (CACM 1976)                             |
| 14 | Database Schema Migration Tracking         | Alembic / Liquibase Standards                          |
| 15 | REST API Gateway Middleware                | Fielding (2000) Architectural Principles               |
| 16 | FHIR Resource Schemas                      | HL7 FHIR Release 4 Standard                            |
| 17 | TLA+ Model Checking                        | Lamport (2002) Specifying Systems                      |
| 18 | Alloy Relational Analyzer                  | Jackson (2006) Software Abstractions                   |
| 19 | Schuirmann TOST Equivalence Design         | Schuirmann (J. Pharmacokinet. Biopharm. 1987)          |
| 20 | Clopper-Pearson Confidence Intervals       | Clopper & Pearson (Biometrika 1934)                    |
| 21 | Wilson Score Confidence Intervals          | Wilson (JASA 1927)                                     |
| 22 | McNemar Paired Concordance Test            | McNemar (Psychometrika 1947)                           |
| 23 | Bounded State-Space Exploration            | Clarke et al. (1999) Model Checking                    |
| 24 | Formally Verified Mutation Testing         | DeMillo et al. (1978) Mutation Analysis                |
| 25 | CBOR Serialization Canonicalization       | RFC 8949 (IETF 2020)                                   |
| 26 | Bearer Token Exemption Auth                | RFC 6750 OAuth 2.0 Bearer Tokens                       |
| 27 | CSRF Double-Submit Cookie Defense          | OWASP Cross-Site Request Forgery Prevention Cheat Sheet|
| 28 | Fast-Path Emergency Escalation              | Standard Clinical Triage Algorithms                    |
| 29 | System Metric Sanitization                 | HIPAA Privacy Rule Security Standards                  |
+----+--------------------------------------------+--------------------------------------------------------+
```

### 1.2 Related Work & Source Support vs. Exact-Disclosure Boundary

Recent transactional agent memory systems, notably **MemTX / MemTxn** (e.g. transactional agent-memory frameworks), introduce database isolation and transactional recovery over external LLM memories. However, these systems focus on **source support**—verifying whether an asserted fact exists anywhere within the agent's long-term memory store or underlying database.

GLHS addresses a fundamentally distinct invariant: **Exact-Disclosure Admission**. In clinical decision-making, it is insufficient to prove that a piece of evidence exists in the global database; the system must guarantee that critical contraindications or updated laboratory results were present in the *exact disclosure supplied* to the inference instance that produced the proposal. 

*Scope Limitation Invariant:* We explicitly note: **We do not prove semantic use by the LLM**. Server-attested dispatch continuity proves that the exact projection $M_{\text{proj}}$ was delivered to the model transport channel; neural internal causal processing remains strictly out of scope.

### 1.3 Formal Novelty Outcome Rule (C3 vs C4)

Our prospective plan established the **Novelty Outcome Rule**:
> *If C3 (`SIGNED_EXACT_DISCLOSURE_TOKEN`) matches C4 (`FULL_GRWC`) in static decision safety across all adversarial schedules, GLHS explicitly surrenders decision-safety superiority over compact capability tokens and restricts its novelty claims strictly to full-lifecycle state-machine governance, server-attested two-digest dispatch receipts, tamper-evident proposal lineage, and bit-exact forensic audit reconstructability.*

In experiment E16 ($N=2,500$), C3 matched C4 with $0$ decision disagreements across all tested schedules. Consequently, GLHS R4 restricts its novelty claims to:
1. Formalization of the **Governed Read-to-Write Continuity (GRWC)** invariant across asynchronous cognitive reasoning epochs.
2. Server-attested **Two-Digest Transport Attestation** ($H_{\text{proj}}$ and $H_{\text{env}}$) and lifecycle state-machine governance (`PENDING` $\to$ `DISPATCHED` $\to$ `COMPLETED`).
3. Tamper-evident, non-downgradable **Proposal Lineage Governance** preventing human review laundering.
4. Bit-exact **Forensic Audit Reconstructability** (Score 100/100 for C4 vs 75/100 for C3).

---

## 2. Theoretical Semantics & Three-Digest Pipeline

Let $\mathcal{S}$ denote the canonical state space of the database, $\mathcal{D}$ denote patient data entities, and $\mathcal{G}$ denote dynamic governance policies.

```
       [Client Gateway]
              |
      compile_thss($t_1$)
              |
              v
     +-----------------+
     | Snapshot S_1    |  ---> Compute H_proj = H(M_proj)
     +-----------------+
              |
     issue_dispatch_token($t_1$)
              |
              v
     +-----------------+
     | Attestation T   |  ---> Status: PENDING -> DISPATCHED
     +-----------------+  ---> Compute H_env = H(R_envelope)
              |
     execute_inference($t_2$)
              |
              v
     +-----------------+
     | Proposal P_1    |  ---> Status: COMPLETED
     +-----------------+
              |
      commit_kernel($t_3$)
              |
              v
     evaluate_grwc_admission()  [PostgreSQL Locks]
              |
   +----------+----------+
   |                     |
[PASS]                [FAIL]
Admit & Commit         Fail-Closed (Reason Code)
```

### 2.1 Three-Digest Model

1. **Projection Digest ($D1 = H_{\text{proj}}$):** Canonical SHA-256 hash of exact model-visible clinical projection $M_{\text{proj}}$.
2. **Semantic Envelope Digest ($D2 = H_{\text{sem}}$):** Canonical hash of requested proposal payload, target parameters, and declared evidence.
3. **Transport Envelope Digest ($D3 = H_{\text{env}}$):** Canonical hash of full HTTP/CBOR request payload, headers, and metadata.

*Scope Limitation Invariant (T4):* Server-attested disclosure supply guarantees that projection $M_{\text{proj}}$ was delivered to the model transport channel. Neural semantic consumption (what internal layers attended to or causally processed) is explicitly **OUT OF SCOPE**.

---

## 3. Five-Way Comparator Architecture (C0–C4)

We define five comparative evaluation arms:

* **C0 (`CURRENT_STATE_ONLY`):** Re-evaluates authorization and state versions at commit time. Ignores read-set, disclosure identity, and evidence containment.
* **C1 (`OCC_READSET`):** Classical OCC tracking entity key-version read-sets. Validates read-set freshness against current DB state.
* **C2 (`PROVENANCE_ONLY`):** W3C PROV retrospective lineage recording entity and activity history post-commit.
* **C3 (`SIGNED_EXACT_DISCLOSURE_TOKEN`):** Macaroon/PCFS-style HMAC capability token holding $H_{\text{proj}}$, purpose, task, actor, entity read-set version caveats $R_{\text{readset}}$, and expiration.
* **C4 (`FULL_GRWC`):** Reference GLHS implementation incorporating two-digest server binding, dependency closure, immutable proposal lineage, and PostgreSQL SSI transaction locks.

---

## 4. Empirical Evaluation & Sealed Results (E15–E22)

```
+----------------------------------------------------------------------------------------------------------+
|                                    SUMMARY OF SEALED EXPERIMENTAL RESULTS                                |
+-----+----------------------------------+-------+-----------------------------+---------------------------+
| Exp | Title                            | N     | Primary Estimand Result     | Status / Verdict          |
+-----+----------------------------------+-------+-----------------------------+---------------------------+
| E15 | Dispatch Attestation Integrity   | 1,024 | Invalid Admission = 0.0%    | SEALED (CP 95% UCB < 0.5%)|
| E16 | Five-Way Comparator Architecture | 2,500 | C3 vs C4 Safety Match (0/500)| SEALED (Novelty Surrender)|
| E17 | Current-State Insufficiency      |  200  | C0/C1 100% False Adm vs C4 0%| SEALED (T1 Confirmed)    |
| E18 | Global vs Disclosed Support      |  200  | C4 100% Rejection (C1 0%)   | SEALED (Reason Match 100%)|
| E19 | Transport Serialization Attacks  |  256  | Rejection Rate = 100.0%     | SEALED (H_env Match 100%) |
| E20 | Provider Receipt Study           |    1  | NOT_RUN_UNAVAILABLE         | SEALED (Gate 4 Verified)  |
| E21 | Formal Novelty Model             |    2  | 64,890 States / 0 Violations| SEALED (Kill Rate 100%)   |
| E22 | Public Reproducibility Audit     |    1  | Checksum Concordance 100%   | SEALED (Gate 5 Passed)    |
+-----+----------------------------------+-------+-----------------------------+---------------------------+
```

### 4.1 E15 — Dispatch Attestation Integrity Protocol

Across $N=1,024$ schedules (800 adversarial across 16 attack classes A01–A16 + 224 clean controls):
- **Adversarial Invalid Admission Rate:** $0/800$ ($0.0\%$, 1-sided Clopper-Pearson 95% UCB $= 0.00374 < 0.005$).
- **Clean Control Liveness Rate:** $224/224$ ($100.0\%$, 1-sided Wilson 95% LCB $= 0.9865 > 0.98$).

### 4.2 E16 — Five-Way Comparator Architecture Study

Across $N=2,500$ executions (500 schedules $\times$ 5 arms):
- **C0 False Admission Rate:** $300/400$ ($75.0\%$, Forensic Score = 0/100)
- **C1 False Admission Rate:** $300/400$ ($75.0\%$, Forensic Score = 20/100)
- **C2 False Admission Rate:** $300/400$ ($75.0\%$, Forensic Score = 60/100)
- **C3 False Admission Rate:** $0/400$ ($0.0\%$, Forensic Score = 75/100)
- **C4 False Admission Rate:** $0/400$ ($0.0\%$, Forensic Score = 100/100)
- **Decision Disagreement (C3 vs C4):** 0/500 ($0.0\%$).

### 4.3 E17 & E18 — Insufficiency and Support Separation Witnesses

In E17 ($N=200$ executions across 100 paired clinical scenarios), C0 and C1 exhibited $100\%$ false admission on disclosure-substituted proposals, while C3 and C4 achieved $0\%$ false admission.

In E18 ($N=200$ schedules), C1 failed to detect undisclosed evidence in 100% of cases (0% omission detection rate), whereas C4 detected and rejected 100% of undisclosed evidence proposals with exact reason code `proposal_evidence_not_disclosed`.

### 4.4 E19 — Transport Serialization Attack Resistance

Across $N=256$ mutated transport envelopes spanning 8 mutation patterns, GLHS achieved a $100.0\%$ rejection rate ($256/256$) with exact reason code `proposal_envelope_digest_mismatch`, while maintaining $100.0\%$ projection digest invariance ($H_{\text{proj}}$).

### 4.5 E20 — Optional Provider Verifiable Receipt Attestation

Live hardware attestation receipts were inactive in the local environment. Per prospective Gate 4 rules, E20 was cleanly recorded as `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE` without generating synthetic signatures.

### 4.6 E21 — Formal State-Space Assurance

TLC/Alloy bounded state-space exploration up to depth $d=6$ visited $64,890$ distinct reachable states and $284,120$ state transitions across 9 target invariants (I16–I24) with **zero violations**. Formal mutation testing achieved a $100.0\%$ kill rate ($18/18$ mutants killed).

### 4.7 E22 — Hermetic Offline Reproducibility Audit

The master reproduction script `reproduce_q4_r4.py` executed under strict fail-closed network isolation, verifying $100.0\%$ checksum concordance across all 7 evidence bundles and passing Gate 5.

### 4.8 Statistical Power & Equivalence Design

Note on Sample Size & TOST Equivalence Bounds: $N=384$ was the original prospective design target for Schuirmann Two One-Sided Tests (TOST) equivalence designs under a pre-specified margin $\delta=0.05$. Actual powered sample size $N$ must be derived directly from effect size variances. Exploratory pilot probes with small sample sizes (such as $N=8$ subjects in early utility pilots) are explicitly treated as qualitative probes and do not support claims of $\pm 2\%$ statistical equivalence without a powered confirmatory sample.

---

## 5. Conclusion

GLHS R4 establishes **Governed Read-to-Write Continuity (GRWC)** as a foundational system invariant for longitudinal health AI. By surrendering 29 constituent mechanisms, enforcing a strict prospective freeze, and executing a five-way prior-art comparator study, GLHS transparently demarcates its scientific contributions. While compact capability tokens (C3) match decision safety on static single-step admissions, full GLHS (C4) uniquely provides full-lifecycle state-machine governance, server-attested two-digest dispatch receipts, non-downgradable proposal lineage, and bit-exact forensic audit reconstructability.

---

## References

1. Kung, H. T., & Robinson, J. T. (1981). On optimistic methods for concurrency control. *ACM Transactions on Database Systems (TODS)*, 6(2), 213-226.
2. Cahill, M. J., Röhm, U., & Fekete, A. (2008). Serializability by tracking active transactions. In *Proceedings of the 2008 ACM SIGMOD International Conference on Management of Data* (pp. 145-156).
3. Birgisson, A., Politz, J. G., Erlingsson, Ú., Taly, A., Vrable, M., & Lentczner, M. (2014). Macaroons: Cookies with contextual caveats for decentralized authorization in the cloud. In *2014 IEEE Network and Distributed System Security Symposium (NDSS)*.
4. Garg, D., Franklin, J., Peterson, D., & Wing, J. M. (2010). Proof-carrying file systems. *Carnegie Mellon University Technical Report*.
5. W3C PROV-DM: PROV Data Model. W3C Recommendation (2013).
6. RFC 8785: JSON Canonicalization Scheme (JCS). IETF (2020).
