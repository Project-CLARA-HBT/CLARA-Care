# GLHS R3 Protocol Schema Specification (`PROTOCOL_SCHEMA_SPEC.md`)

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Curator:** Agent B — Systems & Formal Architecture  
**Schema Identifier:** `glhs-r3-protocol.schema.json` (`schema_version: "glhs-r3-protocol.v1"`)  
**Git Provenance Baseline:**
- `system_under_test_sha`: `81f040d3e05905cc384239c5ae130f629e722d3e`
- `parent_harness_sha`: `e7a073749d8d3d434f6d47204238cc6655431f76`
- `freeze_timestamp_utc`: `2026-09-28T00:00:00Z`

---

## 1. Executive Summary & Architectural Scope

This specification establishes the unified formal schema and prospective verification rules governing all prospective experiment protocols (`E00` through `E14`) in Phase 4 of the GLHS R3 research program.

To eliminate retrospective bias, p-hacking, simulation misrepresentation, and unanchored claims, every experiment must:
1. Comply strictly with `glhs-r3-protocol.schema.json`.
2. Explicitly bind its execution to a frozen git revision and UTC freeze timestamp prior to execution.
3. Formally declare target invariants from the 15-invariant GLHS R3 registry (`I01` through `I15`).
4. Declare its exact physical backend engine and adhere to the backend attestation contract.
5. Define prespecified statistical estimands, confidence intervals, stopping rules, and artifact layouts.

---

## 2. Standard Schema Fields & Inviolable Definitions

The unified schema `glhs-r3-protocol.schema.json` mandates 16 top-level properties on every `protocol.json`:

| Field Name | Type | Allowed Values / Pattern | Semantic Description |
| :--- | :--- | :--- | :--- |
| `schema_version` | String | `"glhs-r3-protocol.v1"` | Canonical version string for R3 protocol declarations. |
| `protocol_id` | String | `^GLHS-R3-E[0-9]{2}-[A-Z0-9_]+$` | Globally unique protocol identifier. |
| `experiment_id` | String | `E00` through `E14` | Canonical 3-character experiment token. |
| `priority` | String | `"P0"`, `"P1"`, `"P2"` | Phase prioritization category. |
| `freeze_id` | String | `^GLHS-R3-E[0-9]{2}-FREEZE-[0-9]{8}-V[0-9]+$` | Cryptographic freeze registration ID. |
| `freeze_timestamp_utc` | String | ISO 8601 UTC timestamp | Prospective freeze timestamp (must precede trial execution). |
| `git_sha` | String | 40-character hex string | Root commit SHA containing code under test (`81f040d3...`). |
| `target_invariants` | Array[String] | Enum `[I01_state_isolation, ..., I15_clean_path_reachability]` | Subset of formal invariants evaluated by this experiment. |
| `backend_requirement` | String | Exhaustive engine enum (see Section 4) | Physical runtime engine required for valid execution. |
| `scientific_unit` | String | Non-empty string | Atomic scientific unit for statistical sample denominator $N$. |
| `primary_endpoints` | Array[Object] | Structured endpoint specifications | Prespecified primary hypotheses, thresholds, and metrics. |
| `secondary_endpoints` | Array[Object] | Structured endpoint specifications | Secondary, characterization, and latency metrics. |
| `sample_size` | Object | `{"total_executions_N": int, ...}` | Exact sample size allocation and breakdown. |
| `statistical_plan` | Object | `{"method": str, "confidence_level": float, ...}` | Inferential statistical framework (Wilson, Clopper-Pearson, TOST, McNemar). |
| `stopping_rules` | Object | `{"fail_closed_criteria": str, "missing_data_rule": str}` | Predefined rules governing test termination and data integrity. |
| `artifact_layout` | Object | `{"required_artifacts": [...], "artifact_directory": str}` | Mandatory leaf files and directory path. |

---

## 3. Formal Invariant Registry & Experiment Cross-Walk

The GLHS R3 formal invariant specification (`formal_invariants_r3.json`) defines 15 system and transaction invariants. All protocols link directly to this registry:

| Invariant ID | Formal Name | Architectural Enforcement Layer | Primary Target Experiments |
| :--- | :--- | :--- | :--- |
| `I01` | `I01_state_isolation` | `commit_kernel.py`: Phase 3 Dependency Revalidation | `E04`, `E05`, `E08`, `E09`, `E14` |
| `I02` | `I02_governance_freshness` | `commit_kernel.py`: Phase 3 Governance Revalidation | `E04`, `E05`, `E08`, `E14` |
| `I03` | `I03_phantom_free` | `lock_hierarchy.py`: Class 1, 2, 3 Advisory Locks | `E04`, `E08`, `E14` |
| `I04` | `I04_deadlock_free` | `lock_hierarchy.py`: Total Lock Acquisition Ordering | `E04`, `E08`, `E09`, `E14` |
| `I05` | `I05_idempotency_atomicity` | `commit_kernel.py`: Phase 1 & 2 Idempotency Gate | `E04`, `E10`, `E14` |
| `I06` | `I06_cas_monotonicity` | `commit_kernel.py`: Phase 5 CAS Monotonic Progression | `E04`, `E05`, `E08`, `E09`, `E14` |
| `I07` | `I07_evidence_closure` | `gateway.py`: `validate_exact_disclosure_dependency()` | `E01`, `E02`, `E03`, `E05`, `E13`, `E14` |
| `I08` | `I08_binding_immutability` | `models.py`: `_reject_glhs_ledger_mutation` listeners | `E01`, `E02`, `E03`, `E06`, `E07`, `E08`, `E14` |
| `I09` | `I09_lineage_preservation` | `commitment_gateway.py`: `_require_lineage_binding()` | `E01`, `E06`, `E14` |
| `I10` | `I10_dependency_completeness` | `dependency_contract.py`: `validate_proposed_dependencies()` | `E05`, `E12`, `E13`, `E14` |
| `I11` | `I11_no_weak_route_downgrade` | `commitment_gateway.py`: `validate_base_proposal_context()` | `E01`, `E06`, `E14` |
| `I12` | `I12_exact_inference_disclosure_continuity` | `gateway.py` & `commitment_gateway.py`: Two-Digest Attestation | `E01`, `E02`, `E03`, `E06`, `E07`, `E08`, `E10`, `E11`, `E12`, `E13`, `E14` |
| `I13` | `I13_non_downgradable_human_lineage` | `commitment_gateway.py`: Lineage Root Pinning | `E01`, `E06`, `E08`, `E14` |
| `I14` | `I14_undisclosed_evidence_rejection` | `gateway.py`: `validate_exact_disclosure_dependency()` | `E01`, `E08`, `E14` |
| `I15` | `I15_clean_path_reachability` | `commit_kernel.py`: `execute_atomic_glhs_commit()` | `E01`, `E04`, `E05`, `E06`, `E08`, `E09`, `E10`, `E14` |

---

## 4. Backend Requirement Taxonomy & Attestation Rules

To prevent misleading simulation claims, each protocol explicitly declares its backend requirement from the following closed vocabulary:

```text
                                  ┌─────────────────────────────┐
                                  │   glhs-r3-protocol.schema   │
                                  └──────────────┬──────────────┘
                                                 │
          ┌──────────────────────┬───────────────┴──────────────┬──────────────────────┐
          │                      │                              │                      │
┌─────────▼──────────┐ ┌─────────▼──────────┐         ┌─────────▼──────────┐ ┌─────────▼──────────┐
│ real_postgresql_16 │ │cross_runtime_node_ │         │bounded_model_      │ │live_llm_provider_  │
│                    │ │     python         │         │     checker        │ │     ledger         │
│ E01, E02, E03, E04,│ │                    │         │                    │ │                    │
│ E05, E06, E09, E10 │ │      E07           │         │      E08           │ │     E11, E12       │
└────────────────────┘ └────────────────────┘         └────────────────────┘ └────────────────────┘
          │                                                                            │
┌─────────▼──────────┐                                                       ┌─────────▼──────────┐
│ static_claim_audit │                                                       │ external_corpus_   │
│                    │                                                       │     evaluator      │
│      E00           │                                                       │      E13           │
└────────────────────┘                                                       └────────────────────┘
                                         ┌─────────────────────┐
                                         │hermetic_reproduction│
                                         │       engine        │
                                         │        E14          │
                                         └─────────────────────┘
```

### Complete Experiment Matrix (E00–E14)

| Exp ID | Directory Name | Priority | Backend Requirement | Scientific Unit | Sample $N$ | Primary Endpoint |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **E00** | `E00_literature_claim_freeze` | `P0` | `static_claim_audit` | `claim_assertion_clause` | 47 | Zero unbacked or forbidden novelty claim breaches |
| **E01** | `E01_inference_continuity` | `P0` | `real_postgresql_16` | `frozen_logical_proposal_schedule` | 768 | 0/640 invalid admissions ($\theta_{rej}=1.0$), 128/128 clean admissions |
| **E02** | `E02_binding_ablation` | `P0` | `real_postgresql_16` | `ablation_schedule_execution` | 2,816 | $2^4$ factorial component necessity; 0 false admissions on $B111$ |
| **E03** | `E03_minimal_comparator` | `P0` | `real_postgresql_16` | `comparator_schedule_execution` | 1,408 | Paired decision concordance & metadata byte overhead trade-off |
| **E04** | `E04_postgres_toctou` | `P0` | `real_postgresql_16` | `unique_logical_schedule` | 2,280 | Zero forbidden commits under randomized concurrent timing races |
| **E05** | `E05_dependency_completeness` | `P0` | `real_postgresql_16` | `clinical_operation_mutation_execution` | 312 | $P(\text{admit}\mid\text{omission})=0.0$, FalseStaleRate(superset) $=0.0$ |
| **E06** | `E06_anti_downgrade` | `P0` | `real_postgresql_16` | `lineage_transition_schedule` | 300 | $P(\text{admit}\mid\text{laundering})=0.0$ (0/250), 50/50 clean review chains |
| **E07** | `E07_canonicalization` | `P0` | `cross_runtime_node_python` | `canonical_test_vector` | 45 | 100% byte equality across RFC 8785 vectors in Python & Node.js |
| **E08** | `E08_formal_assurance` | `P0` | `bounded_model_checker` | `formal_state_space_configuration` | 69,342 | 0 invariant violations at depth $d \in \{5, 6\}$; 100% mutant kill rate |
| **E09** | `E09_concurrency` | `P1` | `real_postgresql_16` | `concurrent_transaction_workload_run` | 504 | 0.0% false-stale aborts on disjoint partitions; 0 deadlocks |
| **E10** | `E10_fullstack` | `P1` | `real_postgresql_16` | `http_api_request_transaction` | 700 | HTTP latency $p95 \le 50\text{ms}$ across 7 operations ($N \ge 100$/op) |
| **E11** | `E11_model_utility` | `P1` | `live_llm_provider_ledger` | `clinical_decision_support_query` | 240 | TOST clinical fact retention equivalence ($\Delta \le 2.0\text{pp}$) |
| **E12** | `E12_error_taxonomy` | `P1` | `live_llm_provider_ledger` | `malformed_model_response_trial` | 360 | 100% fail-closed containment of malformed provider outputs |
| **E13** | `E13_external_validation` | `P2` | `external_corpus_evaluator` | `external_patient_timeline_task` | 200 | Inter-rater $\kappa \ge 0.80$, $\alpha \ge 0.80$ on 4 external cohorts |
| **E14** | `E14_reproduction_audit` | `P0` | `hermetic_reproduction_engine` | `clean_environment_reproduction_trial` | 15 | 100% deterministic reproduction of all 15 experiment seals |

---

## 5. Statistical Rigor & Scientific Unit Invariants

### 5.1 Prevention of Pseudoreplication
- **Rule:** The scientific sample size $N$ must represent **unique logical schedules** or **distinct patient/operation scenarios**.
- **Timing Jitter Probes:** Repeated executions of the same logical schedule (e.g., 100 timing perturbations for TOCTOU) are treated strictly as internal robustness tests and must NEVER be pooled to artificially inflate the sample denominator $N$.

### 5.2 Confidence Interval Standards
- **Zero-Failure Bounds:** Reported using Wilson score intervals with continuity correction and Clopper-Pearson exact binomial bounds:
  $$\text{Upper Limit} = 1 - \alpha^{1/N}$$
  For $N=640$ (E01), the 1-sided 95% Clopper-Pearson upper bound on false admission is $< 0.58\%$.
- **Equivalence Testing (E11):** Assessed via Two One-Sided Tests (TOST) against the prespecified margin $\Delta = \pm 2.0\text{pp}$ at $\alpha = 0.05$.
- **Paired Comparators (E02, E03):** Analyzed via exact two-sided McNemar tests for discordant outcomes.

---

## 6. Prospective Freeze & Cryptographic Sealing

Every protocol file `protocol.json` is prospectively sealed:
1. Formatted in canonical RFC 8785 JSON.
2. SHA-256 hashed into `protocol.sha256`.
3. Verified by automated CI before any experiment runner is allowed to execute.

---

## 7. Verification Script

To verify all protocols against the schema, execute:
```bash
python3 -c "
import os, json, jsonschema
schema = json.load(open('research/glhs_journal/q3_r3/protocols/glhs-r3-protocol.schema.json'))
validator = jsonschema.Draft202012Validator(schema)
base = 'research/glhs_journal/q3_r3/protocols'
for d in os.listdir(base):
    p = os.path.join(base, d, 'protocol.json')
    if os.path.isfile(p):
        data = json.load(open(p))
        validator.validate(data)
        print(f'PASS: {d} -> {data[\"protocol_id\"]}')
"
```
