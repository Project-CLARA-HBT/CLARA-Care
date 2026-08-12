# Human review and adjudication

Status: **NOT RUN**. No qualified human labels are present in the repository.
Harness labels and LLM outputs must never be converted into human-review or
clinical-validation claims.

`prepare_packets.py` creates method-blinded structural-review packets from a
sealed, complete CommitLoop/GLHS-Bench run. Every candidate for the same source
case is reviewed against the same neutral source context, while model identity,
experimental condition, source case ID, and response hashes remain in a
coordinator-only mapping. Reviewer packets use unique `packet_id` values so
multiple model/condition cells from one source case cannot be confused.

Example:

```bash
python3 -m evaluation.human_review.prepare_packets \
  --run-dir /secure/sealed-run \
  --output /secure/review-packets \
  --split validation \
  --randomization-seed-file /secure/review-randomization-seed.txt
```

Distribute only:

- `blinded_packets.jsonl`
- `reviewer_import_template.csv`
- `GLHS_BENCH_RUBRIC.md`

Do **not** distribute `coordinator_only/coordinator_mapping.json` before first-pass
review files are frozen. Two independent qualified reviewers should label each
packet; a distinct qualified adjudicator resolves disagreements. Preserve all
original reviewer rows.

This workflow evaluates structural state judgments unless a separately approved,
independently curated clinical annotation protocol and appropriate reviewers are
used. `READY_FOR_EXTERNAL_ADJUDICATION` means only that packet preparation is
complete; it does not mean human or clinical validation has occurred.

The older burden-data validator remains separate because review-time/automation
burden requires clinician-collected timing and escalation data. Validate such
human-collected burden data only after the corresponding frozen attestation
manifest exists:

```bash
python3 -m evaluation.human_review.validate_results \
  --results /secure/human_review.csv \
  --manifest /secure/human_review_manifest.json
```
