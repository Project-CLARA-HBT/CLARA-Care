"""Independent persisted governance writers for the W4 GLHS concurrency v2 workstream.

Each writer is a self-contained session/transaction contract: it takes an
explicit duck-typed session (and optional barrier/trace handles) and performs a
single persisted governance mutation followed by a commit. No function mutates
module or global state, and no writer imports the v1 ``development_probe``
private helpers.

Writers:

- ``consent_revoke``: load target, barrier, persist revocation, commit, record
  metadata.
- ``role_change``: mutate authoritative role/grant, commit, fresh scope
  resolution, before/after.
- ``purpose_or_authorization_change``: mutate a persisted purpose/authorization
  row, commit, fresh scope resolution, before/after.
- ``advance_governance_policy_epoch``: persist a new row of the
  ``governance_policy_epochs`` concept (id, policy_domain, version, active_from,
  canonical_digest, created_at).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from evaluation.glhs_postgres_toctou.schedule_primitives import (
    BarrierLike,
    SessionLike,
    TransactionTrace,
    now_monotonic_ns,
)


class GovernanceWriterError(RuntimeError):
    """A persisted governance writer could not complete its transaction contract."""


GOVERNANCE_DIMENSIONS = frozenset(
    {
        "consent_revoke",
        "role_change",
        "purpose_or_authorization_change",
        "advance_governance_policy_epoch",
    }
)


@dataclass(frozen=True)
class WriterMetadata:
    """Structured result recorded by a governance writer after its commit."""

    writer: str
    committed: bool
    begin_monotonic_ns: int
    commit_monotonic_ns: int
    details: Mapping[str, object] = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        return round((self.commit_monotonic_ns - self.begin_monotonic_ns) / 1_000_000.0, 3)

    def to_dict(self) -> dict[str, object]:
        return {
            "writer": self.writer,
            "committed": self.committed,
            "begin_monotonic_ns": self.begin_monotonic_ns,
            "commit_monotonic_ns": self.commit_monotonic_ns,
            "latency_ms": self.latency_ms,
            "details": dict(self.details),
        }


# --- consent writer -----------------------------------------------------------

ConsentLoader = Callable[[SessionLike, int, str], object]
ConsentRecordFactory = Callable[[int, str, str, datetime], object]


def _default_consent_record(
    *,
    user_id: int,
    consent_type: str,
    consent_version: str,
    revoked_at: datetime,
) -> object:
    return SimpleNamespace(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=consent_version,
        revoked_at=revoked_at,
    )


def load_consent_target(
    session: SessionLike,
    *,
    user_id: int,
    consent_type: str,
    loader: ConsentLoader | None = None,
) -> object:
    """Load the authoritative consent target for ``consent_type``.

    Uses the injected ``loader`` when provided, else a ``load_consent_target``
    duck method on the session. A missing target is a hard error: the writer
    must not revoke consent that cannot be located.
    """
    if loader is not None:
        target = loader(session, user_id, consent_type)
        if target is not None:
            return target
        raise GovernanceWriterError(f"consent_target_not_found:{consent_type}")
    duck = getattr(session, "load_consent_target", None)
    if callable(duck):
        target = duck(user_id=user_id, consent_type=consent_type)
        if target is not None:
            return target
        raise GovernanceWriterError(f"consent_target_not_found:{consent_type}")
    raise GovernanceWriterError("consent_target_loader_unavailable")


def consent_revoke(
    session: SessionLike,
    *,
    user_id: int,
    consent_type: str,
    consent_version: str,
    loader: ConsentLoader | None = None,
    record_factory: ConsentRecordFactory | None = None,
    barrier: BarrierLike | None = None,
    barrier_phase: str = "release",
    trace: TransactionTrace | None = None,
    revoked_at: datetime | None = None,
) -> WriterMetadata:
    """Persist a consent revocation as its own transaction contract.

    Sequence: load target, barrier release, persist revocation, commit, record
    metadata. ``barrier`` gates the mutation so a schedule can place this write
    exactly at a controlled release point.
    """
    begin_ns = now_monotonic_ns()
    if trace is not None:
        trace.begin(session)
    load_consent_target(session, user_id=user_id, consent_type=consent_type, loader=loader)
    if barrier is not None:
        barrier.wait(barrier_phase)
    revoke_at = revoked_at or datetime.now(UTC)
    record = (record_factory or _default_consent_record)(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=consent_version,
        revoked_at=revoke_at,
    )
    session.add(record)
    session.commit()
    commit_ns = now_monotonic_ns()
    if trace is not None:
        trace.commit(session)
    return WriterMetadata(
        writer="consent_revoke",
        committed=True,
        begin_monotonic_ns=begin_ns,
        commit_monotonic_ns=commit_ns,
        details={
            "user_id": user_id,
            "consent_type": consent_type,
            "consent_version": consent_version,
            "revoked": True,
            "revoked_at": revoke_at.isoformat(),
        },
    )


# --- role writer --------------------------------------------------------------

RoleMutator = Callable[[SessionLike, object, str], None]
FreshScopeResolver = Callable[[SessionLike, object], object]


def _default_role_mutator(session: SessionLike, actor: object, new_role: str) -> None:
    actor.role = new_role
    session.flush()


def _default_fresh_scope_resolver(session: SessionLike, subject: object) -> object:
    return SimpleNamespace(
        actor_role=getattr(subject, "role", None),
        purpose=getattr(subject, "purpose", None),
    )


def role_change(
    session: SessionLike,
    *,
    actor: object,
    new_role: str,
    mutator: RoleMutator | None = None,
    scope_resolver: FreshScopeResolver | None = None,
    barrier: BarrierLike | None = None,
    barrier_phase: str = "release",
    trace: TransactionTrace | None = None,
) -> WriterMetadata:
    """Mutate an authoritative persisted role/grant, commit, then re-resolve scope.

    Sequence: before role, barrier release, authoritative role/grant mutation,
    commit, after role (fresh read), fresh scope resolution. The fresh scope
    resolution proves the new role governs subsequent access decisions.
    """
    begin_ns = now_monotonic_ns()
    if trace is not None:
        trace.begin(session)
    before_role = getattr(actor, "role", None)
    if barrier is not None:
        barrier.wait(barrier_phase)
    (mutator or _default_role_mutator)(session, actor, new_role)
    session.commit()
    after_role = getattr(actor, "role", None)
    fresh_scope = (scope_resolver or _default_fresh_scope_resolver)(session, actor)
    commit_ns = now_monotonic_ns()
    if trace is not None:
        trace.commit(session)
    return WriterMetadata(
        writer="role_change",
        committed=True,
        begin_monotonic_ns=begin_ns,
        commit_monotonic_ns=commit_ns,
        details={
            "before_role": before_role,
            "after_role": after_role,
            "fresh_scope_actor_role": getattr(fresh_scope, "actor_role", None),
        },
    )


# --- purpose / authorization writer -------------------------------------------

AuthorizationMutator = Callable[[SessionLike, object, str], None]


def _default_authorization_mutator(
    session: SessionLike, authorization: object, *, new_purpose: str
) -> None:
    authorization.purpose = new_purpose
    session.flush()


def purpose_or_authorization_change(
    session: SessionLike,
    *,
    authorization: object,
    new_purpose: str,
    mutator: AuthorizationMutator | None = None,
    scope_resolver: FreshScopeResolver | None = None,
    barrier: BarrierLike | None = None,
    barrier_phase: str = "release",
    trace: TransactionTrace | None = None,
) -> WriterMetadata:
    """Mutate a persisted purpose/authorization row, commit, re-resolve scope.

    Sequence: before purpose, barrier release, authoritative mutation, commit,
    after purpose (fresh read), fresh scope resolution.
    """
    begin_ns = now_monotonic_ns()
    if trace is not None:
        trace.begin(session)
    before_purpose = getattr(authorization, "purpose", None)
    before_status = getattr(authorization, "status", None)
    if barrier is not None:
        barrier.wait(barrier_phase)
    if mutator is not None:
        mutator(session, authorization, new_purpose)
    else:
        _default_authorization_mutator(session, authorization, new_purpose=new_purpose)
    session.commit()
    after_purpose = getattr(authorization, "purpose", None)
    fresh_scope = (scope_resolver or _default_fresh_scope_resolver)(session, authorization)
    commit_ns = now_monotonic_ns()
    if trace is not None:
        trace.commit(session)
    return WriterMetadata(
        writer="purpose_or_authorization_change",
        committed=True,
        begin_monotonic_ns=begin_ns,
        commit_monotonic_ns=commit_ns,
        details={
            "before_purpose": before_purpose,
            "after_purpose": after_purpose,
            "before_status": before_status,
            "after_status": getattr(authorization, "status", None),
            "fresh_scope_actor_role": getattr(fresh_scope, "actor_role", None),
            "fresh_scope_purpose": getattr(fresh_scope, "purpose", None),
        },
    )


# --- governance policy epoch writer --------------------------------------------


@dataclass(frozen=True)
class GovernancePolicyEpoch:
    """A row of the persisted ``governance_policy_epochs`` concept.

    Columns: id, policy_domain, version, active_from, canonical_digest,
    created_at.
    """

    id: str
    policy_domain: str
    version: str
    active_from: datetime
    canonical_digest: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "policy_domain": self.policy_domain,
            "version": self.version,
            "active_from": self.active_from.isoformat(),
            "canonical_digest": self.canonical_digest,
            "created_at": self.created_at.isoformat(),
        }


EpochFactory = Callable[..., object]
EpochLoader = Callable[[SessionLike, str], object | None]


def _default_epoch_factory(
    *,
    id: str,
    policy_domain: str,
    version: str,
    active_from: datetime,
    canonical_digest: str,
    created_at: datetime,
) -> GovernancePolicyEpoch:
    return GovernancePolicyEpoch(
        id=id,
        policy_domain=policy_domain,
        version=version,
        active_from=active_from,
        canonical_digest=canonical_digest,
        created_at=created_at,
    )


def load_policy_epoch(
    session: SessionLike,
    *,
    policy_domain: str,
    loader: EpochLoader | None = None,
) -> object | None:
    """Load the active governance policy epoch for ``policy_domain``."""
    if loader is not None:
        return loader(session, policy_domain)
    duck = getattr(session, "load_policy_epoch", None)
    if callable(duck):
        return duck(policy_domain=policy_domain)
    raise GovernanceWriterError("policy_epoch_loader_unavailable")


def advance_governance_policy_epoch(
    session: SessionLike,
    *,
    policy_domain: str,
    version: str,
    canonical_digest: str,
    active_from: datetime | None = None,
    epoch_id: str | None = None,
    epoch_factory: EpochFactory | None = None,
    barrier: BarrierLike | None = None,
    barrier_phase: str = "release",
    trace: TransactionTrace | None = None,
) -> WriterMetadata:
    """Persist a new ``governance_policy_epochs`` row and commit it.

    Replaces any in-memory global policy-version mutation with a persisted,
    digest-bound epoch. The row carries id, policy_domain, version, active_from,
    canonical_digest, created_at.
    """
    begin_ns = now_monotonic_ns()
    if trace is not None:
        trace.begin(session)
    previous = load_policy_epoch(session, policy_domain=policy_domain)
    if barrier is not None:
        barrier.wait(barrier_phase)
    created = datetime.now(UTC)
    epoch = (epoch_factory or _default_epoch_factory)(
        id=epoch_id or uuid4().hex,
        policy_domain=policy_domain,
        version=version,
        active_from=active_from or created,
        canonical_digest=canonical_digest,
        created_at=created,
    )
    session.add(epoch)
    session.commit()
    commit_ns = now_monotonic_ns()
    if trace is not None:
        trace.commit(session)
    details: Mapping[str, object] = {
        "policy_domain": policy_domain,
        "version": version,
        "canonical_digest": canonical_digest,
        "epoch": epoch.to_dict() if hasattr(epoch, "to_dict") else str(epoch),
        "previous_version": getattr(previous, "version", None),
    }
    return WriterMetadata(
        writer="advance_governance_policy_epoch",
        committed=True,
        begin_monotonic_ns=begin_ns,
        commit_monotonic_ns=commit_ns,
        details=details,
    )


# --- compound drift helper ----------------------------------------------------


def compound_drift_detected(metadata: Sequence[WriterMetadata]) -> bool:
    """True when a schedule combined two or more distinct governance dimensions."""
    dimensions = {m.writer for m in metadata if m.writer in GOVERNANCE_DIMENSIONS}
    return len(dimensions) >= 2
