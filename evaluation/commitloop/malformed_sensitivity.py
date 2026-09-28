"""Phase 12 (E12): Prospective 12-Class Error Taxonomy and Sensitivity Recovery Arms.

Implements the 12-class error taxonomy and evaluates sensitivity recovery arms
R0 (ITT primary), R1 (deterministic local repair), R2 (1 identical prompt retry),
and R3 (1 constrained repair prompt).
"""

from __future__ import annotations

import json
import re
from typing import Any

TAXONOMY_12_CLASSES = (
    "invalid_json",
    "schema_mismatch",
    "truncation",
    "refusal",
    "empty_response",
    "provider_error",
    "wrong_model",
    "timeout",
    "content_format_violation",
    "semantic_failure",
    "rate_limit",
    "unclassified",
)

TAXONOMY_12_CLASSES_CANONICAL = TAXONOMY_12_CLASSES

TAXONOMY_12_CLASSES_FROZEN_PROTOCOL = (
    "invalid_json",
    "schema_mismatch",
    "truncation",
    "refusal",
    "empty_response",
    "provider_error",
    "wrong_model",
    "timeout",
    "content_format_violation",
    "semantic_failure",
    "rate_limit_exhaustion",
    "unclassified_error",
)

TAXONOMY_CLASS_ALIASES: dict[str, str] = {
    "rate_limit_exhaustion": "rate_limit",
    "rate_limit": "rate_limit",
    "ratelimit": "rate_limit",
    "429": "rate_limit",
    "quota_exceeded": "rate_limit",
    "unclassified_error": "unclassified",
    "unclassified": "unclassified",
    "unknown_error": "unclassified",
}


def normalize_error_class(class_name: str | None) -> str | None:
    """Normalize any error class string to the canonical 12-class taxonomy name."""
    if not class_name:
        return None
    cleaned = str(class_name).strip().lower()
    return TAXONOMY_CLASS_ALIASES.get(cleaned, cleaned)

REQUIRED_PREDICTION_KEYS = {"lifecycle_state", "evidence_state", "timeliness_state"}

VALID_LIFECYCLE_STATES = {
    "OPEN",
    "PARTIALLY_SATISFIED",
    "SATISFIED",
    "SUPERSEDED",
    "CANCELLED",
}
VALID_EVIDENCE_STATES = {"CLEAR", "CONFLICTED", "INSUFFICIENT_EVIDENCE"}
VALID_TIMELINESS_STATES = {
    "NOT_APPLICABLE",
    "BEFORE_DUE",
    "IN_GRACE",
    "OVERDUE",
    "UNKNOWN",
}


def classify_error_12_class(
    error_type: object,
    error_detail: object = None,
    content: object = None,
) -> str:
    """Classify a provider response failure into the prospective 12-class taxonomy.

    Evaluates error type, error detail message, and raw content body to assign
    exactly one taxonomy class.
    """
    diag = str(error_detail or "").lower()
    name = str(error_type or "").lower()
    text = str(content or "").strip()
    combined = f"{name} {diag}"

    if any(k in combined for k in ("rate_limit", "429", "quota_exceeded", "ratelimit")):
        return "rate_limit"
    if any(k in combined for k in ("timeout", "timed_out")):
        return "timeout"
    if any(k in combined for k in ("wrong_model", "model_substitution", "model_mismatch")):
        return "wrong_model"
    if any(k in combined for k in ("500", "502", "503", "provider_error", "http_error", "bad gateway")):
        return "provider_error"
    if not text and any(k in combined for k in ("empty", "no_content")) or (not text and not combined.strip()):
        return "empty_response"
    if any(k in combined for k in ("refusal", "safety", "policy_violation")) or text.startswith("I cannot") or text.startswith("As an AI"):
        return "refusal"
    if any(k in combined for k in ("truncat", "max_tokens", "length")) or (text.startswith("```") and not text.endswith("```")):
        return "truncation"
    if any(k in combined for k in ("format", "markdown", "fence", "content_format")):
        return "content_format_violation"
    if any(k in combined for k in ("jsondecodeerror", "invalid_json", "json_decode_error")):
        return "invalid_json"
    if any(k in combined for k in ("schema", "missing_key")):
        return "schema_mismatch"
    if any(k in combined for k in ("semantic", "invalid_enum")):
        return "semantic_failure"

    if text:
        if text.startswith("```") and not text.endswith("```"):
            return "truncation"
        if text.startswith("```") and "```" in text[3:]:
            return "content_format_violation"
        if text.startswith("{") or text.startswith("[") or "json" in combined:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    if not REQUIRED_PREDICTION_KEYS.issubset(parsed.keys()):
                        return "schema_mismatch"
                    if (
                        parsed.get("lifecycle_state") not in VALID_LIFECYCLE_STATES
                        or parsed.get("evidence_state") not in VALID_EVIDENCE_STATES
                        or parsed.get("timeliness_state") not in VALID_TIMELINESS_STATES
                    ):
                        return "semantic_failure"
            except json.JSONDecodeError:
                return "invalid_json"

    return "unclassified"


def validate_prediction_schema(parsed: Any) -> bool:
    """Verify that a parsed dictionary conforms to the prediction schema."""
    if not isinstance(parsed, dict):
        return False
    if not REQUIRED_PREDICTION_KEYS.issubset(parsed.keys()):
        return False
    if parsed.get("lifecycle_state") not in VALID_LIFECYCLE_STATES:
        return False
    if parsed.get("evidence_state") not in VALID_EVIDENCE_STATES:
        return False
    if parsed.get("timeliness_state") not in VALID_TIMELINESS_STATES:
        return False
    return True


def repair_local_json_r1(raw_content: str) -> dict[str, Any] | None:
    """Execute deterministic local JSON repair (Arm R1) without network calls.

    Steps:
    1. Strip markdown code fences (```json ... ``` or ``` ... ```).
    2. Extract substring between first `{` and last `}`.
    3. Remove trailing commas before `}` or `]`.
    4. Attempt json.loads and validate against prediction schema.
    """
    if not raw_content or not isinstance(raw_content, str):
        return None

    cleaned = raw_content.strip()

    # Step 1: Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().endswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Step 2: Extract JSON object payload
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]

    # Step 3: Remove trailing commas
    cleaned = re.sub(r",\s*([\}\]])", r"\1", cleaned)

    # Step 4: Parse and validate
    try:
        parsed = json.loads(cleaned)
        if validate_prediction_schema(parsed):
            return parsed
    except Exception:
        pass

    return None


def evaluate_sensitivity_arms(
    cell_outputs: list[dict[str, Any]],
    gold_by_case: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate recovery arms R0, R1, R2, R3 over a cohort run.

    Each cell_output contains:
    - case_id, model, condition, key
    - raw_content (initial attempt)
    - initial_error (if any)
    - retry_content / retry_error (attempt 2 for R2/R3)
    - constrained_repair_content / error (attempt 2 for R3)
    """
    total_cells = len(cell_outputs)
    r0_correct = 0
    r1_correct = 0
    r2_correct = 0
    r3_correct = 0

    error_counts: dict[str, int] = {cls: 0 for cls in TAXONOMY_12_CLASSES}
    stratified_errors: dict[str, dict[str, int]] = {}

    r1_repairs = 0
    r2_repairs = 0
    r3_repairs = 0

    for cell in cell_outputs:
        case_id = str(cell.get("case_id"))
        gold = gold_by_case.get(case_id, {})
        model = str(cell.get("model", "unknown"))
        condition = str(cell.get("condition", "unknown"))
        stratum = str(cell.get("stratum", "default"))

        raw_content = str(cell.get("raw_content", ""))
        initial_error = cell.get("initial_error")
        initial_diag = cell.get("initial_error_detail")

        # R0 (ITT Raw) evaluation
        r0_pred = cell.get("prediction") if isinstance(cell.get("prediction"), dict) else None
        is_r0_valid = validate_prediction_schema(r0_pred)
        is_r0_correct = is_r0_valid and all(
            r0_pred.get(axis) == gold.get(axis) for axis in ("lifecycle_state", "evidence_state", "timeliness_state")
        )
        if is_r0_correct:
            r0_correct += 1

        if not is_r0_valid:
            err_class = classify_error_12_class(initial_error, initial_diag, raw_content)
            error_counts[err_class] += 1

            strat_key = f"{model}:{condition}:{stratum}"
            if strat_key not in stratified_errors:
                stratified_errors[strat_key] = {cls: 0 for cls in TAXONOMY_12_CLASSES}
            stratified_errors[strat_key][err_class] += 1

        # R1 (Local Repair) evaluation
        if is_r0_correct:
            r1_correct += 1
        else:
            r1_parsed = repair_local_json_r1(raw_content)
            if r1_parsed and validate_prediction_schema(r1_parsed):
                r1_repairs += 1
                if all(r1_parsed.get(axis) == gold.get(axis) for axis in ("lifecycle_state", "evidence_state", "timeliness_state")):
                    r1_correct += 1

        # R2 (1 Identical Retry) evaluation
        if is_r0_correct:
            r2_correct += 1
        else:
            retry_pred = cell.get("retry_prediction") if isinstance(cell.get("retry_prediction"), dict) else None
            if not retry_pred:
                retry_raw = str(cell.get("retry_content", ""))
                try:
                    retry_pred = json.loads(retry_raw)
                except Exception:
                    retry_pred = None

            if validate_prediction_schema(retry_pred):
                r2_repairs += 1
                if all(retry_pred.get(axis) == gold.get(axis) for axis in ("lifecycle_state", "evidence_state", "timeliness_state")):
                    r2_correct += 1

        # R3 (1 Constrained Repair Prompt) evaluation
        if is_r0_correct:
            r3_correct += 1
        else:
            repair_pred = cell.get("r3_prediction") if isinstance(cell.get("r3_prediction"), dict) else None
            if not repair_pred:
                r3_raw = str(cell.get("r3_content", ""))
                r3_repaired = repair_local_json_r1(r3_raw)
                repair_pred = r3_repaired if r3_repaired else None

            if validate_prediction_schema(repair_pred):
                r3_repairs += 1
                if all(repair_pred.get(axis) == gold.get(axis) for axis in ("lifecycle_state", "evidence_state", "timeliness_state")):
                    r3_correct += 1

    initial_malformed_cells = sum(error_counts.values())

    return {
        "schema_version": "commitloop-malformed-sensitivity.v8-q2-r2",
        "total_cells": total_cells,
        "initial_malformed_cells": initial_malformed_cells,
        "initial_malformed_rate": initial_malformed_cells / total_cells if total_cells else 0.0,
        "taxonomy_12_class_counts": error_counts,
        "stratified_errors": stratified_errors,
        "arms": {
            "R0_ITT_Primary": {
                "correct_cells": r0_correct,
                "accuracy": r0_correct / total_cells if total_cells else 0.0,
                "repair_count": 0,
            },
            "R1_Local_Repair": {
                "correct_cells": r1_correct,
                "accuracy": r1_correct / total_cells if total_cells else 0.0,
                "repair_count": r1_repairs,
                "accuracy_gain_over_r0": (r1_correct - r0_correct) / total_cells if total_cells else 0.0,
            },
            "R2_Identical_Retry": {
                "correct_cells": r2_correct,
                "accuracy": r2_correct / total_cells if total_cells else 0.0,
                "repair_count": r2_repairs,
                "accuracy_gain_over_r0": (r2_correct - r0_correct) / total_cells if total_cells else 0.0,
            },
            "R3_Constrained_Repair": {
                "correct_cells": r3_correct,
                "accuracy": r3_correct / total_cells if total_cells else 0.0,
                "repair_count": r3_repairs,
                "accuracy_gain_over_r0": (r3_correct - r0_correct) / total_cells if total_cells else 0.0,
            },
        },
    }
