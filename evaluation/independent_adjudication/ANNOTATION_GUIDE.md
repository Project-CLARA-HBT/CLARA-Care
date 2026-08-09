# Independent clinical-state annotation guide v1 (DRAFT — NOT APPROVED)

This guide must be frozen, SHA-256 recorded, and approved by the qualified
review team before labels are collected. Codex and developers must not label,
adjudicate, or attest reviewer independence.

For each deidentified task record at index time `t`, label current state,
supersession, unresolved conflict, supporting evidence IDs, escalation need,
and task-critical facts. Use `unanswerable` rather than inferring from absent
evidence. Never infer a diagnosis, prescription, or personal dosage.

Two qualified annotators label independently and blinded to system identity and
output where technically feasible. A distinct adjudicator receives only
disagreement packets and writes a reason plus final label. Preserve original
labels. Report qualifications, blinding, case counts, disagreement, eligible
Cohen kappa/Krippendorff alpha, temporal-boundary agreement, and unresolved
cases.
