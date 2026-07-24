"""Small, truthful LifeMap service contracts exposed from Phase 0."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import PhrProfile
from clara_api.db.session import get_db

router = APIRouter()
USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))
SCHEMA_VERSION = "2026-07-25.1"


class LifeMapHealthResponse(BaseModel):
    status: str
    schema_version: str
    profile_ready: bool
    generated_at: datetime


@router.get("/health", response_model=LifeMapHealthResponse)
def lifemap_health(
    db: Session = Depends(get_db), token: TokenPayload = USER_ROLE_DEP
) -> LifeMapHealthResponse:
    user = current_user(db, token)
    ready = (
        db.execute(select(PhrProfile.id).where(PhrProfile.user_id == user.id)).first() is not None
    )
    return LifeMapHealthResponse(
        status="ok",
        schema_version=SCHEMA_VERSION,
        profile_ready=ready,
        generated_at=datetime.now(UTC),
    )


@router.get("/schema-version")
def schema_version(_token: TokenPayload = USER_ROLE_DEP) -> dict[str, str]:
    return {"schema_version": SCHEMA_VERSION}
