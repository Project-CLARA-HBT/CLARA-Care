"""Common longitudinal evidence record contract for evaluation adapters."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "clara-common-longitudinal-evidence.v1"
REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "source_dataset",
        "source_subject",
        "source_record_id",
        "encounter_id",
        "evidence_type",
        "domain",
        "original_value",
        "normalized_value",
        "valid_time",
        "valid_time_field",
        "knowledge_time",
        "knowledge_time_field",
        "temporal_precision",
        "estimated_time",
        "source_provenance",
        "source_schema",
        "original_payload_pointer",
        "original_payload_sha256",
        "uncertainty",
        "missingness",
    }
)


class CommonEvidenceError(ValueError):
    """Raised when an adapter emits an invalid common evidence record."""


def validate_common_record(record: Mapping[str, Any]) -> None:
    if REQUIRED_FIELDS - set(record):
        raise CommonEvidenceError("common_record_fields_missing")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise CommonEvidenceError("common_record_schema_invalid")
    for field in (
        "source_dataset",
        "source_subject",
        "source_record_id",
        "evidence_type",
        "domain",
        "source_schema",
        "original_payload_pointer",
    ):
        if not isinstance(record.get(field), str) or not record[field]:
            raise CommonEvidenceError(f"common_record_{field}_invalid")
    if record.get("estimated_time") is not False:
        raise CommonEvidenceError("estimated_time_must_be_false_without_estimation_protocol")
    digest = record.get("original_payload_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CommonEvidenceError("common_record_payload_digest_invalid")
    if not isinstance(record.get("source_provenance"), dict):
        raise CommonEvidenceError("common_record_provenance_invalid")
    if not isinstance(record.get("uncertainty"), list) or not isinstance(
        record.get("missingness"), list
    ):
        raise CommonEvidenceError("common_record_uncertainty_invalid")
    if record.get("valid_time") is None and record.get("valid_time_field") is not None:
        raise CommonEvidenceError("common_record_valid_time_field_without_value")
    if record.get("knowledge_time") is None and record.get("knowledge_time_field") is not None:
        raise CommonEvidenceError("common_record_knowledge_time_field_without_value")
