---------------------------- MODULE GLHS_GSA ----------------------------
(***************************************************************************)
(* Formal TLA+ Specification of Governance-Snapshot Atomicity (GSA)        *)
(* and Governed State Transition (GST) Engine for CLARA-Care / GLHS.       *)
(*                                                                         *)
(* Key Guarantees Verified:                                                *)
(* 1. GSA_StateIsolation: Causal read-dependency invariance across commits *)
(* 2. GSA_GovernanceFreshness: Monotonic policy and consent epoch stability*)
(* 3. GSA_PhantomFree: Strict fail-closed abort on concurrent epoch drift  *)
(* 4. DeadlockFree: Acyclic wait-for graph under canonical lock hierarchy  *)
(***************************************************************************)

EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS
    Agents,         \* Set of autonomous agent identifiers
    Entities,       \* Set of clinical entity identifiers
    Domains,        \* Set of governance policy domains
    MaxVersion,     \* Maximum state version counter (bounded model checking)
    MaxEpoch        \* Maximum policy/consent epoch counter

VARIABLES
    entity_versions,\* [Entities -> 0..MaxVersion]
    consent_epochs, \* [Domains -> 0..MaxEpoch]
    policy_epochs,  \* [Domains -> 0..MaxEpoch]
    leases,         \* [Agents -> [domain : Domains, entity : Entities, v_s : 0..MaxVersion, c_s : 0..MaxEpoch, p_s : 0..MaxEpoch, active : BOOLEAN]]
    lock_state,     \* [Entities -> {"free", "held"}]
    policy_lock,    \* [Domains -> {"free", "held"}]
    consent_lock,   \* [Domains -> {"free", "held"}]
    txn_state,      \* [Agents -> {"idle", "reading", "proposing", "locking_policy", "locking_consent", "locking_entity", "committing", "aborted"}]
    wait_for        \* Subset of Agents \X Agents (explicit wait-for graph edges)

vars == <<entity_versions, consent_epochs, policy_epochs, leases,
          lock_state, policy_lock, consent_lock, txn_state, wait_for>>

(***************************************************************************)
(* Helper Predicates and Operators                                         *)
(***************************************************************************)

RECURSIVE TransitiveClosure(_)
TransitiveClosure(R) ==
    LET nextR == R \cup {<<a, c>> \in Agents \X Agents : \E b \in Agents : <<a, b>> \in R /\ <<b, c>> \in R}
    IN IF nextR = R THEN R ELSE TransitiveClosure(nextR)

PolicyLockHolder(d) ==
    {a \in Agents : leases[a].domain = d /\ txn_state[a] \in {"locking_consent", "locking_entity", "committing"}}

ConsentLockHolder(d) ==
    {a \in Agents : leases[a].domain = d /\ txn_state[a] \in {"locking_entity", "committing"}}

EntityLockHolder(e) ==
    {a \in Agents : leases[a].entity = e /\ txn_state[a] \in {"committing"}}

(***************************************************************************)
(* Initial State Predicate (Init)                                          *)
(***************************************************************************)

Init ==
    /\ entity_versions = [e \in Entities |-> 0]
    /\ consent_epochs = [d \in Domains |-> 0]
    /\ policy_epochs = [d \in Domains |-> 0]
    /\ leases = [a \in Agents |-> [
           domain |-> CHOOSE d \in Domains : TRUE,
           entity |-> CHOOSE e \in Entities : TRUE,
           v_s    |-> 0,
           c_s    |-> 0,
           p_s    |-> 0,
           active |-> FALSE
       ]]
    /\ lock_state = [e \in Entities |-> "free"]
    /\ policy_lock = [d \in Domains |-> "free"]
    /\ consent_lock = [d \in Domains |-> "free"]
    /\ txn_state = [a \in Agents |-> "idle"]
    /\ wait_for = {}

(***************************************************************************)
(* Protocol Actions                                                        *)
(***************************************************************************)

\* 1. Issue a Task-Bounded Governed Lease at Snapshot Disclosure Time
IssueLease(a, d, e) ==
    /\ txn_state[a] = "idle"
    /\ leases' = [leases EXCEPT ![a] = [
           domain |-> d,
           entity |-> e,
           v_s    |-> entity_versions[e],
           c_s    |-> consent_epochs[d],
           p_s    |-> policy_epochs[d],
           active |-> TRUE
       ]]
    /\ txn_state' = [txn_state EXCEPT ![a] = "reading"]
    /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs,
                  lock_state, policy_lock, consent_lock, wait_for>>

\* 2. Formulate State Transition Proposal during Autonomous Inference Window
ProposeWrite(a, e) ==
    /\ txn_state[a] = "reading"
    /\ leases[a].active = TRUE
    /\ leases[a].entity = e
    /\ txn_state' = [txn_state EXCEPT ![a] = "proposing"]
    /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs, leases,
                  lock_state, policy_lock, consent_lock, wait_for>>

\* 3. Canonical Lock Hierarchy Level 1: Acquire Policy Lock Anchor
LockPolicy(a, d) ==
    /\ leases[a].domain = d
    /\ txn_state[a] \in {"proposing", "locking_policy"}
    /\ IF policy_lock[d] = "free"
       THEN /\ policy_lock' = [policy_lock EXCEPT ![d] = "held"]
            /\ txn_state' = [txn_state EXCEPT ![a] = "locking_consent"]
            /\ wait_for' = {edge \in wait_for : edge[1] /= a}
       ELSE /\ txn_state[a] = "proposing"
            /\ policy_lock' = policy_lock
            /\ txn_state' = [txn_state EXCEPT ![a] = "locking_policy"]
            /\ wait_for' = wait_for \cup {<<a, h>> : h \in PolicyLockHolder(d)}
    /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs, leases,
                  lock_state, consent_lock>>

AcquirePolicy(a) == LockPolicy(a, leases[a].domain)

\* 4. Canonical Lock Hierarchy Level 2: Acquire Consent Lock Anchor
LockConsent(a, d) ==
    /\ leases[a].domain = d
    /\ txn_state[a] = "locking_consent"
    /\ IF consent_lock[d] = "free"
       THEN /\ consent_lock' = [consent_lock EXCEPT ![d] = "held"]
            /\ txn_state' = [txn_state EXCEPT ![a] = "locking_entity"]
            /\ wait_for' = {edge \in wait_for : edge[1] /= a}
            /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs, leases,
                          lock_state, policy_lock>>
       ELSE /\ ~(\E h \in ConsentLockHolder(d) : <<a, h>> \in wait_for)
            /\ consent_lock' = consent_lock
            /\ txn_state' = txn_state
            /\ wait_for' = wait_for \cup {<<a, h>> : h \in ConsentLockHolder(d)}
            /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs, leases,
                          lock_state, policy_lock>>

AcquireConsent(a) == LockConsent(a, leases[a].domain)

\* 5. Canonical Lock Hierarchy Level 3: Acquire Entity Lock & Validate Invariants
LockEntity(a, e) ==
    /\ leases[a].entity = e
    /\ txn_state[a] = "locking_entity"
    /\ IF lock_state[e] = "free"
       THEN IF /\ leases[a].v_s = entity_versions[e]
               /\ leases[a].c_s = consent_epochs[leases[a].domain]
               /\ leases[a].p_s = policy_epochs[leases[a].domain]
            THEN /\ lock_state' = [lock_state EXCEPT ![e] = "held"]
                 /\ txn_state' = [txn_state EXCEPT ![a] = "committing"]
                 /\ wait_for' = {edge \in wait_for : edge[1] /= a}
                 /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs,
                               leases, policy_lock, consent_lock>>
            ELSE \* Validation failed: stale snapshot, consent revoked, or policy updated. Abort immediately.
                 /\ lock_state' = lock_state
                 /\ policy_lock' = [policy_lock EXCEPT ![leases[a].domain] = "free"]
                 /\ consent_lock' = [consent_lock EXCEPT ![leases[a].domain] = "free"]
                 /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
                 /\ leases' = [leases EXCEPT ![a].active = FALSE]
                 /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                 /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs>>
       ELSE /\ ~(\E h \in EntityLockHolder(e) : <<a, h>> \in wait_for)
            /\ lock_state' = lock_state
            /\ txn_state' = txn_state
            /\ wait_for' = wait_for \cup {<<a, h>> : h \in EntityLockHolder(e)}
            /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs, leases,
                          policy_lock, consent_lock>>

AcquireEntity(a) == LockEntity(a, leases[a].entity)

\* 6. Commit Governed State Transition (GST_Commit)
CommitGST(a) ==
    LET d == leases[a].domain
        e == leases[a].entity
    IN
        /\ txn_state[a] = "committing"
        /\ entity_versions[e] < MaxVersion
        /\ entity_versions' = [entity_versions EXCEPT ![e] = entity_versions[e] + 1]
        /\ lock_state' = [lock_state EXCEPT ![e] = "free"]
        /\ consent_lock' = [consent_lock EXCEPT ![d] = "free"]
        /\ policy_lock' = [policy_lock EXCEPT ![d] = "free"]
        /\ leases' = [leases EXCEPT ![a].active = FALSE]
        /\ txn_state' = [txn_state EXCEPT ![a] = "idle"]
        /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
        /\ UNCHANGED <<consent_epochs, policy_epochs>>

\* 7. Concurrent User Mutation: Revoke / Modify Informed Consent
RevokeConsent(d) ==
    /\ consent_lock[d] = "free"
    /\ consent_epochs[d] < MaxEpoch
    /\ consent_epochs' = [consent_epochs EXCEPT ![d] = consent_epochs[d] + 1]
    /\ UNCHANGED <<entity_versions, policy_epochs, leases, lock_state,
                  policy_lock, consent_lock, txn_state, wait_for>>

\* 8. Concurrent Governance / Regulatory Mutation: Advance Policy Epoch
AdvancePolicy(d) ==
    /\ policy_lock[d] = "free"
    /\ policy_epochs[d] < MaxEpoch
    /\ policy_epochs' = [policy_epochs EXCEPT ![d] = policy_epochs[d] + 1]
    /\ UNCHANGED <<entity_versions, consent_epochs, leases, lock_state,
                  policy_lock, consent_lock, txn_state, wait_for>>

\* 9. Abort and Release Held Locks
Abort(a) ==
    LET d == leases[a].domain
        e == leases[a].entity
    IN
        /\ txn_state[a] \in {"reading", "proposing", "locking_policy",
                             "locking_consent", "locking_entity", "committing", "aborted"}
        /\ IF txn_state[a] = "aborted"
           THEN /\ txn_state' = [txn_state EXCEPT ![a] = "idle"]
                /\ leases' = [leases EXCEPT ![a].active = FALSE]
                /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs,
                              lock_state, policy_lock, consent_lock>>
           ELSE IF txn_state[a] \in {"reading", "proposing", "locking_policy"}
           THEN /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
                /\ leases' = [leases EXCEPT ![a].active = FALSE]
                /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs,
                              lock_state, policy_lock, consent_lock>>
           ELSE IF txn_state[a] = "locking_consent"
           THEN /\ policy_lock' = [policy_lock EXCEPT ![d] = "free"]
                /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
                /\ leases' = [leases EXCEPT ![a].active = FALSE]
                /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs,
                              lock_state, consent_lock>>
           ELSE IF txn_state[a] = "locking_entity"
           THEN /\ policy_lock' = [policy_lock EXCEPT ![d] = "free"]
                /\ consent_lock' = [consent_lock EXCEPT ![d] = "free"]
                /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
                /\ leases' = [leases EXCEPT ![a].active = FALSE]
                /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs,
                              lock_state>>
           ELSE \* txn_state[a] = "committing"
                /\ policy_lock' = [policy_lock EXCEPT ![d] = "free"]
                /\ consent_lock' = [consent_lock EXCEPT ![d] = "free"]
                /\ lock_state' = [lock_state EXCEPT ![e] = "free"]
                /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
                /\ leases' = [leases EXCEPT ![a].active = FALSE]
                /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                /\ UNCHANGED <<entity_versions, consent_epochs, policy_epochs>>

(***************************************************************************)
(* Next State Relation and Full Specification                              *)
(***************************************************************************)

Next ==
    \/ \E a \in Agents, d \in Domains, e \in Entities: IssueLease(a, d, e)
    \/ \E a \in Agents, e \in Entities: ProposeWrite(a, e)
    \/ \E a \in Agents: AcquirePolicy(a)
    \/ \E a \in Agents: AcquireConsent(a)
    \/ \E a \in Agents: AcquireEntity(a)
    \/ \E a \in Agents: CommitGST(a)
    \/ \E a \in Agents: Abort(a)
    \/ \E d \in Domains: RevokeConsent(d)
    \/ \E d \in Domains: AdvancePolicy(d)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Formal Safety and Liveness Invariants                                   *)
(***************************************************************************)

TypeOK ==
    /\ entity_versions \in [Entities -> 0..MaxVersion]
    /\ consent_epochs \in [Domains -> 0..MaxEpoch]
    /\ policy_epochs \in [Domains -> 0..MaxEpoch]
    /\ leases \in [Agents -> [
           domain : Domains,
           entity : Entities,
           v_s    : 0..MaxVersion,
           c_s    : 0..MaxEpoch,
           p_s    : 0..MaxEpoch,
           active : BOOLEAN
       ]]
    /\ lock_state \in [Entities -> {"free", "held"}]
    /\ policy_lock \in [Domains -> {"free", "held"}]
    /\ consent_lock \in [Domains -> {"free", "held"}]
    /\ txn_state \in [Agents -> {"idle", "reading", "proposing", "locking_policy",
                                "locking_consent", "locking_entity", "committing", "aborted"}]
    /\ wait_for \subseteq (Agents \X Agents)

\* Invariant 1: State Isolation (Causal read-dependency version stability)
GSA_StateIsolation ==
    \A a \in Agents :
        (txn_state[a] = "committing") => (leases[a].v_s = entity_versions[leases[a].entity])

\* Invariant 2: Governance Freshness (Policy & Consent epoch stability)
GSA_GovernanceFreshness ==
    \A a \in Agents :
        (txn_state[a] = "committing") => (
            /\ leases[a].c_s = consent_epochs[leases[a].domain]
            /\ leases[a].p_s = policy_epochs[leases[a].domain]
        )

\* Invariant 3: Phantom-Free Rejection (Concurrent mutations force abort)
GSA_PhantomFree ==
    \A a \in Agents :
        (leases[a].active /\ (
            \/ leases[a].c_s /= consent_epochs[leases[a].domain]
            \/ leases[a].p_s /= policy_epochs[leases[a].domain]
        )) => (txn_state[a] /= "committing")

\* Invariant 4: Deadlock Freedom (Acyclic Wait-For Graph)
DeadlockFree ==
    \A a \in Agents : <<a, a>> \notin TransitiveClosure(wait_for)

=============================================================================
