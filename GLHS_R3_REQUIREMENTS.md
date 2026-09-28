# GLHS R3 REQUIREMENTS SPECIFICATION

## Legend
- **MUST** = publication blocker
- **SHOULD** = strong requirement
- **MAY** = enhancement

| ID | Level | Requirement | Verification |
|---|---|---|---|
| SCI-001 | MUST | Novelty centered on GRWC / Exact-Disclosure Admission | literature audit |
| SCI-002 | MUST | No novelty claim for OCC/provenance/consent/hash/THSS alone | claim lint |
| SCI-003 | MUST | Cite strongest DB/security/health/agent-memory neighbors | bibliography audit |
| SCI-004 | MUST | Cite MemTX/MemTxn as concurrent close work | manuscript review |
| ARCH-001 | MUST | Persist server-owned inference binding at actual request boundary | integration test |
| ARCH-002 | MUST | Bind exact governed disclosure projection digest | substitution tests |
| ARCH-003 | MUST | Persist canonical request-envelope digest/version | adapter tests |
| ARCH-004 | MUST | Proposal retains immutable inference lineage | lineage tests |
| ARCH-005 | MUST | Human review cannot erase model lineage | downgrade tests |
| ARCH-006 | MUST | Admission revalidates state in same DB transaction | PostgreSQL tests |
| ARCH-007 | MUST | Admission revalidates policy and consent | TOCTOU tests |
| ARCH-008 | MUST | Required dependencies are operation-derived | mutation tests |
| ARCH-009 | MUST | No weak-route downgrade for bound lineage | route audit |
| ARCH-010 | MUST | Canonicalization profile is versioned | vector tests |
| ARCH-011 | MUST | Idempotent replay cannot double-apply | integration test |
| ARCH-012 | MUST | Admitted transition is reconstructable | reconstruction test |
| EXP-001 | MUST | PostgreSQL claims use actual PostgreSQL | backend attestation |
| EXP-002 | MUST | Provider claims use actual provider outputs | provider ledger |
| EXP-003 | MUST | Simulations explicitly labeled simulation | release lint |
| EXP-004 | MUST | Unique logical schedule is TOCTOU scientific N | analyzer test |
| EXP-005 | MUST | Minimal token/capability baseline evaluated fairly | E03 |
| EXP-006 | MUST | Actual consumed-disclosure substitution tested | E01 |
| EXP-007 | MUST | Global source support vs disclosed support tested | E01 |
| EXP-008 | MUST | Dependency omission tested end-to-end | E05 |
| EXP-009 | MUST | Formal model includes inference binding | E08 |
| STAT-001 | MUST | Freeze before first claim-bearing run | chronology gate |
| STAT-002 | MUST | Equivalence uses prospectively powered design | E11 |
| STAT-003 | MUST | Zero events reported as 0/N plus bound | manuscript lint |
| STAT-004 | MUST | Pseudoreplication prohibited | statistics audit |
| REPRO-001 | MUST | Record SUT SHA and harness SHA | manifest |
| REPRO-002 | MUST | Raw claim artifacts publicly retrievable | fresh-checkout audit |
| REPRO-003 | MUST | Checksums cover raw and derived artifacts | seal |
| REPRO-004 | MUST | Fresh checkout reproduces deterministic tables | E14 |
| REPRO-005 | MUST | Missing artifact causes release failure | negative test |
| ETH-001 | MUST | Internal agents not called independent peer reviewers | wording lint |
| ETH-002 | MUST | Synthetic adjudication not called human validation | wording lint |
| PRIV-001 | MUST | No PII/secrets in public artifacts | scanner |
| PERF-001 | SHOULD | Real PostgreSQL concurrency benchmark | E09 |
| PERF-002 | SHOULD | Full HTTP/PostgreSQL benchmark | E10 |
| MODEL-001 | SHOULD | Real two-model confirmatory study | E11 |
| MODEL-002 | SHOULD | Malformed analysis from actual provider ledger | E12 |
| EXT-001 | MAY | External/source-disjoint validation | E13 |

## Acceptance policy

All MUST requirements are required before the manuscript may describe R3 as claim-bearing.

SHOULD requirements may be omitted only when:
- omission is explicitly documented;
- related claims are removed;
- the limitations section states the missing evidence.

MAY requirements never justify delaying P0 correctness work.
