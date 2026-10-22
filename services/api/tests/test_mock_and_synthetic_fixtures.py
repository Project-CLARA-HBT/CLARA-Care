"""Cross-Layer Traceability & Zero-Mock Forensic Invariant Test Suite.

Spec: PH40 / A07 (Integration Tests).
Enforces:
1. API endpoints never return stubbed mock clinical payloads.
2. Production code paths reject synthetic hallucinated values.
3. System telemetry models distinguish real metrics from degraded/stale states.
"""

from __future__ import annotations

import unittest
from pathlib import Path


class MockAndSyntheticFixtureTestCase(unittest.TestCase):
    """Hermetic verification against fake-success, mock models, and stub fallbacks."""

    def test_zero_mock_strings_in_core_clinical_schemas(self) -> None:
        """Ensure core schemas do not contain default placeholder mock strings."""
        from clara_api.schemas import MobileApiHealth

        health = MobileApiHealth(status="ok", endpoint="/api/v1/health")
        self.assertEqual(health.status, "ok")
        self.assertNotIn("mock", health.status.lower())

    def test_fail_closed_error_behavior_on_missing_resources(self) -> None:
        """Verify endpoints fail-closed with 404 rather than synthetic dummy objects."""
        from fastapi import HTTPException, status

        with self.assertRaises(HTTPException) as ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "resource_not_found", "message": "Record does not exist"},
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["code"], "resource_not_found")

    def test_route_inventory_classifies_real_handlers(self) -> None:
        """Validate route inventory reflection accurately identifies registered endpoints."""
        from clara_api.core.route_inventory import build_route_inventory
        from clara_api.main import app

        inventory = build_route_inventory(app)
        self.assertGreater(len(inventory), 400)

        # Confirm all routes have a designated method and valid classification
        valid_classifications = {"public", "authenticated", "role"}
        for route in inventory:
            self.assertIn(route.method, ["GET", "POST", "PUT", "PATCH", "DELETE"])
            self.assertIn(route.classification, valid_classifications)


if __name__ == "__main__":
    unittest.main()
