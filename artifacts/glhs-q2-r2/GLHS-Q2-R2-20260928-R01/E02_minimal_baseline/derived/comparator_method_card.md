# Method Card: Minimal Read-Set Token Baseline (`MIN_READSET_TOKEN` / `HMAC_READSET_TOKEN`)

Status: **Frozen alternative-design mechanism comparator; not a branded product**.

## 1. Scientific Objective

Evaluates whether a minimal, compact immutable read-set / disclosure token mechanism can enforce the Exact-Disclosure Admission Invariant without requiring the full multi-record GLHS snapshot manifest structure. Answers the peer review question: *"Could a simpler immutable token or read-set mechanism satisfy the same invariant?"*

## 2. Construction & Semantics

The baseline evaluates two experimental variants:
1. `MIN_READSET_TOKEN`: Compact unsigned JSON document containing:
   - Scope coordinates: `profile_id`, `actor_id`, `actor_role`, `purpose`, `task`
   - Exact disclosure coordinates: `snapshot_id`, `snapshot_digest`, `evidence_commitment`
   - State & governance coordinates: `state_dependencies`, `policy_version`, `consent_version`, `expires_at`
2. `HMAC_READSET_TOKEN`: Signed variant authenticated with an experiment-scoped HMAC-SHA256 signature to evaluate transport integrity and anti-tamper overhead without claiming server-compromise resistance.

## 3. Evaluation Protocol Parity

Executes the identical 352-schedule corpus from E01 (256 adversarial schedules across 8 families + 96 clean positive controls across 12 clinical contexts) against:
- `GLHS_B111`: Production GLHS full exact-binding
- `MIN_READSET_TOKEN`: Unsigned minimal read-set token
- `HMAC_READSET_TOKEN`: Signed HMAC-SHA256 minimal read-set token

## 4. Endpoints & Metrics

- **Decision agreement**: Disagreement matrix, false acceptances, false rejections, McNemar test vs GLHS_B111.
- **Metadata byte overhead**: Serialized RFC 8785 canonical bytes per schedule.
- **Validation latency**: CPU validation execution duration in microseconds.
- **Database operations**: Read and write counts per validation.

## 5. Scope & Limitations

The minimal token baseline is an experimental comparator for representation minimality analysis. It does not provide historical DAG traversal, rich provenance querying, or human-review adaptation chains outside the immediate admission decision boundary.
