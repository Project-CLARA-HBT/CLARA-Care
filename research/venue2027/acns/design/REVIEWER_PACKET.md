# ACNS first-pass reviewer packet

Use the [registered seed receipts](../corpus/seed_retrieval_receipts.json) to identify the source documents. Match the full-document SHA-256 before extraction. An HTTP failure records an acquisition attempt. It leaves the work eligible for later retrieval. Each FHIR resource has its own digest, and the three resources belong to one registered seed. Apply the date and topical criteria to every seed, including Macaroons (2014) and PROV-DM (2013).

## Correction before screening

Section 7 of the [selection protocol](sok_review_protocol.md) contains a conflicting instruction to compute Cohen’s κ after adjudication. For RQ3, use the two independent first-pass labels as specified in the [registered estimand](../rq_and_estimands.yaml) and the [rater manual](rater_manual.md). Seal those two streams before the reviewers see each other's decisions. Report first-pass raw agreement and κ. Use the separate adjudication ledger for the final label, the proportion of disagreements resolved, and the ambiguous fraction. Computing agreement from a consensus label copied to both raters would discard every resolved disagreement.

Acquisition covers the registered seeds only. The five-index search, deduplication, dual screening, snowballing and claim coding each require their own ledger. These receipts contribute zero screening decisions.
