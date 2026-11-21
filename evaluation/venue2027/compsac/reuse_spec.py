"""Finite-domain business specifications. No access to either arm or its trace."""


def bank_instruction(operation, savings, checking):
    """Nominal signed increments in tenths of a currency unit, or refusal."""
    if operation == "deposit":
        return "checking", 13
    if operation == "withdraw":
        return ("savings", -202) if savings >= 20.2 else ("refused", 0)
    if operation == "check":
        return "checking", -50 if savings + checking >= 5 else -40
    raise ValueError(operation)


def finding_valid(refs, registry, field_bound):
    """Registry maps authorized revision IDs to their current field names."""
    return all(ref in registry and (not field_bound or registry[ref] == "history") for ref in refs)
