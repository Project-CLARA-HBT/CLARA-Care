"""COMPSAC-X05_silo_occ — Silo-style entity read-set OCC comparator entry point.

Purpose
-------
Expose the REAL B1 strong algorithmic comparator (registry arm
``silo-style-entity-readset-occ``, blueprint arm B1) behind the task-manifest
signature ``execute_occ(op, store) -> Outcome``. The OCC protocol is NOT
re-implemented here: this module is a thin additive adapter over the already
verified B1 engine in ``evaluation/venue2027/compsac/baselines.py``, dispatched
through its public ``run_baseline`` entry point (registry fidelity
``FAITHFUL_PORT``). The adapter never substitutes, simulates or weakens the
baseline (EXECUTION_CONTRACT rule 8).

DISCLOSURE (task contract): the comparator is a faithful PORT of the published
Silo algorithm — Tu et al., "Speedy Transactions in Multicore In-Memory
Databases", SOSP 2013, DOI 10.1145/2517349.2522713, Sec. 3-4 — NOT Silo source
code; no official Silo release exists to pin. The same disclosure is recorded
in ``BASELINE_REGISTRY[B1_SILO_READSET]`` and in
``research/venue2027/compsac/tasks/silo_occ_impl.md``.

Algorithm (exactly the B1 commit fence, per the published Silo design)
----------------------------------------------------------------------
1. the operation records the version of every entity it READ (declared read
   set only; Silo validates reads and installs writes after validation);
2. at commit, every read-set version is re-validated against the CURRENT
   store: an entity mutated by an already-committed concurrent operation
   fails the fence (``READSET_VERSION_STALE``) and the operation is
   INVALIDATED — its writes are never installed (no partial install);
3. consent/policy epochs bound to the validated entities are checked when the
   operation declares epochs (``CONSENT_EPOCH_STALE`` / ``POLICY_EPOCH_STALE``);
4. on success, writes install with ``version + 1``.

Guarantee: commit-time validation of EXACTLY the declared read set — a
committed operation's declared reads were never mutated between observation
and commit. Semantic dependencies the workload fails to declare are OUTSIDE
the fence: the omitted-dependency write-skew window this arm deliberately
admits and the candidate arm B4 (dependency-complete scope-local OCC) rejects.
That differential is the RQ2 scientific contrast, asserted with real abort
counts in ``research/venue2027/compsac/tests/test_x05_silo_occ.py``.

Allowed input
-------------
- ``op``: JSON-serializable mapping (``tx_id`` non-empty string;
  ``declared_reads`` / ``declared_writes`` sequences of entity-id strings;
  ``read_versions`` mapping entity -> integer version observed at operation
  start; ``write_values`` mapping entity -> value; optional ``operation_type``,
  ``consent_epoch``, ``policy_epoch``) or a :class:`SiloOperation` instance.
  Unknown keys are refused (fail closed, never silently dropped).
- ``store``: JSON-serializable snapshot mapping entity -> record with an
  integer ``version`` >= 0, optional ``value`` and optional live
  ``consent_epoch`` / ``policy_epoch`` epoch bindings. The snapshot is the
  CURRENT store at commit time; ``read_versions`` carry what the operation
  observed when it started — staleness is exactly their divergence.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes: ``OP_MALFORMED``,
``STORE_MALFORMED`` (returned as ``EXECUTION_ERROR`` outcomes, never silently
counted as safe rejections or successes). The B1 engine's own reason codes
(``READSET_VERSION_STALE``, ``ENTITY_UNKNOWN``, ``CONSENT_EPOCH_STALE``,
``POLICY_EPOCH_STALE``, ``SCHEDULE_MALFORMED``) pass through unchanged.

Version
-------
``SILO_READSET_PORT_VERSION = "1.0.0"`` — additive-only over
``COMPSAC_BASELINES_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.compsac import baselines as bl

__all__ = [
    "PORT_DISCLOSURE",
    "RC_OP_MALFORMED",
    "RC_STORE_MALFORMED",
    "SILO_READSET_PORT_VERSION",
    "SiloOperation",
    "execute_occ",
]

SILO_READSET_PORT_VERSION = "1.0.0"

#: Faithful-port disclosure (task contract; mirrors the B1 registry entry).
PORT_DISCLOSURE = (
    "Faithful re-implementation of the published Silo algorithm (Tu et al., "
    "'Speedy Transactions in Multicore In-Memory Databases', SOSP 2013, "
    "DOI 10.1145/2517349.2522713, Sec. 3-4); NOT Silo source code — no official "
    "Silo release exists to pin. Executed through the real B1 baseline adapter "
    "run_baseline('silo-style-entity-readset-occ', ...) (registry fidelity "
    "FAITHFUL_PORT); never simulated."
)

RC_OP_MALFORMED = "OP_MALFORMED"
RC_STORE_MALFORMED = "STORE_MALFORMED"

_ALLOWED_OP_KEYS = frozenset(
    {
        "tx_id",
        "declared_reads",
        "declared_writes",
        "read_versions",
        "write_values",
        "operation_type",
        "consent_epoch",
        "policy_epoch",
    }
)


@dataclasses.dataclass(frozen=True)
class SiloOperation:
    """One clinical write operation under the Silo-style read-set fence.

    JSON-serializable via :meth:`to_dict` (the engine's transaction mapping
    shape). ``read_versions`` are the entity versions the operation OBSERVED at
    start; the commit fence re-validates them against the CURRENT store.
    """

    tx_id: str
    declared_reads: tuple[str, ...] = ()
    declared_writes: tuple[str, ...] = ()
    read_versions: Mapping[str, int] = dataclasses.field(default_factory=dict)
    write_values: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    operation_type: str = ""
    consent_epoch: str | None = None
    policy_epoch: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view in the engine's transaction mapping shape."""
        return {
            "tx_id": self.tx_id,
            "declared_reads": list(self.declared_reads),
            "declared_writes": list(self.declared_writes),
            "read_versions": dict(self.read_versions),
            "write_values": dict(self.write_values),
            "operation_type": self.operation_type,
            "consent_epoch": self.consent_epoch,
            "policy_epoch": self.policy_epoch,
        }


def _coerce_op(op: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize one operation to the engine's transaction shape; fail closed."""
    if isinstance(op, SiloOperation):
        raw = op.to_dict()
    elif isinstance(op, Mapping):
        raw = dict(op)
    else:
        return None, "op must be a mapping or SiloOperation"
    unknown = sorted(set(raw) - _ALLOWED_OP_KEYS)
    if unknown:
        return None, f"unknown op keys: {unknown}"
    tx_id = raw.get("tx_id")
    if not isinstance(tx_id, str) or not tx_id:
        return None, "tx_id must be a non-empty string"
    for key in ("declared_reads", "declared_writes"):
        value = raw.get(key, [])
        if isinstance(value, str) or not isinstance(value, list | tuple):
            return None, f"{key} must be a sequence of entity ids"
        if not all(isinstance(x, str) for x in value):
            return None, f"{key} must be a sequence of entity ids"
        raw[key] = list(value)
    read_versions = raw.get("read_versions", {})
    if not isinstance(read_versions, Mapping):
        return None, "read_versions must be a mapping of entity -> version"
    for entity, version in read_versions.items():
        if not isinstance(entity, str) or not entity:
            return None, "read_versions keys must be non-empty entity ids"
        if isinstance(version, bool) or not isinstance(version, int):
            return None, f"read_versions[{entity!r}] must be an integer version"
    raw["read_versions"] = {str(k): int(v) for k, v in read_versions.items()}
    write_values = raw.get("write_values", {})
    if not isinstance(write_values, Mapping):
        return None, "write_values must be a mapping of entity -> value"
    raw["write_values"] = dict(write_values)
    operation_type = raw.get("operation_type", "")
    if not isinstance(operation_type, str):
        return None, "operation_type must be a string"
    raw["operation_type"] = operation_type
    for key in ("consent_epoch", "policy_epoch"):
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            return None, f"{key} must be a string epoch id or None"
    return raw, None


def _coerce_store(store: Any) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    """Validate one store snapshot (entity -> {version, value, epochs})."""
    if not isinstance(store, Mapping) or not store:
        return None, "store must be a non-empty mapping of entity -> record"
    snapshot: dict[str, dict[str, Any]] = {}
    for entity, record in store.items():
        if not isinstance(entity, str) or not entity:
            return None, "store entity keys must be non-empty strings"
        if not isinstance(record, Mapping):
            return None, f"store entry {entity!r} must be a mapping"
        version = record.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            return None, f"store entry {entity!r} needs an integer version >= 0"
        snapshot[entity] = dict(record)
    return snapshot, None


def _epoch_bindings_from_store(
    snapshot: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve live consent/policy epoch bindings from the store records."""
    consent: dict[str, str] = {}
    policy: dict[str, str] = {}
    for entity, record in snapshot.items():
        for kind, target in (("consent_epoch", consent), ("policy_epoch", policy)):
            value = record.get(kind)
            if isinstance(value, str | int) and not isinstance(value, bool):
                target[entity] = str(value)
    return consent, policy


def execute_occ(op: Mapping[str, Any] | SiloOperation, store: Mapping[str, Any]) -> Outcome:
    """Run ONE clinical write operation through the REAL B1 read-set fence.

    Commit-time semantics (Silo, Tu et al. 2013 Sec. 3-4, via the real B1
    engine): every declared-read version is re-validated against the current
    ``store``; a stale read set aborts the operation with
    ``READSET_VERSION_STALE`` and its writes are never installed; a valid
    fence installs the declared writes with ``version + 1``. Validation covers
    EXACTLY the declared read set — omitted semantic dependencies are outside
    the fence (the write-skew window B4 closes and this comparator admits).
    """
    op_dict, op_err = _coerce_op(op)
    if op_err is not None:
        return Outcome(observed_outcome="EXECUTION_ERROR", detail=f"{RC_OP_MALFORMED}: {op_err}")
    snapshot, store_err = _coerce_store(store)
    if store_err is not None:
        return Outcome(
            observed_outcome="EXECUTION_ERROR", detail=f"{RC_STORE_MALFORMED}: {store_err}"
        )
    consent_epochs, policy_epochs = _epoch_bindings_from_store(snapshot)
    schedule = {
        "store": snapshot,
        "consent_epochs": consent_epochs,
        "policy_epochs": policy_epochs,
        "transactions": [op_dict],
    }
    case = {"case_id": f"silo-readset-port:{op_dict['tx_id']}", "schedule": schedule}
    return bl.run_baseline(bl.B1_SILO_READSET, case, None)
