from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import Settings
from clara_api.core.passwords import hash_password
from clara_api.db.models import User

logger = logging.getLogger(__name__)


def _is_weak_bootstrap_password(password: str) -> bool:
    weak_defaults = {"wrongpass", "change-me", "admin", "admin123", "password"}
    if password in weak_defaults:
        return True
    if len(password) < 12:
        return True
    has_alpha = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)
    return not (has_alpha and has_digit)


def ensure_bootstrap_admin(db: Session, settings: Settings) -> None:
    if not settings.auth_bootstrap_admin_enabled:
        return

    email = settings.auth_bootstrap_admin_email.strip().lower()
    password = settings.auth_bootstrap_admin_password
    if not email or "@" not in email or not password:
        return
    if settings.environment.lower() == "production" and _is_weak_bootstrap_password(password):
        logger.warning(
            "Skip bootstrap admin setup in production because bootstrap password is weak."
        )
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
