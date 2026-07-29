"""Transitive, profile-contained invalidation for derived LifeMap outputs."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from clara_api.db.models import LifeMapProjectionDependency

ProjectionKey = tuple[str, str]


class ProjectionDependencyError(ValueError):
    pass


def add_projection_dependency(
    db: Session,
    *,
    profile_id: int,
    projection_type: str,
    projection_public_id: str,
    rule_version: str,
    input_revision_id: int | None = None,
    input_projection: ProjectionKey | None = None,
) -> LifeMapProjectionDependency:
    if (
        not projection_type
        or not projection_public_id
        or not rule_version
        or (input_revision_id is None) == (input_projection is None)
    ):
        raise ProjectionDependencyError("projection_dependency_requires_one_input")
    parent_type, parent_id = input_projection or (None, None)
    row = LifeMapProjectionDependency(
        profile_id=profile_id,
        projection_type=projection_type,
        projection_public_id=projection_public_id,
        input_type=(
            "event_revision" if input_revision_id is not None else "projection"
        ),
        input_revision_id=input_revision_id,
        input_projection_type=parent_type,
        input_projection_public_id=parent_id,
        rule_version=rule_version,
    )
    db.add(row)
    return row


def invalidate_projection_graph(
    db: Session,
    *,
    profile_id: int,
    reason: str,
    revision_ids: tuple[int, ...] = (),
    projection_inputs: tuple[ProjectionKey, ...] = (),
    invalidate_all: bool = False,
) -> tuple[ProjectionKey, ...]:
    """Invalidate direct and transitive dependants exactly once.

    The caller owns the surrounding command transaction. A cycle is harmless:
    visited projection keys bound the traversal.
    """

    if not reason or (
        not invalidate_all and not revision_ids and not projection_inputs
    ):
        raise ProjectionDependencyError("projection_invalidation_source_required")
    now = datetime.now(UTC)
    queue = deque(projection_inputs)
    visited_inputs: set[ProjectionKey] = set()
    invalidated_outputs: set[ProjectionKey] = set()

    direct_filters: list[ColumnElement[bool]] = []
    if revision_ids:
        direct_filters.append(
            LifeMapProjectionDependency.input_revision_id.in_(set(revision_ids))
        )
    if projection_inputs:
        direct_filters.extend(
            (
                LifeMapProjectionDependency.input_projection_type == parent_type
            )
            & (
                LifeMapProjectionDependency.input_projection_public_id == parent_id
            )
            for parent_type, parent_id in projection_inputs
        )
    query = select(LifeMapProjectionDependency).where(
        LifeMapProjectionDependency.profile_id == profile_id,
        LifeMapProjectionDependency.invalidated_at.is_(None),
    )
    if not invalidate_all:
        query = query.where(or_(*direct_filters))
    rows = list(db.execute(query).scalars())
    for row in rows:
        row.invalidated_at = now
        row.invalidation_reason = reason
        key = (row.projection_type, row.projection_public_id)
        invalidated_outputs.add(key)
        queue.append(key)

    while queue:
        parent = queue.popleft()
        if parent in visited_inputs:
            continue
        visited_inputs.add(parent)
        children = list(
            db.execute(
                select(LifeMapProjectionDependency).where(
                    LifeMapProjectionDependency.profile_id == profile_id,
                    LifeMapProjectionDependency.input_projection_type == parent[0],
                    LifeMapProjectionDependency.input_projection_public_id == parent[1],
                    LifeMapProjectionDependency.invalidated_at.is_(None),
                )
            ).scalars()
        )
        for child in children:
            child.invalidated_at = now
            child.invalidation_reason = reason
            key = (child.projection_type, child.projection_public_id)
            if key not in invalidated_outputs:
                invalidated_outputs.add(key)
                queue.append(key)
    db.flush()
    return tuple(sorted(invalidated_outputs))
