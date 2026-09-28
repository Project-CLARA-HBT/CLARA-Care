# GLHS R3 Literature & Lineage Novelty Audit: Non-Downgradable Multi-Agent Proposal Lineage

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Artifact Path:** `research/glhs_journal/q3_r3/lineage_literature_audit.md`  
**Author / Role:** Agent A — Literature & Novelty  
**Phase:** Phase 2 — Proposal Lineage & Admission Literature Audit  
**Status:** Frozen Prospective Audit & Lineage Novelty Contract  
**Date:** 2026-09-29  
**Primary Target Venue:** Q1–Q3 Health Informatics / Systems Journal (Journal of Medical Systems → Methods of Information in Medicine → Health Information Science and Systems)

---

## 1. Executive Summary & Problem Formulation

In clinical AI and multi-agent Clinical Decision Support Systems (CDSS), autonomous AI agents and human clinicians collaboratively iteratively refine mutation proposals before persisting changes to Electronic Health Record (EHR) databases. A multi-turn clinical workflow typically progresses through distinct operational stages:

1. **Root Inference Generation ($t_1$):** An AI agent consumes a governed health disclosure snapshot $H_0$, executes model inference $I_0$, and generates an initial mutation proposal $P_0$ (e.g., recommending a medication dosage modification or care plan revision).
2. **Human-in-the-Loop Review or Multi-Agent Adaptation ($t_2$):** A human clinician or secondary specialist agent reviews $P_0$. The clinician may accept, modify, adjust, or refine the proposed payload, producing a child proposal $P_1$.
3. **Transactional Write Admission ($t_3$):** The refined proposal $P_1$ is submitted to the relational database commit kernel for durable persistence.

In traditional software architectures, distributed workflows, and CDSS audit systems, human review or agent adaptation introduces a critical systems vulnerability: **Lineage Laundering and Route Downgrade**.

```text
[UNSAFE TRADITIONAL CDSS WORKFLOW]
t1: Snapshot H0 -> Inference I0 -> Model Proposal P0 (bound to H0)
                                        |
t2: Clinician reviews & modifies ------+ -> Child Proposal P1
                                        |  (Attributed to Clinician; I0 stripped!)
                                        v
t3: DB Commit -> Admitted as standard human write (base_version_only route)
                 *** RESULT: AI provenance laundered; H0 freshness & consent ignored! ***
```

When a clinician modifies an AI-generated proposal, traditional systems treat the clinician's explicit sign-off as an **authoritative privilege transfer** or **epistemic firewall**. The downstream database mutation is attributed entirely to the human user as an un-bound transaction (`base_version_only`), stripping the root inference consumption binding $I_0$. Consequently, if the original disclosure snapshot $H_0$ consumed by the AI was corrupted, truncated, or stale, or if the patient revoked consent for AI optimization between $t_1$ and $t_3$, the database commit kernel has no mechanism to detect the violation because the machine lineage was laundered.

GLHS R3 resolves this vulnerability through **Non-Downgradable Multi-Agent Proposal Lineage**:

> **The Lineage Non-Downgrade Invariant:** Human review or adaptation cannot strip or weaken the root inference consumption binding ($I_0$) or convert a snapshot-bound proposal lineage into an un-bound `base_version_only` proposal. Every child proposal $P_1$ descending from a model inference $I_0$ permanently retains $I_0$ as its root binding and remains subject to full commit-time GRWC revalidation against $H_0$, current clinical state $S(t_c)$, and dynamic governance $G(t_c)$.

This audit evaluates human-in-the-loop and multi-agent proposal lineage against foundational literature in W3C PROV provenance modeling, distributed delegation security, and CDSS audit trails, establishing strict non-novelty surrenders and bounding the defensible scientific claims of the R3 program.

---

## 2. Formalization of Non-Downgradable Multi-Agent Lineage

### 2.1 Schema & Structural Definitions

Following `GLHS_R3_MASTER_SPEC.md` (§3.4) and `GLHS_R3_TECHNICAL_DESIGN.md` (§6), a proposal $P$ in GLHS R3 is defined as a tuple:

$$P = \langle \text{id}, \text{root\_id}, \text{parent\_id}, I_{\text{id}}, \text{mode}, V_{\text{base}}, V_{\text{pol}}, V_{\text{con}}, \mathbf{D}(P), M_{\text{asserted}}, \text{op}, \text{payload\_digest}, \text{origin}, t_{\text{created}} \rangle$$

Where:
- $\text{id}$: Unique identifier of the proposal $P$.
- $\text{root\_id}$: Immutable identifier of the root proposal in the derivation tree ($P_{\text{root}}$).
- $\text{parent\_id}$: Identifier of the immediate parent proposal ($P_{\text{parent}}$), or $\emptyset$ if $P$ is the root proposal.
- $I_{\text{id}}$: Reference to the server-owned `GlhsInferenceContextBinding` ($I_0$).
- $\text{mode} \in \{\text{"strict\_grwc"}, \text{"snapshot\_bound"}, \text{"base\_version\_only"}\}$: Binding admission mode.
- $V_{\text{base}}$: Target base entity version at proposal compilation.
- $V_{\text{pol}}, V_{\text{con}}$: Active policy and consent versions expected by the proposal.
- $\mathbf{D}(P)$: Semantic state dependency vector required for target operation $\text{op}$.
- $M_{\text{asserted}}$: Set of evidence IDs asserted by the proposal payload.
- $\text{origin} \in \{\text{"model"}, \text{"human\_review"}, \text{"multi\_agent\_refinement"}, \text{"system"}\}$: Entity origin indicator.

### 2.2 Formal Lineage Invariants

In accordance with `formal_invariants_r3.json`, GLHS R3 defines three formal invariants governing proposal lineage:

#### Invariant I09: Lineage Preservation (`I09_lineage_preservation`)
Every reviewed proposal originating from human review or agent adaptation must preserve the root proposal identifier and the root inference context binding:

$$\forall P \in \mathcal{P}: \text{origin}(P) \in \{\text{"human\_review"}, \text{"multi\_agent\_refinement"}\} \implies \left( \text{root\_id}(P) \neq \emptyset \land I_{\text{id}}(P) = I_{\text{id}}(\text{Root}(P)) \right)$$

#### Invariant I11: Anti-Downgrade Routing (`I11_no_weak_route_downgrade`)
Any proposal whose origin or lineage ancestor is an AI model is strictly forbidden from executing under the `base_version_only` commit route:

$$\forall P \in \mathcal{P}: \left( \text{origin}(P) = \text{"model"} \lor \text{origin}(\text{Root}(P)) = \text{"model"} \right) \implies \text{mode}(P) \neq \text{"base\_version\_only"}$$

#### Invariant I13: Non-Downgradable Human Lineage (`I13_non_downgradable_human_lineage`)
Human adaptation of a model proposal cannot alter or strip the root inference binding, target snapshot ID, or binding mode to bypass GRWC admission checks:

$$\begin{aligned}
\forall P \in \mathcal{P}: & \left( \text{origin}(P) = \text{"human\_review"} \land \text{origin}(\text{Root}(P)) = \text{"model"} \right) \implies \\
& \left( I_{\text{id}}(P) = I_{\text{id}}(\text{Root}(P)) \land \text{mode}(P) = \text{"snapshot\_bound"} \land H_{\text{id}}(P) = H_{\text{id}}(\text{Root}(P)) \right)
\end{aligned}$$

```text
[GLHS R3 NON-DOWNGRADABLE LINEAGE ATOM]
Root Model Proposal P0:
  id: "prop_001", root_id: "prop_001", parent_id: null
  inference_binding_id: "bind_9948", context_binding_mode: "strict_grwc"
  origin: "model", source_snapshot_id: "snap_4401"
         |
         | (Clinician adapts dosage in UI)
         v
Child Reviewed Proposal P1:
  id: "prop_002", root_id: "prop_001", parent_id: "prop_001"
  inference_binding_id: "bind_9948"  <-- [IMMUTABLE INHERITANCE]
  context_binding_mode: "strict_grwc" <-- [CANNOT DOWNGRADE TO base_version_only]
  origin: "human_review", source_snapshot_id: "snap_4401"
```

---

## 3. Comparative Literature Evaluation across Three Foundations

We evaluate GLHS R3's lineage mechanism against three established bodies of literature: W3C PROV-DM, Distributed Workflow Security & Delegation Trees, and Clinical Decision Support System (CDSS) Audit Trails.

### 3.1 Domain 1: W3C PROV-DM Revision & Delegation Relations

#### 3.1.1 Architectural Mechanism
The W3C Provenance Data Model (PROV-DM; Moreau et al., 2013; Missier et al., 2013; Groth & Moreau, 2013) defines a conceptual data model for tracking derivation history across entities, activities, and agents. Standard PROV-DM provides core relations:
- $\text{wasDerivedFrom}(e_2, e_1)$: Entity $e_2$ was generated using data from entity $e_1$.
- $\text{wasRevisionOf}(e_2, e_1)$: A specific derivation indicating $e_2$ is a revised version of $e_1$.
- $\text{actedOnBehalfOf}(ag_2, ag_1, a)$: Agent $ag_2$ acted on behalf of agent $ag_1$ during activity $a$ (delegation).
- $\text{wasAttributedTo}(e, ag)$: Entity $e$ is attributed to agent $ag$.
- $\text{wasGeneratedBy}(e, a)$: Entity $e$ was created by activity $a$.

#### 3.1.2 Mechanistic Limitations & Structural Deficiencies
1. **Descriptive Graph vs. Prescriptive Admission Gating:** W3C PROV-DM is an **open-world descriptive ontology**. It provides a schema for serializing what occurred *post-hoc* into an RDF/XML/JSON graph. It possesses zero execution semantics, zero transaction boundaries, and zero write admission gating. PROV-DM cannot prevent an application from committing a write that violates provenance rules.
2. **Malleability & Graph Truncation:** In standard PROV-DM graphs, a downstream agent or service can emit a provenance fragment asserting that entity $e_3$ is a brand new root entity, omitting the $\text{wasRevisionOf}$ or $\text{wasDerivedFrom}$ edge linking back to $e_1$. PROV-DM has no transactional kernel to reject graph truncation or enforce non-downgradability.
3. **Absence of Disclosure-Consumption Binding:** PROV-DM records that an activity $a$ $\text{used}$ an entity $e_1$. It does not cryptographically bind the exact model-visible projection digest ($H_{\text{proj}}$) or request envelope ($H_{\text{env}}$) of an LLM invocation to a relational database commit transaction executing under row locks.

#### 3.1.3 The GLHS R3 Contrast
GLHS R3 transitions provenance from an **open-world observational graph** into a **closed-world transactional commit predicate**:
- While W3C PROV describes derivation, GLHS R3 enforces derivation inside the database commit transaction (`commit_kernel.py`).
- Attempting to omit `root_proposal_id` or set `context_binding_mode = "base_version_only"` on a human-reviewed child proposal causes immediate transaction abort with `commitment_lineage_base_only_forbidden`.

---

## 3.2 Domain 2: Distributed Workflow Security & Delegation Trees

#### 3.2.1 Architectural Mechanism
Distributed workflow security, capability delegation, and provenance-aware storage architectures govern privilege transfer across multi-party workflows:
- **Delegation Calculus & Privilege Attenuation:** Lampson et al. (*Calculus for Access Control*, 1993), Howell & Kotz (*Formal Model for Delegation*, 2000), and SPKI/SDSI (Ellison et al., 1999) formalize how Principal $A$ delegates authority to Principal $B$ using proxy certificates (RFC 3820) or capability attenuation chains (Macaroons; Birgisson et al., 2014).
- **Provenance-Aware Operating & Storage Systems:** PASS (Braun et al., 2008), Linux Provenance Modules (LPM; Bates et al., 2015), and CamFlow (Pasquier et al., 2017) capture kernel-level information flow and enforce access control over derivation graphs.

#### 3.2.2 Mechanistic Limitations & Structural Deficiencies: The Delegation Transfer Fallacy
1. **The Delegation Authority Transfer Fallacy:** In classical workflow authorization, delegation models **privilege transfer** ("Does Agent $B$ have authority to act for Principal $A$?"). When a human user intervenes in a workflow and signs an action, classical access control treats the human's signature as a **superseding authorization**. The human's credentials subsume and replace the automated agent's credentials.
2. **Provenance Laundering by Design:** Under standard RBAC/DAC delegation frameworks, when Dr. Alice modifies an AI proposal, the resulting request payload is signed by Dr. Alice's session token. The storage engine checks: *"Is Dr. Alice authorized to write medication orders? Yes."* The database executes the commit as an ordinary user transaction. The fact that the proposal originated from an AI inference $I_0$ that observed disclosure snapshot $H_0$ is stripped from the database commit check.
3. **Capability Attenuation vs. Consumption Attestation:** Cryptographic delegation chains (such as Macaroons) attenuate authorization caveats (e.g., restricting time or API endpoints). They do **not** bind the non-deterministic LLM input disclosure snapshot $H_0$ to downstream write admission.

#### 3.2.3 The GLHS R3 Contrast
GLHS R3 strictly rejects the assumption that human authorization subsumes machine provenance:
- Under GRWC, human intervention adds human authorization, but **cannot erase machine consumption binding**.
- Proposal $P_1$ carries both Dr. Alice's actor identity (`actor_id = "user_doc_99"`) AND the immutable root inference binding ($I_{\text{id}} = \text{"bind\_9948"}$).
- The commit kernel enforces that even though Dr. Alice approved the change, the payload must still satisfy $EvidenceCovered(P_1, H_0)$, and $H_0$ must still pass temporal, consent, and state freshness checks at commit time $t_c$.

---

## 3.3 Domain 3: Human-in-the-Loop Clinical Decision Support Systems (CDSS Audit Trails)

#### 3.3.1 Architectural Mechanism
Clinical Decision Support Systems (CDSS) and clinical AI governance frameworks manage human interaction with automated medical recommendations:
- **CDSS Audit Trails & Guideline Systems:** Systems based on Arden Syntax, PROforma, EON, Curcin et al. (*JBI* 2017), and Margheri et al. (*IJMI* 2020) maintain audit logs recording when alerts or guidance rules are triggered and displayed to clinicians.
- **Clinician Override & Sign-off Workflows:** Standard EHRs (Epic, Cerner, OpenMRS) record clinician actions ("Accepted", "Rejected", "Modified with reason").
- **Clinical AI Documentation Standards:** Standards such as FUTURE-AI (Lekadir et al., *BMJ* 2025) and SMART documentation (JAMIA 2026) mandate lifecycle traceability and audit logging for AI recommendations.

#### 3.3.2 Mechanistic Limitations & Structural Deficiencies: The Clinical Epistemic Firewall Fallacy
1. **The Epistemic Firewall Fallacy:** Traditional CDSS architectures treat clinician sign-off as a legal and epistemic firewall. The system assumes that because a licensed clinician reviewed the proposal, the clinician independently verified all underlying patient data, active consent directives, and drug interactions.
2. **Automation Bias & Cognitive Load Vulnerabilities:** Empirical health informatics literature demonstrates that clinicians under alert fatigue and high cognitive load frequently click "Accept" or make minor dosage tweaks without re-auditing whether the CDSS observed a complete, fresh patient record.
3. **Decoupled Audit Logs:** In existing CDSS implementations, the alert log (recording what the CDSS recommended) and the medication order table (recording what was saved to PostgreSQL) are separate database entities. The medication order table has no foreign key constraint, transaction lock predicate, or GRWC contract linking the order to the CDSS disclosure snapshot.
4. **Un-bound Mutation Risk:** If an AI model proposes a medication update based on an incomplete snapshot $H_0$ (missing a critical kidney function lab result due to a read-path glitch), and a clinician accepts the proposal, standard EHRs commit the order directly to the database. The system never re-validates $H_0$ against current database state $S(t_c)$ at commit time.

#### 3.3.3 The GLHS R3 Contrast
GLHS R3 eliminates the epistemic firewall assumption by embedding GRWC directly into the database write path:
- Clinician review is a **necessary condition** for human-in-the-loop admission, but **not a sufficient condition** to bypass machine governance.
- If the AI proposal $P_0$ was generated from snapshot $H_0$, and during clinician review the patient revokes consent or another clinician commits an conflicting order, the commit kernel aborts Dr. Alice's submission under row locks, returning `stale_entity_partition` or `consent_revoked`.
- Clinician approval cannot launder stale or unconsented AI disclosures into persistent EHR state.

---

## 4. Comprehensive Lineage Literature Comparison Matrix

The following matrix provides an exhaustive technical comparison between GLHS R3's Non-Downgradable Lineage and nearest-neighbor paradigms:

| Architectural Property | W3C PROV-DM (Moreau et al. 2013) | Distributed Delegation Trees (Lampson 1993, Macaroons) | Kernel Provenance Systems (PASS, LPM, CamFlow) | CDSS Audit Trails (Curcin 2017, Margheri 2020) | AI Agent Memory (MemTX, MemTxn 2026) | GLHS R3 (Non-Downgradable Lineage / GRWC) |
|---|---|---|---|---|---|---|
| **Primary Objective** | Open-world conceptual provenance modeling | Cryptographic privilege delegation & attenuation | Whole-system OS information flow tracking | Audit logging of clinical alerts & clinician sign-offs | Staging uncommitted agent belief graph updates | Non-downgradable continuous verification of AI disclosure to write |
| **Lineage Representation** | RDF/XML/JSON Directed Acyclic Graph (DAG) | Cryptographic capability chain / HMAC caveat list | Kernel dependency DAG over inodes & processes | Informational audit log / database trace table | In-memory agent belief graph & patch history | Relational DB Proposal Tree with immutable root binding |
| **Enforcement Point** | None; post-hoc descriptive representation | Gateway interceptor / authorization check | OS system call hook / LSM module | Application UI log event writer | Agent state machine / tool invocation runner | Atomic Database Commit Kernel inside DB transaction |
| **Retention of Root AI Binding ($I_0$) under Human Adaptation** | Optional; graph edges can be omitted by editor | **NO;** Human credentials replace machine credentials | Preserves OS process lineage; unaware of LLM prompts | **NO;** Clinician sign-off severs machine alert link | N/A (Focuses on autonomous agent patches) | **YES; Immutable root_proposal_id & inference_binding_id** |
| **Protection against Lineage Laundering** | None; open-world graph permits arbitrary subgraphs | **FAIL;** Privilege transfer explicitly launders provenance | Prevents OS process spoofing; blind to application semantic route | **FAIL;** Clinician sign-off converts AI write to user write | None; client can alter patch provenance | **YES; Strict rejection of base_version_only downgrade (I11, I13)** |
| **Commit-Time State & Consent Revalidation** | None | None | None | None | Partial; checks belief version tags | **YES; Atomic revalidation under PostgreSQL row locks** |
| **Evidence Scope Enforcement ($EvidenceCovered$)** | None | None | None | None | Verifies citation existence in knowledge base | **YES; Asserts P_1 evidence subset of H_0 manifest (I07)** |
| **Fail-Closed Reason Codes** | None | `invalid_macaroon`, `permission_denied` | `EACCES`, `EPERM` | None | `patch_conflict` | `commitment_lineage_base_only_forbidden`, `lineage_downgrade` |

---

## 5. Strict Novelty Bounds & Non-Novelty Declarations for Lineage

To maintain scientific integrity and adhere to Requirements **SCI-001**, **SCI-002**, and **SCI-003**, GLHS R3 explicitly surrenders broad novelty claims for general lineage mechanisms and defines its precise scientific contribution.

### 5.1 Surrendered Lineage Claims (Definitive Non-Novelty Declarations)

GLHS R3 explicitly surrenders and strictly forbids claiming novelty for the following concepts and structures:

1. **W3C PROV Graph Representations & Derivation Modeling:** Representing data lineage using DAG structures, nodes, edges, or derivation terms (`wasDerivedFrom`, `wasRevisionOf`) is established prior art (W3C PROV-DM 2013, Provenance Semirings 2007). GLHS R3 makes no novelty claim for graph-based provenance representations.
2. **Delegation Trees & Privilege Attenuation:** Delegating rights across multi-party workflows, delegating capabilities, or using proxy certificates (RFC 3820, Macaroons) is mature security art. GLHS R3 makes no novelty claim for capability delegation.
3. **CDSS Audit Trails & Clinician Override Logging:** Recording clinician alert responses, override reason codes, or maintaining audit tables in healthcare software (Arden Syntax, Curcin et al. 2017, Margheri et al. 2020) is established medical informatics practice. GLHS R3 makes no novelty claim for logging clinician reviews.
4. **Multi-Agent Message Passing & Sequential Proposal Refinement:** Architectures where Agent $A$ passes a message or proposal to Agent $B$ for critique or modification (Autogen, LangGraph, CrewAI) are established software design patterns. GLHS R3 makes no novelty claim for multi-agent proposal refinement workflows.
5. **Relational Database Parent-Child Foreign Keys:** Storing parent proposal references (`parent_proposal_id`) in a relational database table is standard database design. GLHS R3 makes no novelty claim for relational parent pointers.

### 5.2 The Specific Lineage Novelty Claim

The sole, defensible scientific contribution of GLHS R3 regarding proposal lineage is:

> **Non-downgradable, transactional enforcement of root inference consumption bindings across human-in-the-loop and multi-agent proposal adaptations within database write admission.**

#### 5.2.1 Deconstruction of the Specific Lineage Claim
1. **Non-Downgradable:** Human review, clinician adaptation, or downstream multi-agent refinement cannot strip the root inference binding $I_0$ or downgrade a snapshot-bound proposal into an un-bound `base_version_only` route.
2. **Root Inference Consumption Binding Retention:** The commit kernel enforces that child proposal $P_1$ remains cryptographically and structurally bound to the exact disclosure snapshot $H_0$ consumed by the original model inference $I_0$.
3. **Transactional Commit Enforcement:** Rather than relying on post-hoc audit logs or human epistemic firewalls, the lineage invariant is enforced atomically inside the relational database transaction executing the write under strict concurrency locks.

### 5.3 Boundary of Lineage Guarantees: What Non-Downgradable Lineage Does NOT Prove
- **No Guarantee of Human Review Quality:** The lineage invariant guarantees that human modification does not launder machine context; it does **not** prove that the human clinician conducted a thorough clinical evaluation of the proposal payload.
- **No Proof of Causal Intent in Human Modifications:** The invariant records that $P_1$ was derived from $P_0$ by human review; it cannot prove the cognitive motivation of the human reviewer.
- **Application Server Trust Boundary:** Lineage enforcement assumes that the application server executing the commit kernel has not been compromised at the root kernel level.

---

## 6. Program Traceability & Engineering Directives

This audit directly maps to and enforces the core requirements established across GLHS R3 program specifications:

| Requirement ID | Specification Document | Requirement Description | Lineage Audit Conformance & Enforcement |
|---|---|---|---|
| **ARCH-004** | `GLHS_R3_REQUIREMENTS.md` | Proposal retains immutable inference lineage ($I_{\text{id}}$) | **Fully Conforming.** Section 2.2 formalizes Invariant I09 (`I09_lineage_preservation`). |
| **ARCH-005** | `GLHS_R3_REQUIREMENTS.md` | Human review cannot erase or launder model lineage | **Fully Conforming.** Section 2.2 formalizes Invariant I13 (`I13_non_downgradable_human_lineage`). |
| **ARCH-009** | `GLHS_R3_REQUIREMENTS.md` | Prevent weak-route downgrade (`base_version_only` rejection) | **Fully Conforming.** Section 2.2 formalizes Invariant I11 (`I11_no_weak_route_downgrade`). |
| **SCI-001** | `GLHS_R3_REQUIREMENTS.md` | Centered novelty strictly on GRWC & Non-Downgradable Admission | **Fully Conforming.** Section 5.2 bounds the lineage contribution to transactional non-downgradable binding retention. |
| **SCI-002** | `GLHS_R3_REQUIREMENTS.md` | Surrender claims for PROV graphs, delegation, and CDSS logs alone | **Fully Conforming.** Section 5.1 explicitly surrenders 5 non-novel lineage categories with comprehensive literature citations. |
| **EXP-001** | `GLHS_R3_REQUIREMENTS.md` | Actual inference continuity under human review tested (E01) | **Fully Conforming.** Section 6 directives mandate Attack Family 10 testing in Experiment E01. |
| **EXP-006** | `GLHS_R3_REQUIREMENTS.md` | Anti-downgrade routing verification (E06) | **Fully Conforming.** Directives mandate testing route downgrade rejection in Experiment E06. |

### 6.1 Directives for Engineering & Test Execution

1. **Commit Kernel Rejection Codes:** The database admission engine (`commitment_gateway.py` and `commit_kernel.py`) must enforce exact rejection codes for lineage violations:
   - `commitment_lineage_binding_missing`: Raised when a child proposal lacks a root inference binding.
   - `commitment_lineage_base_only_forbidden`: Raised when a model-derived proposal attempts to execute via `base_version_only`.
   - `commitment_lineage_snapshot_mismatch`: Raised when a child proposal attempts to alter the `source_snapshot_id`.
   - `lineage_downgrade`: Raised on any structural attempt to strip model lineage.
2. **Experiment E01 — Attack Family 10 (Human-Review Lineage Laundering):**
   - The test harness must simulate a human clinician attempting to submit a modified proposal $P_1$ with `context_binding_mode = "base_version_only"` or with a cleared `inference_binding_id`.
   - The test must verify that the PostgreSQL commit kernel rejects the submission with 100% precision, demonstrating that human review cannot launder machine provenance.
3. **Experiment E06 — Anti-Downgrade factorial:**
   - Execute prospective ablation testing comparing strict GRWC, snapshot-only mode, and legacy base-version-only mode across human-modified proposals to empirically prove the necessity of Invariants I09, I11, and I13.

---
*End of Literature & Lineage Novelty Audit — GLHS R3 Phase 2*
