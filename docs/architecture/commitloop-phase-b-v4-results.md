# CommitLoop exploratory Phase-B v4 result

Status date: 2026-08-11. This is synthetic software evidence only. It is an
exploratory post-error-slice rerun on the same controlled mechanism cohort, not
an independent confirmatory evaluation and not clinical evidence.

## Frozen execution boundary

- Implementation SHA: `ac599d35d240dba83aa08ca3111575ccf23d25dd`.
- Replacement Phase-A freeze: `COMPLETE` and `VALID`, 47 transitive inputs,
  with `router_calls_before_initial_freeze=0` and 1,182 disclosed historical
  Phase-B calls before replacement.
- Canonical exact-model probe: two calls, one attempt per declared model, no
  retry or fallback; probe SHA-256
  `919facc940009471c7fbd134878b1cfca6dfc805ebac4f3a130dafdd78ce145e`.
- Dual-review construction smoke: `ACCEPTED` in exactly two requests/two HTTP
  attempts. Deterministic code owns candidate, predicate, and note projections;
  Gemini and Claude are non-clinical reviewers only; smoke SHA-256
  `7def621e21a307db9bf72dfe91d2c63d71f51f9ab5b44056a2656661da4b9d42`.
- Benchmark: eight controlled R4 subjects, eight source cases, 36 deterministic
  variants, 44 total cases, two models, and nine conditions. All 792 solver
  cells were attempted; 791 produced valid outputs and one Gemini long-context
  cell failed closed with `JSONDecodeError`. Four of eight source constructions
  passed dual review and four were rejected at the first review stage. The run
  used 804 requests, validated, passed artifact secret scanning, and resumed
  with an injected transport using zero calls.
- Final benchmark checksum-file SHA-256:
  `abd8949c3a5faae43314fcbf66727635a666b171842c3d51155c6d05e2d775dd`.
- External-call lifecycle total after this run: 1,990. No call occurred after
  the completed benchmark.

## Metric movement

| Metric | Corrective v3 | Exploratory v4 | Change |
| --- | ---: | ---: | ---: |
| Lifecycle accuracy | 699/792 = 88.26% | 777/792 = 98.11% | +9.85 pp |
| Evidence accuracy | 693/792 = 87.50% | 765/792 = 96.59% | +9.09 pp |
| Timeliness accuracy | 708/792 = 89.39% | 783/792 = 98.86% | +9.47 pp |
| Escalation accuracy | 773/792 = 97.60% | 788/792 = 99.49% | +1.89 pp |
| All-axes exact | 597/792 = 75.38% | 749/792 = 94.57% | +19.19 pp |
| False-alert rate | 27/72 = 37.50% | 2/72 = 2.78% | -34.72 pp |
| Missed-loop rate | 10/378 = 2.65% | 1/378 = 0.26% | -2.38 pp |
| Transition-sequence accuracy | 97/144 = 67.36% | 130/144 = 90.28% | +22.92 pp |

The strict THSS arm reached 41/44 all-axes exact for Claude and 44/44 for
Gemini. Claude strict was descriptively higher by subject-cluster mean than
BTSA (+0.2375), LWW (+0.1875), and Naive RAG (+0.1875), tied full authorized
history at the cell level, and did not dominate every arm. Gemini was at or
near the ceiling across most conditions.

Construction acceptance improved from 0/8 to 4/8. Candidate-slot F1 is 0.667
and due-window exact accuracy is 3/7, but these describe deterministic
projection plus model-review acceptance—not model-authored clinical truth.

## Why this still is not a statistical win

Every pre-registered strict-versus-comparator Holm-adjusted p-value is 1.0.
The cohort is structurally underpowered for the chosen exact two-sided sign
test and ten-test Holm family. With at most eight non-tied subject pairs, the
best possible raw p-value is `2 / 2^8 = 0.0078125`; the best possible first Holm
adjustment is `10 * 0.0078125 = 0.078125`, already above alpha 0.05. Therefore
no amount of additional tuning on these same eight subjects can yield a valid
superiority result under the frozen analysis plan.

The minimum mathematical boundary is nine independent, non-tied subjects all
favoring the reference (`10 * 2 / 2^9 = 0.0390625`). A defensible follow-up
needs a larger prospectively frozen independent cohort and should use an
explicit power calculation rather than the bare minimum. Reusing or tailoring
the current eight subjects to force significance is prohibited.

## Remaining claim limits

- The cohort is controlled synthetic R4 data, not Synthea, MIMIC-derived
  commitment evidence, real EHR data, or clinician-adjudicated data.
- Solver v4 was written after disclosed error slicing on this cohort, so the
  large metric improvement is exploratory and requires independent validation.
- BTSA remains mechanism-mapped rather than a faithful end-to-end reproduction.
- Real-EHR evaluation, clinical adjudication, longer longitudinal replay, and
  deployed-boundary/PostgreSQL adversarial execution remain `NOT_RUN` or
  `BLOCKED_EXTERNAL`.
