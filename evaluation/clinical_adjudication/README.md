# Independent adjudication

Status: **NOT RUN**. No qualified reviewers or independent adjudication data
are present in this worktree. The guide is a protocol draft, not a substitute
for clinician labels.

The curator must create deidentified labels and adjudications plus a manifest
with controlled reviewer-role codes, eligibility and independence attestations,
blinding, guide hash, original-label preservation, and final-oracle hash.
Anything other than exactly two annotators plus a distinct adjudicator is
rejected. Before importing adjudications, the tool also binds those annotator
codes and the annotation-guide hash to the issued packet manifest. It accepts
only pseudonymous reviewer IDs and role codes; it cannot verify the truth of an
external qualification attestation.

After human collection, compute field-stratified paired-case disagreement and
Cohen kappa without changing labels:

```bash
python3 -m evaluation.clinical_adjudication.analyze \
  --labels /secure/labels.csv --annotation-manifest /secure/annotation.json \
  --output artifacts/evidence-program/<run-id>/agreement.json
```

## Blinded packet workflow

The packet tool does not create labels or simulate reviewers.  A qualified
curator first supplies a deidentified JSONL record for each case containing
only `case_id`, `review_payload`, and review `fields`.  It rejects system-arm,
model, prediction, score, and gold keys from reviewer payloads.  Store the
resulting `controlled_packet_map.csv` separately from reviewer packet copies.

```bash
python3 -m evaluation.clinical_adjudication.packets export \
  --input /secure/deidentified-review-input.jsonl \
  --output /secure/packets-<freeze-id> \
  --annotation-guide evaluation/clinical_adjudication/ANNOTATION_GUIDE.md \
  --review reviewer-code-a --review reviewer-code-b \
  --blinding-salt "$CONTROLLED_RANDOM_SALT"

python3 -m evaluation.clinical_adjudication.packets import-labels \
  --labels /secure/returned-blinded-labels.csv \
  --packet-dir /secure/packets-<freeze-id> \
  --output /secure/normalized-labels.csv

python3 -m evaluation.clinical_adjudication.packets disagreements \
  --labels /secure/returned-blinded-labels.csv \
  --packet-dir /secure/packets-<freeze-id> \
  --output /secure/adjudication-disagreements.json

python3 -m evaluation.clinical_adjudication.packets import-adjudications \
  --adjudications /secure/adjudicator-decisions.csv \
  --disagreements /secure/adjudication-disagreements.json \
  --packet-dir /secure/packets-<freeze-id> \
  --annotation-manifest /secure/frozen-annotation-manifest.json \
  --output /secure/final-human-adjudications.csv
```

`disagreements` emits only two-reviewer disagreements. A distinct qualified
adjudicator—not an LLM—must provide final decisions; until then the manifest
remains `READY_FOR_EXTERNAL_ADJUDICATION` / `NOT_RUN`.
