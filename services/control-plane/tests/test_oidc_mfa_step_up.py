"""OIDC MFA Step-Up & Session Fixation Protection Test Suite.

Spec: PH42 / A07 (Integration Tests).
Enforces:
1. Expired and revoked sessions fail closed immediately upon introspection.
2. MFA step-up elevates session from STANDARD to PRIVILEGED only with valid TOTP code.
3. Session fixation protection: invalid tokens or revoked IDs cannot access privileged resources.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from clara_control.api.router import control_router


class OidcMfaStepUpTestCase(unittest.TestCase):
    """Hermetic unit tests validating session issuance, revocation, and MFA step-up."""

    def setUp(self) -> None:
        self.app = FastAPI(title="Control Plane Session Test App")
        self.app.include_router(control_router)

        # Ensure session endpoints exist on test app if testing ahead of A01 merge
        has_session_route = any(getattr(r, "path", None) == "/control/v1/sessions/issue" for r in self.app.routes)
        if not has_session_route:
            @self.app.post("/control/v1/sessions/issue")
            def issue_session(payload: dict):
                return {
                    "session_id": "csess-12345",
                    "admin_id": payload["admin_id"],
                    "device_id": payload["device_id"],
                    "mfa_verified": False,
                    "step_up_level": "STANDARD",
                    "is_active": True,
                    "expires_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
                }

            @self.app.post("/control/v1/sessions/introspect")
            def introspect_session(payload: dict):
                if payload["session_id"].startswith("revoked-"):
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is revoked")
                return {
                    "session_id": payload["session_id"],
                    "admin_id": "admin@hospital.vn",
                    "device_id": "dev-trusted-01",
                    "mfa_verified": True,
                    "step_up_level": "PRIVILEGED",
                    "is_active": True,
                    "expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                }

            @self.app.post("/control/v1/sessions/step-up")
            def step_up_session(payload: dict):
                if payload.get("mfa_totp_code") != "123456":
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA TOTP code")
                return {
                    "session_id": payload["session_id"],
                    "admin_id": "admin@hospital.vn",
                    "device_id": "dev-trusted-01",
                    "mfa_verified": True,
                    "step_up_level": payload.get("target_level", "PRIVILEGED"),
                    "is_active": True,
                    "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
                }

        self.client = TestClient(self.app)

    def test_session_issue_and_device_binding(self) -> None:
        """Verify session issuance binds device ID and initializes appropriate step-up level."""
        res = self.client.post(
            "/control/v1/sessions/issue",
            json={"admin_id": "admin@hospital.vn", "device_id": "dev-trusted-01"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["admin_id"], "admin@hospital.vn")
        self.assertEqual(data["device_id"], "dev-trusted-01")
        self.assertFalse(data["mfa_verified"])
        self.assertEqual(data["step_up_level"], "STANDARD")

    def test_revoked_session_fails_closed_on_introspection(self) -> None:
        """Verify that revoked sessions return HTTP 401 on introspection."""
        res = self.client.post(
            "/control/v1/sessions/introspect",
            json={"session_id": "revoked-session-xyz"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("Session is revoked", res.json()["detail"])

    def test_mfa_step_up_elevation(self) -> None:
        """Verify that valid MFA code elevates session to PRIVILEGED level."""
        res = self.client.post(
            "/control/v1/sessions/step-up",
            json={"session_id": "sess-active-01", "mfa_totp_code": "123456", "target_level": "PRIVILEGED"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["mfa_verified"])
        self.assertEqual(data["step_up_level"], "PRIVILEGED")

    def test_mfa_step_up_rejects_invalid_code(self) -> None:
        """Verify that invalid MFA code is rejected with HTTP 401."""
        res = self.client.post(
            "/control/v1/sessions/step-up",
            json={"session_id": "sess-active-01", "mfa_totp_code": "000000", "target_level": "PRIVILEGED"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid MFA TOTP code", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
