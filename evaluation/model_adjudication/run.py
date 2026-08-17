"""Run blinded independent structured reviews through an OpenAI-compatible router."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_URL = "https://router.theclaracare.com/v1"
MODELS = ("gemini-3.6-flash-high", "claude-sonnet-4-6")


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("model_review_manifest_not_object")
    if value.get("schema_version") != "clara-model-review-manifest.v1" or value.get("status") != "frozen":
        raise ValueError("model_review_manifest_not_frozen")
    if not isinstance(value.get("rubric"), dict) or not isinstance(value.get("cases"), list):
        raise TypeError("model_review_manifest_invalid")
    return value


def _call(*, model: str, prompt: str, retries: int = 2) -> dict[str, Any]:
    key = os.environ.get("CLARA_ROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("model_review_router_key_missing")
    # The configured router streams when response_format is supplied, despite an
    # explicit stream=false. The prompt and local parser enforce the contract.
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "stream": False}
    body = json.dumps(payload).encode()
    last_error = ""
    for attempt in range(retries + 1):
        started = time.monotonic()
        request = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload_bytes = response.read()
                content_type = response.headers.get_content_type()
            if content_type == "text/event-stream":
                chunks = []
                for line in payload_bytes.decode("utf-8").splitlines():
                    event_data = line.removeprefix("data:").strip()
                    if line.startswith("data:") and event_data != "[DONE]":
                        event = json.loads(event_data)
                        choice = event.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        if isinstance(delta.get("content"), str):
                            chunks.append(delta["content"])
                        elif isinstance(choice.get("message", {}).get("content"), str):
                            chunks.append(choice["message"]["content"])
                        elif isinstance(choice.get("text"), str):
                            chunks.append(choice["text"])
                content = "".join(chunks)
            else:
                parsed = json.loads(payload_bytes)
                content = parsed["choices"][0]["message"]["content"]
            review = json.loads(content)
            if not isinstance(review, dict) or not isinstance(review.get("label"), str) or not isinstance(review.get("rationale"), str):
                raise TypeError("model_review_response_schema_invalid")
            return {"model_id": model, "timestamp_utc": datetime.now(UTC).isoformat(), "attempt": attempt + 1, "latency_ms": round((time.monotonic() - started) * 1000, 3), "response_sha256": _sha(review), "review": review, "unsupported_parameters": []}
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = type(exc).__name__
            if attempt == retries:
                raise RuntimeError(f"model_review_call_failed:{last_error}") from exc
    raise RuntimeError("model_review_call_failed")


def run(*, manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = _load(manifest_path)
    rubric_hash = _sha(manifest["rubric"])
    prompt_template = "You are a blinded methodological reviewer. Return strict JSON only: {label:string,rationale:string,evidence_ids:list[string],confidence:number}. Do not infer hidden hypotheses, systems, or reviewer identity.\nRUBRIC:\n" + json.dumps(manifest["rubric"], sort_keys=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = output_dir / "raw"
    raw.mkdir(exist_ok=True)
    records: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise TypeError("model_review_case_invalid")
        prompt = prompt_template + "\nEVIDENCE:\n" + json.dumps(case.get("evidence", {}), sort_keys=True)
        row = {"case_id": case["case_id"], "prompt_sha256": _sha(prompt), "rubric_sha256": rubric_hash, "router_base_url": BASE_URL, "decoding": {"temperature": 0}, "reviews": []}
        for reviewer_id, model in zip(("reviewer_a", "reviewer_b"), MODELS, strict=True):
            result = _call(model=model, prompt=prompt)
            result["reviewer_id"] = reviewer_id
            row["reviews"].append(result)
        (raw / f"{case['case_id']}.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        records.append(row)
    summary = {"schema_version": "clara-model-review-run.v1", "status": "independent_reviews_complete", "manifest_sha256": _sha(manifest), "rubric_sha256": rubric_hash, "model_ids": list(MODELS), "router_base_url": BASE_URL, "case_count": len(records), "raw_outputs": [f"raw/{row['case_id']}.json" for row in records]}
    (output_dir / "model_review_results.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(manifest_path=args.manifest, output_dir=args.output_dir), sort_keys=True))
