#!/usr/bin/env python3
"""Hermetic CLI runner for CLARA Care Security Negative Test Suite (PH03_A09).

Executes the 36 security negative-test vectors and outputs structured JSON audit results.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest


def main() -> int:
    suite_path = Path(__file__).parent / "test_security_negative_vectors.py"
    print(f"=== CLARA Care Security Negative-Test Suite (PH03_A09) ===")
    print(f"Target suite: {suite_path}")
    print("Executing 36 negative-test vectors across 6 test classes...")

    t0 = time.time()
    # Run pytest programmatically
    args = [
        "-q",
        "--tb=short",
        str(suite_path),
    ]
    exit_code = pytest.main(args)
    elapsed = time.time() - t0

    result = {
        "suite": "security_negative_vectors",
        "phase": "PH03",
        "agent": "A09",
        "total_test_vectors": 36,
        "elapsed_seconds": round(elapsed, 3),
        "status": "PASS" if exit_code == 0 else "FAIL",
        "exit_code": int(exit_code),
        "categories_covered": [
            "expired_jwt_tokens",
            "wrong_signature_and_tampering",
            "malformed_authorization_headers",
            "cross_tenant_idor_object_isolation",
            "revoked_token_replay_denylist",
            "e2e_http_middleware_pipeline",
        ],
    }

    print("\n--- Execution Summary ---")
    print(json.dumps(result, indent=2))
    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
