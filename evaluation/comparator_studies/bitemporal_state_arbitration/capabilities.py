UNSUPPORTED_BY_METHOD = "UNSUPPORTED_BY_METHOD"


def unsupported_operation(operation: str) -> dict[str, str]:
    return {
        "status": UNSUPPORTED_BY_METHOD,
        "operation": operation,
        "reason": "mechanism_mapping_excludes_governance_boundary",
    }
