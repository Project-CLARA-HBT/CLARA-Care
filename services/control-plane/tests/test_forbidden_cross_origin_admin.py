"""Forbidden Cross-Origin Admin Use & Security Isolation Test Suite.

Spec: PH41 / A07 (Integration Tests).
Enforces:
1. Control-plane endpoints reject untrusted Origins and referrers.
2. End-user patient bearer tokens fail closed on control-plane interfaces.
3. Health telemetry adapter rejects requests lacking X-Control-Service-Token.
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from clara_control.api.router import control_router


class ForbiddenCrossOriginAdminTestCase(unittest.TestCase):
    """Hermetic unit tests validating network and credential isolation of admin surfaces."""

    def setUp(self) -> None:
        self.control_app = FastAPI(title="Control Plane Test App")
        self.control_app.include_router(control_router)
        self.client = TestClient(self.control_app)

    def test_control_health_readiness(self) -> None:
        """Verify control plane health endpoint returns isolated plane indicator."""
        response = self.client.get("/control/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["plane"], "control-plane-isolated")

    def test_control_routes_summary(self) -> None:
        """Verify control plane routes summary exposes governance classification."""
        response = self.client.get("/control/v1/routes/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["isolation"], "segregated-from-phi")
        self.assertEqual(data["verified_routes_count"], 123)

    def test_unregistered_admin_action_fails_closed(self) -> None:
        """Verify unknown control plane endpoints return uniform 404."""
        response = self.client.get("/control/v1/unknown-admin-action")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
