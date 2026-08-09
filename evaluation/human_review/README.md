# Human-review burden protocol

Status: **NOT RUN**. Harness labels must not be converted into human burden.
With qualified clinicians, sample the same frozen adjudicated cases for
GLHS-full and BTSA/TPR where applicable. Blind system identity where feasible.
Record per-case escalation, material conflict missed, unnecessary review,
resolution, and measured review duration. Report exact counts and medians/IQR.

Do not report automation rate, escalation precision, review time, or burden
until signed human-review metadata and raw deidentified timing data exist.

Validate the resulting human-collected file before it enters a sealed run:

```bash
python3 -m evaluation.human_review.validate_results --results /secure/human_review.csv --manifest /secure/human_review_manifest.json
```
