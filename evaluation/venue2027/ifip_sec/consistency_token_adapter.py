"""CLARA-Care 2027 IFIP_SEC task IFIP_SEC-X06_zanzibar_style — consistency-token adapter.

Purpose
-------
In-process reference implementation of the Zanzibar consistency-aware
authorization semantics (Pang & Pang, "Zanzibar: Google's Consistent, Global
Authorization System", USENIX ATC 2019, Sec. 2.3-2.4) serving blueprint arm
B2 for "Replay-Closed Authorization Across Purpose, Delegation, and AI
Proposal Lineage" (IFIP_SEC 2027). It is the task's exact target contract
``check_with_revision(principal, resource, token) -> Verdict`` realized over:

- **Relation tuples** — append-only changelog of ``(object, relation, user)``
  writes and deletes, each stamped with a monotonically increasing per-store
  revision (the tuple-change ordering of Zanzibar Sec. 2.3).
- **Zookie-style consistency tokens** — HMAC-bound snapshot-version tokens
  carrying the store id and the revision they were captured at. A ``FRESH``
  token is issued at the current head revision (the
  ``minimize_latency=false`` / strong-consistency option); ``issue_token_at``
  captures a token at an earlier revision (bounded-staleness read).
- **Relation-walk evaluation** — namespace rewrite rules
  (``computed_userset`` relation aliasing and ``tuple_to_userset`` hierarchy
  walks) evaluated over the tuple snapshot visible at the token revision,
  with union semantics and a cycle guard.

Exact consistency guarantee (documented, tested):
- A ``FRESH`` check evaluates at the current head revision and therefore sees
  every completed write, including a just-granted relation AND a just-applied
  revocation: a replayed pre-revocation request is REJECTED with
  ``RELATION_REVOKED``.
- A token captured at revision ``R`` evaluates the snapshot at ``R``: writes
  committed after ``R`` are invisible in BOTH directions — a later grant is
  not seen (``RELATION_ABSENT``) and a later revocation is not seen either,
  so a pre-revocation replay inside the stale-read window is ADMITTED. This
  bounded-staleness boundary is the published Zanzibar behaviour and the RQ1
  measurement gap this comparator quantifies; it is asserted, never hidden.

Honest scope (execution contract rule 8 — never a toy under the same name):
this module is an in-process reference of the *published* Zanzibar semantics,
NOT the pinned OpenFGA v1.22.1 server (registry row ``B2_OPENFGA`` remains
``NOT_RUN_EXTERNAL`` in ``baselines.py``). Unsupported constructs are marked
in ``research/venue2027/ifip_sec/tasks/zanzibar_style_impl.md``: no real
distributed changelog/index storage (single-process logical revision counter),
no ``new_epoch`` per-user monotonic-read enforcement, no userset user ids
(``obj#relation``), no intersection/exclusion rewrite rules, no leases.

Allowed input
-------------
JSON-serializable string identifiers (principal, resource, relation), tokens
issued by :meth:`ZanzibarStore.issue_token` / :meth:`ZanzibarStore.issue_token_at`
of a store sharing the injected HMAC key, and a namespace config (defaults
provided). No network, no database, no hidden clock or randomness: revisions
are logical, the HMAC key is injected by the caller.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes returned inside
:class:`ConsistencyVerdict` (``RELATION_PRESENT`` / ``RELATION_ABSENT`` /
``RELATION_REVOKED`` / ``TOKEN_MISSING`` / ``TOKEN_UNPARSEABLE`` /
``TOKEN_SIGNATURE_INVALID`` / ``TOKEN_STORE_MISMATCH`` /
``TOKEN_REVISION_UNKNOWN``): token faults are first-class REJECT verdicts,
never unhandled exceptions miscounted as safe rejections. Only caller wiring
errors (bad key, non-string identifiers, unknown namespace rule shape) raise
:class:`ConsistencyError`. Every verdict records real evaluation counts
(``tuples_examined``, ``nodes_visited``, ``db_round_trips``).

Version
-------
``CONSISTENCY_ADAPTER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

CONSISTENCY_ADAPTER_VERSION = "1.0.0"

#: Stable reason codes (uppercase, machine-checkable). Allowed/rejecting.
RC_RELATION_PRESENT = "RELATION_PRESENT"
RC_RELATION_ABSENT = "RELATION_ABSENT"
RC_RELATION_REVOKED = "RELATION_REVOKED"
RC_TOKEN_MISSING = "TOKEN_MISSING"
RC_TOKEN_UNPARSEABLE = "TOKEN_UNPARSEABLE"
RC_TOKEN_SIGNATURE_INVALID = "TOKEN_SIGNATURE_INVALID"
RC_TOKEN_STORE_MISMATCH = "TOKEN_STORE_MISMATCH"
RC_TOKEN_REVISION_UNKNOWN = "TOKEN_REVISION_UNKNOWN"

#: Default relation queried when the caller does not pin one (ReBAC viewer).
DEFAULT_RELATION = "viewer"

#: HMAC key floor, mirroring baselines.BaselineContext hygiene.
_HMAC_KEY_MIN_BYTES = 16

#: Token payload schema version (zookie v1: store id + snapshot revision).
_TOKEN_VERSION = 1

#: Hard depth cap for relation walks (defense in depth on top of the cycle set).
_MAX_WALK_DEPTH = 16

#: Default namespace: document.viewer <- editor (computed_userset) UNION
#: parent.viewer (tuple_to_userset hierarchy walk); folder.viewer <- parent.viewer.
DEFAULT_NAMESPACE: Mapping[str, Mapping[str, Any]] = {
    "document": {
        "viewer": [
            {"computed_userset": "editor"},
            {"tuple_to_userset": {"tupleset": "parent", "computed_userset": "viewer"}},
        ]
    },
    "folder": {
        "viewer": {"tuple_to_userset": {"tupleset": "parent", "computed_userset": "viewer"}}
    },
}

__all__ = [
    "CONSISTENCY_ADAPTER_VERSION",
    "DEFAULT_NAMESPACE",
    "DEFAULT_RELATION",
    "ConsistencyError",
    "ConsistencyVerdict",
    "RelationTuple",
    "ZanzibarStore",
    "bind_consistency_checker",
    "check_with_revision",
    "zookie_bytes",
]


class ConsistencyError(ValueError):
    """Caller wiring/configuration error (never an arm outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class RelationTuple:
    """One relation tuple with its changelog stamps (JSON-serializable).

    ``written_at`` — revision at which the tuple was written.
    ``deleted_at`` — revision at which the tombstone was applied, or ``None``.
    """

    object_id: str
    relation: str
    user: str
    written_at: int
    deleted_at: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "relation": self.relation,
            "user": self.user,
            "written_at": self.written_at,
            "deleted_at": self.deleted_at,
        }


@dataclasses.dataclass(frozen=True)
class ConsistencyVerdict:
    """Outcome of one ``check_with_revision`` call (JSON-serializable).

    ``allowed`` / ``reason_code`` — the decision and its stable code.
    ``revision_evaluated`` — snapshot revision the token selected (the zookie
    semantics: the decision is a pure function of the tuple state at exactly
    this revision, never of the current head unless the token is FRESH).
    ``tuples_examined`` / ``nodes_visited`` / ``db_round_trips`` — real
    evaluation counts recorded during the walk (RQ3 cost markers).
    """

    allowed: bool
    reason_code: str
    revision_evaluated: int
    tuples_examined: int
    nodes_visited: int
    db_round_trips: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "revision_evaluated": self.revision_evaluated,
            "tuples_examined": self.tuples_examined,
            "nodes_visited": self.nodes_visited,
            "db_round_trips": self.db_round_trips,
        }


def _sign(key: bytes, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def zookie_bytes(token: str) -> int:
    """RQ3 token-size metric: serialized zookie length in bytes."""
    return len(token.encode("utf-8"))


class ZanzibarStore:
    """In-process Zanzibar-style store: tuple changelog + zookie issuance.

    The revision counter is logical and single-process (documented scope);
    every successful write or delete advances it by exactly one, giving the
    total tuple-change ordering the consistency tokens select snapshots from.
    The HMAC key is injected by the caller; nothing here reads a clock, the
    network or a database.
    """

    def __init__(
        self,
        *,
        store_id: str,
        hmac_key: bytes,
        namespace: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None,
    ) -> None:
        if not isinstance(store_id, str) or not store_id:
            raise ConsistencyError("STORE_ID_INVALID", "store_id must be a non-empty string")
        if not isinstance(hmac_key, bytes | bytearray) or len(hmac_key) < _HMAC_KEY_MIN_BYTES:
            raise ConsistencyError(
                "CONTEXT_KEY_TOO_SHORT",
                f"hmac_key must be >= {_HMAC_KEY_MIN_BYTES} bytes",
            )
        self.store_id = store_id
        self._hmac_key = bytes(hmac_key)
        self._namespace = DEFAULT_NAMESPACE if namespace is None else namespace
        # Append-only changelog of (revision, tuple, is_delete) events.
        self._log: list[tuple[int, RelationTuple, bool]] = []
        self._head = 0

    # -- changelog operations ------------------------------------------------

    @property
    def head_revision(self) -> int:
        """Current head revision (all writes with stamp <= head are committed)."""
        return self._head

    def write(self, object_id: str, relation: str, user: str) -> int:
        """Append one relation tuple; returns the revision it committed at."""
        self._require_identifiers(object_id, relation, user)
        self._head += 1
        tuple_ = RelationTuple(object_id, relation, user, written_at=self._head)
        self._log.append((self._head, tuple_, False))
        return self._head

    def delete(self, object_id: str, relation: str, user: str) -> int:
        """Tombstone the latest live tuple (object, relation, user).

        Deleting a tuple that does not exist (or is already tombstoned) is a
        no-op that does NOT advance the revision — documented, so a delete
        never fabricates change history. Returns the head revision after the
        operation.
        """
        self._require_identifiers(object_id, relation, user)
        for index in range(len(self._log) - 1, -1, -1):
            revision, tuple_, is_delete = self._log[index]
            if (
                not is_delete
                and tuple_.object_id == object_id
                and tuple_.relation == relation
                and tuple_.user == user
                and tuple_.deleted_at is None
            ):
                self._head += 1
                tombstoned = dataclasses.replace(tuple_, deleted_at=self._head)
                self._log[index] = (revision, tombstoned, False)
                self._log.append((self._head, tombstoned, True))
                return self._head
        return self._head

    # -- consistency tokens (zookies) ----------------------------------------

    def issue_token(self) -> str:
        """Issue a FRESH (strong-consistency) zookie bound to the head revision.

        Equivalent to the OpenFGA ``minimize_latency=false`` consistency
        option: the subsequent check sees every completed write.
        """
        return self._encode_token(self._head)

    def issue_token_at(self, revision: int) -> str:
        """Capture a zookie at an earlier revision (bounded-staleness read).

        ``revision`` must be a revision this store actually committed
        (``0 <= revision <= head``); anything else fails closed — a token
        claiming a snapshot that never existed is never issued.
        """
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise ConsistencyError(
                "TOKEN_REVISION_UNKNOWN", f"revision must be an integer, got {revision!r}"
            )
        if revision < 0 or revision > self._head:
            raise ConsistencyError(
                "TOKEN_REVISION_UNKNOWN",
                f"revision {revision} was never committed by store {self.store_id!r} "
                f"(head={self._head})",
            )
        return self._encode_token(revision)

    def _encode_token(self, revision: int) -> str:
        payload: dict[str, Any] = {
            "v": _TOKEN_VERSION,
            "store": self.store_id,
            "revision": revision,
        }
        payload["mac"] = _sign(self._hmac_key, payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    # -- snapshot views -------------------------------------------------------

    def _candidates(self, object_id: str, relation: str, user: str) -> Iterator[RelationTuple]:
        """All changelog tuples matching (object, relation, user), any stamp."""
        for _, tuple_, _ in self._log:
            if (
                tuple_.object_id == object_id
                and tuple_.relation == relation
                and tuple_.user == user
            ):
                yield tuple_

    def _scan(self, object_id: str, relation: str, user: str, revision: int) -> str:
        """One simulated authorization-store read: status of (obj, rel, user) @ rev.

        Returns ``PRESENT`` if some matching tuple is live at ``revision``
        (written at <= revision, not tombstoned at/before it), ``REVOKED`` if
        every matching tuple written by then was tombstoned at/before the
        evaluated revision, else ``ABSENT``.
        """
        statuses: list[str] = []
        for tuple_ in self._candidates(object_id, relation, user):
            if tuple_.written_at > revision:
                continue  # committed after the captured snapshot: invisible
            if tuple_.deleted_at is not None and tuple_.deleted_at <= revision:
                statuses.append("REVOKED")  # tombstone visible at this snapshot
            else:
                statuses.append("PRESENT")
        return (
            "REVOKED"
            if statuses and "PRESENT" not in statuses
            else ("PRESENT" if "PRESENT" in statuses else "ABSENT")
        )

    def _parents(self, object_id: str, tupleset: str, revision: int) -> list[str]:
        """Visible parent objects linked by (object, tupleset, parent) tuples."""
        parents: list[str] = []
        for _, tuple_, _ in self._log:
            if (
                tuple_.object_id == object_id
                and tuple_.relation == tupleset
                and tuple_.written_at <= revision
                and (tuple_.deleted_at is None or tuple_.deleted_at > revision)
            ):
                parents.append(tuple_.user)
        return parents

    @staticmethod
    def _require_identifiers(*identifiers: str) -> None:
        for value in identifiers:
            if not isinstance(value, str) or not value:
                raise ConsistencyError(
                    "IDENTIFIER_INVALID", f"identifiers must be non-empty strings, got {value!r}"
                )

    def snapshot_visible(self, revision: int) -> list[RelationTuple]:
        """Tuples visible at ``revision`` (audit view used by the impl doc)."""
        visible: list[RelationTuple] = []
        for _, tuple_, is_delete in self._log:
            if is_delete or tuple_.written_at > revision:
                continue
            if tuple_.deleted_at is None or tuple_.deleted_at > revision:
                visible.append(tuple_)
        return visible


# ---------------------------------------------------------------------------
# Relation-walk evaluator + the exact target contract
# ---------------------------------------------------------------------------


class _WalkCounts:
    """Mutable evaluation counters for one check (real, recorded per verdict)."""

    __slots__ = ("db_round_trips", "nodes_visited", "tuples_examined")

    def __init__(self) -> None:
        self.tuples_examined = 0
        self.nodes_visited = 0
        self.db_round_trips = 0


_STATUS_ORDER = {"PRESENT": 0, "REVOKED": 1, "ABSENT": 2}


def _combine(statuses: list[str]) -> str:
    """Union semantics: PRESENT beats REVOKED beats ABSENT."""
    return min(statuses, key=lambda s: _STATUS_ORDER[s]) if statuses else "ABSENT"


def _relation_walk(
    store: ZanzibarStore,
    namespace: Mapping[str, Mapping[str, Mapping[str, Any]]],
    object_id: str,
    relation: str,
    user: str,
    revision: int,
    counts: _WalkCounts,
    visited: frozenset[tuple[str, str]],
    depth: int = 0,
) -> str:
    """Evaluate (object, relation, user) at the snapshot ``revision``.

    One walk node = one simulated authorization-store read
    (``db_round_trips``), examining every candidate tuple for the direct
    (object, relation, user) lookup (``tuples_examined``), then expanding the
    namespace rewrite rules (``computed_userset`` / ``tuple_to_userset``)
    with union semantics and a (object, relation) cycle guard.
    """
    if depth > _MAX_WALK_DEPTH:
        # Cycle guard backstop beyond the visited set; a config that reaches
        # here is a wiring fault, not a decision.
        raise ConsistencyError("WALK_DEPTH_EXCEEDED", f"{object_id}#{relation}")
    node = (object_id, relation)
    if node in visited:
        return "ABSENT"
    visited = visited | {node}
    counts.nodes_visited += 1
    counts.db_round_trips += 1

    statuses = [store._scan(object_id, relation, user, revision)]
    counts.tuples_examined += sum(
        1
        for tuple_ in store._candidates(object_id, relation, user)
        if tuple_.written_at <= revision
    )

    rules = namespace.get(object_id.split(":", 1)[0], {}).get(relation)
    branches: list[Any]
    if isinstance(rules, Mapping):
        branches = [rules]  # single-rewrite shorthand
    elif isinstance(rules, Sequence) and not isinstance(rules, str):
        branches = list(rules)  # union of rewrite branches
    else:
        branches = []
    for branch in branches:
        if not isinstance(branch, Mapping):
            raise ConsistencyError(
                "NAMESPACE_RULE_INVALID", f"rewrite rule for {object_id}#{relation}"
            )
        if "computed_userset" in branch:
            parent_relation = branch["computed_userset"]
            if not isinstance(parent_relation, str):
                raise ConsistencyError(
                    "NAMESPACE_RULE_INVALID", f"computed_userset for {object_id}#{relation}"
                )
            statuses.append(
                _relation_walk(
                    store,
                    namespace,
                    object_id,
                    parent_relation,
                    user,
                    revision,
                    counts,
                    visited,
                    depth + 1,
                )
            )
        elif "tuple_to_userset" in branch:
            spec = branch["tuple_to_userset"]
            if (
                not isinstance(spec, Mapping)
                or not isinstance(spec.get("tupleset"), str)
                or not isinstance(spec.get("computed_userset"), str)
            ):
                raise ConsistencyError(
                    "NAMESPACE_RULE_INVALID", f"tuple_to_userset for {object_id}#{relation}"
                )
            for parent in store._parents(object_id, str(spec["tupleset"]), revision):
                statuses.append(
                    _relation_walk(
                        store,
                        namespace,
                        parent,
                        str(spec["computed_userset"]),
                        user,
                        revision,
                        counts,
                        visited,
                        depth + 1,
                    )
                )
        else:
            raise ConsistencyError(
                "NAMESPACE_RULE_INVALID", f"unsupported rewrite rule for {object_id}#{relation}"
            )
    return _combine(statuses)


def check_with_revision(
    principal: str,
    resource: str,
    token: str,
    *,
    store: ZanzibarStore,
    relation: str = DEFAULT_RELATION,
) -> ConsistencyVerdict:
    """Exact X06 target contract: ``check_with_revision(principal, resource, token)``.

    Evaluates whether ``principal`` holds ``relation`` on ``resource`` in the
    tuple snapshot selected by the zookie ``token`` (injected ``store``; the
    three-positional-argument contract is :func:`bind_consistency_checker`).
    Token faults fail closed as REJECT verdicts with stable reason codes —
    never exceptions that could be miscounted as safe rejections. The verdict
    carries the evaluated revision and the real walk counts.
    """
    counts = _WalkCounts()
    if (
        not isinstance(principal, str)
        or not isinstance(resource, str)
        or not isinstance(relation, str)
    ):
        raise ConsistencyError(
            "CHECK_ARGUMENT_INVALID", "principal, resource and relation must be strings"
        )
    if not isinstance(token, str) or not token:
        return ConsistencyVerdict(False, RC_TOKEN_MISSING, -1, 0, 0, 0)
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return ConsistencyVerdict(False, RC_TOKEN_UNPARSEABLE, -1, 0, 0, 0)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("revision"), int)
        or isinstance(payload.get("revision"), bool)
    ):
        return ConsistencyVerdict(False, RC_TOKEN_UNPARSEABLE, -1, 0, 0, 0)
    mac = payload.get("mac")
    expected = _sign(store._hmac_key, {k: v for k, v in payload.items() if k != "mac"})
    if not isinstance(mac, str) or not hmac.compare_digest(mac, expected):
        return ConsistencyVerdict(False, RC_TOKEN_SIGNATURE_INVALID, -1, 0, 0, 0)
    if payload.get("v") != _TOKEN_VERSION or not isinstance(payload.get("store"), str):
        return ConsistencyVerdict(False, RC_TOKEN_UNPARSEABLE, -1, 0, 0, 0)
    if payload["store"] != store.store_id:
        return ConsistencyVerdict(False, RC_TOKEN_STORE_MISMATCH, -1, 0, 0, 0)
    revision = payload["revision"]
    if revision < 0 or revision > store.head_revision:
        # A snapshot that never existed in this store: fail closed.
        return ConsistencyVerdict(False, RC_TOKEN_REVISION_UNKNOWN, -1, 0, 0, 0)

    status = _relation_walk(
        store, store._namespace, resource, relation, principal, revision, counts, frozenset()
    )
    reason = {
        "PRESENT": RC_RELATION_PRESENT,
        "REVOKED": RC_RELATION_REVOKED,
        "ABSENT": RC_RELATION_ABSENT,
    }[status]
    return ConsistencyVerdict(
        allowed=status == "PRESENT",
        reason_code=reason,
        revision_evaluated=revision,
        tuples_examined=counts.tuples_examined,
        nodes_visited=counts.nodes_visited,
        db_round_trips=counts.db_round_trips,
    )


def bind_consistency_checker(
    store: ZanzibarStore, relation: str = DEFAULT_RELATION
) -> Callable[[str, str, str], ConsistencyVerdict]:
    """Bind the injected store/key into the exact 3-argument target contract.

    The returned closure is ``check_with_revision(principal, resource, token)``
    — the task signature ``check_with_revision(principal,resource,token)
    -> Verdict`` with all I/O injected, suitable for direct comparator wiring.
    """

    def check(principal: str, resource: str, token: str) -> ConsistencyVerdict:
        return check_with_revision(principal, resource, token, store=store, relation=relation)

    return check
