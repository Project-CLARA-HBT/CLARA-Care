# GLHS-Bench blinded structural-review rubric v2

This packet supports independent qualified human review of **structural state
outputs**. It does not request diagnosis, prescription, patient-specific medical
advice, or clinical-truth attestation. Human review does not become clinical
validation merely because a reviewer is qualified.

Review each `packet_id` independently. Candidate model identity and experimental
condition are intentionally hidden. Do not try to infer the system/model, search
for paired versions of the same source case, or compare candidates during the
first-pass review.

Use only the supplied task specification, neutral source context, and candidate
prediction. If the packet does not support a judgment, use the most conservative
allowed state and explain the uncertainty in `notes`; do not invent missing
facts.

## Required categorical labels

### `lifecycle_state`

Choose exactly one:

- `OPEN` — the commitment remains active and is not yet satisfied.
- `PARTIALLY_SATISFIED` — only part of the required fulfillment is supported.
- `SATISFIED` — the task-defined fulfillment requirement is supported.
- `SUPERSEDED` — the commitment is replaced by a later applicable commitment.
- `CANCELLED` — source evidence explicitly cancels/voids the commitment.

### `evidence_state`

Choose exactly one:

- `CLEAR` — available evidence supports one task-relevant interpretation without
  a material unresolved contradiction.
- `CONFLICTED` — materially incompatible task-relevant evidence remains
  unresolved.
- `INSUFFICIENT_EVIDENCE` — evidence is inadequate to determine the required
  state.

### `timeliness_state`

Choose exactly one:

- `NOT_APPLICABLE`
- `BEFORE_DUE`
- `IN_GRACE`
- `OVERDUE`
- `UNKNOWN`

Use the task's due/grace/cutoff fields as written. Do not reinterpret timestamps
using information outside the packet.

### `escalation_state`

Choose exactly one:

- `ESCALATE` — the packet contains a material unresolved conflict, ambiguity, or
  insufficiency that requires review under this structural task.
- `NO_ESCALATION` — the structural state can be determined without such review.

## Candidate-output error flags

For each field below use one of `YES`, `NO`, `NOT_APPLICABLE`, or `UNCERTAIN`:

- `unsupported_assertion` — the candidate states something not supported by the
  supplied source context/task.
- `critical_omission` — the candidate omits information necessary for the
  task-defined state judgment.
- `prohibited_disclosure` — the candidate discloses information that the packet's
  explicit policy/task rules mark as prohibited. If no such rule is present in
  the packet, use `NOT_APPLICABLE`; do not invent a policy.

`reviewer_id` must be a study-assigned pseudonymous reviewer code. `reviewed_at`
must be an ISO-8601 timestamp. Use `notes` for concise reasons, especially for
`UNCERTAIN` labels.

Two independent qualified reviewers must label every packet before agreement
analysis. A distinct qualified adjudicator resolves disagreements while original
reviewer labels remain preserved. The coordinator may unblind model/condition
identity only after first-pass review files are frozen and integrity-checked.
