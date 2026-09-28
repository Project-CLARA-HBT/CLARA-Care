# GLHS R3 MASTER RESEARCH & ENGINEERING SPECIFICATION

**Program:** GLHS R3 — Governed Read-to-Write Continuity  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Starting research branch:** `research/glhs-q2-r2-experiments`  
**Starting branch SHA:** `e7a073749d8d3d434f6d47204238cc6655431f76`  
**Rule:** this SHA is a starting point only. No claim-bearing R3 experiment may run until the final implementation SHA and experiment-harness SHA are prospectively frozen.  
**Primary paper target:** Q1–Q3 health/medical-informatics systems journal.  
**Candidate ladder:** Journal of Medical Systems → Methods of Information in Medicine → Health Information Science and Systems.

---

## 0. Executive objective

GLHS R3 is a research and engineering revision, not an editorial polish pass.

The R3 program MUST transform the manuscript from a broad “co-versioned governance architecture” claim into a narrow, falsifiable systems contribution:

> **A persistent AI-generated health-state mutation is admissible only when the system can verify continuity to the exact governed disclosure actually supplied to the inference that produced the proposal lineage, while independently revalidating current state, governance, consent, actor/purpose/task, and required dependencies at commit time.**

R3 names this property **Governed Read-to-Write Continuity (GRWC)**.

The implementation may use THSS, inference-context binding, proposal dependencies, a commit kernel, and provenance graphs. These are realization mechanisms. The scientific contribution is the invariant and a health-governance realization of it.

R3 MUST NOT claim novelty for constituent mechanisms already established by prior work:
- optimistic concurrency control;
- serializable/snapshot transaction validation;
- temporal/bitemporal state;
- provenance itself;
- purpose-based access control;
- dynamic consent;
- proof-carrying authorization;
- contextual capability tokens;
- hash commitments;
- immutable audit history;
- persistent LLM memory;
- transactional memory in general;
- THSS merely as a data structure.

---

# 1. Literature-derived novelty contract

## 1.1 Transactional freshness

Required anchors:
- Kung & Robinson, ACM TODS 1981.
- Cahill, Röhm & Fekete, SIGMOD 2008.
- Ports & Grittner, PVLDB 2012.
- TicToc, SIGMOD 2016.

R3 distinction:
OCC can establish whether database dependencies remain current. GRWC additionally asks whether the semantic proposal is still attributable to the exact governed disclosure actually supplied to the AI inference.

## 1.2 Purpose-aware privacy and usage control

Required anchors:
- Agrawal et al., *Hippocratic Databases*, VLDB 2002.
- Byun & Li, purpose-based access control, VLDB Journal 2008.
- mature usage-control/UCON literature.

R3 distinction:
Purpose-aware authorization governs whether use is permitted. GRWC makes a specific inference-time disclosure-consumption relationship part of later write admission.

## 1.3 Proof-carrying authorization and contextual capabilities

Required anchors:
- Proof-Carrying File System, IEEE S&P 2010.
- Macaroons, NDSS 2014.

Consequence:
A compact signed capability may implement the same core invariant. GLHS must not claim THSS is uniquely necessary. A minimal token/capability baseline is mandatory.

## 1.4 Provenance

Required anchors:
- Provenance Semirings, PODS 2007.
- Linux Provenance Modules, USENIX Security 2015.
- W3C PROV where appropriate.

R3 distinction:
Prior provenance represents ancestry and can support enforcement. GRWC focuses on the exact model-visible governed disclosure of a specific inference event and uses that coordinate during later semantic write admission.

## 1.5 Health provenance

Required anchors:
- Curcin et al., JBI 2017.
- Margheri et al., IJMI 2020.
- mature clinical warehouse provenance/versioning literature.

R3 distinction:
Clinical provenance strongly supports traceability/reconstruction. GLHS must demonstrate the shift from provenance as an audit object to provenance as a commit-admission predicate for AI-generated persistent writes.

## 1.6 Dynamic consent and clinical-AI governance

Required anchors:
- Kaye et al., Dynamic Consent, EJHG 2015.
- FUTURE-AI, BMJ 2025.
- SMART clinical-AI documentation/governance, JAMIA 2026.

R3 distinction:
GLHS is a runtime per-inference/per-write mechanism, not a replacement for lifecycle governance.

## 1.7 Persistent agent memory

Required anchors:
- LongMemEval, ICLR 2025.
- Wang et al., memory privacy, ACL 2025.
- MemTX, 2026 preprint.
- MemTxn, 2026 preprint.

R3 distinction:
GLHS must distinguish **source support** from **governed disclosure actually consumed by inference**.

---

# 2. Primary scientific invariant

Let:
- `H` = governed disclosure / THSS.
- `I` = server-owned inference-context binding proving the model request used `H`.
- `P` = persistent-write proposal.
- `D(P)` = semantically required dependency set.
- `M(H)` = evidence/provenance manifest.
- `S(t)` = current state.
- `G(t)` = current governance.
- `tc` = admission time.

R3 MUST implement and evaluate:

```text
Admit(P, tc)
iff
exists H, I:
    Issued(H)
    and SuppliedToInference(I, H)
    and ProposalDescendsFrom(P, I)
    and ExactDisclosure(P, I, H)
    and EvidenceCovered(P, H)
    and DependencyComplete(P)
    and StateCurrent(P, S(tc))
    and GovernanceCurrent(P, G(tc))
    and DisclosureAdmissibleAtCommit(H, tc)
```

Strongest defensible consequence:

```text
Admit(P, tc)
=>
exists persisted H, I:
    I proves that the trusted application supplied H
    (or its exact bounded projection) to the inference lineage,
    and all mutable coordinates required by P
    were revalidated inside the admission transaction.
```

This does NOT prove:
- clinical correctness;
- model causal reasoning from only that disclosure;
- absence of parametric knowledge;
- security against a compromised application/database unless separately modeled;
- universal safety under arbitrary external writers.

---

# 3. R3 architecture

## 3.1 Governed disclosure

Required fields:
- `snapshot_id`
- `profile_id`
- `actor_id`
- `actor_role`
- `purpose`
- `task`
- `state_dependencies`
- `policy_version`
- `consent_version`
- `valid_from`
- `expires_at`
- `evidence_manifest`
- `disclosure_projection`
- `projection_digest`
- `manifest_digest`
- `canonicalization_profile`
- `compiler_version`

## 3.2 Inference consumption binding

R3 MUST elevate the current inference-context binding into a first-class research object.

Conceptual schema:

```text
InferenceContextBinding
  binding_id
  profile_id
  snapshot_id
  projection_digest
  manifest_digest
  actor_id
  actor_role
  purpose
  task
  provider
  requested_model_id
  reported_model_id
  prompt_template_version
  system_prompt_version
  disclosure_slot_digest
  request_envelope_digest
  response_digest?
  request_started_at
  request_completed_at
  status
```

Critical rule:
The authoritative binding is created by the trusted server-side inference path immediately after final request construction and before provider dispatch.

Clients and model output cannot author authoritative binding fields.

## 3.3 Two-digest design

1. `projection_digest`
   - exact governed health-information projection intended for model visibility.

2. `request_envelope_digest`
   - canonical server-owned request object immediately before provider serialization.

This distinguishes:
“a valid snapshot existed”
from:
“this exact governed projection was supplied to this inference.”

## 3.4 Proposal lineage

Conceptual proposal:

```text
Proposal
  proposal_id
  root_proposal_id
  parent_proposal_id?
  inference_binding_id
  context_binding_mode
  base_state_version
  expected_policy_version
  expected_consent_version
  dependency_vector
  dependency_vector_digest
  asserted_evidence_ids
  target_operation
  target_payload_digest
  origin
  created_at
```

Human review may modify content but MUST NOT erase model lineage.

## 3.5 Admission

The commit path MUST:
1. resolve lineage;
2. resolve inference binding;
3. resolve disclosure;
4. verify exact binding;
5. acquire canonical locks;
6. derive/verify dependencies;
7. revalidate state;
8. revalidate policy;
9. revalidate consent;
10. revalidate actor/role/purpose/task;
11. validate evidence membership;
12. validate expiry/admissibility;
13. execute mutation;
14. CAS version changes;
15. persist transition lineage;
16. emit outbox/audit event.

No bound lineage may silently enter a weaker base-version-only path.

---

# 4. Functional requirements

- **FR-01** Persist stable disclosure identity and digest.
- **FR-02** Create a server-owned binding at actual inference dispatch.
- **FR-03** Preserve immutable proposal lineage.
- **FR-04** Require asserted evidence to be disclosed unless a new governed inference occurs.
- **FR-05** Revalidate state dependencies under locks in the write transaction.
- **FR-06** Revalidate policy and consent.
- **FR-07** Revalidate actor/role/purpose/task.
- **FR-08** Derive required dependencies from trusted operation semantics.
- **FR-09** Prevent weak-route downgrade.
- **FR-10** Allow human adaptation without provenance laundering.
- **FR-11** Guarantee idempotent replay.
- **FR-12** Make admitted transitions reconstructable.
- **FR-13** Version every digest-bearing canonicalization profile.
- **FR-14** Preserve legacy read compatibility.
- **FR-15** Fail closed on missing/unknown binding coordinates.

---

# 5. Non-functional requirements

- **NFR-01 Privacy:** no PII/secrets/raw clinical prompts in public evidence.
- **NFR-02 Auditability:** claim → protocol → SHA → raw → analyzer → result.
- **NFR-03 Reproducibility:** deterministic analyses reproduce offline.
- **NFR-04 Provenance:** record both `system_under_test_sha` and `experiment_harness_sha`.
- **NFR-05 Public bytes:** checksum is insufficient when bytes are unavailable.
- **NFR-06 Chronology:** freeze MUST precede first claim-bearing execution.
- **NFR-07 Internal agents:** may perform QA but are not independent peer reviewers.
- **NFR-08 Backend truth:** simulations are labeled simulations; PostgreSQL claims execute PostgreSQL.
- **NFR-09 Deterministic tables:** manuscript metrics generated programmatically.
- **NFR-10 Release gate:** unsupported wording fails the release.

---

# 6. Literature-derived research requirements

- **RR-01 OCC insufficiency:** construct a schedule where state/auth are current but proposal references the wrong inference disclosure.
- **RR-02 Purpose-control insufficiency:** actor/purpose valid but disclosure lineage wrong.
- **RR-03 Provenance vs admission:** compare logging provenance with admission-enforced provenance.
- **RR-04 Minimal capability/token baseline:** compact read-set/disclosure token comparator.
- **RR-05 Source support vs consumed disclosure:** globally supportive evidence not disclosed to the model must not satisfy disclosure-specific provenance.
- **RR-06 MemTX/MemTxn property comparison:** explicit property-level nearest-neighbor table.

---

# 7. R3 experiment program

## E00 — Literature/claim/code freeze
Outputs:
- literature matrix;
- novelty contract;
- claim budget;
- code/manuscript sync;
- provenance manifest.

Gate:
No central novelty claim depends on provenance/OCC/consent/hash/THSS alone.

## E01 — Inference Consumption Integrity
Highest-priority novelty experiment.

Question:
Can the system distinguish “a valid disclosure existed” from “this exact disclosure was actually supplied to the inference lineage”?

Recommended attack families:
1. snapshot-ID substitution;
2. projection-digest substitution;
3. request-envelope substitution;
4. undisclosed evidence added after compilation;
5. disclosed evidence omitted at provider request;
6. cross-actor reuse;
7. cross-purpose reuse;
8. cross-task reuse;
9. proposal replay across inference runs;
10. human-review lineage laundering;
11. prompt-template drift;
12. fallback-provider binding loss;
13. retry binding reuse;
14. cross-profile snapshot.

Arms:
- current authorization only;
- snapshot identity only;
- disclosure digest only;
- inference-binding ID only;
- exact inference binding + disclosure;
- full GRWC.

Primary:
invalid-admission rate.

Control:
valid-control admission rate.

Must exercise actual proposal/admission code.

## E02 — Binding component factorial
Fresh R3 prospective freeze.
Headline backend: real PostgreSQL.

Prefer factors:
- identity;
- projection digest;
- evidence membership;
- inference-binding continuity.

A component is “necessary” only if removal exposes a targeted counterexample while controls remain valid.

## E03 — Minimal alternative baseline
Comparators:
- GLHS full GRWC;
- `MIN_READSET_TOKEN`;
- `HMAC_READSET_TOKEN`;
- optional Macaroon-inspired caveat token.

Measure:
- decision agreement;
- false admission;
- false rejection;
- serialized bytes;
- DB ops;
- CPU validation;
- reconstructability;
- review-lineage support;
- mutable purpose/consent/policy support.

If token matches GLHS safety, report equivalence and narrow novelty.

## E04 — Real PostgreSQL TOCTOU
R2 simulated executor MUST NOT be used as PostgreSQL evidence.

Use actual:
- PostgreSQL sessions;
- commit kernel;
- governance writers;
- row/advisory locks;
- persisted transitions.

Freeze >=1,024 unique logical schedules.

Primary:
forbidden commits / eligible adversarial schedules.

Report confidence upper bound; never “TOCTOU eliminated.”

## E05 — Dependency completeness end-to-end
Wire operation-derived dependency contracts into actual admission.

Mutation classes:
- omit read entity;
- omit write entity;
- mutate key/domain/access mode/version;
- omit evidence dependency;
- omit governance dependency;
- unrelated replacement;
- conservative superset.

Must include real DB write-skew.

## E06 — Anti-downgrade/lineage
Static route inventory plus dynamic tests.

Attempt:
- AI→base-only;
- reviewed AI→human reset;
- root replacement;
- missing inference binding;
- snapshot replacement;
- actor/purpose/task replacement;
- cross-profile;
- direct service call;
- alternate API route.

Target:
0 successful laundering in frozen audited routes.

## E07 — Canonicalization
Keep RFC 8785 cross-runtime vectors and legacy compatibility.

## E08 — Formal model with inference binding
Add formal state:
- disclosure issued;
- disclosure supplied;
- binding identity;
- lineage;
- substitution;
- request-envelope mismatch.

New invariants:
- I12 no commit when binding does not point to supplied disclosure.
- I13 lineage descendant cannot downgrade.
- I14 undisclosed globally valid evidence cannot satisfy disclosure evidence.
- I15 clean disclosure→inference→proposal→commit remains reachable.

Bounded exploration only; no universal-proof wording.

## E09 — Real PostgreSQL concurrency
Replace simulated headline benchmark with production PostgreSQL path.

Workloads:
disjoint, same-entity, partial overlap, Zipfian, governance+entity, evidence+entity, dependency widths.

## E10 — Real full-stack HTTP
Use existing HTTP→auth→GLHS→PostgreSQL path.

## E11 — Actual two-model study
R2 synthetic generator cannot support provider claims.

Prospectively freeze real provider runs:
- cohort;
- prompts;
- models;
- decoding;
- order;
- retries;
- schema;
- endpoint;
- equivalence margin;
- power.

Persist requested/reported model IDs and provider ledger.

## E12 — Real malformed-output sensitivity
Derive from actual E11 ledger.
No injected 10% error simulation for headline claims.

## E13 — External/source-disjoint
Synthetic tasks must be labeled synthetic.
Human validation requires actual humans.

## E14 — Public reproduction audit
Fresh checkout must:
- retrieve every raw artifact;
- verify checksums;
- regenerate summaries/tables;
- fail on missing artifact;
- fail on invalid chronology;
- fail on backend/wording mismatch.

---

# 8. Statistics

Scientific units:
- conformance/attack: unique logical schedule;
- model study: subject;
- canonicalization: vector;
- performance requests: performance distribution only;
- formal states/transitions: descriptive search counts, not samples.

Zero-event claims:
report `0/N` plus upper confidence bound.

Equivalence:
only with prospectively powered TOST/CI design.

Pseudoreplication:
timing jitter of one schedule is robustness, not new N.

---

# 9. Claim budget

Allowed when supported:
- “operationalizes an Exact-Disclosure Admission / GRWC invariant.”
- “within tested routes/schedules…”
- “no forbidden commit observed in N PostgreSQL schedules.”
- “bounded exploration found zero violations through depth d.”
- “minimal token matched/differed from GLHS on the frozen corpus.”
- “equivalence within ±δ” only when actually established.

Forbidden:
- first provenance-aware health AI;
- first transactional AI memory;
- TOCTOU eliminated;
- formally proven secure;
- clinically safe;
- regulatory compliant;
- tamper-proof under trusted-store threat model;
- GLHS uniquely necessary;
- real Claude/Gemini result from synthetic outputs;
- PostgreSQL benchmark from Python lock simulation;
- independent adjudication by internal agents/models.

---

# 10. Manuscript redesign

Preferred conservative title:

**GLHS: Exact Disclosure Binding for Governed Persistent Writes in Longitudinal Health AI**

Alternative:
**GLHS: Enforcing Governed Read-to-Write Continuity in Longitudinal Health AI**

Abstract:
1. problem;
2. gap;
3. invariant/method;
4. real systems evaluation;
5. bounded scope.

Related Work:
1. transaction freshness;
2. purpose/usage control;
3. proof-carrying/capabilities;
4. provenance;
5. health provenance + AI governance;
6. persistent agent memory;
7. precise gap.

Contribution bullets:
1. invariant;
2. system realization;
3. evidence.

Do not list provenance, consent, bitemporality, hashing as independent contributions.

---

# 11. Release architecture

```text
research/glhs_journal/q3_r3/
  literature/
  novelty/
  protocols/
  claim_budget/
  paper_code_sync/
  publication/
  release/

artifacts/glhs-r3/<run-id>/
  E00/
  ...
  E14/
```

Every experiment:
```text
protocol.json
protocol.sha256
freeze.json
environment.json
code_manifest.json
backend_attestation.json
raw/
derived/
validation.json
checksums.sha256
seal.json
```

Backend attestation must explicitly state:
- actual backend;
- version;
- production path yes/no;
- simulation yes/no;
- network/provider yes/no;
- fallback usage.

---

# 12. CI gates

- G0: no unsupported novelty statement.
- G1: no PostgreSQL wording for simulations.
- G2: no provider result without provider ledger.
- G3: freeze timestamp before execution.
- G4: all checksum targets retrievable.
- G5: fresh checkout reproduces analyses.
- G6: claim wording permitted.
- G7: internal five-agent audit may say engineering-ready, never journal-accepted.

---

# 13. Phases

1. R3 branch + literature/claim freeze.
2. exact inference binding.
3. admission contract + lineage.
4. dependency contract.
5. prospectively freeze protocols.
6. correctness experiments E01–E08.
7. systems experiments E09–E10.
8. real provider studies E11–E12.
9. E13 if available.
10. E14 public reproduction.
11. manuscript rewrite only from claim-eligible evidence.

---

# 14. Definition of Done

R3 is ready for submission only when:
- novelty survives strongest neighboring literature;
- actual inference consumption is server-attested;
- proposal lineage cannot downgrade;
- PostgreSQL backs database concurrency claims;
- actual provider ledgers back provider claims;
- minimal comparator is fairly reported;
- dependency completeness is enforced;
- formal model includes inference binding;
- raw claim artifacts are publicly retrievable;
- chronology is valid;
- fresh checkout reproduces deterministic outputs;
- null/equivalent findings remain visible;
- no internal-agent report is presented as independent peer review.

The goal is not to maximize positive results. The goal is to identify the strongest claim that remains true after hostile comparison with mature database, security, health-informatics, and persistent-agent-memory literature.
