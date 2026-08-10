"""Explicit capability boundary for the unimplemented Vital Trace comparator."""

UNSUPPORTED_BY_METHOD = "UNSUPPORTED_BY_METHOD"


def unsupported_operation(operation: str) -> dict[str, str]:
    """Return a machine-readable refusal instead of emulating GLHS features."""

    return {
        "status": UNSUPPORTED_BY_METHOD,
        "operation": operation,
        "reason": "public_reproducible_asset_not_source_reviewed",
    }
