#!/usr/bin/env python3
"""Hermetic CLI runner for CLARA Care Multi-Tenant Billing Boundary Privacy Audit (PH04_A09).

Executes the comprehensive 44-vector billing privacy audit test suite and outputs
structured JSON telemetry summary.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    target_test = repo_root / "research" / "billing_tenant_privacy_audit" / "test_tenant_billing_boundary_audit.py"

    if not target_test.exists():
        print(f"[ERROR] Audit test file not found at {target_test}", file=sys.stderr)
        return 1

    print("=== CLARA Care Multi-Tenant Billing Boundary Privacy Audit (PH04_A09) ===")
    print(f"Target suite: {target_test}")
    print("Executing 44 boundary isolation, non-enumeration, and zero-PII vectors...")

    # Ensure repo_root and services/api/src are on sys.path for in-process pytest collection
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "services" / "api" / "src"))

    python_path = str(repo_root / "services" / "api" / "src")
    existing_pp = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{python_path}:{str(repo_root)}:{existing_pp}" if existing_pp else f"{python_path}:{str(repo_root)}"

    start_time = time.perf_counter()
    exit_code = pytest.main([
        "-v",
        str(target_test),
        "--tb=short",
    ])
    duration = time.perf_counter() - start_time

    summary = {
        "suite": "tenant_billing_boundary_audit",
        "phase": "PH04",
        "agent": "A09",
        "total_test_vectors": 44,
        "elapsed_seconds": round(duration, 3),
        "status": "PASS" if exit_code == 0 else "FAIL",
        "exit_code": int(exit_code),
        "categories_covered": [
            "tenant_meter_storage_isolation",
            "billing_aggregator_boundaries",
            "cross_tenant_metadata_disclosure_prevention",
            "zero_pii_zero_phi_billing_invariant",
            "side_channel_and_timing_isolation",
            "privacy_audit_receipts_and_tamper_evidence",
            "e2e_http_billing_gateway_rbac_idor",
        ],
    }

    print("\n--- Execution Summary ---")
    print(json.dumps(summary, indent=2))

    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
