from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import Settings
from clara_api.core.passwords import hash_password
from clara_api.db.models import User


def ensure_bootstrap_admin(db: Session, settings: Settings) -> None:
    if not settings.auth_bootstrap_admin_enabled:
        return

    email = settings.auth_bootstrap_admin_email.strip().lower()
    password = settings.auth_bootstrap_admin_password
    if not email or "@" not in email or not password:
        return

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                role="admin",
                full_name="System Administrator",
                is_email_verified=True,
                status="active",
            )
        )
        db.commit()
        return

    changed = False
    if user.role != "admin":
        user.role = "admin"
        changed = True
    if settings.auth_bootstrap_admin_force_reset_password:
        user.hashed_password = hash_password(password)
        changed = True
    if not user.is_email_verified:
        user.is_email_verified = True
        changed = True
    if user.status != "active":
        user.status = "active"
        changed = True

    if changed:
        db.add(user)
        db.commit()
