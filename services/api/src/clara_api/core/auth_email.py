from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from clara_api.core.config import Settings

logger = logging.getLogger(__name__)


def should_expose_action_token_preview(settings: Settings) -> bool:
    if settings.environment.lower() == "production":
        return False
    if settings.auth_expose_action_token_preview:
        return True
    return settings.auth_email_delivery_mode == "preview"


def _build_action_link(settings: Settings, action: str, token: str) -> str:
    if action == "verify_email":
        path = settings.auth_verify_email_path
    elif action == "reset_password":
        path = settings.auth_reset_password_path
    elif action == "login_otp":
        path = "/login"
    else:
        path = "/"
    base = settings.auth_public_web_base_url.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}?token={quote(token)}"


def _build_message(
    action: str,
    *,
    action_link: str,
    token: str,
    settings: Settings,
) -> tuple[str, str]:
    if action == "login_otp":
        subject = "[CLARA] Ma OTP dang nhap"
        body = (
            "Chao ban,\n\n"
            "Ma OTP dang nhap cua ban la:\n"
            f"{token}\n\n"
            f"Ma co hieu luc trong {settings.auth_login_otp_ttl_minutes} phut. "
            "Vui long khong chia se voi nguoi khac.\n"
        )
        return subject, body

    if action == "verify_email":
        subject = "[CLARA] Xac thuc email"
        body = (
            "Chao ban,\n\n"
            "Vui long xac thuc email de kich hoat tai khoan CLARA.\n"
            f"Link xac thuc: {action_link}\n\n"
            "Neu ban khong tao tai khoan nay, hay bo qua email.\n"
        )
        return subject, body

    subject = "[CLARA] Dat lai mat khau"
    body = (
        "Chao ban,\n\n"
        "Ban da yeu cau dat lai mat khau CLARA.\n"
        f"Link dat lai mat khau: {action_link}\n\n"
        "Neu ban khong thuc hien yeu cau nay, hay bo qua email.\n"
    )
    return subject, body


def _send_via_smtp(settings: Settings, *, recipient: str, subject: str, body: str) -> str:
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("SMTP missing host/from email; auth email skipped")
        return "failed"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = recipient
    msg.set_content(body)

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send auth email")
        return "failed"
    return "sent"


def dispatch_action_email(
    settings: Settings,
    *,
    action: str,
    recipient: str,
    token: str,
) -> str:
    mode = settings.auth_email_delivery_mode
    link = _build_action_link(settings, action=action, token=token)
    subject, body = _build_message(action, action_link=link, token=token, settings=settings)

    if mode == "disabled":
        return "disabled"

    if mode == "preview":
        # Preview delivery is still an operational log path.  A recipient is
        # PII and an action link contains a bearer-style credential, so neither
        # may enter logs even outside production.  Callers that explicitly
        # enable a local token preview receive it through the authenticated API
        # response, never through a log sink.
        logger.info("auth email preview dispatched action=%s", action)
        return "preview"

    return _send_via_smtp(settings, recipient=recipient, subject=subject, body=body)
