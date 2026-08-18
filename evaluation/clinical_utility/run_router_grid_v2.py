"""W6: source-disjoint utility grid with ACTUAL condition-specific context bytes.

Fixes AUD-050: each (task, condition) renders real governed-context content via
``evaluation.clinical_utility.context_builders`` and the model sees those bytes,
never a ``Context condition: <label>`` string. Uses the locked models
``gemini-3.6-flash-high`` and ``claude-sonnet-4-6`` and reads the router key
only from ``CLARA_ROUTER_API_KEY``. Credentials are never written to artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from evaluation.clinical_utility.context_builders import CONDITIONS, build_context

ROUTER_BASE_URL = "https://router.theclaracare.com/v1"
MODELS = (
    ("gemini-3.6-flash-high", "gemini"),
    ("claude-sonnet-4-6", "claude"),
)

COLUMNS = (
    "task_id", "context_condition", "context_sha256", "model_id", "model_family",
    "state_correct", "critical_omission", "unsupported_assertion",
    "conflict_handling", "evidence_fidelity", "prohibited_disclosure",
    "authorized_recall", "abstention", "input_tokens", "output_tokens",
    "latency_ms", "completion_status", "error_code",
)

PROMPT_TEMPLATE = (
    "You are evaluating a synthetic, non-clinical longitudinal-state governance "
    "task. The governed context below is the ONLY information you may rely on. "
    "Return strict JSON only with keys: state (current state version), "
    "decision (committed|rejected|abstain, whether a bound persistent commit is "
    "authorized), conflict (any governance conflict or null), provenance_ok "
    "(true/false), abstain (true/false). Do not diagnose, prescribe, or invent "
    "patient facts.\n\nGOVERNED CONTEXT:\n{context}\n\nTASK:\n{task}"
)


@dataclass(frozen=True)
class CallResult:
    payload: dict[str, object]
    latency_ms: float
    error: str | None


def _call(base: str, key: str, model: str, prompt: str) -> CallResult:
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    import time

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload_bytes = response.read()
            content_type = response.headers.get_content_type()
        if content_type == "text/event-stream":
            chunks: list[str] = []
            for line in payload_bytes.decode("utf-8").splitlines():
                if not line.startswith("data:"):
                    continue
                event_data = line.removeprefix("data:").strip()
                if event_data == "[DONE]":
                    continue
                event = json.loads(event_data)
                choices = event.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                delta = choices[0].get("delta", {})
                if isinstance(delta.get("content"), str):
                    chunks.append(delta["content"])
            content = "".join(chunks)
            payload = {"choices": [{"message": {"content": content}}], "usage": {}}
        else:
            payload = json.loads(payload_bytes)
        return CallResult(payload, (time.monotonic() - started) * 1000.0, None)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return CallResult({}, (time.monotonic() - started) * 1000.0, type(exc).__name__)


def _parse(choice: str) -> dict[str, object]:
    value = choice.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value.strip("`").strip()
        if value.startswith("json"):
            value = value[4:].strip()
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except (TypeError, json.JSONDecodeError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True, help="JSON array of task dicts")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="0 = all tasks")
    args = parser.parse_args()

    key = os.environ.get("CLARA_ROUTER_API_KEY", "").strip()
    if not key:
        parser.error("CLARA_ROUTER_API_KEY is required")

    loaded = json.loads(args.tasks.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        tasks = loaded.get("tasks")
    else:
        tasks = loaded
    if not isinstance(tasks, list) or not tasks:
        parser.error("tasks must be a non-empty JSON array")
    if args.limit > 0:
        tasks = tasks[: args.limit]

    args.output_dir.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, object]] = []
    for task in tasks:
        task_id = str(task["task_id"])
        expected_state = task.get("expected_state")
        expected_decision = task.get("expected_decision")
        task_kind = task.get("task_kind", "state")
        for condition in CONDITIONS:
            built = build_context(task, condition)
            for model, family in MODELS:
                prompt = PROMPT_TEMPLATE.format(context=built.text, task=str(task.get("scenario", "")))
                result = _call(ROUTER_BASE_URL, key, model, prompt)
                choice = ((result.payload.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                usage = result.payload.get("usage") or {}
                parsed = _parse(str(choice))
                state = parsed.get("state")
                abstain = parsed.get("abstain") is True or parsed.get("state") is None
                if task_kind == "auth":
                    # Authorization tasks: the model reports the current state
                    # version plus a conflict/decision. Correct iff the reported
                    # decision matches expected_decision.
                    decision = parsed.get("decision") or (
                        "rejected" if parsed.get("conflict") and str(parsed.get("conflict")).lower() != "none" else "committed"
                    )
                    correct = (
                        result.error is None
                        and expected_decision is not None
                        and str(decision).lower() == str(expected_decision).lower()
                    )
                else:
                    correct = (
                        result.error is None
                        and expected_state is not None
                        and str(state) == str(expected_state)
                    )
                rows.append(
                    {
                        "task_id": task_id,
                        "context_condition": condition,
                        "context_sha256": built.sha256,
                        "model_id": model,
                        "model_family": family,
                        "state_correct": str(correct).lower(),
                        "critical_omission": "unknown",
                        "unsupported_assertion": "unknown",
                        "conflict_handling": str(parsed.get("conflict", "unknown")),
                        "evidence_fidelity": "unknown",
                        "prohibited_disclosure": "unknown",
                        "authorized_recall": "unknown",
                        "abstention": str(abstain).lower(),
                        "input_tokens": usage.get("prompt_tokens", ""),
                        "output_tokens": usage.get("completion_tokens", ""),
                        "latency_ms": round(result.latency_ms, 3),
                        "completion_status": "error" if result.error else "ok",
                        "error_code": result.error or ("invalid_json" if not parsed else ""),
                    }
                )

    with (args.output_dir / "utility_grid_v2.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "schema_version": "clara-utility-grid-v2.v1",
        "status": "completed",
        "router_base_url": ROUTER_BASE_URL,
        "models": [m for m, _ in MODELS],
        "conditions": list(CONDITIONS),
        "task_count": len(tasks),
        "row_count": len(rows),
        "raw_model_text_retained": False,
        "api_key_retained": False,
    }
    (args.output_dir / "grid_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
