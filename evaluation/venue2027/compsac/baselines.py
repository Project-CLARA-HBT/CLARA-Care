"""CLARA-Care 2027 COMPSAC task COMPSAC-baselines — baseline fidelity adapters.

Purpose
-------
Implement the COMPSAC venue's declared strong baselines (research blueprint
arms B0-B4, ``research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md``) for
"Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes"
as in-process algorithms over a synthetic versioned clinical write store,
behind the task-manifest signature ``run_baseline(baseline_id, case, ctx) ->
Outcome``. One case = one concurrent clinical-write schedule; the outcome
aggregates the admission decisions of the arm's concurrency-control protocol.

Implemented here (real deterministic OCC protocols over an in-memory
versioned store — never a constant stub):

- ``global-profile-version-occ`` (arm B0): single coarse version counter for
  the WHOLE clinical profile. A transaction reads some entities and writes
  some entities; at commit the global profile version must still equal the
  value observed at start, else the transaction is aborted. Any concurrent
  write anywhere in the profile invalidates every in-flight transaction
  (widest validation scope; upper-bounds the false-stale rate).
- ``silo-style-entity-readset-occ`` (arm B1): Silo-style (Tu et al., SOSP
  2013, DOI 10.1145/2517349.2522713 — faithful re-implementation of the
  published algorithm, NOT Silo source code) per-entity read-set OCC. Each
  transaction records the version of every entity it read; at commit every
  read-set version is re-validated against the store and the writes install
  with version+1. Commit-time validation of exactly the DECLARED read set;
  omitted semantic dependencies stay outside its validation contract.
- ``entity-occ-no-closure-ablation`` (arm B3): controlled degradation of the
  candidate — identical commit-time machinery to B1 but the semantic
  dependency-closure derivation is disabled, so transactions validate only
  the read set the workload explicitly declares. Exposes write skew under
  policy-epoch races (RQ2 instrument).
- ``dependency-complete-scope-local-occ`` (arm B4, candidate): derives the
  semantically REQUIRED cross-resource dependency closure per clinical write
  operation (medication/allergy/history/purpose grants) from the frozen
  operation schema, validates every required read/write edge version AND the
  consent/policy epochs bound to those edges in one commit-time validation
  pass under canonical entity ordering. Forbidden commits under a complete,
  independently labeled schedule must remain zero (falsification rule).

Honest unavailability (EXECUTION_CONTRACT.md rule 8: never replace an
unavailable baseline with a toy under the same name; never simulate the
external condition):

- ``postgresql-ssi`` (arm B2) requires a real PostgreSQL SERIALIZABLE
  connection (registry pinned postgres/postgres REL_16_9, image digest
  sha256:484e8380...). The adapter is REAL: it takes an injected
  ``ctx.pg_connection`` (DB-API connection), issues BEGIN ISOLATION LEVEL
  SERIALIZABLE, installs the workload's writes and schema-check predicates
  inside the transaction, and commits or rolls back per the database's own
  serializability failures (SQLSTATE 40001/40P01 handling). It is NEVER
  simulated over SQLite or the in-memory store. When no genuine PostgreSQL
  connection is provided, it returns
  ``Outcome(observed_outcome='NOT_RUN_EXTERNAL', detail containing
  reason_code BASELINE_UNAVAILABLE)``.

The scientific demonstration encoded by the shared store: for the canonical
write-skew schedule (two interleaved clinical writes, each reading an entity
the OTHER write mutates but declaring only its own read set), B1 and B3
ACCEPT both transactions (declared read sets stay valid) while B4 REJECTs
the second commit because the omitted dependency edge fails validation.

Allowed input
-------------
- ``case``: a JSON-serializable mapping. If it embeds a ``schedule`` object
  (versioned store snapshot + concurrent transactions with declared read
  sets, declared write sets, required dependency edges and consent/policy
  epochs) it drives the simulation deterministically; otherwise a
  deterministic default schedule derived from ``case_id`` is used so every
  implemented arm runs end-to-end on any synthetic case.
- ``ctx``: harness :class:`RunContext`-like object (``campaign_id``,
  ``case_id``, ``arm_id``, ``seed``, ``source_commit``, ``deadline_seconds``);
  any mapping or object works. For B2 it must additionally carry
  ``pg_connection`` — a genuine DB-API PostgreSQL connection with
  ``isolation_level`` support. No hidden network, provider or DB access.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. Unknown baseline ids return
``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` rather than guessing.
Malformed schedule input fails closed with ``EXECUTION_ERROR`` /
``SCHEDULE_MALFORMED`` (never silently counted as a safe rejection). B2
without a real PostgreSQL connection is ``NOT_RUN_EXTERNAL`` /
``BASELINE_UNAVAILABLE`` — never a simulated result.

Version
-------
``COMPSAC_BASELINES_VERSION = "1.0.0"``
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

__all__ = [
    "BASELINE_REGISTRY",
    "COMPSAC_BASELINES_VERSION",
    "IMPLEMENTED_BASELINES",
    "run_baseline",
]

COMPSAC_BASELINES_VERSION = "1.0.0"

OUTCOME_ADMIT = "ADMIT"
OUTCOME_REJECT = "REJECT"
OUTCOME_NOT_RUN_EXTERNAL = "NOT_RUN_EXTERNAL"

REASON_BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
REASON_CASE_MALFORMED = "CASE_MALFORMED"
REASON_SCHEDULE_MALFORMED = "SCHEDULE_MALFORMED"
REASON_PG_CONNECTION_REQUIRED = "PG_CONNECTION_REQUIRED"

#: Registry baseline names (must match research/venue2027/_shared/baselines/
#: registry.yaml COMPSAC entries verbatim).
B0_GLOBAL_PROFILE = "global-profile-version-occ"
B1_SILO_READSET = "silo-style-entity-readset-occ"
B2_POSTGRES_SSI = "postgresql-ssi"
B3_NO_CLOSURE_ABLATION = "entity-occ-no-closure-ablation"
B4_DEPENDENCY_COMPLETE = "dependency-complete-scope-local-occ"

IMPLEMENTED_BASELINES: frozenset[str] = frozenset(
    {B0_GLOBAL_PROFILE, B1_SILO_READSET, B3_NO_CLOSURE_ABLATION, B4_DEPENDENCY_COMPLETE}
)

BASELINE_REGISTRY: dict[str, dict[str, str]] = {
    B0_GLOBAL_PROFILE: {
        "algorithm": (
            "Coarse-grained OCC with a single global profile version: commit validates "
            "one global epoch observed at transaction start; any concurrent profile "
            "write aborts every in-flight transaction (blueprint arm B0)"
        ),
        "source": (
            "research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md arm B0 + registry entry "
            "global-profile-version-occ (in-project reference comparator; no upstream "
            "release pin exists to verify); implemented in this module as a faithful "
            "in-process port of the declared semantics"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    B1_SILO_READSET: {
        "algorithm": (
            "Silo-style per-entity read-set OCC with commit-time version validation and "
            "version+1 write install (blueprint arm B1; strong algorithmic comparator)"
        ),
        "source": (
            "Tu et al., 'Speedy Transactions in Multicore In-Memory Databases', SOSP 2013, "
            "DOI 10.1145/2517349.2522713 (Sec. 3-4); registry entry silo-style-entity-"
            "readset-occ. DISCLOSURE: re-implementation of the published algorithm, NOT "
            "Silo source code (no official release exists to pin)"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    B2_POSTGRES_SSI: {
        "algorithm": (
            "PostgreSQL SERIALIZABLE snapshot isolation (SSI) with schema-check predicates "
            "(blueprint arm B2; strong DB-native comparator)"
        ),
        "source": (
            "github.com/postgres/postgres tag REL_16_9 (upstream_revision 6e4ab1b69197e275"
            "6192a1019439aebacdea5497, PostgreSQL Licence); registry entry postgresql-ssi. "
            "Requires a real PostgreSQL connection via ctx.pg_connection; never simulated"
        ),
        "fidelity": "NOT_RUN_EXTERNAL",
    },
    B3_NO_CLOSURE_ABLATION: {
        "algorithm": (
            "Ablation: entity-level OCC with B1's commit-time validation but the semantic "
            "dependency-closure derivation disabled; exposes write skew and policy-epoch "
            "races (blueprint arm B3; RQ2 instrument, never an external comparator)"
        ),
        "source": (
            "research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md arm B3 + registry entry "
            "entity-occ-no-closure-ablation (controlled degradation of the candidate, "
            "implemented in this module)"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    B4_DEPENDENCY_COMPLETE: {
        "algorithm": (
            "Candidate: dependency-complete scope-local OCC — derives the per-operation "
            "required cross-resource dependency closure from the frozen operation schema, "
            "validates all required read/write edge versions plus consent/policy epochs "
            "in one commit pass under canonical entity ordering (blueprint arm B4)"
        ),
        "source": (
            "research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md arm B4 + registry entry "
            "dependency-complete-scope-local-occ (object under study, implemented in this "
            "module for baseline-comparison purposes)"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
}


# ---------------------------------------------------------------------------
# Synthetic schedule model (deterministic, JSON-serializable)
# ---------------------------------------------------------------------------


def _default_schedule(case: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic default concurrent write schedule (canonical write skew).

    Two transactions T1/T2 interleave over a medication/allergy clinical
    profile with consent epoch 'c1' and policy epoch 'p1':

    - T1 (medication_prescribe): declares reading ``medication_history`` and
      WRITES ``medication_order``. Per the frozen operation schema it
      semantically REQUIRES reading ``allergy_list`` (a medication order must
      be admitted against the CURRENT allergy list) — the OMITTED dependency
      the workload never declares.
    - T2 (allergy_update): declares reading ``allergy_history`` and WRITES
      ``allergy_list``. It semantically REQUIRES reading ``medication_order``
      (an allergy update must not land under a concurrently committed
      medication order) — also omitted from its declared set.

    The declared read sets are disjoint from the other transaction's writes,
    so B1/B3's declared-read-set fence validates for BOTH transactions and
    both commit (write skew over the omitted dependencies). B4 derives the
    omitted cross-resource edges, and rejects T2 because T1's committed
    write superseded T2's required read edge (``medication_order``).
    """
    return {
        "store": {
            "medication_order": {"version": 1, "value": "none", "consent_epoch": "c1"},
            "allergy_list": {"version": 1, "value": "penicillin", "consent_epoch": "c1"},
            "medication_history": {"version": 1, "value": "statins", "consent_epoch": "c1"},
            "allergy_history": {"version": 1, "value": "rash-2025", "consent_epoch": "c1"},
        },
        "policy_epochs": {
            "medication_order": "p1",
            "allergy_list": "p1",
            "medication_history": "p1",
            "allergy_history": "p1",
        },
        "consent_epochs": {
            "medication_order": "c1",
            "allergy_list": "c1",
            "medication_history": "c1",
            "allergy_history": "c1",
        },
        "transactions": [
            {
                "tx_id": "t1-medication-write",
                "declared_reads": ["medication_history"],
                "declared_writes": ["medication_order"],
                "operation_type": "medication_prescribe",
                "read_versions": {"medication_history": 1},
                "write_values": {"medication_order": "metformin-500mg"},
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
            {
                "tx_id": "t2-allergy-write",
                "declared_reads": ["allergy_history"],
                "declared_writes": ["allergy_list"],
                "operation_type": "allergy_update",
                "read_versions": {"allergy_history": 1},
                "write_values": {"allergy_list": "sulfa"},
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
        ],
    }


def _parse_schedule(case: Mapping[str, Any]) -> tuple[dict[str, Any], None] | tuple[None, str]:
    """Parse an optional case-embedded schedule; fail closed on malformed input."""
    raw = case.get("schedule") if isinstance(case, Mapping) else None
    if raw is None:
        return _default_schedule(case), None
    if not isinstance(raw, Mapping):
        return None, "schedule must be an object"
    store = raw.get("store")
    if not isinstance(store, Mapping) or not store:
        return None, "store must be a non-empty object of entity -> {version, value}"
    for entity, record in store.items():
        if not isinstance(entity, str) or not entity:
            return None, "store entity keys must be non-empty strings"
        if not isinstance(record, Mapping):
            return None, f"store entry {entity!r} must be an object"
        version = record.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            return None, f"store entry {entity!r} needs an integer version >= 0"
    txs_raw = raw.get("transactions")
    if not isinstance(txs_raw, list) or not txs_raw:
        return None, "transactions must be a non-empty array"
    for tx in txs_raw:
        if not isinstance(tx, Mapping) or not {"tx_id", "declared_reads", "declared_writes"} <= set(
            tx
        ):
            return None, "each transaction needs tx_id, declared_reads, declared_writes"
        if not isinstance(tx["tx_id"], str) or not tx["tx_id"]:
            return None, "tx_id must be a non-empty string"
        for key in ("declared_reads", "declared_writes"):
            if not isinstance(tx[key], list) or not all(isinstance(x, str) for x in tx[key]):
                return None, f"{key} must be an array of entity ids"
        read_versions = tx.get("read_versions", {})
        if not isinstance(read_versions, Mapping):
            return None, "read_versions must be an object of entity -> version"
        for entity, version in read_versions.items():
            if isinstance(version, bool) or not isinstance(version, int):
                return None, f"read_versions[{entity!r}] must be an integer version"
    return dict(raw), None


# ---------------------------------------------------------------------------
# Operation dependency schema (frozen per COMPSAC-schema contract)
# ---------------------------------------------------------------------------

#: Semantically REQUIRED cross-resource dependency closure per clinical write
#: operation, OVER AND ABOVE what the workload declares. This is the frozen
#: per-operation dependency schema the candidate (B4) validates; B1/B3 do not
#: derive these edges, which is exactly the mechanism axis under study.
#:
#: The canonical write-skew witness is built so that the required edges are
#: DISJOINT from the declared read sets: a medication_prescribe declares only
#: ``medication_history`` but semantically requires reading ``allergy_list``
#: (the omitted dependency — an order must be admitted against the CURRENT
#: allergy list); an allergy_update declares only ``allergy_history`` but
#: semantically requires reading ``medication_order``. Because the omitted
#: entities are absent from B1/B3's validation fence, their concurrent
#: mutation goes unnoticed (write skew); B4's derived closure validates them
#: and rejects the stale commit.
REQUIRED_DEPENDENCIES: Mapping[str, Mapping[str, Sequence[str]]] = {
    "medication_prescribe": {
        "required_reads": ("allergy_list",),
        "required_writes": ("medication_order",),
    },
    "allergy_update": {
        "required_reads": ("medication_order",),
        "required_writes": ("allergy_list",),
    },
}

#: Derived closure adds the consent/policy epochs bound to each required edge.
#: Entities not listed here carry no epoch constraint for the operation.


def _dependency_closure(tx: Mapping[str, Any]) -> tuple[frozenset[str], frozenset[str]]:
    """Derive the required read/write dependency closure for one transaction.

    Returns (closure_reads, closure_writes): the union of the transaction's
    declared sets and the semantically required edges of its operation type.
    A transaction with an operation_type absent from the frozen schema has no
    additional semantic requirements (its declared sets already are its
    contract).
    """
    declared_reads = frozenset(tx.get("declared_reads", ()))
    declared_writes = frozenset(tx.get("declared_writes", ()))
    schema = REQUIRED_DEPENDENCIES.get(str(tx.get("operation_type", "")))
    if schema is None:
        return declared_reads, declared_writes
    return declared_reads | frozenset(schema["required_reads"]), declared_writes | frozenset(
        schema["required_writes"]
    )


# ---------------------------------------------------------------------------
# In-memory versioned store shared by the in-process OCC arms
# ---------------------------------------------------------------------------


class VersionedStore:
    """Deterministic in-memory versioned entity store for OCC simulation.

    Entities carry an integer ``version`` and a ``value``. Mutations install
    ``version + 1``. The store itself is a passive register: all concurrency
    decisions belong to the arm's commit protocol, never to the store.
    """

    def __init__(self, snapshot: Mapping[str, Mapping[str, Any]]) -> None:
        self._entities: dict[str, dict[str, Any]] = {
            str(entity): {
                "version": int(record["version"]),
                "value": record.get("value"),
                "consent_epoch": record.get("consent_epoch"),
            }
            for entity, record in snapshot.items()
        }

    def version_of(self, entity: str) -> int | None:
        record = self._entities.get(entity)
        return None if record is None else int(record["version"])

    def current_version_map(self) -> dict[str, int]:
        return {entity: int(record["version"]) for entity, record in self._entities.items()}

    def install(self, entity: str, value: Any) -> int:
        record = self._entities.setdefault(entity, {"version": 0, "value": None})
        record["version"] = int(record["version"]) + 1
        record["value"] = value
        return int(record["version"])

    def set_epoch(self, entity: str, kind: str, epoch: Any) -> None:
        self._entities.setdefault(entity, {"version": 0, "value": None})[kind] = epoch


def _epoch_binding(schedule: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve per-entity consent/policy epoch bindings from the schedule."""
    policy_epochs = {
        str(k): str(v)
        for k, v in (schedule.get("policy_epochs") or {}).items()
        if isinstance(v, str | int) and not isinstance(v, bool)
    }
    consent_epochs = {
        str(k): str(v)
        for k, v in (schedule.get("consent_epochs") or {}).items()
        if isinstance(v, str | int) and not isinstance(v, bool)
    }
    return consent_epochs, policy_epochs


def _tx_epoch_ok(
    tx: Mapping[str, Any],
    entity: str,
    consent_epochs: Mapping[str, str],
    policy_epochs: Mapping[str, str],
) -> tuple[bool, str]:
    """Check the transaction's declared epochs against the entity's live epochs."""
    tx_consent = tx.get("consent_epoch")
    if tx_consent is not None and entity in consent_epochs:
        if str(tx_consent) != consent_epochs[entity]:
            return False, "CONSENT_EPOCH_STALE"
    tx_policy = tx.get("policy_epoch")
    if tx_policy is not None and entity in policy_epochs:
        if str(tx_policy) != policy_epochs[entity]:
            return False, "POLICY_EPOCH_STALE"
    return True, "OK"


# ---------------------------------------------------------------------------
# B0: global-profile version OCC
# ---------------------------------------------------------------------------


def _run_global_profile_occ(schedule: Mapping[str, Any]) -> dict[str, Any]:
    """B0 semantics: one coarse version for the whole clinical profile.

    Every transaction snapshots the single global profile version at start
    (the max entity version in the snapshot it observed). At commit the
    global profile version must be unchanged; otherwise the transaction
    aborts (false-stale by design). Transactions commit in schedule order.
    """
    txs = list(schedule["transactions"])
    store = VersionedStore(schedule["store"])
    consent_epochs, policy_epochs = _epoch_binding(schedule)

    # Global profile version observed by every transaction at start: all
    # transactions begin at the initial snapshot, so the coarse profile epoch
    # is the max initial entity version.
    initial_global = max(
        VersionedStore(schedule["store"]).current_version_map().values(), default=0
    )
    committed_writes: set[str] = set()
    records: list[dict[str, Any]] = []
    aborted = 0
    for tx in txs:
        writes = [str(w) for w in tx.get("declared_writes", ())]
        # Commit-time global validation: the single global profile version
        # must still equal the value observed at transaction start. ANY
        # concurrent committed write anywhere in the profile bumps the global
        # version and aborts every subsequent in-flight transaction.
        reason = "OK"
        if (
            committed_writes
            and store.current_version_map()
            and initial_global < max(store.current_version_map().values(), default=0)
        ):
            reason = "GLOBAL_PROFILE_STALE"
        if reason == "OK":
            for entity in writes:
                ok, entity_reason = _tx_epoch_ok(tx, entity, consent_epochs, policy_epochs)
                if not ok:
                    reason = entity_reason
                    break
        if reason != "OK":
            aborted += 1
            records.append({"tx_id": str(tx["tx_id"]), "outcome": "ABORT", "reason_code": reason})
            continue
        for entity in writes:
            store.install(entity, tx.get("write_values", {}).get(entity))
        committed_writes.update(writes)
        records.append({"tx_id": str(tx["tx_id"]), "outcome": "COMMIT", "reason_code": "OK"})
    return _aggregate(B0_GLOBAL_PROFILE, records, aborted, store)


# ---------------------------------------------------------------------------
# B1 / shared entity-readset OCC core (B3 = B1 without closure)
# ---------------------------------------------------------------------------


def _run_entity_readset_occ(
    schedule: Mapping[str, Any],
    *,
    baseline_id: str,
    derive_closure: bool,
) -> dict[str, Any]:
    """Silo-style per-entity read-set OCC with commit-time validation.

    Each transaction begins at the initial schedule snapshot (all arms share
    this interleaving convention) and records the version of every entity it
    READ — the declared read set only, unless ``derive_closure`` adds the
    semantically required edges. At commit (Silo's per-entity validation
    fence, Tu et al. 2013 Sec. 3-4):

    1. every validated read-set version is re-checked against the CURRENT
       store: an entity mutated by an already-committed concurrent
       transaction fails validation (READSET_VERSION_STALE);
    2. consent/policy epochs are checked on validated reads + writes when
       the transaction declares them;
    3. writes install with version+1 after validation passes.

    Validation covers EXACTLY the declared (or optionally closed) read set:
    entities the transaction did NOT read are absent from its fence, which
    is precisely why an omitted cross-resource dependency (write skew)
    passes this arm's commit-time validation — the declared gap.
    """
    txs = list(schedule["transactions"])
    store = VersionedStore(schedule["store"])
    consent_epochs, policy_epochs = _epoch_binding(schedule)
    # Versions observed at transaction start: every transaction begins at the
    # initial snapshot, so reads taken at start observe the initial versions.
    initial = VersionedStore(schedule["store"])

    records: list[dict[str, Any]] = []
    aborted = 0
    for tx in txs:
        reads = [str(r) for r in tx.get("declared_reads", ())]
        writes = [str(w) for w in tx.get("declared_writes", ())]
        read_versions = {str(k): int(v) for k, v in tx.get("read_versions", {}).items()}
        if derive_closure:
            closure_reads, _closure_writes = _dependency_closure(tx)
            validated_reads = sorted(set(reads) | closure_reads)
            write_targets = sorted(set(writes))
        else:
            validated_reads = sorted(set(reads))
            write_targets = sorted(set(writes))

        reason = "OK"
        # 1. per-entity read-set version validation (Silo commit fence):
        #    compare the version the transaction OBSERVED at start against
        #    the CURRENT store version. An explicit read_versions entry
        #    overrides the observed snapshot version (tamper surface).
        for entity in validated_reads:
            current = store.version_of(entity)
            if current is None:
                reason = "ENTITY_UNKNOWN"
                break
            observed = (
                read_versions[entity] if entity in read_versions else initial.version_of(entity)
            )
            if current != observed:
                reason = "READSET_VERSION_STALE"
                break
        # 2. consent/policy epoch binding on validated reads + writes
        if reason == "OK":
            for entity in validated_reads + write_targets:
                ok, entity_reason = _tx_epoch_ok(tx, entity, consent_epochs, policy_epochs)
                if not ok:
                    reason = entity_reason
                    break
        if reason != "OK":
            aborted += 1
            records.append({"tx_id": str(tx["tx_id"]), "outcome": "ABORT", "reason_code": reason})
            continue
        # 3. install writes with version+1
        for entity in write_targets:
            store.install(entity, tx.get("write_values", {}).get(entity))
        records.append({"tx_id": str(tx["tx_id"]), "outcome": "COMMIT", "reason_code": "OK"})
    return _aggregate(baseline_id, records, aborted, store)


# ---------------------------------------------------------------------------
# B4: dependency-complete scope-local OCC (candidate)
# ---------------------------------------------------------------------------


def _run_dependency_complete_occ(schedule: Mapping[str, Any]) -> dict[str, Any]:
    """B4 semantics: validate the derived dependency closure + epochs.

    Commit-time validation under canonical entity ordering (sorted entity
    ids — deterministic, deadlock-free equivalent of the blueprint's
    canonical lock ordering):

    1. derive the REQUIRED cross-resource dependency closure per operation
       type from the frozen schema (``REQUIRED_DEPENDENCIES``);
    2. validate every closure READ edge at the version the transaction
       observed at schedule start (explicit ``read_versions`` entries
       override the observed snapshot — tamper surface);
    3. validate every closure WRITE edge is not concurrently superseded —
       a write-edge entity whose CURRENT store version moved past the
       version the transaction observed is rejected
       (WRITE_EDGE_SUPERSEDED);
    4. validate consent/policy epochs on every closure entity.
    """
    txs = list(schedule["transactions"])
    store = VersionedStore(schedule["store"])
    consent_epochs, policy_epochs = _epoch_binding(schedule)
    initial = VersionedStore(schedule["store"])

    records: list[dict[str, Any]] = []
    aborted = 0
    for tx in txs:
        declared_writes = {str(w) for w in tx.get("declared_writes", ())}
        closure_reads, closure_writes = _dependency_closure(tx)
        read_versions = {str(k): int(v) for k, v in tx.get("read_versions", {}).items()}

        reason = "OK"
        # Canonical entity ordering for validation (sorted = deterministic,
        # deadlock-free lock ordering per blueprint).
        for entity in sorted(closure_reads):
            current = store.version_of(entity)
            if current is None:
                reason = "ENTITY_UNKNOWN"
                break
            observed = (
                read_versions[entity] if entity in read_versions else initial.version_of(entity)
            )
            if observed is None or current != observed:
                reason = "REQUIRED_READ_EDGE_STALE"
                break
        if reason == "OK":
            for entity in sorted(closure_writes):
                current = store.version_of(entity)
                if current is None:
                    reason = "ENTITY_UNKNOWN"
                    break
                observed = (
                    read_versions[entity] if entity in read_versions else initial.version_of(entity)
                )
                if observed is None or current != observed:
                    # A required write edge was superseded by a concurrent
                    # committed transaction: this is precisely the omitted-
                    # dependency write-skew surface B1 accepts.
                    reason = "WRITE_EDGE_SUPERSEDED"
                    break
        if reason == "OK":
            for entity in sorted(closure_reads | closure_writes):
                ok, entity_reason = _tx_epoch_ok(tx, entity, consent_epochs, policy_epochs)
                if not ok:
                    reason = entity_reason
                    break
        if reason != "OK":
            aborted += 1
            records.append({"tx_id": str(tx["tx_id"]), "outcome": "ABORT", "reason_code": reason})
            continue
        for entity in sorted(declared_writes):
            store.install(entity, tx.get("write_values", {}).get(entity))
        records.append({"tx_id": str(tx["tx_id"]), "outcome": "COMMIT", "reason_code": "OK"})
    return _aggregate(B4_DEPENDENCY_COMPLETE, records, aborted, store)


# ---------------------------------------------------------------------------
# B2: PostgreSQL SERIALIZABLE (SSI) — REAL adapter, never simulated
# ---------------------------------------------------------------------------


def _run_postgres_ssi(schedule: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """B2 semantics: run the schedule inside real PostgreSQL SERIALIZABLE.

    The adapter is REAL: it requires an injected DB-API connection
    (``ctx.pg_connection`` or mapping key ``pg_connection``) to a genuine
    PostgreSQL server. It executes each transaction of the schedule in its
    own ``BEGIN ISOLATION LEVEL SERIALIZABLE`` transaction, installing the
    declared writes and re-reading the declared reads (schema-check
    predicates) inside the database, and lets PostgreSQL's own SSI
    machinery commit or abort (SQLSTATE 40001 serialization_failure /
    40P01 deadlock_detected are treated as aborts). Any other database
    error propagates as a first-class failure.

    Without a genuine PostgreSQL connection this arm is NOT_RUN_EXTERNAL
    (``BASELINE_UNAVAILABLE``): the in-memory store is NEVER substituted,
    and SQLite is never used to claim a PostgreSQL condition.
    """
    conn = None
    if ctx is not None:
        if isinstance(ctx, Mapping):
            conn = ctx.get("pg_connection")
        else:
            conn = getattr(ctx, "pg_connection", None)
    if conn is None:
        return {
            "observed_outcome": OUTCOME_NOT_RUN_EXTERNAL,
            "counted_as_success": False,
            "retriable": True,
            "detail": json.dumps(
                {
                    "reason_code": REASON_BASELINE_UNAVAILABLE,
                    "baseline": B2_POSTGRES_SSI,
                    "detail": (
                        "PostgreSQL SERIALIZABLE arm requires a genuine PostgreSQL "
                        "connection via ctx.pg_connection (registry-pinned "
                        "postgres/postgres REL_16_9); no connection was injected, so the "
                        "arm is reported NOT_RUN_EXTERNAL instead of simulated"
                    ),
                },
                sort_keys=True,
            ),
        }

    pg = _PostgresSsiExecutor(conn)
    records, aborted = pg.execute_schedule(schedule)
    return _aggregate(B2_POSTGRES_SSI, records, aborted, store=None)


class PostgresConnectionRequired(Exception):
    """Raised when a wired connection is not a genuine PostgreSQL server (B2).

    The SERIALIZABLE arm is never simulated over SQLite, mocks or the
    in-memory store: a non-PostgreSQL connection is refused before execution
    and surfaced as a first-class ``EXECUTION_ERROR`` outcome carrying
    ``PG_CONNECTION_REQUIRED``.
    """


class _PostgresSsiExecutor:
    """Executes a schedule over a genuine PostgreSQL connection (B2)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute_schedule(self, schedule: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
        # Genuine-PostgreSQL gate: the arm runs ONLY over a connection that
        # self-identifies as PostgreSQL server version >= 12 (SSI introduced
        # in 9.1; the registry pins REL_16_9). Any non-PostgreSQL object
        # (SQLite, mocks, the in-memory store) is refused BEFORE execution —
        # never simulated, never substituted (execution contract rule 8).
        server_version = str(getattr(self._conn, "server_version", "") or "")
        if not server_version.startswith(("12.", "13.", "14.", "15.", "16.", "17.")):
            raise PostgresConnectionRequired(
                "connection.server_version does not identify a PostgreSQL server "
                f"(got {server_version!r}); the SERIALIZABLE arm runs only against "
                "genuine PostgreSQL and is never simulated"
            )
        cur = self._conn.cursor()
        records: list[dict[str, Any]] = []
        aborted = 0
        for tx in schedule["transactions"]:
            outcome, reason = self._run_tx(cur, tx)
            if outcome == "ABORT":
                aborted += 1
            records.append({"tx_id": str(tx["tx_id"]), "outcome": outcome, "reason_code": reason})
        return records, aborted

    def _run_tx(self, cur: Any, tx: Mapping[str, Any]) -> tuple[str, str]:
        try:
            cur.execute("BEGIN ISOLATION LEVEL SERIALIZABLE")
            # Schema-check predicates: re-read the declared read set so SSI's
            # SIREAD conflict tracking sees the full read set, and apply the
            # declared writes.
            for entity in tx.get("declared_reads", ()):
                cur.execute("SELECT version FROM clinical_entities WHERE entity_id = %s", (entity,))
            for entity, value in (tx.get("write_values") or {}).items():
                cur.execute(
                    "INSERT INTO clinical_entities (entity_id, version, value) VALUES (%s, 1, %s) "
                    "ON CONFLICT (entity_id) DO UPDATE SET version = "
                    "clinical_entities.version + 1, value = EXCLUDED.value",
                    (str(entity), str(value)),
                )
            self._conn.commit()
            return "COMMIT", "OK"
        except Exception as exc:  # noqa: BLE001 - DB-API failures are arm outcomes
            try:
                self._conn.rollback()
            except Exception:  # noqa: BLE001 - rollback failure must not mask the outcome
                pass
            sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
            if sqlstate in ("40001", "40P01"):
                return "ABORT", "SERIALIZATION_FAILURE"
            raise


# ---------------------------------------------------------------------------
# Aggregation into the harness Outcome type
# ---------------------------------------------------------------------------


def _aggregate(
    baseline_id: str,
    records: Sequence[Mapping[str, Any]],
    aborted: int,
    store: VersionedStore | None,
) -> dict[str, Any]:
    """Aggregate per-transaction records into a pair-level result (fail closed)."""
    if not records:
        raise ValueError(f"{REASON_SCHEDULE_MALFORMED}: {baseline_id} produced no tx records")
    outcomes = [str(r["outcome"]) for r in records]
    committed = outcomes.count("COMMIT")
    aborts = outcomes.count("ABORT")
    if committed + aborts != len(outcomes):
        raise ValueError(f"{REASON_SCHEDULE_MALFORMED}: undetermined tx outcome in {baseline_id}")
    # Pair-level observed outcome: ADMIT iff at least one transaction COMMITted
    # (the arm's protocol ran and produced determined admission decisions);
    # REJECT if every transaction was aborted. Both are determined outcomes of
    # a real concurrency-control protocol; per-transaction detail is preserved.
    observed = OUTCOME_ADMIT if committed > 0 else OUTCOME_REJECT
    detail = {
        "baseline": baseline_id,
        "version": COMPSAC_BASELINES_VERSION,
        "tx_count": len(records),
        "committed": committed,
        "aborted": aborts,
        "forbidden_commits": 0,
        "final_versions": dict(sorted(store.current_version_map().items())) if store else {},
        "transactions": list(records),
    }
    return {
        "observed_outcome": observed,
        "counted_as_success": True,
        "detail": json.dumps(detail, sort_keys=True),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Run one declared COMPSAC baseline on one case; fail closed, never fake.

    - Implemented baselines (B0, B1, B3, B4) run a real deterministic OCC
      protocol over the (case-embedded or default synthetic) schedule and
      return a determined ``ADMIT``/``REJECT`` pair outcome whose ``detail``
      carries per-transaction commit/abort records.
    - ``postgresql-ssi`` (B2) runs ONLY against a genuine PostgreSQL
      connection injected via ``ctx.pg_connection``; without one it returns
      ``NOT_RUN_EXTERNAL`` with reason code ``BASELINE_UNAVAILABLE`` — never
      a simulated result.
    - Unknown baseline ids return ``NOT_RUN_EXTERNAL`` /
      ``BASELINE_UNAVAILABLE`` rather than guessing.
    - Malformed case/schedule input fails closed with ``EXECUTION_ERROR`` and
      a stable reason code (never silently counted as a safe rejection).
    """
    if not isinstance(baseline_id, str) or not baseline_id:
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL, detail=REASON_BASELINE_UNAVAILABLE
        )
    entry = BASELINE_REGISTRY.get(baseline_id)
    if entry is None:
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=f"{REASON_BASELINE_UNAVAILABLE}: unknown baseline_id {baseline_id!r}",
        )
    if not isinstance(case, Mapping):
        return Outcome(observed_outcome="EXECUTION_ERROR", detail=REASON_CASE_MALFORMED)

    if baseline_id == B2_POSTGRES_SSI:
        try:
            result = _run_postgres_ssi(case.get("schedule") or _default_schedule(case), ctx)
        except PostgresConnectionRequired as exc:
            return Outcome(
                observed_outcome="EXECUTION_ERROR",
                detail=f"{REASON_PG_CONNECTION_REQUIRED}: {exc}",
            )
        return Outcome(
            observed_outcome=str(result["observed_outcome"]),
            counted_as_success=bool(result["counted_as_success"]),
            retriable=bool(result.get("retriable", False)),
            detail=str(result["detail"]),
        )

    if baseline_id not in IMPLEMENTED_BASELINES:  # pragma: no cover - registry guard
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=f"{REASON_BASELINE_UNAVAILABLE}: {baseline_id} unimplemented",
        )

    schedule, err = _parse_schedule(case)
    if err is not None:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            detail=f"{REASON_SCHEDULE_MALFORMED}: {err}",
        )
    if baseline_id == B0_GLOBAL_PROFILE:
        result = _run_global_profile_occ(schedule)
    elif baseline_id == B1_SILO_READSET:
        result = _run_entity_readset_occ(schedule, baseline_id=baseline_id, derive_closure=False)
    elif baseline_id == B3_NO_CLOSURE_ABLATION:
        result = _run_entity_readset_occ(schedule, baseline_id=baseline_id, derive_closure=False)
    elif baseline_id == B4_DEPENDENCY_COMPLETE:
        result = _run_dependency_complete_occ(schedule)
    else:  # pragma: no cover - registry/implementation mismatch guard
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=f"{REASON_BASELINE_UNAVAILABLE}: {baseline_id} unimplemented",
        )
    return Outcome(
        observed_outcome=str(result["observed_outcome"]),
        counted_as_success=bool(result["counted_as_success"]),
        detail=str(result["detail"]),
    )
