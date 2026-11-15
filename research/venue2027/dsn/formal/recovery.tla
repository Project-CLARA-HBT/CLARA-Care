\*******************************************************************
(* recovery.tla -- Recoverable Safety Journals for Crash-Consistent *)
(* AI-Mediated Health-State Mutations (DSN 2027, task DSN-X02).     *)
(*                                                                  *)
(* Purpose: bounded TLA+ model of the joint recoverability          *)
(* contract for governed AI-mediated health-state mutations. It     *)
(* composes the four concern planes of the DSN study design:        *)
(*   (1) consumer replay      -- at-least-once outbox delivery,     *)
(*   (2) consent mutation     -- concurrent revocation / renewal,   *)
(*   (3) kernel commit        -- the durable clinical-row write,    *)
(*   (4) receipt persistence  -- the versioned decision receipt.    *)
(*                                                                  *)
(* A crash (SIGKILL) may strike any process at ANY transition and   *)
(* discards all volatile state (program counter); durable state is  *)
(* crash-consistent, so disagreement between the clinical row, the  *)
(* decision receipt and the outbox arises only from the ORDER of    *)
(* durable writes across crash windows. Recovery is the only lever  *)
(* after a crash and decides from durable evidence alone;           *)
(* ambiguous evidence never becomes a positive outcome.             *)
(*                                                                  *)
(* The model supports RQ1 (clinical row / receipt / outbox          *)
(* disagreement after bounded recovery) and RQ2 (idempotence under  *)
(* duplicate delivery and concurrent consent revocation), and       *)
(* encodes the reconciler semantics behind the oracle labels        *)
(* COMMITTED / REJECTED / INDETERMINATE:                            *)
(*   DSN-CASE-02  crash before commit  -> nothing durable, retry    *)
(*   DSN-CASE-03  crash after commit   -> receipt "none" +          *)
(*                                        committed row => reconcile*)
(*   DSN-CASE-04  broker replay        -> idempotent consumer,      *)
(*                                        bounded redeliveries      *)
(*   DSN-CASE-05  revocation race      -> commit-time consent       *)
(*                                        re-check => REJECTED      *)
(*   DSN-CASE-06  corrupted receipt    -> INDETERMINATE, never a    *)
(*                                        silent successful state   *)
(*   DSN-CASE-07  outbox delay         -> commit decoupled from     *)
(*                                        delivery (box may lag)    *)
(*                                                                  *)
(* TLC invocation (counterexample export):                          *)
(*   java -cp tla2tools.jar tlc2.TLC -config Recovery.cfg \         *)
(*        -dumptrace counterexample.txt recovery.tla                *)
(* Any invariant or property violation makes TLC print and dump a   *)
(* behavior counterexample trace (see Recovery.cfg header).         *)
(*                                                                  *)
(* Allowed input: constants OpCount (2..4), Procs (1..3),           *)
(* MaxEpochs (1..4), MaxRedelivery (1..4) -- see Recovery.cfg.      *)
(* Failure semantics: every invariant / property below is checked   *)
(* against all bounded behaviors; a violation is a counterexample   *)
(* to export, never silently swallowed.                             *)
(*                                                                  *)
(* Target contract (task manifest): Init, Next, Recovery,           *)
(* NoPhantomSuccess, ExactlyOnceEffect.                             *)
(*                                                                  *)
(* Version: DSN-X02-recovery.tla v1.0.0                             *)
\*******************************************************************
MODULE recovery

EXTENDS Naturals, Sequences

CONSTANTS
  \* OpCount: bounded number of governed operations in the history.
  OpCount,
  \* Procs: bounded number of competing pipeline processes.
  Procs,
  \* MaxEpochs: bounded number of consent mutations (revoke/renew).
  MaxEpochs,
  \* MaxRedelivery: bounded at-least-once redeliveries per message
  \* (3 reproduces the DSN-CASE-04 triple broker replay).
  MaxRedelivery

ASSUME
  OpCount \in 2 .. 4
  /\ Procs \in 1 .. 3
  /\ MaxEpochs \in 1 .. 4
  /\ MaxRedelivery \in 1 .. 4

(***************************************************************************
 * State variables.                                                         *
 *                                                                          *
 * Durable (survives a crash): consentEpoch, consentLive, committedOps,     *
 * rowVer, receipts, receiptEpoch, box, effects, opId.                      *
 *   consentEpoch / consentLive : monotone medical-consent epoch + flag.    *
 *   committedOps               : ops whose clinical-row write is durable.  *
 *   rowVer                     : monotone version of durable row writes.   *
 *   receipts                   : per-op decision receipt, one of           *
 *                                "none" | "rejected" | "committed" |       *
 *                                "corrupted" | "indeterminate".            *
 *   receiptEpoch               : consent epoch captured by the latest      *
 *                                durable receipt write (receipt version).  *
 *   box                        : durable outbox messages awaiting delivery.*
 *   effects                    : applied downstream side effects, the      *
 *                                ground truth for duplicate detection.     *
 *   opId                       : monotone op-id minter (durable sequence;  *
 *                                retries reuse the immutable op id).       *
 *                                                                          *
 * Volatile (lost on crash): phase (per-process program counter), crashed.  *
 * The broker delivery ledger is volatile too, which is why redelivery      *
 * after restart is possible (bounded by MaxRedelivery).                    *
 ***************************************************************************)

VARIABLES
  opId, phase, consentEpoch, consentLive,
  committedOps, rowVer, receipts, receiptEpoch,
  effects, box, dcount, crashed, verdict

vars ==
  << opId, phase, consentEpoch, consentLive, committedOps, rowVer,
     receipts, receiptEpoch, effects, box, dcount, crashed, verdict >>

ProcSet == 1 .. Procs
OpSet == 1 .. OpCount

ReceiptValues == {"none", "rejected", "committed", "corrupted",
                  "indeterminate"}
VerdictValues == {"none", "consistent", "reconciled", "rejected",
                  "indeterminate", "no_effect"}
PhaseValues == {"idle", "authorized", "consentChecked", "kernelWrote",
                "receiptWrote", "done", "crashed"}

\* ---------------------------------------------------------------------------
\* Init: the system starts empty and healthy. No durable trace of any
\* operation exists; consent is live at epoch 0.
\* ---------------------------------------------------------------------------
Init ==
  /\ opId         = 0
  /\ phase        = [p \in ProcSet |-> "idle"]
  /\ consentEpoch = 0
  /\ consentLive  = TRUE
  /\ committedOps = {}
  /\ rowVer       = 0
  /\ receipts     = [r \in OpSet |-> "none"]
  /\ receiptEpoch = 0
  /\ effects      = <<>>
  /\ box          = {}
  /\ dcount       = [m \in OpSet |-> 0]
  /\ crashed      = [p \in ProcSet |-> FALSE]
  /\ verdict      = "none"

\* ---------------------------------------------------------------------------
\* Type invariant: every variable stays inside its declared domain.
\* ---------------------------------------------------------------------------
TypeOK ==
  /\ opId \in 0 .. OpCount
  /\ phase \in [ProcSet -> PhaseValues]
  /\ consentEpoch \in 0 .. MaxEpochs
  /\ consentLive \in BOOLEAN
  /\ committedOps \subseteq OpSet
  /\ rowVer \in 0 .. OpCount
  /\ receipts \in [OpSet -> ReceiptValues]
  /\ receiptEpoch \in 0 .. MaxEpochs
  /\ \A i \in DOMAIN effects : effects[i] \in OpSet
  /\ box \subseteq OpSet
  /\ dcount \in [OpSet -> 0 .. MaxRedelivery]
  /\ crashed \in [ProcSet -> BOOLEAN]
  /\ verdict \in VerdictValues

\* ---------------------------------------------------------------------------
\* NoPhantomSuccess: a user-visible success (a "committed" decision
\* receipt) never exists without the matching durable committed clinical
\* row. Invalid or ambiguous receipt evidence is never a positive claim.
\* ---------------------------------------------------------------------------
NoPhantomSuccess ==
  \A r \in OpSet : receipts[r] = "committed" => r \in committedOps

\* ---------------------------------------------------------------------------
\* ExactlyOnceEffect: no duplicate committed effect. The effects log
\* carries every operation at most once, and every applied effect is
\* grounded in a durably committed clinical row (delivered via the
\* durable outbox only).
\* ---------------------------------------------------------------------------
ExactlyOnceEffect ==
  /\ \A i, j \in DOMAIN effects :
       effects[i] = effects[j] => i = j
  /\ \A i \in DOMAIN effects : effects[i] \in box
  /\ \A i \in DOMAIN effects : effects[i] \in committedOps

\* ---------------------------------------------------------------------------
\* ReceiptConsistency: the versioned decision receipts agree with the
*  durable consent epoch and with the committed clinical rows. A
\* rejected receipt never binds an op whose row is committed (that
\* combination is contradictory evidence and Recovery normalizes it to
\* INDETERMINATE), and the outbox is grounded in committed rows.
\* ---------------------------------------------------------------------------
ReceiptConsistency ==
  /\ receiptEpoch <= consentEpoch
  /\ \A r \in OpSet :
       receipts[r] = "rejected" => r \notin committedOps
  /\ \A r \in OpSet :
       receipts[r] = "committed" => receiptEpoch <= consentEpoch
  /\ box \subseteq committedOps

\* ---------------------------------------------------------------------------
\* OutboxIsGrounded: every effect was applied to a message that the
\* durable outbox carried (independent outbox receipt), and delivery
\* counters respect the at-least-once bound.
\* ---------------------------------------------------------------------------
OutboxIsGrounded ==
  /\ \A i \in DOMAIN effects : effects[i] \in box
  /\ \A m \in OpSet : dcount[m] > 0 => m \in box

\* ---------------------------------------------------------------------------
\* NoCommittedThenLost: a durably committed clinical row is never
\* erased. checked as a temporal property over every real step
\* (committedOps only grows); see PROPERTY in Recovery.cfg.
\* ---------------------------------------------------------------------------
NoCommittedThenLost ==
  [][ \A r \in OpSet :
        (r \in committedOps) => (r \in committedOps') ]_vars

\* ---------------------------------------------------------------------------
\* RecoveryFailClosed: the reconciler verdict always leaves explicit
\* durable evidence behind. Reconciled and consistent verdicts are
\* backed by a committed receipt for a committed row; an INDETERMINATE
\* verdict always normalizes the ambiguous receipt to "indeterminate"
\* (invalid/ambiguous evidence never becomes a positive outcome).
\* ---------------------------------------------------------------------------
RecoveryFailClosed ==
  /\ verdict = "reconciled" =>
       \E r \in committedOps : receipts[r] = "committed"
  /\ verdict = "consistent" =>
       \E r \in committedOps : receipts[r] = "committed"
  /\ verdict = "rejected" =>
       \E r \in OpSet : receipts[r] = "rejected"
  /\ verdict = "indeterminate" =>
       \E r \in OpSet : receipts[r] = "indeterminate"

\* ---------------------------------------------------------------------------
\* Plane 1: consumer replay. The durable outbox is drained with
\* at-least-once semantics, bounded by MaxRedelivery per message
\* (DSN-CASE-04): the delivery counter is bumped, then the effect is
\* applied IDEMPOTENTLY -- a redelivery of an operation whose effect is
\* already on the effects log must not append a second effect.
\* ---------------------------------------------------------------------------
ConsumerReplay(m) ==
  /\ m \in box
  /\ dcount[m] < MaxRedelivery
  /\ dcount' = [dcount EXCEPT ![m] = @ + 1]
  /\ IF m \in {effects[i] : i \in DOMAIN effects}
       THEN effects' = effects          \* idempotent replay: no duplicate
       ELSE effects' = Append(effects, m)
  /\ UNCHANGED << opId, phase, consentEpoch, consentLive, committedOps,
                  rowVer, receipts, receiptEpoch, box, crashed, verdict >>

\* ---------------------------------------------------------------------------
\* Plane 2: consent mutation. A concurrent revocation bumps the consent
\* epoch and clears the live flag; a renewal (re-consent) bumps the
\* epoch again and restores the flag. The commit step re-checks the
\* flag under the commit lock (governance race, DSN-CASE-05).
\* ---------------------------------------------------------------------------
ConsentRevoke ==
  /\ consentLive
  /\ consentEpoch < MaxEpochs
  /\ consentEpoch' = consentEpoch + 1
  /\ consentLive' = FALSE
  /\ UNCHANGED << opId, phase, committedOps, rowVer, receipts,
                  receiptEpoch, effects, box, dcount, crashed, verdict >>

ConsentRenew ==
  /\ ~consentLive
  /\ consentEpoch < MaxEpochs
  /\ consentEpoch' = consentEpoch + 1
  /\ consentLive' = TRUE
  /\ UNCHANGED << opId, phase, committedOps, rowVer, receipts,
                  receiptEpoch, effects, box, dcount, crashed, verdict >>

\* ---------------------------------------------------------------------------
\* Plane 3 + 4: the governed mutation pipeline of process p.
\*
\* Authorize      : mint the next immutable operation id (the stable
\*                  idempotency / retry key; retries reuse it).
\* ConsentCheck   : consent gate before any write; refusal is terminal
\*                  and persists a durable REJECTED receipt.
\* KernelCommit   : durable clinical-row write, valid only while
\*                  consent is still live at commit time (lock
\*                  re-check); if consent was revoked in the window,
\*                  the op aborts with a durable REJECTED receipt and
\*                  no forbidden write (DSN-CASE-05).
\* PersistReceipt : durable versioned decision receipt.
\* Enqueue        : durable outbox insert; downstream delivery is
\*                  decoupled from the commit decision (DSN-CASE-07).
\* ---------------------------------------------------------------------------
Authorize(p) ==
  /\ phase[p] = "idle"
  /\ opId < OpCount
  /\ opId' = opId + 1
  /\ phase' = [phase EXCEPT ![p] = "authorized"]
  /\ UNCHANGED << consentEpoch, consentLive, committedOps, rowVer,
                  receipts, receiptEpoch, effects, box, dcount,
                  crashed, verdict >>

ConsentCheck(p) ==
  /\ phase[p] = "authorized"
  /\ IF consentLive
       THEN phase' = [phase EXCEPT ![p] = "consentChecked"]
       ELSE phase' = [phase EXCEPT ![p] = "done"]
  /\ IF consentLive
       THEN UNCHANGED << receipts, receiptEpoch >>
       ELSE /\ receipts' = [receipts EXCEPT ![opId] = "rejected"]
            /\ receiptEpoch' = consentEpoch
  /\ UNCHANGED << opId, consentEpoch, consentLive, committedOps, rowVer,
                  effects, box, dcount, crashed, verdict >>

KernelCommit(p) ==
  /\ phase[p] = "consentChecked"
  /\ IF consentLive
       THEN /\ committedOps' = committedOps \cup {opId}
            /\ rowVer' = rowVer + 1
            /\ phase' = [phase EXCEPT ![p] = "kernelWrote"]
            /\ UNCHANGED << receipts, receiptEpoch >>
       ELSE /\ receipts' = [receipts EXCEPT ![opId] = "rejected"]
            /\ receiptEpoch' = consentEpoch
            /\ phase' = [phase EXCEPT ![p] = "done"]
            /\ UNCHANGED << committedOps, rowVer >>
  /\ UNCHANGED << opId, consentEpoch, consentLive, effects, box,
                  dcount, crashed, verdict >>

PersistReceipt(p) ==
  /\ phase[p] = "kernelWrote"
  /\ receipts' = [receipts EXCEPT ![opId] = "committed"]
  /\ receiptEpoch' = consentEpoch
  /\ phase' = [phase EXCEPT ![p] = "receiptWrote"]
  /\ UNCHANGED << opId, consentEpoch, consentLive, committedOps, rowVer,
                  effects, box, dcount, crashed, verdict >>

Enqueue(p) ==
  /\ phase[p] = "receiptWrote"
  /\ box' = box \cup {opId}
  /\ phase' = [phase EXCEPT ![p] = "done"]
  /\ UNCHANGED << opId, consentEpoch, consentLive, committedOps, rowVer,
                  receipts, receiptEpoch, effects, dcount, crashed,
                  verdict >>

ReturnToIdle(p) ==
  /\ phase[p] = "done"
  /\ phase' = [phase EXCEPT ![p] = "idle"]
  /\ UNCHANGED << opId, consentEpoch, consentLive, committedOps, rowVer,
                  receipts, receiptEpoch, effects, box, dcount,
                  crashed, verdict >>

\* ---------------------------------------------------------------------------
\* Crash: a SIGKILL may strike any process at ANY point of its protocol.
\* The program counter is lost; durable variables are untouched (the
\* store is crash-consistent, so no torn durable write exists in this
\* model -- disagreement comes from the order of durable writes). The
\* in-memory broker ledger is lost, which re-opens the bounded
\* redelivery budget after restart.
\* ---------------------------------------------------------------------------
Crash(p) ==
  /\ ~crashed[p]
  /\ phase[p] # "crashed"
  /\ crashed' = [crashed EXCEPT ![p] = TRUE]
  /\ phase' = [phase EXCEPT ![p] = "crashed"]
  /\ dcount' =
       [m \in OpSet |-> 0]      \* volatile broker ledger is lost
  /\ UNCHANGED << opId, consentEpoch, consentLive, committedOps, rowVer,
                  receipts, receiptEpoch, effects, box, verdict >>

\* ---------------------------------------------------------------------------
\* Recovery: the reconciler of the recoverable safety journal. It fires
\* for a crashed process and decides from DURABLE evidence only,
\* scanning any operation r; the verdict always leaves explicit
\* durable evidence:
\*
\*   r committed + receipt "committed"  -> "consistent": nothing to do.
\*   r committed + receipt "none"       -> "reconciled": the committed
\*       row is the durable ground truth (crash window between
\*       KernelCommit and PersistReceipt, DSN-CASE-03): stamp a
\*       committed receipt for the row's op and (re)queue the outbox.
\*   r committed + corrupted/rejected/indeterminate receipt -> the row
\*       and the receipt disagree (tamper or torn evidence, CASE-06):
\*       normalize the receipt to "indeterminate"; never a silent
\*       successful state; independent adjudication decides next.
\*   r not committed + committed/corrupted receipt -> phantom receipt
\*       evidence: "indeterminate", fail closed (defensive branch).
\*   r not committed + "rejected" receipt -> "rejected": the durable
\*       refusal stands; no write is manufactured (CASE-05).
\*   r not committed + "none"/"indeterminate" -> "no_effect": nothing
\*       durable happened; retry under the same immutable op id is
\*       safe (CASE-02). An existing indeterminate receipt is never
\*       upgraded to a positive outcome.
\* ---------------------------------------------------------------------------
Recovery(p) ==
  /\ crashed[p]
  /\ \E r \in OpSet :
       /\ verdict' =
            IF r \in committedOps
              THEN IF receipts[r] = "committed" THEN "consistent"
                   ELSE IF receipts[r] = "none" THEN "reconciled"
                   ELSE "indeterminate"
            ELSE IF receipts[r] \in {"committed", "corrupted"} THEN "indeterminate"
            ELSE IF receipts[r] = "rejected" THEN "rejected"
            ELSE "no_effect"
       /\ ( IF r \in committedOps /\ receipts[r] = "none"
            THEN /\ receipts' = [receipts EXCEPT ![r] = "committed"]
                 /\ receiptEpoch' = consentEpoch
                 /\ box' = box \cup {r}
            ELSE IF r \in committedOps /\ receipts[r] # "committed"
            THEN /\ receipts' = [receipts EXCEPT ![r] = "indeterminate"]
                 /\ receiptEpoch' = receiptEpoch
                 /\ box' = box
            ELSE IF r \notin committedOps
                    /\ receipts[r] \in {"committed", "corrupted"}
            THEN /\ receipts' = [receipts EXCEPT ![r] = "indeterminate"]
                 /\ receiptEpoch' = receiptEpoch
                 /\ box' = box
            ELSE UNCHANGED << receipts, receiptEpoch, box >> )
  /\ crashed' = [crashed EXCEPT ![p] = FALSE]
  /\ phase' = [phase EXCEPT ![p] = "idle"]
  /\ UNCHANGED << opId, consentEpoch, consentLive, committedOps, rowVer,
                  effects, dcount >>

\* ---------------------------------------------------------------------------
\* Tamper: adversarial storage corruption of a durable committed
\* receipt (bit-rot or attacker, DSN-CASE-06). The digest of the stored
\* receipt no longer matches the stored transition; the corrupt value
\* is distinct from every positive label so the tamper is flaggable
\* and Recovery normalizes it to INDETERMINATE.
\* ---------------------------------------------------------------------------
Tamper ==
  /\ \E r \in committedOps : receipts[r] = "committed"
  /\ \E r \in committedOps :
       /\ receipts[r] = "committed"
       /\ receipts' = [receipts EXCEPT ![r] = "corrupted"]
  /\ receiptEpoch' = receiptEpoch
  /\ UNCHANGED << opId, phase, consentEpoch, consentLive, committedOps,
                  rowVer, effects, box, dcount, crashed, verdict >>

\* ---------------------------------------------------------------------------
\* Next
\* ---------------------------------------------------------------------------
Next ==
  \/ \E p \in ProcSet :
       \/ Authorize(p) \/ ConsentCheck(p) \/ KernelCommit(p)
       \/ PersistReceipt(p) \/ Enqueue(p) \/ ReturnToIdle(p)
       \/ Crash(p) \/ Recovery(p)
  \/ \E m \in OpSet : ConsumerReplay(m)
  \/ ConsentRevoke \/ ConsentRenew
  \/ Tamper

\* ---------------------------------------------------------------------------
\* Fairness (repeatable settings, mirrored by SPECIFICATION Spec in
\* Recovery.cfg): the reconciler eventually runs for every crashed
\* process; a queued outbox message is eventually delivered; an idle
\* process is eventually scheduled while operations remain. Crash and
\* Tamper are deliberately unfair -- adversarial events are not
\* required to occur.
\* ---------------------------------------------------------------------------
Fairness ==
  /\ \A p \in ProcSet : WF_vars(Recovery(p))
  /\ WF_vars(\E m \in OpSet : ConsumerReplay(m))
  /\ \A p \in ProcSet : WF_vars(Authorize(p))

\* ---------------------------------------------------------------------------
\* Spec: the full checked specification (bounds via Recovery.cfg).
\* ---------------------------------------------------------------------------
Spec ==
  Init /\ [][Next]_vars /\ Fairness

=============================================================================
