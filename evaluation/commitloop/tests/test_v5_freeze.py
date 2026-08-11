from __future__ import annotations

from datetime import UTC, datetime

import pytest

from evaluation.commitloop.v5_freeze import (
    REQUIRED_VALIDATION_GATES,
    V5FreezeError,
    _validate_evidence,
)


def _evidence() -> dict[str, object]:
    return {
        "schema_version": "commitloop-v5-validation-evidence.v1",
        "validated_git_sha": "a" * 40,
        "provider_calls_before_freeze": 0,
        "commands": [
            {
                "gate": gate,
                "command": f"validate {gate}",
                "exit_code": 0,
                "result": "passed",
                "completed_at_utc": datetime.now(UTC).isoformat(),
            }
            for gate in sorted(REQUIRED_VALIDATION_GATES)
        ],
    }


def test_validation_evidence_requires_exact_sha_zero_calls_and_all_gates() -> None:
    evidence = _evidence()
    _validate_evidence(evidence, git_sha="a" * 40)

    evidence["provider_calls_before_freeze"] = 1
    with pytest.raises(V5FreezeError, match="validation_evidence_invalid"):
        _validate_evidence(evidence, git_sha="a" * 40)

    evidence = _evidence()
    evidence["commands"] = list(evidence["commands"])[1:]
    with pytest.raises(V5FreezeError, match="validation_gates_missing"):
        _validate_evidence(evidence, git_sha="a" * 40)
