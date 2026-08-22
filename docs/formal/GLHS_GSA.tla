---------------------------- MODULE GLHS_GSA ----------------------------
(***************************************************************************)
(* Formal TLA+ Specification of Governance-Snapshot Atomicity (GSA)        *)
(* and Governed State Transition (GST) Engine for CLARA-Care / GLHS.       *)
(*                                                                         *)
(* Key Guarantees Verified:                                                *)
(* 1. GSA_StateIsolation: Multi-entity read-dependency version stability   *)
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
    entity_versions,    \* [Entities -> 0..MaxVersion]
    consent_event_ids,  \* [Domains -> 0..MaxEpoch] (Monotonic append-only consent event ID)
    policy_epochs,      \* [Domains -> 0..MaxEpoch]
    leases,             \* [Agents -> [domain : Domains, deps : SUBSET Entities, target : Entities, v_s : [Entities -> 0..MaxVersion], c_s : 0..MaxEpoch, p_s : 0..MaxEpoch, active : BOOLEAN]]
    gov_anchor_shared,  \* [Domains -> SUBSET Agents] (Shared governance read lock holders)
    gov_anchor_exclusive,\* [Domains -> {"free", "held"}] (Exclusive governance write lock)
    lock_state,         \* [Entities -> Agents \cup {"none"}] (Exclusive entity partition lock holders)
    lease_lock,         \* [Agents -> {"free", "held"}] (Level 3 lease state lock)
    locks_held,         \* [Agents -> SUBSET Entities] (Set of entity partition locks held by agent)
    txn_state,          \* [Agents -> {"idle", "reading", "proposing", "locking_gov", "locking_entities", "locking_lease", "committing", "aborted"}]
    wait_for            \* Subset of Agents \X Agents (explicit wait-for graph edges)

vars == <<entity_versions, consent_event_ids, policy_epochs, leases,
          gov_anchor_shared, gov_anchor_exclusive, lock_state, lease_lock,
          locks_held, txn_state, wait_for>>

(***************************************************************************)
(* Helper Operators and Canonical Hierarchy Ordering                       *)
(***************************************************************************)

EntityRank(e) ==
    IF ToString(e) = "e1" THEN 1
    ELSE IF ToString(e) = "e2" THEN 2
    ELSE IF ToString(e) = "e3" THEN 3
    ELSE 4

CanonicalMin(S) ==
    CHOOSE item \in S : \A other \in S : EntityRank(item) <= EntityRank(other)

RECURSIVE TransitiveClosure(_)
TransitiveClosure(R) ==
    LET nextR == R \cup {<<a, c>> \in Agents \X Agents : \E b \in Agents : <<a, b>> \in R /\ <<b, c>> \in R}
    IN IF nextR = R THEN R ELSE TransitiveClosure(nextR)

DefaultDomain == CHOOSE d \in Domains : TRUE
DefaultEntity == CHOOSE e \in Entities : TRUE

DefaultLease == [
    domain |-> DefaultDomain,
    deps   |-> {},
    target |-> DefaultEntity,
    v_s    |-> [e \in Entities |-> 0],
    c_s    |-> 0,
    p_s    |-> 0,
    active |-> FALSE
]

Symmetry == Permutations(Agents) \cup Permutations(Domains)

(***************************************************************************)
(* Initial State Predicate (Init)                                          *)
(***************************************************************************)

Init ==
    /\ entity_versions = [e \in Entities |-> 0]
    /\ consent_event_ids = [d \in Domains |-> 0]
    /\ policy_epochs = [d \in Domains |-> 0]
    /\ leases = [a \in Agents |-> DefaultLease]
    /\ gov_anchor_shared = [d \in Domains |-> {}]
    /\ gov_anchor_exclusive = [d \in Domains |-> "free"]
    /\ lock_state = [e \in Entities |-> "none"]
    /\ lease_lock = [a \in Agents |-> "free"]
    /\ locks_held = [a \in Agents |-> {}]
    /\ txn_state = [a \in Agents |-> "idle"]
    /\ wait_for = {}

(***************************************************************************)
(* Protocol Actions                                                        *)
(***************************************************************************)

\* 1. Issue a Task-Bounded Governed Lease at Snapshot Disclosure Time over Deps(a)
IssueLease(a, d, deps) ==
    /\ txn_state[a] = "idle"
    /\ deps \in (SUBSET Entities) \ {{}}
    /\ leases' = [leases EXCEPT ![a] = [
           domain |-> d,
           deps   |-> deps,
           target |-> CanonicalMin(deps),
           v_s    |-> entity_versions,
           c_s    |-> consent_event_ids[d],
           p_s    |-> policy_epochs[d],
           active |-> TRUE
       ]]
    /\ txn_state' = [txn_state EXCEPT ![a] = "reading"]
    /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs,
                  gov_anchor_shared, gov_anchor_exclusive, lock_state,
                  lease_lock, locks_held, wait_for>>

\* 2. Formulate State Transition Proposal during Autonomous Inference Window
ProposeWrite(a, target) ==
    /\ txn_state[a] = "reading"
    /\ leases[a].active = TRUE
    /\ target \in leases[a].deps
    /\ leases' = [leases EXCEPT ![a].target = target]
    /\ txn_state' = [txn_state EXCEPT ![a] = "proposing"]
    /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs,
                  gov_anchor_shared, gov_anchor_exclusive, lock_state,
                  lease_lock, locks_held, wait_for>>

\* 3. Canonical Lock Hierarchy Level 1: Acquire Shared Governance Lock (GovShared)
AcquireGovShared(a) ==
    LET d == leases[a].domain IN
    /\ txn_state[a] \in {"proposing", "locking_gov"}
    /\ IF gov_anchor_exclusive[d] = "free"
       THEN /\ gov_anchor_shared' = [gov_anchor_shared EXCEPT ![d] = gov_anchor_shared[d] \cup {a}]
            /\ txn_state' = [txn_state EXCEPT ![a] = "locking_entities"]
            /\ wait_for' = {edge \in wait_for : edge[1] /= a}
            /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, leases,
                          gov_anchor_exclusive, lock_state, lease_lock, locks_held>>
       ELSE /\ txn_state[a] = "proposing"
            /\ gov_anchor_shared' = gov_anchor_shared
            /\ txn_state' = [txn_state EXCEPT ![a] = "locking_gov"]
            /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, leases,
                          gov_anchor_exclusive, lock_state, lease_lock, locks_held, wait_for>>

\* 4. Canonical Lock Hierarchy Level 2: Acquire Entity Partitions in Strict Lexicographical Order
AcquireEntityPartition(a) ==
    LET remaining == leases[a].deps \ locks_held[a]
    IN
    /\ txn_state[a] = "locking_entities"
    /\ remaining /= {}
    /\ LET next_e == CanonicalMin(remaining) IN
       IF lock_state[next_e] = "none" \/ lock_state[next_e] = a
       THEN /\ lock_state' = [lock_state EXCEPT ![next_e] = a]
            /\ locks_held' = [locks_held EXCEPT ![a] = locks_held[a] \cup {next_e}]
            /\ wait_for' = {edge \in wait_for : edge[1] /= a}
            /\ IF locks_held[a] \cup {next_e} = leases[a].deps
               THEN txn_state' = [txn_state EXCEPT ![a] = "locking_lease"]
               ELSE txn_state' = txn_state
            /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, leases,
                          gov_anchor_shared, gov_anchor_exclusive, lease_lock>>
       ELSE /\ ~ (<<a, lock_state[next_e]>> \in wait_for)
            /\ wait_for' = wait_for \cup {<<a, lock_state[next_e]>>}
            /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, leases,
                          gov_anchor_shared, gov_anchor_exclusive, lock_state,
                          lease_lock, locks_held, txn_state>>

\* 5. Canonical Lock Hierarchy Level 3: Acquire LeaseState & Validate GSA Invariants
AcquireLeaseAndValidate(a) ==
    LET d == leases[a].domain IN
    /\ txn_state[a] = "locking_lease"
    /\ IF lease_lock[a] = "free"
       THEN IF /\ (\A e \in leases[a].deps : leases[a].v_s[e] = entity_versions[e])
               /\ leases[a].c_s = consent_event_ids[d]
               /\ leases[a].p_s = policy_epochs[d]
            THEN /\ lease_lock' = [lease_lock EXCEPT ![a] = "held"]
                 /\ txn_state' = [txn_state EXCEPT ![a] = "committing"]
                 /\ wait_for' = {edge \in wait_for : edge[1] /= a}
                 /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, leases,
                               gov_anchor_shared, gov_anchor_exclusive, lock_state, locks_held>>
            ELSE \* Fail-closed abort: release all acquired locks immediately
                 /\ gov_anchor_shared' = [gov_anchor_shared EXCEPT ![d] = gov_anchor_shared[d] \ {a}]
                 /\ lock_state' = [e \in Entities |-> IF e \in locks_held[a] THEN "none" ELSE lock_state[e]]
                 /\ locks_held' = [locks_held EXCEPT ![a] = {}]
                 /\ lease_lock' = [lease_lock EXCEPT ![a] = "free"]
                 /\ leases' = [leases EXCEPT ![a] = DefaultLease]
                 /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
                 /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
                 /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, gov_anchor_exclusive>>
       ELSE UNCHANGED vars

\* 6. Commit Governed State Transition (GST_Commit)
CommitGST(a) ==
    LET d == leases[a].domain
        target == leases[a].target
    IN
    /\ txn_state[a] = "committing"
    /\ entity_versions[target] < MaxVersion
    /\ entity_versions' = [entity_versions EXCEPT ![target] = entity_versions[target] + 1]
    /\ gov_anchor_shared' = [gov_anchor_shared EXCEPT ![d] = gov_anchor_shared[d] \ {a}]
    /\ lock_state' = [e \in Entities |-> IF e \in locks_held[a] THEN "none" ELSE lock_state[e]]
    /\ locks_held' = [locks_held EXCEPT ![a] = {}]
    /\ lease_lock' = [lease_lock EXCEPT ![a] = "free"]
    /\ leases' = [leases EXCEPT ![a] = DefaultLease]
    /\ txn_state' = [txn_state EXCEPT ![a] = "idle"]
    /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
    /\ UNCHANGED <<consent_event_ids, policy_epochs, gov_anchor_exclusive>>

\* 7. Concurrent User Mutation: Revoke / Modify Consent (Append Monotonic Event ID)
RevokeConsent(d) ==
    /\ gov_anchor_shared[d] = {}
    /\ gov_anchor_exclusive[d] = "free"
    /\ consent_event_ids[d] < MaxEpoch
    /\ consent_event_ids' = [consent_event_ids EXCEPT ![d] = consent_event_ids[d] + 1]
    /\ UNCHANGED <<entity_versions, policy_epochs, leases, gov_anchor_shared,
                  gov_anchor_exclusive, lock_state, lease_lock, locks_held,
                  txn_state, wait_for>>

\* 8. Concurrent Policy Mutation: Advance Governance Policy Epoch
AdvancePolicy(d) ==
    /\ gov_anchor_shared[d] = {}
    /\ gov_anchor_exclusive[d] = "free"
    /\ policy_epochs[d] < MaxEpoch
    /\ policy_epochs' = [policy_epochs EXCEPT ![d] = policy_epochs[d] + 1]
    /\ UNCHANGED <<entity_versions, consent_event_ids, leases, gov_anchor_shared,
                  gov_anchor_exclusive, lock_state, lease_lock, locks_held,
                  txn_state, wait_for>>

\* 9. Abort and Release Held Locks
Abort(a) ==
    LET d == leases[a].domain IN
    /\ txn_state[a] \in {"reading", "proposing", "locking_gov", "locking_entities",
                         "locking_lease", "committing", "aborted"}
    /\ IF txn_state[a] = "aborted"
       THEN /\ txn_state' = [txn_state EXCEPT ![a] = "idle"]
            /\ leases' = [leases EXCEPT ![a] = DefaultLease]
            /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
            /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs,
                          gov_anchor_shared, gov_anchor_exclusive, lock_state,
                          lease_lock, locks_held>>
       ELSE /\ gov_anchor_shared' = [gov_anchor_shared EXCEPT ![d] = gov_anchor_shared[d] \ {a}]
            /\ lock_state' = [e \in Entities |-> IF e \in locks_held[a] THEN "none" ELSE lock_state[e]]
            /\ locks_held' = [locks_held EXCEPT ![a] = {}]
            /\ lease_lock' = [lease_lock EXCEPT ![a] = "free"]
            /\ leases' = [leases EXCEPT ![a] = DefaultLease]
            /\ txn_state' = [txn_state EXCEPT ![a] = "aborted"]
            /\ wait_for' = {edge \in wait_for : edge[1] /= a /\ edge[2] /= a}
            /\ UNCHANGED <<entity_versions, consent_event_ids, policy_epochs, gov_anchor_exclusive>>

(***************************************************************************)
(* Next State Relation and Full Specification                              *)
(***************************************************************************)

Next ==
    \/ \E a \in Agents, d \in Domains, deps \in (SUBSET Entities) \ {{}}: IssueLease(a, d, deps)
    \/ \E a \in Agents, target \in Entities: ProposeWrite(a, target)
    \/ \E a \in Agents: AcquireGovShared(a)
    \/ \E a \in Agents: AcquireEntityPartition(a)
    \/ \E a \in Agents: AcquireLeaseAndValidate(a)
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
    /\ consent_event_ids \in [Domains -> 0..MaxEpoch]
    /\ policy_epochs \in [Domains -> 0..MaxEpoch]
    /\ leases \in [Agents -> [
           domain : Domains,
           deps   : SUBSET Entities,
           target : Entities,
           v_s    : [Entities -> 0..MaxVersion],
           c_s    : 0..MaxEpoch,
           p_s    : 0..MaxEpoch,
           active : BOOLEAN
       ]]
    /\ gov_anchor_shared \in [Domains -> SUBSET Agents]
    /\ gov_anchor_exclusive \in [Domains -> {"free", "held"}]
    /\ lock_state \in [Entities -> Agents \cup {"none"}]
    /\ lease_lock \in [Agents -> {"free", "held"}]
    /\ locks_held \in [Agents -> SUBSET Entities]
    /\ txn_state \in [Agents -> {"idle", "reading", "proposing", "locking_gov",
                                "locking_entities", "locking_lease", "committing", "aborted"}]
    /\ wait_for \subseteq (Agents \X Agents)

\* Invariant 1: Multi-Entity State Isolation (Causal read-dependency version stability)
GSA_StateIsolation ==
    \A a \in Agents :
        (txn_state[a] = "committing") => (
            \A e \in leases[a].deps : leases[a].v_s[e] = entity_versions[e]
        )

\* Invariant 2: Governance Freshness (Policy & Monotonic Consent stability)
GSA_GovernanceFreshness ==
    \A a \in Agents :
        (txn_state[a] = "committing") => (
            /\ leases[a].c_s = consent_event_ids[leases[a].domain]
            /\ leases[a].p_s = policy_epochs[leases[a].domain]
        )

\* Invariant 3: Phantom-Free Rejection (Concurrent mutations force abort)
GSA_PhantomFree ==
    \A a \in Agents :
        (leases[a].active /\ (
            \/ (\E e \in leases[a].deps : leases[a].v_s[e] /= entity_versions[e])
            \/ leases[a].c_s /= consent_event_ids[leases[a].domain]
            \/ leases[a].p_s /= policy_epochs[leases[a].domain]
        )) => (txn_state[a] /= "committing")

\* Invariant 4: Deadlock Freedom (Acyclic Wait-For Graph)
DeadlockFree ==
    \A a \in Agents : <<a, a>> \notin TransitiveClosure(wait_for)

=============================================================================
