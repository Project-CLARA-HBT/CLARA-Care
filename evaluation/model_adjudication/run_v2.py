"""W7 hardened review runner: strict validation, provider provenance, fail-closed transport.

Loads a ``clara-model-review-manifest.v2`` manifest, runs blinded independent reviews
through the OpenAI-compatible router, and records provider provenance. Unlike ``run.py``,
every field/range/evidence id is validated, unexpected keys are rejected, retries are
bounded, credentials are never retained, and malformed/truncated provider payloads fail
closed. Both JSON and SSE payloads are accepted even though ``stream=false`` is sent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_URL = "https://router.theclaracare.com/v1"
MODELS = ("gemini-3.6-flash-high", "claude-sonnet-4-6")
SCHEMA_VERSION = "clara-model-review-manifest.v2"
RUN_VERSION = "clara-model-review-run.v2"
RETRY_COUNT = 2

UrlOpen = Callable[..., Any]


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _reject_unexpected_keys(value: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"model_review_unexpected_keys:{where}:{','.join(unexpected)}")


def _validate_evidence(evidence: Any) -> list[str]:
    if isinstance(evidence, dict):
        if not evidence:
            raise ValueError("model_review_evidence_empty")
        ids = [key for key in evidence if isinstance(key, str) and key]
        if len(ids) != len(evidence):
            raise TypeError("model_review_evidence_id_invalid")
        return ids
    if isinstance(evidence, list):
        if not evidence:
            raise ValueError("model_review_evidence_empty")
        ids: list[str] = []
        for item in evidence:
            if (
                not isinstance(item, dict)
                or "id" not in item
                or not isinstance(item.get("id"), str)
                or not item["id"]
            ):
                raise TypeError("model_review_evidence_item_invalid")
            ids.append(item["id"])
        if len(set(ids)) != len(ids):
            raise ValueError("model_review_evidence_duplicate_ids")
        return ids
    raise TypeError("model_review_evidence_invalid")


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("model_review_manifest_malformed") from exc
    if not isinstance(value, dict):
        raise TypeError("model_review_manifest_not_object")
    _reject_unexpected_keys(
        value,
        {"schema_version", "status", "study_id", "models", "protocols", "rubric", "cases"},
        "manifest",
    )
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("model_review_manifest_schema_version_unsupported")
    if value.get("status") != "frozen":
        raise ValueError("model_review_manifest_not_frozen")
    if not isinstance(value.get("study_id"), str) or not value["study_id"].strip():
        raise ValueError("model_review_manifest_study_id_invalid")
    models = value.get("models")
    if not isinstance(models, list) or list(models) != list(MODELS):
        raise ValueError("model_review_manifest_models_not_locked")
    protocols = value.get("protocols")
    if not isinstance(protocols, dict) or not protocols:
        raise ValueError("model_review_manifest_protocols_empty")
    allowed_by_protocol: dict[str, tuple[str, ...]] = {}
    for name, spec in protocols.items():
        if not isinstance(spec, dict):
            raise TypeError(f"model_review_protocol_invalid:{name}")
        _reject_unexpected_keys(spec, {"allowed_labels", "description"}, f"protocol:{name}")
        labels = spec.get("allowed_labels")
        if (
            not isinstance(labels, list)
            or len(labels) < 2
            or any(not isinstance(label, str) or not label.strip() for label in labels)
            or len(set(labels)) != len(labels)
        ):
            raise ValueError(f"model_review_protocol_labels_invalid:{name}")
        allowed_by_protocol[name] = tuple(labels)
    rubric = value.get("rubric")
    if not isinstance(rubric, dict) or not rubric:
        raise ValueError("model_review_manifest_rubric_empty")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("model_review_manifest_cases_empty")
    case_ids: set[str] = set()
    normalized_cases: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            raise TypeError(f"model_review_case_invalid:{idx}")
        _reject_unexpected_keys(case, {"case_id", "protocol", "evidence"}, f"case:{idx}")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"model_review_case_id_invalid:{idx}")
        if case_id in case_ids:
            raise ValueError(f"model_review_case_id_duplicate:{case_id}")
        case_ids.add(case_id)
        protocol = case.get("protocol")
        if not isinstance(protocol, str) or protocol not in allowed_by_protocol:
            raise ValueError(f"model_review_case_protocol_unknown:{case_id}")
        evidence_ids = _validate_evidence(case.get("evidence"))
        normalized_cases.append(
            {
                "case_id": case_id,
                "protocol": protocol,
                "evidence": case["evidence"],
                "evidence_ids": evidence_ids,
            }
        )
    manifest = dict(value)
    manifest["cases"] = normalized_cases
    manifest["_allowed_by_protocol"] = allowed_by_protocol
    return manifest


def _parse_review_v2(
    *, content: str, allowed_labels: tuple[str, ...], available_evidence_ids: list[str]
) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    try:
        review = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("model_review_response_malformed_json") from exc
    if not isinstance(review, dict):
        raise TypeError("model_review_response_not_object")
    _reject_unexpected_keys(review, {"label", "rationale", "evidence_ids", "confidence"}, "review")
    label = review.get("label")
    if not isinstance(label, str) or label not in allowed_labels:
        raise ValueError("model_review_label_not_allowed")
    rationale = review.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("model_review_rationale_invalid")
    evidence_ids = review.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise ValueError("model_review_evidence_ids_invalid")
    if any(not isinstance(eid, str) or not eid for eid in evidence_ids):
        raise TypeError("model_review_evidence_id_not_string")
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("model_review_evidence_ids_duplicate")
    unknown = sorted(set(evidence_ids) - set(available_evidence_ids))
    if unknown:
        raise ValueError(f"model_review_evidence_ids_unknown:{','.join(unknown)}")
    confidence = review.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise TypeError("model_review_confidence_not_numeric")
    if not (0 <= confidence <= 1):
        raise ValueError("model_review_confidence_out_of_range")
    return {
        "label": label,
        "rationale": rationale,
        "evidence_ids": evidence_ids,
        "confidence": confidence,
    }


def _structured_content_v2(*, payload_bytes: bytes, content_type: str) -> str:
    """Extract OpenAI JSON or SSE completion text without accepting partial SSE."""

    if content_type == "text/event-stream":
        chunks: list[str] = []
        complete = False
        try:
            text = payload_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("model_review_sse_undecodable") from exc
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            event_data = line.removeprefix("data:").strip()
            if event_data == "[DONE]":
                complete = True
                continue
            if not event_data:
                continue
            try:
                event = json.loads(event_data)
            except json.JSONDecodeError as exc:
                raise ValueError("model_review_sse_malformed") from exc
            choices = event.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("model_review_sse_malformed")
            choice = choices[0]
            delta = choice.get("delta")
            content = delta.get("content") if isinstance(delta, dict) else None
            if content is None and isinstance(choice.get("message"), dict):
                content = choice["message"].get("content")
            if content is None:
                content = choice.get("text")
            if isinstance(content, str):
                chunks.append(content)
        if not complete or not chunks:
            raise ValueError("model_review_sse_incomplete")
        return "".join(chunks)
    try:
        parsed = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("model_review_response_malformed_json") from exc
    if (
        not isinstance(parsed, dict)
        or not isinstance(parsed.get("choices"), list)
        or not parsed["choices"]
    ):
        raise ValueError("model_review_response_malformed_json")
    message = parsed["choices"][0].get("message")
    if not isinstance(message, dict):
        raise TypeError("model_review_response_malformed_json")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("model_review_response_empty")
    return content


def _call(
    *,
    model: str,
    prompt: str,
    allowed_labels: tuple[str, ...],
    available_evidence_ids: list[str],
    retries: int = RETRY_COUNT,
    urlopen: UrlOpen | None = None,
) -> dict[str, Any]:
    key = (
        os.environ.get("ROUTER_API_KEY", "")
        or os.environ.get("CLARA_UNOFFICIAL_GEMINI_API_KEY", "")
        or os.environ.get("DEEPSEEK_API_KEY", "")
        or os.environ.get("CLARA_ROUTER_API_KEY", "")
    ).strip()
    if not key:
        raise RuntimeError("model_review_router_key_missing")
    opener = urlopen or urllib.request.urlopen
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "stream": False,
    }
    body = json.dumps(payload).encode()
    last_error = ""
    for attempt in range(1, retries + 2):
        started = time.monotonic()
        request = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with opener(request, timeout=120) as response:
                raw = response.read()
                content_type = response.headers.get_content_type()
                http_status = int(getattr(response, "status", getattr(response, "code", 200)))
            content = _structured_content_v2(payload_bytes=raw, content_type=content_type)
            review = _parse_review_v2(
                content=content,
                allowed_labels=allowed_labels,
                available_evidence_ids=available_evidence_ids,
            )
            return {
                "model_id": model,
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "attempts": attempt,
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "decoding": {"temperature": 0, "stream": False},
                "provider": {
                    "router_base_url": BASE_URL,
                    "http_status": http_status,
                    "content_type": content_type,
                    "raw_http_body_sha256": hashlib.sha256(raw).hexdigest(),
                    "parsed_review_sha256": _sha(review),
                },
                "review": review,
            }
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            KeyError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            last_error = type(exc).__name__
            if attempt > retries:
                raise RuntimeError(f"model_review_call_failed:{last_error}:{exc}") from exc
    raise RuntimeError(f"model_review_call_failed:{last_error}")


def run(
    *,
    manifest_path: Path,
    output_dir: Path,
    retries: int = RETRY_COUNT,
    urlopen: UrlOpen | None = None,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    allowed_by_protocol = manifest.pop("_allowed_by_protocol")
    prompt_template = (
        "You are a blinded methodological reviewer. Return strict JSON only: "
        '{"label":string,"rationale":string,"evidence_ids":list[string],"confidence":number}.\n'
        "Do not infer hidden hypotheses, systems, or reviewer identity.\n"
        "RUBRIC:\n" + json.dumps(manifest["rubric"], sort_keys=True)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = output_dir / "raw"
    raw.mkdir(exist_ok=True)
    records: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        prompt = prompt_template + "\nEVIDENCE:\n" + json.dumps(case["evidence"], sort_keys=True)
        row = {
            "case_id": case["case_id"],
            "protocol": case["protocol"],
            "allowed_labels": list(allowed_by_protocol[case["protocol"]]),
            "evidence_ids": case["evidence_ids"],
            "prompt_sha256": _sha(prompt),
            "rubric_sha256": _sha(manifest["rubric"]),
            "router_base_url": BASE_URL,
            "decoding": {"temperature": 0, "stream": False},
            "reviews": [],
        }
        for reviewer_id, model in zip(("reviewer_a", "reviewer_b"), MODELS, strict=True):
            result = _call(
                model=model,
                prompt=prompt,
                allowed_labels=allowed_by_protocol[case["protocol"]],
                available_evidence_ids=case["evidence_ids"],
                retries=retries,
                urlopen=urlopen,
            )
            result["reviewer_id"] = reviewer_id
            row["reviews"].append(result)
        (raw / f"{case['case_id']}.json").write_text(
            json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        records.append(row)
    summary = {
        "schema_version": RUN_VERSION,
        "status": "independent_reviews_complete",
        "manifest_sha256": _sha(manifest),
        "rubric_sha256": _sha(manifest["rubric"]),
        "models": list(MODELS),
        "router_base_url": BASE_URL,
        "case_count": len(records),
        "raw_outputs": [f"raw/{row['case_id']}.json" for row in records],
    }
    (output_dir / "model_review_results.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--retries", type=int, default=RETRY_COUNT)
    args = parser.parse_args()
    print(
        json.dumps(
            run(manifest_path=args.manifest, output_dir=args.output_dir, retries=args.retries),
            sort_keys=True,
        )
    )
