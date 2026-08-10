from evaluation.comparator_studies.vital_trace.capabilities import (
    UNSUPPORTED_BY_METHOD,
    unsupported_operation,
)


def test_glhs_only_operations_fail_closed_for_unimplemented_comparator() -> None:
    result = unsupported_operation("governed_write_with_consent_replay")
    assert result["status"] == UNSUPPORTED_BY_METHOD
    assert result["reason"] == "public_reproducible_asset_not_source_reviewed"
