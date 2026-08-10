# Independent adjudication

Status: **NOT RUN**. No qualified reviewers or independent adjudication data
are present in this worktree. The guide is a protocol draft, not a substitute
for clinician labels.

The curator must create deidentified labels and adjudications plus a manifest
with controlled reviewer-role codes, blinding, guide hash, original-label
preservation, and final-oracle hash. Fewer than two annotators plus a distinct
adjudicator is rejected.

After human collection, compute field-stratified paired-case disagreement and
Cohen kappa without changing labels:

```bash
python3 -m evaluation.clinical_adjudication.analyze \
  --labels /secure/labels.csv --annotation-manifest /secure/annotation.json \
  --output artifacts/evidence-program/<run-id>/agreement.json
```
