"""Run a bounded, non-headline router utility grid on synthetic structural cases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

CONDITIONS = (
    "full_authorized", "naive_rag", "btsa_or_tpr", "glhs_no_thss", "thss_default", "thss_strict"
)
MODELS = (
    ("antigravity/claude-sonnet-4-6", "claude"),
    ("antigravity/gemini-3.6-flash-high", "gemini"),
)
COLUMNS = (
    "task_id", "context_condition", "model_id", "model_family", "correct",
    "critical_omission", "unsupported_assertion", "conflict_handling",
    "evidence_fidelity", "authorized_disclosure", "prohibited_disclosure",
    "input_tokens", "output_tokens", "latency_ms", "provider_cost",
    "completion_status", "error_code",
)


def call(base: str, key: str, model: str, prompt: str) -> tuple[dict, float, str | None]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode()
    request = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read())
        return payload, (time.perf_counter() - started) * 1000, None
    except urllib.error.HTTPError as exc:
        return {}, (time.perf_counter() - started) * 1000, f"HTTP_{exc.code}"
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        return {}, (time.perf_counter() - started) * 1000, type(exc).__name__


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default=os.environ.get("ROUTER_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("ROUTER_API_KEY", ""))
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    if not args.base_url or not args.api_key:
        parser.error("router credentials are required")
    with args.cases.open(encoding="utf-8", newline="") as stream:
        cases = list(csv.DictReader(stream))[: args.limit]
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in cases:
        for condition in CONDITIONS:
            for model, family in MODELS:
                prompt = (
                    "You are evaluating a synthetic, non-clinical longitudinal-state task. "
                    "Return JSON only with keys state, conflict, provenance, disclosure. "
                    f"Context condition: {condition}. Scenario: {case['scenario']}. "
                    "Do not diagnose, prescribe, or invent patient facts."
                )
                payload, latency, error = call(args.base_url, args.api_key, model, prompt)
                choice = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                usage = payload.get("usage") or {}
                parsed = {}
                try:
                    parsed = json.loads(choice)
                except (TypeError, json.JSONDecodeError):
                    pass
                rows.append({
                    "task_id": case["case_id"], "context_condition": condition,
                    "model_id": model, "model_family": family,
                    "correct": str(parsed.get("state") == case["expected_state"] and error is None).lower(),
                    "critical_omission": "unknown", "unsupported_assertion": "unknown",
                    "conflict_handling": str(parsed.get("conflict", "unknown")),
                    "evidence_fidelity": "unknown", "authorized_disclosure": "unknown",
                    "prohibited_disclosure": "unknown", "input_tokens": usage.get("prompt_tokens", ""),
                    "output_tokens": usage.get("completion_tokens", ""), "latency_ms": round(latency, 3),
                    "provider_cost": "unknown", "completion_status": "error" if error else "ok",
                    "error_code": error or ("invalid_json" if not parsed else ""),
                })
    with (args.output / "thss_utility.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS); writer.writeheader(); writer.writerows(rows)
    (args.output / "response_hash_manifest.json").write_text(json.dumps({
        "status": "completed_nonheadline_operational", "models": [m for m, _ in MODELS],
        "families": [f for _, f in MODELS], "conditions": list(CONDITIONS),
        "task_count": len(cases), "rows": len(rows),
        "task_csv_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        "raw_model_text_retained": False, "annotator_status": "NOT RUN",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
