# Risk Register: PH00_A09 R4 E01–E22 Evidence Provenance & Cryptographic Integrity

## 1. Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant Enforced | Status |
|---|---|---|---|---|---|---|
| **RR-A09-01** | Retroactive Execution | Timestamp manipulation where evidence is collected before or contemporaneously with protocol freezing ($\text{freeze} \ge \text{execution}$). | Critical | Low | Strict inequality checked in `chronology_validator.py` and `chronology_validator_r4.py`: $\text{freeze\_timestamp\_utc} < \text{execution\_started\_utc}$. Zero anomalies across 23 experiments. | Controlled |
| **RR-A09-02** | Git History Drift | SUT kernel or harness modified after statistical freeze, causing reported numbers to mismatch active code. | Critical | Low | Multi-SHA binding locks `system_under_test_sha`, `parent_harness_sha`, `analysis_release_sha`, and `r4_baseline_sha` in `provenance_metadata_r4.json` and release manifests. | Controlled |
| **RR-A09-03** | Invariant Vacuity / Tautology | State exploration and test suites passing trivially because target invariant predicates or preconditions evaluate to false. | Critical | Low | Mutation adequacy audits and counterexample witness suites in E08 and E21 verify 100% kill rate against intentionally injected faulty transitions. | Controlled |
| **RR-A09-04** | Pseudoreplication | Counting non-independent jitter repetitions as independent sample size ($N$) to artificially inflate statistical power. | High | Low | Master statistical plans (`MASTER_STATISTICAL_FREEZE.json`) explicitly decouple primary independent logical schedules ($N$) from secondary jitter robustness repetitions. | Controlled |
| **RR-A09-05** | Merkle Hash Chain Tampering | Alteration of intermediate execution logs in `raw/runs.jsonl` without detection by parent directory checksum. | High | Low | Append-only Merkle hash chain using canonical RFC 8785 JSON serialization; any modified record breaks `hash == canonical_hash(rec)` and invalidates subsequent `prev_hash` pointers. Verified across 19,852 records. | Controlled |
| **RR-A09-06** | Simulation Misrepresentation | In-memory or thread-locking simulations reported to reviewers as live PostgreSQL 16 database concurrency results. | Critical | Low | Mandatory `backend_attestation.json` contract for all bundles; `reproduce_q3_r3.py` and `reproduce_q4_r4.py` fail-closed with `UnattestedSimulationError` if simulation is falsely declared production. | Controlled |
| **RR-A09-07** | Neural Semantic Overclaim | Manuscript or docstrings claiming GLHS proves what an LLM "internally attended to" or "causally reasoned about". | Critical | Low | Automated CI linting (`scripts/ci/r4_claim_lint.py`) scans all R4 files; claim budget restricts scope strictly to "server-attested disclosure supply" and disclaims neural semantic consumption as out of scope. | Controlled |
| **RR-A09-08** | Unearned Capability Superiority | Claiming GLHS (C4) provides superior decision safety compared to compact capability tokens (C3) when empirical results show parity. | High | Low | Novelty Outcome Rule embedded in `novelty_contract_r4.md` §6 and `r4_blocker_ledger.json` (BLK-R4-03): C4 explicitly surrenders decision-safety superiority over C3 and restricts novelty strictly to lifecycle state governance and bit-exact reconstructability (score 100 vs 75). | Controlled |
| **RR-A09-09** | Unbacked Provider Benchmark Claims | Claiming LLM benchmark comparisons without persisting durable, inspectable raw request/response ledgers with token counts. | High | Low | Protocol E11/E12 enforces `audit_provider_run_ledger()`; runs without verified requested vs reported model IDs fail-closed (`UnbackedProviderClaimError`). | Controlled |
| **RR-A09-10** | Hardware Attestation Unavailability | Faking or mocking provider hardware attestation receipts when actual hardware enclave is unavailable. | High | Low | Protocol E20 implements strict conditionality: when provider hardware attestation is unavailable, status is set to `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`; zero mocks permitted. | Controlled |

---

## 2. Invariant & Governance Guardrails Summary

1. **Fail-Closed Network Isolation:** Reproduction scripts prohibit all network socket creation and DNS queries, ensuring 100% offline self-containment.
2. **Canonical JSON Consistency:** All cryptographic digests use RFC 8785 Canonical JSON (`clara.canonical-json.v2-rfc8785`) ensuring cross-runtime (Python/Node.js) bit-for-bit equivalence.
3. **Deterministic Seed Locking:** All statistical schedule permutations and synthetic mutations derive from explicitly declared master seeds (`20260928_00`..`14` for R3; `20260930_15`..`22` for R4).
4. **Non-Destructive Worktree Isolation:** Auditing operations are strictly non-destructive and isolated to the assigned worktree path lane (`artifacts/PH00/A09/`).
