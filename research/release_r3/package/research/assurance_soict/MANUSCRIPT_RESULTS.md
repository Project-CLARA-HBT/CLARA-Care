# SOICT assurance results

Status: **SEALED W8 RESULT — govmut-soict-2026-final-v2**.

The frozen corpus contains 45 non-equivalent mutants and 720 executions (four
strategies x five seeds where applicable), with zero infrastructure exclusions.
The evidence is a controlled software-assurance result, not clinical validation.

## Mutation scores

| Strategy | Killed / denominator | Mutation score |
| --- | ---: | ---: |
| M0 regression | 16 / 45 | 0.356 |
| M1 stateless property | 4 / 45 | 0.089 |
| M2 state machine | 6 / 45 | 0.133 |
| M3 combined | 20 / 45 | 0.444 |

Scores use the frozen `detected_any_seed` rule. Hypothesis seeds are deterministic
example streams, not independent replicates or an independent-N sample. The sealed
analysis also records 161 killed and 559 survived mutant-method executions, with no
infrastructure errors.

## Interpretation boundary

M3 is the union/superset of M0, M1, and M2, so its raw score is expected to be at
least as high as each component. The W8 ranking is raw and **not
budget-normalized**; it does not establish cost-effectiveness under equal
wall-clock budgets. A budget-fair comparison, survivor classification, and W9
extension remain separate gates. No claim of clinical correctness, deployment
security, or superiority over unrelated prior systems follows.
