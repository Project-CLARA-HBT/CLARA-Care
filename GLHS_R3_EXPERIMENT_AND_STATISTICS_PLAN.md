# GLHS R3 EXPERIMENT & STATISTICAL PLAN

## A. Global protocol rules

1. Freeze before execution.
2. Record `system_under_test_sha`.
3. Record `experiment_harness_sha`.
4. Record backend truthfully.
5. Publicly expose raw bytes or immutable release objects.
6. Internal-agent approval does not make a result claim-eligible.
7. Simulations are valid only when labeled simulations.
8. Historical R2 artifacts remain immutable.

---

## B. Experiment matrix

| ID | Experiment | Priority | Backend | Primary question |
|---|---|---|---|---|
| E00 | Literature/claim/code freeze | P0 | static audit | What is actually novel? |
| E01 | Inference Consumption Integrity | P0 | production path + PostgreSQL | Was the claimed disclosure actually supplied to the inference lineage? |
| E02 | Binding component ablation | P0 | PostgreSQL | Which components matter? |
| E03 | Minimal token/capability baseline | P0 | PostgreSQL | Could a simpler mechanism satisfy the invariant? |
| E04 | Generated TOCTOU | P0 | PostgreSQL | Does commit reject stale governance/state in tested schedules? |
| E05 | Dependency completeness | P0 | PostgreSQL | Are semantically required dependencies enforced? |
| E06 | Anti-downgrade | P0 | API/service + PostgreSQL | Can bound lineage be laundered? |
| E07 | Canonicalization | P0/P1 | Python + JS | Are commitments deterministic across runtimes? |
| E08 | Formal bounded assurance | P0/P1 | model checker | Are invariants counterexample-free within bound? |
| E09 | Concurrency | P1 | PostgreSQL | What contention/false-stale behavior occurs? |
| E10 | Full-stack performance | P1 | HTTP + PostgreSQL | What is observed systems cost? |
| E11 | Two-model utility | P1 | real providers | Does governed context preserve benchmark utility? |
| E12 | Malformed sensitivity | P1 | actual E11 ledger | How do real output failures affect estimates? |
| E13 | External/source-disjoint | P2 | source-dependent | Does reconstruction generalize descriptively? |
| E14 | Reproduction audit | P0 | fresh checkout | Can a third party recover every central claim? |

---

## C. E01 — Inference Consumption Integrity

Primary unit:
unique logical schedule.

Primary estimands:
- adversarial invalid-admission rate per arm;
- clean-control admission rate;
- family-level rejection coverage.

Required attack families:
1. snapshot ID substitution;
2. projection digest substitution;
3. request-envelope substitution;
4. undisclosed evidence added after compilation;
5. disclosed evidence omitted at provider dispatch;
6. cross-actor reuse;
7. cross-purpose reuse;
8. cross-task reuse;
9. cross-run response/proposal replay;
10. human-review lineage laundering;
11. prompt-template drift;
12. provider fallback without binding;
13. retry with stale binding;
14. cross-profile snapshot.

Recommended arms:
- current auth only;
- snapshot ID;
- snapshot digest;
- inference-binding ID;
- exact binding;
- full GRWC.

Report deterministic coverage first.
Paired exact tests are secondary.

---

## D. E02 — component factorial

Preferred factors:
- snapshot identity;
- projection digest;
- evidence membership;
- inference-binding continuity.

Prefer full `2^4` if runtime allows.

A component may be called “necessary within the tested threat model” only when:
- a targeted counterexample appears when removed;
- clean controls remain admissible;
- the counterexample cannot be explained by another disabled clause.

---

## E. E03 — minimal comparator

Identical schedules across:
- GLHS full GRWC;
- minimal unsigned read-set/disclosure token;
- HMAC token;
- optional Macaroon-style caveat token.

Primary:
decision disagreement / equivalence.

Secondary:
- serialized bytes;
- validation CPU;
- DB reads/writes;
- reconstruction support;
- review-lineage support;
- policy/consent evolution support.

If comparator matches GLHS:
publish the equivalence prominently.

---

## F. E04 — PostgreSQL TOCTOU

Headline evidence must use actual:
- PostgreSQL sessions;
- production commit kernel;
- production policy/consent writes;
- row/advisory locks;
- persisted transitions.

Freeze >=1,024 unique schedules.

Outcome classes:
- SAFE_ADMIT
- SAFE_REJECT
- FORBIDDEN_COMMIT
- OPERATIONAL_FAILURE
- INDETERMINATE_ORDER

Unique schedule is scientific N.
Jitter is robustness only.

If zero forbidden commits:
report `0/N` plus one-sided upper confidence bound.

Never use “eliminated” or “guaranteed”.

---

## G. E05 — dependency completeness

Primary:
accepted required-dependency omission.

Controls:
- exact required vector;
- conservative superset.

Mutants:
- omit entity read;
- omit entity write;
- mutate key/domain/access;
- mutate observed version;
- omit evidence dependency;
- omit governance dependency;
- substitute unrelated dependency.

Must include multi-entity write-skew with real PostgreSQL.

---

## H. E06 — anti-downgrade

Scientific unit:
audited route × attack pattern.

Target:
0 successful downgrade among tested routes.

Wording remains bounded:
“no successful downgrade observed across the audited routes and frozen attack patterns.”

---

## I. E07 — canonicalization

Scientific unit:
unique vector.

Requirements:
- official RFC 8785 vectors where applicable;
- float/subnormal/extreme values;
- negative zero;
- Unicode;
- key ordering;
- invalid surrogate behavior;
- legacy read compatibility;
- Python/JS byte equality.

---

## J. E08 — bounded formal assurance

Report:
- exploration depth;
- reachable states;
- transitions;
- runtime;
- violations;
- mutation-test detection.

Phrase:
“bounded exhaustive exploration through depth d.”

Never:
“universal proof” unless a separate universal formal proof exists.

---

## K. E09/E10 systems statistics

Latency:
p50/p95/p99 only with enough samples.

Throughput:
descriptive unless a comparison hypothesis is frozen.

Environment:
hardware, OS, PostgreSQL version/settings, workers, cache/warmup.

---

## L. E11 — actual provider study

Unit:
subject.

Prospectively freeze:
- models/providers;
- requested and accepted aliases;
- prompts;
- cohort;
- conditions;
- retry policy;
- randomization;
- schema;
- primary endpoint;
- equivalence margin;
- power.

Persist:
- requested model ID;
- reported model ID;
- provider request ID or safe equivalent;
- raw/normalized response;
- latency;
- tokens;
- error;
- retry count;
- condition/order.

Primary pair:
strict governed context vs full authorized history.

Equivalence:
use prospectively selected TOST/CI method.

Never infer equivalence from nonsignificance.

---

## M. E12 — real malformed sensitivity

Use E11 ledger only for claim-bearing analysis.

Taxonomy:
- invalid_json;
- schema_mismatch;
- truncation;
- refusal;
- empty_response;
- provider_error;
- wrong_model;
- timeout;
- content_format_violation;
- semantic_failure;
- rate_limit;
- unclassified.

Primary:
ITT.

Secondary:
prespecified deterministic repair and/or one retry.

---

## N. Reproducibility criteria

A result is `CLAIM_ELIGIBLE` only when:
- protocol freeze is valid;
- freeze precedes execution;
- raw artifact exists;
- raw artifact is publicly retrievable;
- checksum passes;
- backend attestation matches wording;
- analyzer reproduces;
- claim wording is allowed;
- all deviations are recorded.

Statuses:
- `NOT_RUN`
- `EXPLORATORY`
- `SEALED_DESCRIPTIVE`
- `CLAIM_ELIGIBLE`
- `CLAIM_REVOKED`

---

## O. Stop/go gates

### Gate 1
If E01 cannot prove actual inference-disclosure continuity:
STOP and fix architecture.

### Gate 2
If minimal token matches GLHS:
continue, but narrow novelty to invariant + operational semantics.

### Gate 3
If real PostgreSQL E04 shows a forbidden commit:
STOP submission; minimize and fix counterexample.

### Gate 4
If E11 is underpowered:
do not claim equivalence.

### Gate 5
If raw evidence is unavailable:
do not claim public reproducibility.
