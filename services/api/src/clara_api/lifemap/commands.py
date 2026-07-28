"""Shared LifeMap command idempotency and outbox helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import LifeMapCommandRecord, LifeMapOutboxEvent


def request_digest(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def key_hash(key: str) -> str:
    if not key or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_idempotency_key", "message": "Invalid Idempotency-Key"},
        )
    return hashlib.sha256(key.encode()).hexdigest()


@dataclass(frozen=True)
class CommandReplay:
    status_code: int
    response: dict


def replay_command(
    db: Session,
    *,
    profile_id: int,
    actor_user_id: int,
    operation: str,
    idempotency_key: str,
    digest: str,
) -> CommandReplay | None:
    record = db.execute(
        select(LifeMapCommandRecord).where(
            LifeMapCommandRecord.profile_id == profile_id,
            LifeMapCommandRecord.actor_user_id == actor_user_id,
            LifeMapCommandRecord.operation == operation,
            LifeMapCommandRecord.idempotency_key_hash == key_hash(idempotency_key),
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if record.request_digest != digest:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency-Key was already used with another request",
            },
        )
    return CommandReplay(status_code=record.status_code, response=record.response_json)


def store_command(
    db: Session,
    *,
    profile_id: int,
    actor_user_id: int,
    operation: str,
    idempotency_key: str,
    digest: str,
    status_code: int,
    response: dict,
) -> LifeMapCommandRecord:
    record = LifeMapCommandRecord(
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        operation=operation,
        idempotency_key_hash=key_hash(idempotency_key),
        request_digest=digest,
        status_code=status_code,
        response_json={**response},
    )
    db.add(record)
    db.flush()
    return record


def add_outbox(
    db: Session,
    *,
    event_id: str,
    profile_id: int,
    aggregate_type: str,
    aggregate_public_id: str,
    event_type: str,
) -> None:
    db.add(
        LifeMapOutboxEvent(
            event_id=event_id,
            profile_id=profile_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_public_id,
            event_type=event_type,
            payload_json={
                "aggregate_id": aggregate_public_id,
                "event_type": event_type,
            },
        )
    )
