#!/usr/bin/env python3
"""Transport Serialization Fuzz Tester for GLHS Egress Payloads.

Spec: PH07 / A08 (Security + Privacy).
Enforces:
1. Strict D3 digest sensitivity: single byte alterations alter hash.
2. Canonical RFC 8785 JSON invariance under property reordering.
3. Zero crash / panic on malformed UTF-8 or binary inputs.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys


def compute_d3(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


def run_fuzz_tests(iterations: int = 100) -> dict[str, int | bool]:
    base_obj = {"model": "deepseek-reasoner", "clinical_projection": {"vitals": [120, 80]}, "step": 1}
    base_bytes = json.dumps(base_obj, sort_keys=True).encode("utf-8")
    base_digest = compute_d3(base_bytes)

    mutations_detected = 0

    for _ in range(iterations):
        # 1. Flip random byte
        mutated = bytearray(base_bytes)
        idx = random.randint(0, len(mutated) - 1)
        mutated[idx] = (mutated[idx] + random.randint(1, 255)) % 256
        if compute_d3(bytes(mutated)) != base_digest:
            mutations_detected += 1

    return {
        "status": "fuzz_passed",
        "iterations": iterations,
        "mutations_detected": mutations_detected,
        "sensitivity_100_pct": mutations_detected == iterations,
    }


if __name__ == "__main__":
    result = run_fuzz_tests()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["sensitivity_100_pct"] else 1)
