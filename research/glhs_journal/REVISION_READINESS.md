# GLHS journal revision-evidence readiness

Status: **revision packet not complete**.

Existing implementation tests demonstrate portions of snapshot, policy, consent, and provenance binding, but they do not close the requested revision blockers. The required 2026 nearest-neighbor set has now been full-text scope-coded with hash-only retrieval receipts; it narrows, rather than proves, the GLHS gap or an exhaustive search result. The Methods/Results unit-of-analysis audit and a revision-ready wording patch set are now present, but the submitted manuscript was not modified. Direct gateway/API binding tests and a model-write-path audit now cover the known implementation surfaces; required next artifacts are isolated PostgreSQL governance TOCTOU schedules/results and independent-adjudication packet outcomes.

The external-adjudication tooling now refuses an annotation manifest lacking
pseudonymous role codes and explicit eligibility/independence attestations for
exactly two reviewers and the distinct adjudicator. It binds the reviewer codes
and annotation-guide hash to the issued blinded-packet manifest before import.
This is a protocol safeguard only: there are still no qualified reviewer
records, human labels, adjudications, or agreement results. The PostgreSQL
probe remains development-only and its concurrent ordering is indeterminate;
it must not be relabeled as a final frozen TOCTOU matrix.

The direct gateway now rejects an explicitly THSS-consuming proposal that lacks an exact snapshot binding. The public commitment proposal route also requires both snapshot coordinates at request validation. This is implementation conformance only; real PostgreSQL governance-writer TOCTOU remains required.

An attempted isolated PostgreSQL development probe was intentionally recorded as
`NOT_RUN`: the deployed API image exposes a pre-binding snapshot DTO with no
`manifest_digest`, so it is not a valid executable image for this revision
evidence. Rebuild from the reviewed source and use a new development run ID
before executing any PostgreSQL schedule.

The rebuilt `2026-08-16-dev-002` image has the reviewed binding contract and
ran two sequential PostgreSQL development schedules in a random dropped schema:
TOCTOU-01 rejected a proposal after consent revocation and TOCTOU-04 rejected a
proposal after a simulated policy-version change. This is not final evidence:
TOCTOU-02, TOCTOU-03, and TOCTOU-05, real concurrent governance writers,
transaction/audit completeness, a frozen manifest, and a sealed run remain
required.

Development run `2026-08-16-dev-004` additionally races a consent writer and
proposal writer across two PostgreSQL sessions. Its single observed schedule
committed the proposal before the revoke commit was observed; it does not test
a post-revocation commit, does not establish linearizability, and leaves
TOCTOU-02/03 plus audit completeness open.

Development run `2026-08-17-dev-005` executes the sequential consent schedule
as a real persistent-write admission attempt: a THSS-bound candidate is created,
consent is revoked, then `apply_transition` is attempted in an isolated random
PostgreSQL schema. The attempt was rejected as `assertion_consent_mismatch` and
the probe recorded no forbidden commit. This strengthens only TOCTOU-01
development traceability; TOCTOU-02/03, a post-revocation concurrent ordering
proof, audit completeness, frozen protocol, and sealed final run remain open.

Development run `2026-08-17-dev-006` records all five schedule identifiers in
an isolated random PostgreSQL schema. TOCTOU-02 rejects a synthetic current
scope-role coordinate change at `apply_transition`, but does not model a
persisted role-policy writer. TOCTOU-03 committed its pre-existing proposal
after the observed revoke commit and is correctly classified
`indeterminate_ordering_transition_committed`, not safe. TOCTOU-05 rejected a
proposal during/after its observed race. The run remains development-only: a
persisted governance-writer schedule, audit completeness, repeated/frozen race
design, final manifest, and seal are all still required.

Development run `2026-08-17-dev-007` adds sanitized ledger-linkage observations
only. The two rejected commit attempts had zero transition items; the one
indeterminate concurrent commit reconstructed one exact snapshot-linked
decision. This confirms neither a clinical payload nor whole-system audit
completeness, and it does not change the indeterminate concurrency finding.

The revised TOCTOU-02 fixture replaces its former in-memory
`ProfileScope` substitution with a synthetic Family grant, persisted delegate
account-role mutation, and fresh scope resolution in the isolated PostgreSQL
probe. It does not supply a policy-version writer or a final concurrency
conclusion. Any material future change requires a distinct development run ID
and sealed sanitized output.

Development run `2026-08-17-dev-008` executes that revised TOCTOU-02 fixture
in a fresh isolated PostgreSQL schema. It persisted a synthetic delegate role
change from doctor to normal, resolved the Family-grant scope again, and then
rejected the THSS-bound activation as `proposal_snapshot_actor_role_mismatch`
with zero transition items. This is one sequential development trace only; it
does not establish a global role/policy writer schedule, audit completeness,
repeated-race ordering, a frozen protocol, or a final safety conclusion.

An attempted reuse of the older isolated `clara-rivf-20260816-dev002` API image
under run ID `2026-08-17-dev-009` stopped at TOCTOU-02: the copied current
driver observed that image commit after its persisted delegate-role mutation.
The driver raised before writing a result, its random schema was confirmed
dropped, and the temporary driver was removed. `run-status.json` records this
as `NOT_RUN_SOURCE_IMAGE_CONTRACT_MISMATCH`; it is not a result about the
reviewed source, production, or concurrency safety. Any future run must rebuild
from the reviewed source and use a distinct ID.

Development run `2026-08-17-dev-010` then rebuilt a fresh isolated project
from source whose checked gateway/profile-scope hashes matched the reviewed
workspace, executed all five schedules in a random PostgreSQL schema, and
removed the project network and volumes after artifact transfer. TOCTOU-01,
TOCTOU-02, TOCTOU-04, and TOCTOU-05 were rejected as recorded in the sanitized
artifact. TOCTOU-03 committed while the monotonic trace showed that
`apply_transition` started before the observed revoke commit, so it remains
`indeterminate_ordering_transition_committed`, not safe. This sealed
development inventory does not close persisted policy-writer coverage,
audit-completeness, a repeated/frozen race design, or the final TOCTOU matrix.

Development run `2026-08-17-dev-011` rebuilt another fresh isolated project
from the reviewed source and executed all five schedules in a random PostgreSQL
schema. TOCTOU-01, TOCTOU-02, TOCTOU-04, and TOCTOU-05 were rejected as
recorded in the sanitized development artifact. TOCTOU-03 started before the
observed revoke commit and completed after it, so it remains
`indeterminate_ordering_transition_committed`, not safe. This local sealed
development inventory is not claim-eligible and does not close the persisted
policy-writer, audit-completeness, repeated/frozen-race, or final-matrix
blockers.

No previously reported result has been rewritten or reinterpreted by this program work.
