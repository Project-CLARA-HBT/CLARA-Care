# DSN-threat · Threat, trust and failure model

> **Task:** `DSN-threat` · **Venue:** `dsn` · **Phase:** `P01` · **Contract version:** `1.0.0`
>
> **Paper:** *Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations*
> **Status:** Design artifact. Contains no experimental results and no measured numbers; every
> quantitative endpoint is deferred to runs registered under `artifacts/venue2027/dsn/<run_id>/manifest.json`.
> **Dependencies satisfied:** `DSN-scope` (novelty contract, conditional GO), `SH-research_ethics`
> (synthetic-only `synthetic-dsn-2027` data policy). Base SHA of this worktree:
> `f35af111cc04588c8c35705a53b47c4586db137d`.
> Machine-checked by `research/venue2027/_shared/tools/threat_model.py` (`validate_threat`) and
> `research/venue2027/dsn/tests/test_threat_model.py`.

## 1. Scope and protected outcome

The system under study is the CLARA AI-mediated health-state mutation pipeline: an authorized
actor (End_User on `/today`, or a clinician) accepts an AI-proposed health-state mutation; the
pipeline governs the commit against consent and policy, then asynchronously produces externally
visible side effects (notifications, exports, downstream records). The unit of protection is **not
one database commit** but the *joint* outcome across three independent persistence boundaries:

1. **B-row** — the committed clinical row (durable PostgreSQL storage);
2. **B-receipt** — the immutable decision receipt and proposal lineage (append-only safety journal);
3. **B-outbox** — the asynchronous side-effect record (durable outbox, delivered at-least-once).

The recoverable outcome function `O(op) → {COMMITTED, REJECTED, INDETERMINATE}` is computed by a
reconciler from versioned evidence across all three boundaries plus the consent epoch. A result is
**COMMITTED** only when row, receipt and outbox evidence reconcile to the same immutable logical
operation ID under a valid consent epoch; **REJECTED** when governed authorization deterministically
refused the operation; **INDETERMINATE** whenever evidence is missing, ambiguous, or fails
integrity verification. `INDETERMINATE` is a terminal-for-the-moment label: it is never promoted to
a positive outcome, never counted as a safe rejection, and never silently retried into a success.

**Adversarial goal (what a successful attack looks like):** make the joint outcome lie — a phantom
user-visible success (receipt or UI says committed, row or effect does not exist), an orphan
clinical write (row changed with no recoverable receipt/lineage), a duplicate externally visible
side effect, a forbidden commit executed after consent revocation, or an ambiguous state laundered
into COMMITTED. The study endpoint these attacks target is the crash-consistency violation rate
after fault injection on `synthetic-dsn-2027` histories (RQ1–RQ3).

## 2. Attacker and observer capabilities

The adversary model is deliberately layered; each capability below is assumed obtainable by some
concrete actor unless stated otherwise. Capabilities are *fault powers*: the fault-injection design
treats them as schedulable events in an exported history, not as ambient bad luck.

| ID | Actor | Capability | Boundary abused |
|---|---|---|---|
| A1 | Crash-fault injector | SIGKILL / VM pause of the application or broker process at an arbitrary cut point: mid-mutation of an AI-mediated health state, between ORM flush and SQL COMMIT, between COMMIT and HTTP response, between outbox insert and delivery | B-row, B-outbox |
| A2 | Broker / retry layer | At-least-once duplicate delivery of any outbox message, arbitrary multiplicity and delay; recovery re-execution after restart that produces a duplicate or lost transition | B-outbox |
| A3 | Scheduler adversary | Arbitrary reordering of commit, revocation and delivery events across the logical schedule (4 orderings × 3 delivery schedules in the frozen design) | all three |
| A4 | Passive observer | Reads the journal, outbox table, log lines and telemetry labels; times operations to infer that a health event occurred (no write access) | B-receipt, telemetry |
| A5 | Durability liar | Storage layer that acknowledges a write before it is durable: fsync assumption failure, `synchronous_commit` disabled, snapshot/rollback of a paused VM, torn or partial journal append flushed to only some pages/lines | B-receipt, B-row |
| A6 | Consent authority race | Consent revocation landing between initial authorization and actual mutation commit; epoch change while the pipeline is in flight | B-receipt (epoch), B-row |
| A7 | Untrusted AI proposer | The model proposes mutations at will: out-of-scope targets, stale proposals under a changed policy/consent epoch, malformed lineage, or claims that a mutation "already happened". The model has **no direct write path**; its only power is to emit proposal content that enters the governed pipeline | B-receipt (proposal lineage) |
| A8 | Insider with storage write | Edits or corrupts stored journal bytes or a signed receipt at rest (digest tampering); cannot mint a validly signed new entry (key custody, §4) | B-receipt |

**Re-execution power (the "arbitrary duplicate delivery" regime).** Any component between the
commit and the side effect — broker, recovery routine, human operator re-running a job, or the
retry logic itself — may re-deliver or re-execute any journal/outbox message any number of times,
in any order, after arbitrary delays, including after a crash. Non-idempotent retry after a crash
is therefore an expected adversary move, not an operator error: every durable effect must be keyed
to an immutable logical operation ID so that re-execution is a no-op.

**Model agency.** The AI model is outside the trusted base in both directions: it can fail by
proposing nothing (liveness only) and by proposing something harmful or stale (safety). Model
agency never includes the authority to write receipts, to advance the consent epoch, or to mark an
operation committed; a model-asserted "this was already done" has zero evidentiary weight at the
reconciler. Proposal lineage (version, model/task registry identity, prompt/policy revision,
digest of the proposal) is recorded in the receipt at proposal time and re-verified at commit.

**Observer limits.** Observers see structure, not content: telemetry labels, flow events and
analytics are PII-free and exclude names, emails, queries and drug lists (repository safety
invariant). Timing and size side channels that reveal *that* a health event happened remain in
scope as privacy threats; inferring *what* the event was from observability output is treated as a
disclosure defect, not an accepted risk.

## 3. Trusted components

The trusted computing base (TCB) is intentionally small and each member carries a testable
contract. Everything not listed here is untrusted.

1. **Append-only safety journal** (decision receipt + proposal lineage). Contract: entries are
   content-addressed (SHA-256 digest chain), appended by atomic create-and-rename/append semantics,
   never mutated in place; a torn or partial append is detectable (chain/digest mismatch or
   incomplete record framing) and yields `TORN_WRITE_DETECTED` → the affected operation is
   `INDETERMINATE`, never COMMITTED.
2. **Durable storage** (PostgreSQL with WAL). Contract: honest durability per the declared
   configuration (`synchronous_commit` on; fsync performed before acknowledging commit). A storage
   layer that acknowledges before persisting violates the durability contract
   (`DURABILITY_CONTRACT_VIOLATION`) and any outcome observed under it is `INDETERMINATE` until
   re-verified after restart.
3. **Idempotency ledger.** A unique constraint on the immutable logical operation ID together with
   its (tenant, principal, purpose, consent epoch) scope binding, backing exactly-once *effect*
   semantics under at-least-once delivery.
4. **Consent epoch service.** Sole authority to mint and advance versioned consent epochs; epochs
   are monotonic per principal/scope; the reconciler rechecks the epoch that governed each receipt.
5. **The reconciler.** A pure function of (row version, decision receipt, independent outbox
   receipt, consent epoch) → tri-state, fail-closed: invalid or ambiguous evidence can never
   produce a positive outcome; missing dependency is surfaced as a stable reason code, never
   silently dropped.
6. **Journal signing key custody.** The pipeline service account holds the journal signing key;
   compromise of the key is out of modeled power (§4) but its *detection* (digest-chain break) is
   in scope.

**Explicitly untrusted:** the AI model and its provider path; the message broker; the application
process (may crash at any instruction boundary); the network; end-user devices and browsers;
telemetry sinks; human operators (read is assumed possible, write to journal bytes is adversarial
tampering per A8); any LLM runtime configuration or provider-side persistence.

## 4. Excluded domains

The following are **out of scope** and no claim in this study depends on them:

- **Physical destruction / site loss.** Destroyed disks, datacenter loss, unrecoverable media
  damage; backup/restore and DR-site semantics are out of scope.
- **Byzantine storage without detection.** Storage that returns arbitrary *undetectably stale or
  fabricated* data. We assume checksummed storage surfaces corruption at read (a detectable digest
  mismatch is in scope via A8/CASE-06); undetectable Byzantine behavior is excluded.
- **Cryptographic forgery.** Minting a *validly signed* journal entry or receipt without the key
  (key compromise, side-channel key extraction). Tampering that breaks a digest is in scope;
  forging a valid entry is excluded.
- **Superuser database write path.** A malicious postgres superuser editing WAL or bypassing
  constraints out-of-band. Insiders with application-level storage write (A8) are in scope;
  raw-WAL forgery is excluded.
- **Side channels beyond metadata timing.** Power/EM/memory forensics, heap scraping of process
  memory after compromise of the host.
- **Clinical content safety of proposals.** Whether a proposal is *clinically correct* is governed
  by the CLARA safety guardrails (emergency fast-path, legal hard-guard, FIDES verification) and
  other 2027 venues; this study adjudicates the *recoverability of the durable decision*, not the
  medical wisdom of the proposal. A clinically harmful but validly governed and recoverable commit
  is not a crash-consistency violation.

## 5. Attack family and control matrix

Every family is paired: a clean control case (the baseline behavior that must keep working) and an
adversarial case (the injection that must be caught, or honestly labeled `INDETERMINATE`). Verdicts
use the CASE_MATRIX vocabulary: `COMMITTED`, `REJECTED`, `REJECTED_OR_NOT_COMMITTED`, `INDETERMINATE`,
`COMMITTED_BUT_PENDING_DELIVERY`, `ONE_COMMIT`, `MEASURE`. Family IDs are the shared validator's
canonical tokens; registered scenario-family IDs feed the fixture generator's
`scenario_family` field.

| Family | Registered scenario family | Actor / capability | Threat summary | Clean control case | Adversarial case | Expected oracle verdict |
|---|---|---|---|---|---|---|
| `crash_consistency` | `crash_window_joint_outcome` | A1, A5 | SIGKILL across 48 cut points: crash mid-mutation of an AI-mediated health state; crash between COMMIT and response; torn/partial journal append; fsync/durability assumption failure | clean: nominal governed commit — row, receipt and outbox all reference the same operation ID, one durable effect, user sees the truth (DSN-CASE-01) | adversarial: crash before SQL COMMIT (SIGKILL after flushed ORM changes, DSN-CASE-02), torn journal write, or ack-before-fsync storage — no phantom user-visible success, partial journal detected, outcome stays honest | clean → `COMMITTED`; crash-before-commit → `REJECTED_OR_NOT_COMMITTED`; torn/durability-violated evidence → `INDETERMINATE` |
| `replay` | `duplicate_delivery_reexecution` | A2, A3 | Broker triple delivery after consumer restart (DSN-CASE-04); recovery re-execution after crash producing a duplicate or lost transition; non-idempotent retry after crash; concurrent duplicate operation ID (DSN-CASE-08) | clean: single delivery executes exactly one durable effect; post-commit crash retry discovers the committed record by operation ID and does nothing (DSN-CASE-03) | adversarial: same outbox message delivered three times plus a post-crash retry with re-execution power — idempotency ledger collapses all attempts to one effect; deliveries recorded, no duplicate side effect, no lost transition | clean → `COMMITTED`; replay storm → `COMMITTED` with `ONE_COMMIT` effect semantics; undeduplicated retry must surface as a counted violation, never as success |
| `revocation_timing` | `revocation_interleaving` | A6, A3 | Consent revoked between authorization and mutation commit; epoch advances while the pipeline is in flight; revocation and commit racing across the 4 frozen orderings | clean: revocation before proposal → governed refusal before any durable effect (DSN-CASE-05 pre-state) | adversarial: revocation interleaved at every commit/revocation ordering — authorization rechecked under applicable locks at commit time under the receipt's consent epoch; a stale-epoch commit must not land | clean → `REJECTED`; interleaved revocation → `REJECTED`; any forbidden write that survives a complete schedule is a stop-and-revise blocker |
| `model_agency` | `proposal_lineage_authority` | A7 | Model proposes without valid versioned lineage, or a stale proposal is resubmitted after a policy/consent epoch change; model output impersonates a receipt or asserts prior commit | clean: proposal carries valid lineage (model/task registry identity, policy revision, proposal digest) under a current consent epoch → proceeds to governed commit (DSN-CASE-01 lineage check) | adversarial: missing/invalid lineage, stale epoch, or model-asserted "already committed" claim — the reconciler treats model claims as zero-evidence and refuses positive promotion | clean → `COMMITTED` (with lineage recorded); adversarial → `REJECTED`; ambiguous lineage → `INDETERMINATE` |
| `purpose_scope` | `operation_id_scope_binding` | A7, A2, A8 | Operation ID minted for one (tenant, principal, purpose, consent epoch) binding is re-delivered or re-labeled under another purpose or tenant; journal row re-attributed | clean: scope binding stored in the receipt and rechecked at commit; same operation ID within its original scope is idempotent (DSN-CASE-08 single-writer case) | adversarial: cross-purpose or cross-tenant reuse of an operation ID, or a receipt re-labeled post hoc — unique constraint on (operation ID, scope binding) plus receipt re-verification refuses the escalation | clean → `COMMITTED` in scope; adversarial → `REJECTED`; binding ambiguity → `INDETERMINATE` |
| `insider_or_observer` | `journal_integrity_observer` | A8, A4 | Journal tampering: edited receipt or corrupted digest differing from the stored transition (DSN-CASE-06); observer inferring health events from journal growth, timing, or telemetry labels | clean: intact digest chain reconciles independently across row, receipt and outbox (DSN-CASE-06 pre-state) | adversarial: signed receipt digest differs from stored transition — tamper flagged, reconciliation proceeds only on independent evidence, no silent successful state; timing/telemetry disclosure bounded by PII-free labels | clean → `COMMITTED`; tampered → `INDETERMINATE` with `EVIDENCE_DIGEST_MISMATCH` flag; never a silent success |

The `crash_consistency` family is the study's core: its adversarial cells operationalize RQ1
(crash-window joint disagreement), and its cost stress sibling DSN-CASE-09 (`MEASURE` at 1/2/4/8
workers) feeds RQ3. The `replay` and `revocation_timing` families operationalize RQ2.

## 6. Registered scenario families and case mapping

| Scenario family | Validator family | DSN-CASE fixtures | RQ |
|---|---|---|---|
| `crash_window_joint_outcome` | `crash_consistency` | DSN-CASE-01, DSN-CASE-02, DSN-CASE-03, DSN-CASE-07, DSN-CASE-09 | RQ1, RQ3 |
| `duplicate_delivery_reexecution` | `replay` | DSN-CASE-03, DSN-CASE-04, DSN-CASE-08 | RQ2 |
| `revocation_interleaving` | `revocation_timing` | DSN-CASE-05 | RQ2 |
| `proposal_lineage_authority` | `model_agency` | DSN-CASE-01 (lineage), DSN-CASE-06 (evidence validity) | RQ1, RQ2 |
| `operation_id_scope_binding` | `purpose_scope` | DSN-CASE-08 | RQ2 |
| `journal_integrity_observer` | `insider_or_observer` | DSN-CASE-06 | RQ1 |

DSN-CASE-07 (`COMMITTED_BUT_PENDING_DELIVERY`) intentionally separates storage commit status from
downstream delivery: bounded broker unavailability is a liveness condition, not a safety violation,
and must not be coerced into either a phantom success or a false rejection. DSN-CASE-09 is the
resource-frontier fixture: its oracle verdict is `MEASURE`, and per the shared rules a `MEASURE`
expectation is never read as PASS.

## 7. Revocation and schedule-time semantics

- **Logical schedule time, not wall clock.** Adjudication uses the Elle-compatible exported
  history: each event carries a logical order in the schedule. Crash windows are logical cut
  points `c ∈ {0..47}` over the pipeline's interleaving of (flush, journal append, SQL COMMIT,
  outbox insert, response, delivery); revocation carries its logical position in the same order.
  Wall-clock timestamps are observability metadata only and never adjudicate ordering.
- **Revocation is epoch-structured.** Revoking consent mints a new monotonic consent epoch for the
  (principal, scope). An operation's receipt records the epoch that authorized it; the reconciler
  accepts a commit only if the epoch still governs at commit time under the applicable locks.
  Revocation therefore has two defensible answers at the boundary — an operation authorized under
  epoch *n* that commits atomically before epoch *n+1* exists is `COMMITTED`; an operation whose
  commit observes epoch *n+1* is `REJECTED`. Any execution where the order cannot be established
  from the exported history is `INDETERMINATE`.
- **Schedule-time adversary.** The frozen design (48 crash windows × 4 commit/revocation orderings
  × 3 delivery schedules × 5 independent seeds, deduplicated; workers 1/2/4/8) is the adversary's
  move space: the injector may place A1/A2/A3/A6 events anywhere in it. The matrix of §5 must hold
  over the *complete* schedule space; a forbidden commit surviving any complete independently
  labeled schedule is a stop-and-revise condition, not a statistic.

## 8. Oracle and actor authority

Defined (never left unassigned, never implicit, deny-by-default for anything unlisted):

- **Oracle.** The independent oracle is the Jepsen/Elle-compatible history checker plus a
  deterministic SQL-state audit of the real PostgreSQL backend, at a frozen oracle revision
  (`oracle_spec_revision` in each fixture), adjudicated by reviewers who cannot reuse candidate
  code. The oracle owns the truth labels `COMMITTED` / `REJECTED` / `INDETERMINATE` / `ONE_COMMIT` /
  `COMMITTED_BUT_PENDING_DELIVERY` / `MEASURE`; candidate output never overwrites a truth label.
- **Crash-fault injector (A1).** Authority: kill/pause processes at chosen cut points. No authority
  over data content, keys, or labels.
- **Broker (A2).** Authority: duplicate, reorder, delay delivery. Never to alter payloads.
- **Consent epoch service.** Sole authority to mint or advance epochs.
- **Reconciler.** Authority to emit the tri-state label from evidence; never to invent `COMMITTED`
  without reconcilable ground truth, and never to rewrite history to make a label convenient.
- **AI model (A7).** Authority to propose only; zero authority over receipts, epochs, or outcomes.
- **Human adjudicator.** May resolve an `INDETERMINATE` using only oracle-exported evidence and the
  frozen tie-break rules; may not edit candidate or oracle code post hoc, and may not reopen a
  frozen analysis to obtain a desired significance.
- **Unassigned authority is a defect.** Any action in an exported history whose actor is not one of
  the above is a protocol violation and the affected history is quarantined for review, not scored.

## 9. Failure semantics and stable reason codes

All outcomes are stable reason codes; no unhandled exception is ever counted as a safe rejection.

| Code | Meaning | Family |
|---|---|---|
| `COMMITTED` | Joint evidence reconciles under a valid consent epoch; exactly one durable effect | all |
| `REJECTED` | Governed authorization refused, including stale consent epoch and scope escalation | `revocation_timing`, `model_agency`, `purpose_scope` |
| `INDETERMINATE` | Evidence missing, ambiguous, or integrity-failed; never promoted, never counted as safe | all |
| `EVIDENCE_DIGEST_MISMATCH` | Receipt/row/outbox digest disagreement or tamper flag (DSN-CASE-06) | `insider_or_observer` |
| `TORN_WRITE_DETECTED` | Partial journal append or incomplete record framing | `crash_consistency` |
| `DURABILITY_CONTRACT_VIOLATION` | Storage acknowledged before persisting (fsync assumption failure) | `crash_consistency` |
| `DUPLICATE_OPERATION_ID` | Concurrent or replayed operation ID beyond ledger capacity (DSN-CASE-08) | `replay` |
| `CONSENT_EPOCH_STALE` | Commit observed an epoch newer than the receipt's | `revocation_timing` |
| `RECEIPT_ROW_DISAGREEMENT` | Row and receipt reconcile to different outcomes for the same operation ID | `crash_consistency` |
| `DELIVERY_PENDING` | Committed but bounded delivery outstanding (DSN-CASE-07); liveness, not safety | `replay` |

An `INDETERMINATE` outcome, a timeout, or an unknown state is reported in its own denominator
bucket — per the task's stop-and-revise rules, it is never folded into rejections or successes.

## 10. Honest limits and evidence provenance

- This document is a **design artifact**: the matrix above registers attack/control pairs to be
  implemented and adjudicated; it asserts no pass rates, no violation counts, and no cost numbers.
  All measured endpoints derive mechanically from `artifacts/venue2027/dsn/<run_id>/manifest.json`
  under the frozen protocol.
- Trust assumptions here are **genuine, not decorative**: if the journal is writable in place, if
  the durability configuration lies, or if the reconciler imports candidate code, the model above
  collapses and the study must stop and revise rather than re-label failures.
- The falsification rule stands unmodified: a correctly engineered PostgreSQL transaction +
  transactional outbox + idempotent consumer (B1) that achieves the same joint invariants at
  equal/better recovery cost discards the new-mechanism superiority claim.
