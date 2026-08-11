# CommitLoop prospective solver-v5 mechanism-cohort result

Status date: 2026-08-11. This is controlled synthetic R4 software evidence.
It is not clinical evidence, a population estimate, or a real-EHR result.

## Frozen boundary

- Implementation SHA: `17dd4b8c558c2ec0cb8c2572728093d9aa3ce914`.
- Replacement Phase-A freeze: `COMPLETE/VALID`; implementation-freeze
  SHA-256 `a512eefa9ee27adb9f7b8e72bf0bb1646ba92e20c0466b59ec9799ecb01eea51`.
- The freeze discloses 1,990 prior external calls and supersedes solver v4.
- Cohort: 64 new subjects, one source case per subject, no derived variants,
  eight balanced mechanism strata, and 1,152 pre-declared solver cells.
- Pre-registration SHA-256:
  `99a6c1338af87e549fa05406c2c7248713d39fa297e56494fb5bd099efdd6bb2`.
- Pre-execution seal SHA-256:
  `3280f9c9863a76b7bd51891f9bac28401d652d9ce714f6a340099fa37efdb456`.
- Exact-model probe used two one-attempt calls with no retry/fallback; probe
  SHA-256 `5410d00695716e45a770e886f6033d6fbae2680191a37f56ecb357db47cb9f56`.
- Benchmark completed all 1,152 solver cells plus 128 dual-review requests:
  1,280 requests, zero errors, zero retries. A no-call transport resume made
  zero requests and retained the real endpoint hash.
- Final benchmark checksum-file SHA-256:
  `625413adec2e1bc6a905520c5c07654ecbcaae3a440373a4d710ac6aac663b7f`.
- Disclosed external-call lifecycle total: 3,272. No external call occurred
  after the completed benchmark.

## Accuracy

| Metric | Correct / total | Accuracy |
| --- | ---: | ---: |
| Lifecycle | 1,072 / 1,152 | 93.06% |
| Evidence | 1,115 / 1,152 | 96.79% |
| Timeliness | 1,143 / 1,152 | 99.22% |
| Escalation | 1,150 / 1,152 | 99.83% |
| All axes exact | 1,027 / 1,152 | 89.15% |

Strict THSS reached 63/64 (98.44%) all-axes exact with Claude and 64/64
(100%) with Gemini. Deterministic construction plus anchor-only dual review
accepted 64/64 cases; candidate-slot F1 and due-window exact accuracy were both
1.0. Models remained non-clinical reviewers; deterministic code owned every
candidate, predicate, note, and gold projection.

## Pre-registered primary comparisons

The primary endpoint is subject-level all-axes exact match. Strict THSS is the
reference; five comparators for each of two models form one ten-test Holm
family. Missing or malformed outputs count as errors.

| Model | Comparator | Effect | 95% bootstrap CI | Holm p | Non-tied | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Claude | Naive RAG | +32.81 pp | +21.88 to +43.75 pp | 0.00000954 | 21 | Significant; power target unmet |
| Claude | LWW | +25.00 pp | +15.63 to +35.94 pp | 0.00027466 | 16 | Significant; power target unmet |
| Claude | Full history | +18.75 pp | +7.81 to +29.69 pp | 0.01098633 | 14 | Significant; power target unmet |
| Claude | Long context | +14.06 pp | +6.25 to +23.44 pp | 0.01953125 | 9 | Significant; power target unmet |
| Gemini | Naive RAG | +25.00 pp | +14.06 to +35.94 pp | 0.00027466 | 16 | Significant; power target unmet |
| Gemini | LWW | +25.00 pp | +15.63 to +37.50 pp | 0.00027466 | 16 | Significant; power target unmet |

BTSA was not significant for Claude (+4.69 pp, Holm p=1.0). Gemini strict tied
BTSA, full history, and long context exactly. The result therefore supports six
specific adjusted comparisons, not a universal-winner claim.

## Power interpretation and stopping rule

The pre-registration enrolled 64 subjects to target at least 51 non-tied pairs,
which gives approximately 81.5% power at directional probability 0.75 under a
conservative 0.005 per-test threshold. Actual ties were much more frequent:
significant comparisons had only 9 to 21 non-tied pairs. Their exact sign tests
are valid and remain Holm-significant, but the pre-declared power target was not
met. These results are therefore statistically significant controlled
synthetic mechanism evidence, not fully powered confirmatory evidence.

No prompt, cohort, or analysis retuning is permitted on these 64 subjects. A
further replication must prospectively size enrollment using the observed tie
rates, or move to approved real-EHR/clinician-adjudicated evaluation. The one
remaining strict-Claude error—a cancelled history predicted as satisfied—is
retained without post-hoc repair on this cohort.

## Operational and claim limits

- Latency p50/p95/p99: 2,580.14 / 4,902.82 / 16,471.45 ms; retries: zero.
- Provider-reported usage: 2,387,996 prompt, 89,440 completion, and 3,092,775
  total tokens. Provider accounting semantics were not independently verified.
- The cohort deliberately stresses software mechanisms and is not Synthea,
  MIMIC-derived commitment evidence, representative clinical prevalence, or
  clinician adjudication.
- Real-EHR evaluation, clinical review, PostgreSQL/deployed-boundary
  adversarial execution, and longer longitudinal replay remain external gates.
