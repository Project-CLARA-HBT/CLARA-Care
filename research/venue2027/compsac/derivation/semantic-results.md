# Semantic guards on SmallBank proposal reuse

The derived guards and the maintained semantic comparator made 48 identical, correct decisions. Each admitted all 34 reusable instructions and rejected all 14 changed instructions. The prespecified decision therefore retires the accuracy-superiority claim. Changing these three procedures' grid weights cannot create a win because the decisions coincide in every row. [Frozen follow-up](semantic-protocol.md) · [All paired predictions](semantic.jsonl)

| Procedure | Reusable / changed | False rejections, read tracing | False rejections, manual coordinate template | False rejections, traced predicates | False rejections, manual predicates |
|---|---:|---:|---:|---:|---:|
| Deposit | 16 / 0 | 8 | 0 | 0 | 0 |
| Withdraw | 8 / 8 | 0 | 0 | 0 | 0 |
| WriteCheck | 10 / 6 | 6 | 6 | 0 | 0 |

All four arms made zero false admissions. In Deposit, the committed instruction adds a fixed amount and remains reusable when the destination changes. In WriteCheck, the instruction remains reusable while the sum of savings and checking stays on the same side of the debit threshold. Both semantic arms preserve precisely these distinctions.

The manual comparator was written with access to the same procedure source, operation, and old/new account values. It evaluates the withdrawal and check threshold classes explicitly. The derived arm executes the pinned Python procedure against an adapter for the fixed account and records the balance comparisons taken at preparation. It reevaluates those expressions during validation. Each arm returns a reuse decision before comparison to the label. The labels come from a separate business specification cross-checked by executing the SQL port against SQLite. Every grid case was kept, including unchanged-state edits and original refusals. The tested SQL shapes, update magnitudes and branch forms are restricted to these three procedures. This follow-up reused the development grid after diagnosis of coordinate tracing errors, so the 14 corrected decisions quantify the diagnosed mechanism on that grid. It provides no independent corpus result, latency result or measurement of template maintenance effort.

From the repository root, with the same Python environment used for SmallBank:

```sh
python -m evaluation.venue2027.compsac.reuse_predicates /tmp/smallbank-semantic-replay.jsonl
cmp /tmp/smallbank-semantic-replay.jsonl research/venue2027/compsac/derivation/semantic.jsonl
python -m pytest -q evaluation/venue2027/compsac/test_reuse_predicates.py
```
