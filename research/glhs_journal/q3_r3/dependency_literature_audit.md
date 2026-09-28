# GLHS R3 Literature & Novelty Audit: Schema-Derived Dependency Completeness

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Artifact Path:** `research/glhs_journal/q3_r3/dependency_literature_audit.md`  
**Author / Role:** Agent A — Literature & Novelty  
**Phase:** Phase 3 — Dependency Literature & Novelty Audit  
**Status:** Frozen Prospective Audit & Novelty Contract  
**Date:** 2026-09-29  
**Primary Target Venue:** Q1–Q3 Health Informatics / Systems Journal (*Journal of Medical Systems* → *Methods of Information in Medicine* → *Health Information Science and Systems*)

---

## 1. Executive Summary & Problem Formulation

In transactional database systems and optimistic concurrency frameworks, concurrency control hinges on **read-set validation**: ensuring that data items read during transaction execution have not been concurrently modified before write commit. Classical concurrency control models—including Optimistic Concurrency Control (OCC), Serializable Snapshot Isolation (SSI), Predicate Locking, and Software/Hardware Transactional Memory (STM/HTM)—operate under a foundational implicit assumption:

> **The Classical Read-Set Assumption:** The client application, instruction set architecture (ISA), or query engine accurately, exhaustively, and deterministically registers all data items and logical predicates read during execution into a machine-observable read-set ($RS$).

In longitudinal clinical AI and agentic decision support systems (CDSS), an autonomous or human-in-the-loop Neural Large Language Model (LLM) agent generates structured clinical mutation proposals (e.g., modifying medication dosages, superseding allergy assertions, or reconciling problem lists) based on governed health disclosures. This operational pattern invalidates the classical read-set assumption due to a fundamental epistemic disconnect:

1. **Unconstrained Model Output:** Neural LLMs are non-deterministic, probabilistic token generators. If the architecture relies on the model to self-report its read dependencies (e.g., asking the LLM to emit a list of entity IDs or citations it relied upon in its output JSON payload), the model cannot be trusted to generate a complete or accurate read-set.
2. **Omission Vulnerabilities:** Probabilistic sampling, attention decay over long clinical contexts, prompt injection, or context truncation can cause an LLM to omit critical prerequisite data items (such as concurrent nephrotoxic drug orders, renal function lab values, or active patient consent epochs) from its declared read vector.
3. **Validation Blind Spots & Silent Write-Skew:** Under standard optimistic validation, omitting a read dependency removes that item from read-set intersection checks. Consequently, if a concurrent transaction modifies the omitted entity between inference compilation ($t_1$) and write admission ($t_3$), the validation kernel experiences **zero conflict aborts**, admitting a clinically dangerous mutation over stale or invalidated preconditions.

GLHS R3 resolves this fundamental vulnerability through **Schema-Derived Dependency Completeness** (formalized in Invariant **I10: `I10_dependency_completeness`**). Rather than trusting probabilistic LLM output, GLHS R3 derives the required minimum dependency vector deterministically from trusted, server-side clinical operation schemas (`OperationDependencyRule`). Caller-proposed dependency vectors are validated against schema-derived minimums: any omission of a required entity, evidence item, or governance coordinate triggers an immediate fail-closed admission rejection (`dependency_contract_omission`, `dependency_missing`).

This audit evaluates Schema-Derived Dependency Completeness against classical database concurrency literature, formalizes the core scientific contrast, establishes non-novelty boundaries, and documents implementation and test alignment within the GLHS R3 codebase.

---

## 2. Classical Concurrency Literature Evaluation

### 2.1 Classical Write-Skew Anomalies in Snapshot Isolation (SI)

#### Foundational References
- **Berenson et al. (SIGMOD 1995):** *A Critique of ANSI SQL Isolation Levels* (ACM SIGMOD 1995, pp. 1-10. DOI: 10.1145/223784.223785).
- **Fekete et al. (ACM TODS 2005):** *Making Snapshot Isolation Serializable* (ACM Transactions on Database Systems, 30(2):492-528. DOI: 10.1145/1071610.1071615).

#### Literature Analysis & Mechanisms
Berenson et al. demonstrated that ANSI SQL-92 isolation definitions were incomplete and introduced Snapshot Isolation (SI). Under SI, transactions read from a transaction-start snapshot and execute writes optimistically, applying First-Committer-Wins (FCW) to prevent dirty writes ($G1$) and lost updates ($P4$). However, Berenson et al. identified that SI permits non-serializable anomalies, most notably **Write Skew ($A5B$)**:

$$\text{Write Skew } (A5B): \quad r_1[x] \dots r_2[y] \dots w_1[y'] \dots w_2[x'] \dots c_1 \dots c_2$$

Where transactions $T_1$ and $T_2$ read overlapping snapshots of data items $x$ and $y$ that satisfy a multi-record integrity constraint (e.g., $x + y > 0$), but update disjoint items ($T_1$ writes $y$, $T_2$ writes $x$). Because $WS(T_1) \cap WS(T_2) = \emptyset$, FCW permits both to commit, violating the integrity constraint.

Fekete et al. formalized the Dependency Serialization Graph (DSG) for SI and proved that any non-serializable execution contains a cycle with two consecutive **rw-antidependency edges** ($T_1 \xrightarrow{rw} T_2 \xrightarrow{rw} T_3$, where $T_1$ reads a version of item $i$ and $T_2$ writes a newer version of $i$). To guarantee serializability under SI, Fekete et al. established that applications must explicitly materialize conflicts by promoting reads to writes (e.g., using `SELECT FOR UPDATE` or dummy updates) to force write-set overlap.

#### Contrast with GLHS R3
In Longitudinal Health AI, write-skew manifests when an LLM agent updates Medication $A$ based on Lab $L$ (e.g., adjusting an aminoglycoside dose based on serum creatinine), but fails to declare Lab $L$ in its read-set. Under classical SI/OCC, a concurrent update to Lab $L$ produces an rw-antidependency ($T_{\text{agent}} \xrightarrow{rw} T_{\text{lab\_update}}$), but because $WS(T_{\text{agent}}) = \{\text{Medication } A\}$ and $WS(T_{\text{lab\_update}}) = \{\text{Lab } L\}$, standard FCW engines admit both commits, creating clinical write-skew.

GLHS R3 prevents this anomaly by schema construction. The deterministic rule for `RECONCILE_MEDICATION` or `COMMIT_PROPOSAL` mandates that the minimum dependency vector $\mathbf{D}_{\text{schema\_min}}$ must include entity locks for target domain keys, evidence references, and governance epochs. By enforcing $\mathbf{D}_{\text{schema\_min}} \subseteq \mathbf{D}_{\text{proposed}}$, the system guarantees that concurrent modifications to prerequisite clinical coordinates or governance states trigger CAS version conflicts or advisory lock blocking during write admission ($t_3$).

---

### 2.2 Serializable Snapshot Isolation (SSI)

#### Foundational References
- **Cahill, Röhm, Fekete (SIGMOD 2008):** *Serializable Snapshot Isolation in PostgreSQL* (ACM SIGMOD 2008, pp. 729-738. DOI: 10.1145/1376616.1376690).
- **Ports & Grittner (PVLDB 2012):** *Serializable Snapshot Isolation in PostgreSQL* (PVLDB, 5(12):1850-1861. DOI: 10.14778/2367502.2367527).

#### Literature Analysis & Mechanisms
Cahill et al. introduced Serializable Snapshot Isolation (SSI), the first practical algorithm to dynamically track rw-antidependencies at runtime without blocking reads. Ports & Grittner detailed the production realization in PostgreSQL 9.1+. PostgreSQL SSI maintains lock-free `SIREAD` lock tags at tuple, page, and relation levels in shared memory. When a transaction writes a tuple, the engine checks for `SIREAD` locks held by active snapshot transactions. If a dangerous structure ($T_1 \xrightarrow{rw} T_2 \xrightarrow{rw} T_3$) forms in the lock graph, the database aborts one transaction with SQLSTATE `40001` (`serialization_failure`).

#### Contrast with GLHS R3
PostgreSQL SSI operates strictly *within* active SQL transactions inside the database engine, dynamically observing `SELECT` queries as they execute against engine tables. However, neural LLM inference runs **outside** the database transaction boundary: an LLM agent fetches snapshot $H$ at $t_1$, closes its read transaction, and executes non-deterministic inference over seconds or minutes via external APIs (e.g., DeepSeek, Anthropic, OpenAI). By the time the LLM emits a proposal at $t_3$, the database transaction that issued $H$ is terminated, releasing all `SIREAD` locks!

Standard RDBMS SSI cannot track rw-antidependencies across asynchronous out-of-band LLM execution passes. GLHS R3 bridges this temporal chasm by carrying the schema-derived dependency vector across the asynchronous gap and reconstructing explicit entity CAS version locks and advisory governance locks inside the atomic write admission transaction at $t_3$.

---

### 2.3 Predicate Locking & Precision Locking

#### Foundational References
- **Eswaran et al. (CACM 1976):** *The Notions of Consistency and Predicate Locks in a Database System* (Communications of the ACM, 19(11):624-633. DOI: 10.1145/360363.360369).
- **Jordan, Banerjee, Batman (ACM TODS 1981):** *Precision Locks* (ACM Transactions on Database Systems, 6(1):107-123. DOI: 10.1145/319540.319548).

#### Literature Analysis & Mechanisms
Eswaran et al. established that serializability in relational databases requires locking logical predicates (e.g., `WHERE department = 'oncology'`) to prevent phantom insertions ($P3$). Because general predicate-predicate intersection testing is NP-complete or undecidable for complex query languages, Jordan et al. introduced **Precision Locking**. Under precision locking, reading transactions register predicate expressions, while writing transactions evaluate whether newly written physical tuples satisfy any registered read predicate. This eliminates predicate-predicate intersection overhead.

#### Contrast with GLHS R3
Precision locking assumes that the predicate registered by an application query accurately circumscribes the full logical domain of data items influencing the transaction. In neural CDSS workflows, an LLM agent receives a broad clinical context and generates a narrow mutation proposal based on complex, implicit multi-domain rules (e.g., drug-drug-allergy interactions). If the system attempts to infer read predicates from the model's output, unconstrained models emit incomplete or malformed predicates.

GLHS R3's schema-derived contract bypasses dynamic predicate parsing by mapping structured operation types (`operation_kind`) directly to canonical domain key specifications (`domain:semantic_key`) and governance epoch anchors (`policy_epoch:domain`, `consent:version`). This converts arbitrary clinical semantics into normalized, discrete entity coordinates that are validated deterministically without predicate satisfiability checks.

---

### 2.4 Transactional Memory Read-Set Validation

#### Foundational References
- **Herlihy & Moss (ISCA 1993):** *Transactional Memory: Architectural Support for Lock-Free Data Structures* (ACM/IEEE ISCA 1993, pp. 289-300. DOI: 10.1145/165123.165164).
- **Shavit & Touitou (PODC 1995):** *Software Transactional Memory* (ACM PODC 1995, pp. 11-20. DOI: 10.1145/224964.224987).

#### Literature Analysis & Mechanisms
Hardware and Software Transactional Memory (HTM/STM) provide atomic, isolated execution for multi-threaded memory operations. In HTM/STM, a transaction executes speculatively. Every CPU load instruction automatically adds the accessed memory address to a hardware cache line vector or software `Read-Set` ($RS$), while store instructions populate a `Write-Set` ($WS$). At commit, the runtime validates that no memory location in $RS$ has been modified by another thread since it was read.

#### Contrast with GLHS R3
HTM and STM rely on hardware bus trapping or compiler instrumentation: the execution engine physically intercepts every memory load instruction. In neural AI agents, there is no instruction bus connecting the LLM's matrix multiplications to the underlying relational database. The LLM consumes arbitrary prompt text and emits unstructured text.

GLHS R3 provides the semantic analogue of hardware bus trapping for neural agents: **Schema-Derived Derivation**. The commit kernel enforces that the *target clinical operation itself* dictates the minimum set of entity keys, evidence references, and governance epochs that *must* have been read and validated, preventing unconstrained neural networks from bypassing memory validation through read omission.

---

## 3. Mathematical Formalization & Architecture

### 3.1 Schema-Derived Dependency Completeness (Invariant I10)

Following `GLHS_R3_TECHNICAL_DESIGN.md` (§7) and `formal_invariants_r3.json`, GLHS R3 defines the dependency completeness contract through deterministic derivation functions.

#### 1. Operation Dependency Rule Definition
For every registered clinical operation kind $\text{op} \in \mathcal{O}$, the system registers an immutable rule:

$$R(\text{op}) = \langle \text{gov\_req}, \text{con\_req}, \text{ev\_req}, \text{access\_mode}, n_{\text{min\_entity}}, \text{allow\_superset} \rangle$$

#### 2. Deterministic Minimum Dependency Derivation
Given a structured application input $\text{Inp} = \langle \text{op}, \text{domain}, \mathbf{K}_{\text{semantic}}, V_{\text{pol}}, V_{\text{con}}, \mathbf{E}_{\text{ids}}, \mathbf{V}_{\text{obs}} \rangle$, the deterministic derivation kernel constructs the canonical minimum dependency vector:

$$\mathbf{D}_{\text{schema\_min}}(\text{Inp}) = \mathbf{D}_{\text{gov}} \cup \mathbf{D}_{\text{con}} \cup \mathbf{D}_{\text{entity}} \cup \mathbf{D}_{\text{evidence}}$$

Where:
- $\mathbf{D}_{\text{gov}} = \{ \langle \text{GOVERNANCE}, \text{"policy\_epoch:"} \mathbin{\Vert} \text{domain}, \text{READ}, 0, V_{\text{pol}} \rangle \}$ (if $\text{gov\_req} = \text{TRUE}$)
- $\mathbf{D}_{\text{con}} = \{ \langle \text{GOVERNANCE}, \text{"consent:"} \mathbin{\Vert} V_{\text{con}}, \text{READ}, 0, V_{\text{con}} \rangle \}$ (if $\text{con\_req} = \text{TRUE}$)
- $\mathbf{D}_{\text{entity}} = \bigcup_{k \in \mathbf{K}_{\text{semantic}}} \{ \langle \text{ENTITY}, \text{domain} \mathbin{\Vert} \text{":"} \mathbin{\Vert} k, \text{access\_mode}, \mathbf{V}_{\text{obs}}[k], \emptyset \rangle \}$
- $\mathbf{D}_{\text{evidence}} = \bigcup_{e \in \mathbf{E}_{\text{ids}}} \{ \langle \text{EVIDENCE}, \text{"evidence:"} \mathbin{\Vert} e, \text{READ}, 0, \emptyset \rangle \}$ (if $\text{ev\_req} = \text{TRUE}$)

#### 3. Superset Validation & Omission Rejection Rule
Let $\mathbf{D}_{\text{proposed}}$ be the dependency vector attached to a write proposal $P$. The kernel evaluates completeness via identity triples $\text{ID}(d) = \langle \text{kind}(d), \text{key}(d), \text{mode}(d) \rangle$:

$$\begin{aligned}
\text{Missing}(P) &= \{ \text{ID}(d) \mid d \in \mathbf{D}_{\text{schema\_min}} \} \setminus \{ \text{ID}(d) \mid d \in \mathbf{D}_{\text{proposed}} \} \\
\text{Extra}(P) &= \{ \text{ID}(d) \mid d \in \mathbf{D}_{\text{proposed}} \} \setminus \{ \text{ID}(d) \mid d \in \mathbf{D}_{\text{schema\_min}} \}
\end{aligned}$$

The proposal satisfies Invariant **I10 (`I10_dependency_completeness`)** if and only if:

$$\text{AdmissibleDeps}(P) \iff (\text{Missing}(P) = \emptyset) \land (\text{Extra}(P) = \emptyset \lor \text{allow\_superset}(R(\text{op}))) \land \text{VersionsMatch}(P)$$

$$\text{VersionsMatch}(P) \iff \forall d \in \mathbf{D}_{\text{proposed}} \cap \mathbf{D}_{\text{schema\_min}} : v_{\text{proposed}}(d) = v_{\text{schema\_min}}(d)$$

If $\text{Missing}(P) \neq \emptyset$, the commit kernel aborts immediately with fail-closed code `dependency_contract_omission` or `dependency_missing`.

---

## 4. System Comparison: Client Self-Reporting vs. Schema Derivation

The foundational contrast between classical/unconstrained agent dependency modeling and GLHS R3 is summarized across four core dimensions:

```text
[UNSTRAINED AGENT DEPENDENCY MODEL (UNSAFE)]
LLM Prompt -> Model Inference -> Self-Reported JSON Read-Set -> RDBMS Commit Kernel
                                           |
                              *** OMISSION RISK ***
                 Model omits renal lab value or consent epoch;
                 Validation passes; stale clinical write committed!

[GLHS R3 SCHEMA-DERIVED DEPENDENCY CONTRACT (SAFE)]
Application Schema -> Server Derivation Kernel -> Schema-Derived Min D_min
                                                          |
LLM Proposal -------> Proposed Deps D_prop -------------> Superset Check (D_min <= D_prop)
                                                          |
                                           +--------------+--------------+
                                           |                             |
                                    [Missing Item]               [Complete Set]
                                           |                             |
                                           v                             v
                                  FAIL-CLOSED ABORT              POSTGRESQL COMMIT
                             (dependency_contract_omission)    (Atomic CAS + Lock Revalidation)
```

| System Dimension | Classical OCC / SSI (Kung 1981, Cahill 2008) | Unconstrained LLM Self-Reporting | Hardware / Software TM (Herlihy 1993) | GLHS R3 (Schema-Derived GRWC) |
|---|---|---|---|---|
| **Read-Set Origin** | Dynamic SQL statements executed by client in DB transaction. | Self-reported citations or output JSON emitted by model. | Hardware bus loads or compiler-instrumented memory reads. | **Deterministic server derivation from operation schema (`OperationDependencyRule`).** |
| **Trust Model** | Trusted application query code. | **Untrusted, non-deterministic neural LLM output.** | Trusted CPU instruction execution / runtime instrumentation. | **Trusted application schema; zero trust in model self-reporting.** |
| **Omission Handling** | DB engine tracks all queries executed in transaction. | Model omissions bypass validation, causing **silent write-skew**. | CPU hardware traps all load instructions without omission. | **Fail-closed rejection (`dependency_contract_omission`) on any missing coordinate.** |
| **Governance Inclusion** | None (pure relational data tuples). | None or unreliable model text parsing. | None (pure memory addresses). | **Mandatory schema inclusion of policy epoch & consent version coordinates.** |
| **Temporal Boundary** | Synchronous inside active RDBMS transaction. | Asynchronous out-of-band execution. | Synchronous inside thread execution block. | **Asynchronous out-of-band inference bound to atomic $t_3$ commit transaction.** |
| **Superset Policy** | N/A (exact executed queries). | Unconstrained arbitrary strings. | Exact memory footprint. | **Controlled conservative superset allowed; subset strictly forbidden.** |

---

## 5. Definitive Non-Novelty Declarations & Bounded Novelty Contract

To maintain absolute academic integrity, GLHS R3 explicitly surrenders and forbids claiming novelty for established concurrency and schema primitives:

### 5.1 Forbidden Claims (Definitive Surrenders)
1. **Optimistic Read-Set Validation:** GLHS R3 does **not** claim to invent validation of read dependencies against concurrent writes prior to commit (established by Kung & Robinson 1981).
2. **Serializable Snapshot Isolation & Anti-Dependency Tracking:** GLHS R3 does **not** claim to invent SSI, SIREAD locks, or DSG cycle detection inside relational storage engines (established by Cahill et al. 2008, Ports & Grittner 2012).
3. **Predicate / Precision Locking:** GLHS R3 does **not** claim to invent predicate locks or evaluating write tuple intersections against read predicates (established by Eswaran et al. 1976, Jordan et al. 1981).
4. **Read-Set Interception:** GLHS R3 does **not** claim to invent the abstract concept of read-set tracking or transactional memory validation (established by Herlihy & Moss 1993).
5. **Schema Validation Engines:** GLHS R3 does **not** claim to invent structural JSON validation, Pydantic data schemas, or OpenAPI specifications.

### 5.2 The Narrow Novelty Boundary
The single, precise scientific contribution documented in this audit is:

> **The Schema-Derived Dependency Completeness Contract for Asynchronous Neural AI Mutations:** The formalization, implementation, and empirical validation of a server-owned, schema-derived dependency derivation mechanism that eliminates model-omission-induced write-skew and governance drift across asynchronous out-of-band LLM inference passes, enforcing $\mathbf{D}_{\text{schema\_min}} \subseteq \mathbf{D}_{\text{proposed}}$ as a mandatory precondition for atomic database commit.

---

## 6. Code Implementation & Verification Realization

### 6.1 Code Realization (`services/api/src/clara_api/glhs/dependency_contract.py`)

The dependency contract is operationalized in production python modules within `services/api/src/clara_api/glhs/`:

1. **Operation Registry (`_OPERATION_RULES`):** Maps operation kinds (`COMMIT_PROPOSAL`, `RECONCILE_MEDICATION`, `ACTIVATE_ASSERTION`, etc.) to explicit `OperationDependencyRule` instances enforcing required governance, consent, evidence, and entity access modes.
2. **Minimum Vector Derivation (`generate_dependency_vector`):** Accepts structured `DependencyGenerationInput` and deterministically constructs canonical `GeneratedDependencyVector` alongside its canonical digest.
3. **Superset Validation (`validate_proposed_dependencies`):** Performs identity matching ($\text{kind}, \text{key}, \text{mode}$) between minimum required dependencies and proposed dependencies, raising `GlhsInvariantError("dependency_contract_omission")` if any required dependency is absent or version-mismatched.
4. **Metadata Preservation (`dependency_generation_metadata`):** Serializes generation rules, digests, and contract versions into `GlhsAppliedTransition` audit records for immutable post-commit reconstructability.

### 6.2 Formal Invariant Mapping (`formal_invariants_r3.json`)

```json
{
  "id": "I10",
  "name": "I10_dependency_completeness",
  "description": "Proposal dependency vector must cover the schema-derived minimum dependency vector for the operation kind.",
  "category": "Dependency Contract",
  "formal_definition": "\\A p \\in proposals : MinDependencies(p.operation_kind, p.target) \\subseteq p.dependency_vector",
  "enforcement_point": "dependency_contract.py: generate_dependency_vector()",
  "target_experiment": "E05",
  "fail_closed_code": "dependency_contract_insufficient_entities, dependency_missing"
}
```

### 6.3 Test Verification (`services/api/tests/test_dependency_completeness.py`)

The test suite validates every boundary condition of the dependency contract:
- `test_lookup_operation_rule_unknown_raises`: Unknown operation types fail closed with `dependency_contract_unknown_operation`.
- `test_generate_dependency_vector_deterministic`: Derivation produces identical canonical vectors and digests across executions.
- `test_generate_dependency_vector_requires_evidence`: Operations requiring evidence fail closed if evidence references are omitted.
- `test_validate_proposed_omission_rejected`: Parametrized testing of omissions (governance, entity, evidence) verifying fail-closed `dependency_contract_omission` errors.
- `test_validate_proposed_conservative_superset_accepted`: Validates that adding extra entity locks (conservative supersets) passes validation when permitted by schema.
- `test_validate_proposed_extra_rejected_when_not_allowed`: Validates that strict schema operations reject unexpected extra dependencies (`dependency_contract_unexpected_extra`).
- `test_validate_proposed_version_mismatch`: Stale or corrupted entity versions in proposed vectors trigger immediate rejection (`dependency_contract_version_mismatch`).

---

## 7. Comparative Literature Matrix

| Domain / Paper | Canonical Reference | Primary Mechanism | Read-Set Derivation Source | Handles Untrusted Agent Omissions? | Enforces Governance Epochs? | Crosses Asynchronous Inference Gap? |
|---|---|---|---|---|---|---|
| **Optimistic Concurrency Control** | Kung & Robinson (1981) | Read/Write set intersection at commit phase. | Query engine memory buffers. | No (assumes trusted query code). | No | No (same DB transaction). |
| **Snapshot Isolation & Write-Skew** | Berenson et al. (1995), Fekete et al. (2005) | FCW + conflict materialization / DSG cycles. | Executed SQL queries. | No (omitted reads bypass FCW). | No | No (same DB transaction). |
| **Serializable Snapshot Isolation** | Cahill et al. (2008), Ports & Grittner (2012) | Lock-free `SIREAD` flags in shared memory. | Engine SQL execution hooks. | No (reads outside active DB transaction untracked). | No | No (requires open DB transaction). |
| **Precision Locking** | Jordan et al. (1981) | Write tuple testing against registered predicates. | Application query predicates. | No (unconstrained model predicates malformed). | No | No |
| **Software Transactional Memory** | Herlihy & Moss (1993), Shavit & Touitou (1995) | Address vector comparison at commit. | Hardware load instruction trapping. | No (no CPU load bus for LLMs). | No | No (same thread context). |
| **GLHS R3 (GRWC)** | **GLHS R3 (2026)** | **Schema-derived minimum vector validation ($\mathbf{D}_{\text{min}} \subseteq \mathbf{D}_{\text{prop}}$).** | **Trusted application schema (`OperationDependencyRule`).** | **YES (Fail-closed on any omission).** | **YES (Mandatory policy & consent epoch locks).** | **YES (Bound across asynchronous HTTP LLM passes).** |

---

## 8. Conclusion & Manuscript Guidance

Schema-Derived Dependency Completeness bridges the gap between classical transactional concurrency theory and modern neural AI architectures. By recognizing that neural LLMs cannot serve as authoritative sources for their own read-sets, GLHS R3 restores serializability and governance freshness guarantees to clinical write admission.

When describing this mechanism in manuscript revisions (Phase 10):
1. **Frame Accuracy:** Attribute optimistic read-set validation to Kung & Robinson (1981) and write-skew analysis to Berenson et al. (1995) and Fekete et al. (2005).
2. **Precision Claims:** Claim novelty *specifically* for deriving minimum dependency vectors deterministically from structured clinical operation schemas to prevent neural model read-set omissions across asynchronous inference boundaries.
3. **Traceability:** Cite Invariant **I10 (`I10_dependency_completeness`)**, implementation module `dependency_contract.py`, and prospective experiment **E05 (`dependency completeness`)**.
