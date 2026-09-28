# /goal — GLHS R3 Governed Read-to-Write Continuity

Execute the GLHS R3 master specification against `Project-CLARA-HBT/CLARA-Care`, starting from `research/glhs-q2-r2-experiments` at parent SHA `e7a073749d8d3d434f6d47204238cc6655431f76`.

The objective is not to defend the old “co-versioned governance” framing. The objective is to produce a publication-grade, falsifiable systems paper whose core contribution is:

> **Governed Read-to-Write Continuity / Exact-Disclosure Admission:** later persistent writes must remain verifiably continuous with the exact governed disclosure actually supplied to the inference lineage that produced them, while current state and governance are independently revalidated at commit.

## Mandatory five-subagent rule

For EVERY phase, launch **5 subagents concurrently** before substantial work.

### Agent A — Literature & Novelty
- audit Q1/Q2 and CORE A*/A literature;
- attack novelty claims;
- maintain closest-prior-art matrix;
- ensure mature database/security/health-AI work and MemTX/MemTxn are included.

### Agent B — Systems / Formal
- inspect architecture;
- verify invariant semantics;
- review transaction/lock boundaries;
- extend formal model;
- detect bypasses.

### Agent C — Experiment / Statistics
- define estimands and scientific units;
- freeze protocols;
- design controls/ablations/baselines;
- prevent pseudoreplication;
- verify equivalence/power analyses.

### Agent D — Implementation / Reproducibility
- implement code/tests;
- maintain SUT SHA + harness SHA;
- seal artifacts;
- publish raw bytes;
- build fresh-checkout reproduction.

### Agent E — Hostile Q1/Q2 Reviewer
- assume the paper is overclaiming;
- search for simpler explanations;
- inspect whether backends are real;
- challenge every “first”, “proof”, “safe”, “PostgreSQL”, “independent”, and “equivalent” claim;
- block progression on unsupported central claims.

## Parallelism

All 5 agents must run at the same time for each phase whenever technically possible.

Do not replace the five-agent wave with one sequential agent.

If dependencies exist, split the work into parallel subwaves.

## Merge rule

After every five-agent wave:
1. collect all reports;
2. create disagreement matrix;
3. resolve factual conflicts with code/raw evidence;
4. preserve unresolved concerns in blocker ledger;
5. run phase gate;
6. do not advance with unresolved P0 blockers.

No agent may self-certify its own work as publication-ready.

## Evidence rules

- Never fabricate a result.
- Never convert simulation into production evidence.
- Never call generated model outputs real provider evidence.
- Never call internal agents independent reviewers.
- Never overwrite sealed historical R2 evidence.
- Never freeze after seeing the result.
- Never hide null/equivalent outcomes.
- If minimal token matches GLHS, narrow novelty.
- If a forbidden commit appears, stop submission work and fix/minimize it.
- If provider run is unavailable, mark `NOT_RUN`.
- If human validation is unavailable, mark `NOT_RUN_HUMAN_UNAVAILABLE`.
- Public reproducibility requires retrievable bytes, not hashes alone.

## Phase 0 — Literature / novelty / provenance freeze

Run five agents concurrently.

Outputs:
- literature matrix;
- novelty contract;
- claim budget;
- manuscript/code sync;
- `system_under_test_sha`;
- `experiment_harness_sha`;
- chronology validator.

Gate:
no central novelty claim relies on provenance, OCC, consent, hash binding, bitemporality, or THSS alone.

## Phase 1 — Exact inference consumption binding

Run five agents concurrently.

Tasks:
- inspect existing inference-binding implementation;
- add only missing fields;
- define canonical request envelope;
- bind model-visible disclosure projection;
- create binding immediately before provider dispatch;
- finalize binding after response;
- define retry/fallback semantics;
- add substitution and route-drift tests.

Gate:
the system can distinguish “snapshot existed” from “this exact disclosure was actually supplied to this inference.”

## Phase 2 — GRWC admission + lineage

Run five agents concurrently.

Tasks:
- central admission contract;
- immutable root/parent lineage;
- no human-review laundering;
- no weak binding-mode downgrade;
- stable reason codes;
- same-transaction verification and write.

Gate:
all audited bound lineages fail closed when continuity is broken.

## Phase 3 — Dependency completeness

Run five agents concurrently.

Tasks:
- operation-derived minimum dependencies;
- conservative supersets;
- omission mutants;
- multi-entity write-skew;
- actual PostgreSQL integration.

Gate:
required dependency omission cannot pass the strict route in the frozen mutation corpus.

## Phase 4 — Prospective protocols

Run five agents concurrently.

Freeze E01–E14:
- hypotheses;
- endpoints;
- schedules/cohorts;
- seeds;
- models;
- sample sizes/power;
- analysis;
- stopping rules;
- artifact layout.

Gate:
freeze timestamps precede any claim-bearing execution.

## Phase 5 — P0 correctness experiments

Run five-agent waves for each experiment:
- E01 Inference Consumption Integrity;
- E02 component ablation;
- E03 minimal token/capability baseline;
- E04 real PostgreSQL TOCTOU;
- E05 dependency completeness;
- E06 anti-downgrade;
- E07 canonicalization;
- E08 bounded formal assurance.

Each experiment must pass:
- backend attestation;
- raw artifact;
- analyzer;
- validation;
- seal;
- hostile-review check.

## Phase 6 — Systems experiments

Run five agents concurrently around:
- E09 real PostgreSQL concurrency;
- E10 full HTTP/PostgreSQL benchmark.

Do not use the old Python `SimulatedPartitionCoordinator` as production evidence.

## Phase 7 — Real provider study

Only if credentials/budget are available.

Run five agents concurrently.

E11:
- real frozen Claude/Gemini or exact prospectively selected equivalents;
- requested/reported model IDs;
- provider ledger;
- subject-level analysis;
- properly powered equivalence.

E12:
- derive malformed-output sensitivity from the actual E11 ledger.

If only synthetic data can be generated, mark it method-testing/exploratory and do not make provider-performance claims.

## Phase 8 — External/source-disjoint

Run five agents concurrently.

Execute E13 where legitimate data/annotation are available.

Model-based adjudication is never human validation.

## Phase 9 — Public reproducibility

Run five agents concurrently.

E14 must prove:
- every claim-bearing raw artifact is retrievable;
- checksum verification passes;
- fresh checkout reproduces deterministic summaries;
- deleting one raw artifact breaks the release;
- bad freeze chronology breaks release;
- simulated backend with PostgreSQL wording breaks release;
- unsupported claim breaks release.

## Phase 10 — Manuscript rewrite

Only after claim ledger finalization.

Run five agents concurrently:
- Literature/novelty rewrite;
- Methods/formal rewrite;
- Results/statistics rewrite;
- Reproducibility/limitations rewrite;
- hostile full-manuscript review.

Primary title candidate:

**GLHS: Exact Disclosure Binding for Governed Persistent Writes in Longitudinal Health AI**

Primary contribution order:
1. invariant;
2. system realization;
3. empirical evidence.

## Completion standard

Do not declare R3 complete until:
- novelty is defensible against top-tier adjacent literature;
- actual inference consumption is server-attested;
- lineage is non-downgradable;
- real PostgreSQL backs PostgreSQL/concurrency claims;
- real provider ledgers back provider claims;
- minimal comparator is fairly reported;
- dependency completeness is enforced;
- all P0 artifacts are publicly retrievable;
- chronology is valid;
- deterministic results reproduce from fresh checkout;
- the manuscript is generated from claim-eligible evidence;
- final five-agent hostile audit finds no unsupported central claim.

The final objective is not “make GLHS look novel.”

The final objective is:

> **Identify and rigorously demonstrate the smallest defensible cross-layer invariant that remains novel after comparison with mature transaction, authorization, provenance, health-governance, and persistent-agent-memory research.**
