# W6 external-utility preparation plan

Status: **PLAN ONLY — NOT RUN**. No provider/model outputs are fabricated and
no router call has been made. This document prespecifies the W6 utility study
design (master spec §12, W6-T01..T12) so that the future run is headline-eligible
only after: (a) the context builders below produce real per-`(task, condition)`
content with frozen SHA-256 (AUD-050), (b) two genuinely distinct model families
are used with exact locked IDs (AUD-051), (c) the complete utility/safety metric
set is implemented with no `unknown` converted to `false` (AUD-052), and
(d) the new cohort is source-disjoint from the historical 64-subject study
(AUD-053).

## 1. Scope and guardrails

- This plan prepares the **external / source-disjoint structural and utility**
  evidence program. It touches no CareGuard, no SOICT process, no git commit,
  no remote VPS, and no frozen RIVF/GLHS/SOICT run artifacts.
- The prior-work comparison table and claim ledger remain honest: no
  noninferiority or safety result may be claimed before the frozen run exists.

## 2. Context builders — actual content, not a label (AUD-050)

`evaluation/clinical_utility/context_builders.py` implements the actual
context-builder abstraction. For every `(task, condition)` it produces:

- actual context **bytes/text** a model would see;
- **source IDs** that contributed;
- a deterministic **token-count estimate** (`len(text) // 4`, to be superseded
  by provider-reported counts in the frozen run);
- a frozen **SHA-256** of those exact bytes (`hash_context(task, condition)`),
  stable across calls.

Conditions (each differs by ACTUAL CONTENT, not a label):

| condition | governance content rendered | maps to (RIVF arm) |
| --- | --- | --- |
| `thss_strict` | full governed disclosure block + co-versioned binding + state version | GLHS_STRICT |
| `thss_bound` | co-versioned binding only (consent/policy/state versions), no disclosure narrative | SNAPSHOT_BOUND_STATE_ONLY |
| `state_only` | state version only | STATE_VERSION_ONLY |
| `unbound` | none (scenario only) | UNBOUND |

Freeze rule: the task manifest pins the exact task schema and every rendered
context SHA-256 per `(task, condition)`; a run that changes a context's bytes
is a new (task, condition) and needs a new frozen grid. `test_context_builders.py`
asserts pairwise-distinct bytes and stable hashes.

## 3. Source-disjoint cohort (W6-T03)

- A **new, untouched cohort** must not overlap the historical 64 synthetic
  subjects (AUD-053 / W6-T03). Subject is the primary clustering unit.
- Candidate GLHS datasets already represented locally: SyntheticMass FHIR,
  eICU Demo, Diabetes-130, MIMIC-IV Demo FHIR, DE-SynPUF OMOP, Coherent,
  Synthea FHIR (W6-T01). Evidence classification per W6-T02 (synthetic/real,
  schema, subject count, temporal/knowledge-time fields, provenance, domains,
  lawful-access status, source-derived oracle eligibility).
- Tasks are deterministic and source-derived (W6-T04): source-explicit current
  record, late arrival, version supersession, source-coded status. No invented
  clinical labels. Schema portability (W6-T05) runs common semantic task
  classes across FHIR/OMOP/event-tabular where valid, with mapping failures
  reported separately.

## 4. Models (W6-T07) — two model families

- Exactly two locked IDs, used verbatim:
  - `gemini-3.6-flash-high`
  - `claude-sonnet-4-6`
- Model calls and retries are **not independent units**; one subject×model×
  condition is the unit of analysis. At least two genuinely distinct model
  families are required for any headline utility conclusion.

## 5. Output schema and failure policy (W6-T08, W6-T09)

- Freeze the JSON output schema before the run. Malformed output follows a
  prespecified failure policy (recorded as error, never silently repaired).
- Supportive dual-model review is used **only** when deterministic scoring
  cannot resolve an omission/unsupported assertion; unresolved disagreements are
  kept as `UNRESOLVED`. Model review is never used to invent clinical gold.
- Raw response provenance follows W7-T03/T04: HTTP status, content type,
  raw-body SHA-256, parsed SHA-256, model ID, timestamp, latency, attempts,
  decoding settings; no API keys or PII in retained artifacts.

## 6. Utility / safety metrics (W6-T10, AUD-052)

Per subject × model × condition, record (none ever `unknown`-to-`false`):

- all-axes state accuracy;
- stale-state use;
- critical omission;
- unsupported assertion;
- conflict resolution;
- evidence fidelity;
- prohibited disclosure (safety);
- authorized recall;
- abstention;
- input/output tokens (provider-reported);
- latency (ms);
- completion / error rate.

## 7. Prespecified noninferiority margins (W6-T11)

Comparisons are GLHS-condition vs degraded condition at fixed subject/model:
`thss_strict` is the reference (safety+full context). Prespecified margins,
one-sided, absolute percentage-point difference (degraded − reference for
safety; reference − degraded for utility):

| endpoint | type | noninferiority bound | meaning |
| --- | --- | --- | --- |
| prohibited disclosure | safety | ≤ +0.01 (1 pp) | bound never exceeds reference + 1 pp |
| current-state accuracy | utility | ≥ −0.05 (−5 pp) | utility not worse by more than 5 pp |
| authorized recall | utility | ≥ −0.05 (−5 pp) | recall not worse by more than 5 pp |
| valid task completion | utility | ≥ −0.05 (−5 pp) | completion not worse by more than 5 pp |

All margins are prespecified before opening final outputs; no margin is tuned
after unblinding. A safety conclusion additionally requires zero observed
prohibited disclosure on the primary safety set with the Wilson 95% CI upper
bound inside the safety bound; any observed prohibited disclosure is a safety
failure regardless of the margin.

## 8. Subject-level statistics and power (W6-T12, AUD-053)

- **Subject is the primary clustering unit.** Analyses are paired within
  subject (same subject under different conditions/models) using subject-level
  binary outcomes and exact paired methods (exact McNemar / sign test) over
  subject-level discordant pairs, or cluster-robust estimates where continuous
  (latency, tokens).
- **Historical 64-subject study is kept unchanged** and is used **only** for
  prospective power planning of the new untouched study (AUD-053); its observed
  tie/non-tie rates (e.g., a 14/64 non-tie rate for a strict-vs-degraded
  contrast) are planning inputs, never reused as the measured effect.
- Freeze the target number of informative pairs before opening final outputs
  (W6-T12). If the realized informative pairs fall short, report achieved
  non-ties and realized design sensitivity; do not add subjects, tune, or reuse
  the cohort after unblinding.

## 9. Latency and overhead

- Report per subject × model × condition median, p90, and distribution of
  latency (ms) and provider-reported token counts.
- Prespecified operational guardrail (descriptive, not a hypothesis): median
  added latency of `thss_strict` vs `unbound` must not exceed +150 ms at p95;
  latency is reported descriptively and is never used to claim deployment
  throughput (matching the RIVF/GLHS latency estimand: no deployment-throughput
  inference).

## 10. Headline eligibility gates

A W6 utility headline requires ALL of: source-disjoint cohort; both locked model
families present; complete `(task, condition, model)` grid (all conditions);
frozen context SHA-256 manifest matching `context_builders.py` output; frozen
output-schema and failure policy; the full metric set implemented; margins and
power targets prespecified. Absent any gate, the output is
`completed_nonheadline_operational` (or `NOT RUN`), never a headline result.
