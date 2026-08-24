import logging
from uuid import uuid4

from fastapi.testclient import TestClient

from clara_api.core.auth_email import dispatch_action_email
from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_register_requires_email_verification_and_resend(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("AUTH_EMAIL_DELIVERY_MODE", "preview")
    monkeypatch.setenv("AUTH_EXPOSE_ACTION_TOKEN_PREVIEW", "true")
    _clear_settings_cache()

    email = f"verify-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Verify User",
            "role": "normal",
        },
    )
    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["is_email_verified"] is False
    assert register_payload["email_delivery_status"] == "preview"
    assert register_payload["verification_token_preview"]

    blocked_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert blocked_login.status_code == 403

    resend_response = client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert resend_response.status_code == 200
    resend_payload = resend_response.json()
    assert resend_payload["accepted"] is True
    assert resend_payload["email_delivery_status"] == "preview"
    token = resend_payload["verification_token_preview"]
    assert token

    verify_response = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 200
    assert verify_response.json()["verified"] is True

    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]
    _clear_settings_cache()


def test_forgot_password_smtp_mode_hides_token(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "false")
    monkeypatch.setenv("AUTH_EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setenv("AUTH_EXPOSE_ACTION_TOKEN_PREVIEW", "false")
    _clear_settings_cache()

    monkeypatch.setattr(
        "clara_api.core.auth_email._send_via_smtp",
        lambda settings, *, recipient, subject, plain_body, html_body: "sent",
    )

    email = f"smtp-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "SMTP User",
            "role": "normal",
        },
    )
    assert register_response.status_code == 200

    forgot_response = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_response.status_code == 200
    payload = forgot_response.json()
    assert payload["accepted"] is True
    assert payload["email_delivery_status"] == "sent"
    assert payload["reset_token_preview"] is None
    _clear_settings_cache()


def test_preview_email_log_never_contains_recipient_or_action_token(
    monkeypatch, caplog
) -> None:
    """Preview mode must not turn a local log collector into a token store."""

    monkeypatch.setenv("AUTH_EMAIL_DELIVERY_MODE", "preview")
    monkeypatch.setenv("AUTH_PUBLIC_WEB_BASE_URL", "https://theclaracare.com")
    _clear_settings_cache()
    recipient = "private.patient@example.com"
    token = "action-token-must-not-be-logged"

    with caplog.at_level(logging.INFO, logger="clara_api.core.auth_email"):
        status = dispatch_action_email(
            get_settings(),
            action="reset_password",
            recipient=recipient,
            token=token,
        )

    assert status == "preview"
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert recipient not in rendered
    assert token not in rendered
    assert "theclaracare.com" not in rendered
    _clear_settings_cache()


def test_default_smtp_settings() -> None:
    _clear_settings_cache()
    settings = get_settings()
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_username == "noreply@theclaracare.com"
    assert settings.smtp_password.get_secret_value() == ""
    assert settings.smtp_from_email == "noreply@theclaracare.com"
    assert settings.smtp_use_tls is True
    assert settings.smtp_use_ssl is False


def test_register_dispatches_email_smtp_mode_success(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("AUTH_EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setenv("AUTH_EXPOSE_ACTION_TOKEN_PREVIEW", "false")
    _clear_settings_cache()

    monkeypatch.setattr(
        "clara_api.core.auth_email._send_via_smtp",
        lambda settings, *, recipient, subject, plain_body, html_body: "sent",
    )

    email = f"smtp-reg-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "SMTP Register User",
            "role": "normal",
        },
    )
    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["is_email_verified"] is False
    assert payload["email_delivery_status"] == "sent"
    assert payload["verification_token_preview"] is None
    _clear_settings_cache()


def test_register_smtp_auth_error_safety_and_clean_logging(monkeypatch, caplog) -> None:
    import smtplib

    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("AUTH_EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setenv("AUTH_EXPOSE_ACTION_TOKEN_PREVIEW", "false")
    monkeypatch.setenv("SMTP_PASSWORD", "test-ephemeral-pass")
    _clear_settings_cache()

    class MockSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def starttls(self):
            pass

        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(
                535,
                b"5.7.8 Username and Password not accepted. Learn more at https://support.google.com/mail/?p=BadCredentials",
            )

        def send_message(self, msg):
            pass

    monkeypatch.setattr("smtplib.SMTP", MockSMTP)

    email = f"gmail-auth-fail-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    with caplog.at_level(logging.WARNING, logger="clara_api.core.auth_email"):
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Gmail Auth Test",
                "role": "normal",
            },
        )

    # Registration succeeds with 200 OK despite SMTP auth failure
    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["email"] == email
    assert payload["is_email_verified"] is False
    assert payload["email_delivery_status"] == "failed"

    # Verify clean logging explaining Gmail App Password requirement
    warning_logs = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any("App Password may be required" in log for log in warning_logs)
    # Ensure recipient PII was not leaked in log
    assert email not in "\n".join(warning_logs)
    _clear_settings_cache()
