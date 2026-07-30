"""Opt-in, privacy-safe execution of an approved CLARA-Eval VN manifest.

The checked-in fixtures are deliberately *not* executable clinical benchmarks.
This module accepts a separately governed manifest only when an operator
explicitly enables it.  It records case identifiers, status classes and timing
only; request bodies, response bodies and authentication material never enter
the generated report.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib import error, parse, request

from .config import DEFAULT_REQUIRED_METRICS, SuiteConfig
from .tracks import REQUIRED_TRACK_IDS


LIVE_MANIFEST_SCHEMA_VERSION = "clara-eval-vn.live-execution-manifest.v1"
MAX_RECORDS = 5000
MAX_REQUEST_BYTES = 32 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")
_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "email",
        "name",
        "password",
        "phone",
        "secret",
        "ssn",
    }
)
_ALLOWED_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "api": ("/api/v1/",),
    "ml": ("/v1/",),
}


class LiveEvaluationError(ValueError):
    """The operator-supplied live evaluation input is not safe to execute."""


@dataclass(frozen=True)
class LiveExecutionRecord:
    case_id: str
    track_id: str
    endpoint: Literal["api", "ml"]
    path: str
    request_body: dict[str, Any]
    metric_id: str
    json_path: str
    expected: Any
    critical_error_type: str | None
    ablation_variant: str | None


@dataclass(frozen=True)
class LiveManifest:
    path: Path
    sha256: str
    approval_reference: str
    retrieval_snapshot: dict[str, str] | None
    records: tuple[LiveExecutionRecord, ...]


def _is_enabled(value: str | None) -> bool:
    return value == "true"


def _load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveEvaluationError("live_manifest_unreadable") from exc
    if not isinstance(value, dict):
        raise LiveEvaluationError("live_manifest_not_object")
    return value, raw


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in _SENSITIVE_KEYS or _contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _parse_record(raw: Any) -> LiveExecutionRecord:
    if not isinstance(raw, dict):
        raise LiveEvaluationError("live_manifest_record_not_object")
    case_id = raw.get("case_id")
    track_id = raw.get("track_id")
    endpoint = raw.get("endpoint")
    path = raw.get("path")
    body = raw.get("request")
    scorer = raw.get("scorer")
    if not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id):
        raise LiveEvaluationError("live_manifest_case_id_invalid")
    if not isinstance(track_id, str) or track_id not in REQUIRED_TRACK_IDS:
        raise LiveEvaluationError("live_manifest_track_invalid")
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise LiveEvaluationError("live_manifest_endpoint_invalid")
    if not isinstance(path, str) or not path.startswith("/") or "?" in path:
        raise LiveEvaluationError("live_manifest_path_invalid")
    if not path.startswith(_ALLOWED_ENDPOINTS[endpoint]):
        raise LiveEvaluationError("live_manifest_path_not_allowlisted")
    if not isinstance(body, dict) or _contains_sensitive_key(body):
        raise LiveEvaluationError("live_manifest_request_has_sensitive_key")
    try:
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LiveEvaluationError("live_manifest_request_not_json") from exc
    if len(encoded_body) > MAX_REQUEST_BYTES:
        raise LiveEvaluationError("live_manifest_request_too_large")
    if not isinstance(scorer, dict):
        raise LiveEvaluationError("live_manifest_scorer_missing")
    if scorer.get("type") != "json_path_equals":
        raise LiveEvaluationError("live_manifest_scorer_not_supported")
    metric_id = scorer.get("metric_id")
    json_path = scorer.get("json_path")
    if (
        not isinstance(metric_id, str)
        or metric_id not in DEFAULT_REQUIRED_METRICS[track_id]
    ):
        raise LiveEvaluationError("live_manifest_metric_not_declared_for_track")
    if not isinstance(json_path, str) or not json_path or not all(
        part and part.replace("_", "").isalnum() for part in json_path.split(".")
    ):
        raise LiveEvaluationError("live_manifest_json_path_invalid")
    critical_error_type = raw.get("critical_error_type")
    if critical_error_type is not None and (
        not isinstance(critical_error_type, str)
        or not critical_error_type
        or len(critical_error_type) > 100
    ):
        raise LiveEvaluationError("live_manifest_critical_error_type_invalid")
    ablation_variant = raw.get("ablation_variant")
    if ablation_variant is not None and ablation_variant not in {"C0", "C1", "C2", "C3", "C4"}:
        raise LiveEvaluationError("live_manifest_ablation_variant_invalid")
    return LiveExecutionRecord(
        case_id=case_id,
        track_id=track_id,
        endpoint=endpoint,
        path=path,
        request_body=body,
        metric_id=metric_id,
        json_path=json_path,
        expected=scorer.get("expected"),
        critical_error_type=critical_error_type,
        ablation_variant=ablation_variant,
    )


def load_live_manifest(path: Path, *, repository_root: Path) -> LiveManifest:
    """Validate a separately approved manifest before any request is sent."""

    if not path.is_absolute():
        raise LiveEvaluationError("live_manifest_path_must_be_absolute")
    try:
        path.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise LiveEvaluationError("live_manifest_must_not_be_checked_in")
    raw, encoded = _load_json(path)
    if raw.get("schema_version") != LIVE_MANIFEST_SCHEMA_VERSION:
        raise LiveEvaluationError("live_manifest_schema_unsupported")
    approval = raw.get("approval")
    if not isinstance(approval, dict) or approval.get("approved_for_live_execution") is not True:
        raise LiveEvaluationError("live_manifest_not_approved")
    reference = approval.get("reference")
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 200:
        raise LiveEvaluationError("live_manifest_approval_reference_invalid")
    if raw.get("contains_phi") is not False or raw.get("contains_secrets") is not False:
        raise LiveEvaluationError("live_manifest_sensitive_content_forbidden")
    records_raw = raw.get("records")
    if not isinstance(records_raw, list) or not records_raw or len(records_raw) > MAX_RECORDS:
        raise LiveEvaluationError("live_manifest_records_invalid")
    records = tuple(_parse_record(record) for record in records_raw)
    if len({record.case_id for record in records}) != len(records):
        raise LiveEvaluationError("live_manifest_case_ids_not_unique")
    snapshot = raw.get("retrieval_snapshot")
    if snapshot is not None:
        if (
            not isinstance(snapshot, dict)
            or set(snapshot) != {"reference", "sha256"}
            or not isinstance(snapshot["reference"], str)
            or not isinstance(snapshot["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", snapshot["sha256"])
        ):
            raise LiveEvaluationError("live_manifest_retrieval_snapshot_invalid")
        snapshot = {"reference": snapshot["reference"], "sha256": snapshot["sha256"]}
    return LiveManifest(
        path=path,
        sha256=hashlib.sha256(encoded).hexdigest(),
        approval_reference=reference.strip(),
        retrieval_snapshot=snapshot,
        records=records,
    )


def _base_url(endpoint: str) -> str:
    variable = "CLARA_EVAL_API_BASE_URL" if endpoint == "api" else "CLARA_EVAL_ML_BASE_URL"
    base = os.environ.get(variable, "").strip().rstrip("/")
    parsed = parse.urlparse(base)
    if not base or parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise LiveEvaluationError(f"live_endpoint_{endpoint}_missing_or_invalid")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LiveEvaluationError(f"live_endpoint_{endpoint}_unsafe")
    if parsed.scheme != "https" and not _is_enabled(os.environ.get("CLARA_EVAL_ALLOW_INSECURE_HTTP")):
        raise LiveEvaluationError(f"live_endpoint_{endpoint}_requires_https")
    return base


def _headers(endpoint: str) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token_var = "CLARA_EVAL_API_BEARER_TOKEN" if endpoint == "api" else "CLARA_EVAL_ML_BEARER_TOKEN"
    token = os.environ.get(token_var, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if endpoint == "ml":
        internal_key = os.environ.get("CLARA_EVAL_ML_INTERNAL_KEY", "").strip()
        if internal_key:
            headers["X-ML-Internal-Key"] = internal_key
    return headers


def _read_json_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _execute_record(record: LiveExecutionRecord, *, timeout_seconds: float) -> dict[str, Any]:
    start = time.perf_counter()
    status: int | None = None
    outcome = "error"
    error_class: str | None = None
    passed: bool | None = None
    try:
        payload = json.dumps(record.request_body, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{_base_url(record.endpoint)}{record.path}",
            data=payload,
            headers=_headers(record.endpoint),
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:  # nosec B310: operator-approved base URL
            status = int(response.status)
            raw_response = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw_response) > MAX_RESPONSE_BYTES:
            outcome = "response_too_large"
        else:
            try:
                response_json = json.loads(raw_response)
            except json.JSONDecodeError:
                outcome = "response_not_json"
            else:
                passed = _read_json_path(response_json, record.json_path) == record.expected
                outcome = "pass" if passed else "fail"
    except error.HTTPError as exc:
        status = int(exc.code)
        outcome = "http_error"
        error_class = f"http_{status}"
    except (error.URLError, OSError, TimeoutError) as exc:
        error_class = type(exc).__name__
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
    return {
        # Case IDs may be traceable in an external governed registry.  The
        # public/local artifact gets a stable opaque reference instead.
        "case_ref": hashlib.sha256(record.case_id.encode("utf-8")).hexdigest()[:16],
        "track_id": record.track_id,
        "endpoint": record.endpoint,
        "path": record.path,
        "metric_id": record.metric_id,
        "critical_error_type": record.critical_error_type,
        "ablation_variant": record.ablation_variant,
        "status_code": status,
        "duration_ms": duration_ms,
        "outcome": outcome,
        "passed": passed,
        "error_class": error_class,
    }


def maybe_execute_live(
    config: SuiteConfig, *, repository_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run an external approved manifest only under explicit operator control.

    The returned metadata is safe to embed in artifacts.  The manifest itself,
    request payloads, responses and credentials are intentionally excluded.
    """

    command = "CLARA_EVAL_LIVE_EXECUTION_ENABLED=true CLARA_EVAL_LIVE_MANIFEST=/absolute/path/to/approved.json make eval-nightly"
    if not _is_enabled(os.environ.get("CLARA_EVAL_LIVE_EXECUTION_ENABLED")):
        return (
            {
                "state": "not_requested",
                "reason": "Live execution is disabled; set CLARA_EVAL_LIVE_EXECUTION_ENABLED=true and provide an externally governed manifest.",
                "measurement_command": command,
            },
            [],
        )
    if not config.requires_live_dependencies:
        return (
            {
                "state": "blocked",
                "reason": "This suite is offline-only and cannot execute live endpoints.",
                "measurement_command": command,
            },
            [],
        )
    manifest_path = os.environ.get("CLARA_EVAL_LIVE_MANIFEST", "").strip()
    if not manifest_path:
        return (
            {
                "state": "blocked",
                "reason": "No external approved live manifest was supplied.",
                "measurement_command": command,
            },
            [],
        )
    manifest = load_live_manifest(Path(manifest_path), repository_root=repository_root)
    timeout_raw = os.environ.get("CLARA_EVAL_LIVE_TIMEOUT_SECONDS", "20")
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise LiveEvaluationError("live_timeout_invalid") from exc
    if not 1 <= timeout_seconds <= 120:
        raise LiveEvaluationError("live_timeout_out_of_range")
    traces = [_execute_record(record, timeout_seconds=timeout_seconds) for record in manifest.records]
    return (
        {
            "state": "executed",
            "manifest_sha256": manifest.sha256,
            "approval_reference": manifest.approval_reference,
            "record_count": len(traces),
            "completed_count": sum(trace["passed"] is not None for trace in traces),
            "failed_request_count": sum(trace["passed"] is None for trace in traces),
            "retrieval_snapshot": manifest.retrieval_snapshot,
            "measurement_command": command,
        },
        traces,
    )
