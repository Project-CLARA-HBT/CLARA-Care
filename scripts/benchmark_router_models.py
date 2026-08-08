"""Minimal non-clinical stability benchmark for OpenAI-compatible model routers.

It deliberately stores only aggregate latency, success and JSON-contract
metrics.  No patient data, free-text answer or credential is written.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import statistics
import time
from typing import Any

from clara_ml.llm.deepseek_client import DeepSeekClient


MODELS = (
    "antigravity/gemini-3.6-flash-high",
    "antigravity/gemini-3.6-flash-medium",
    "antigravity/gemini-3.6-flash-low",
    "antigravity/claude-opus-4-6-thinking",
    "antigravity/claude-sonnet-4-6",
    "antigravity/gemini-pro-agent",
    "antigravity/gemini-3.1-pro-low",
    "antigravity/gemini-3-flash-agent",
    "antigravity/gemini-3.5-flash-low",
    "antigravity/gemini-3.5-flash-extra-low",
    "antigravity/gemini-3.1-flash-lite",
    "antigravity/gemini-2.5-flash-thinking",
    "antigravity/gemini-2.5-flash",
    "antigravity/gemini-2.5-flash-lite",
)


def _one(model: str, run: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        client = DeepSeekClient(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=os.environ["DEEPSEEK_BASE_URL"],
            model=model,
            fallback_model="",
            timeout_seconds=45,
            retries_per_base=0,
            max_concurrency=6,
            min_interval_seconds=0,
            request_jitter_seconds=0,
        )
        response = client.generate('Return valid JSON only: {"ok": true}', max_tokens=16)
        content = response.content.strip()
        try:
            json_valid = isinstance(
                json.loads(content.removeprefix("```json").removesuffix("```").strip()), dict
            )
        except (TypeError, ValueError):
            json_valid = False
        return {
            "model": model,
            "run": run,
            "success": bool(content),
            "json_valid": json_valid,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error_type": "",
        }
    except Exception as exc:  # no upstream request body/error is persisted
        return {
            "model": model,
            "run": run,
            "success": False,
            "json_valid": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error_type": exc.__class__.__name__,
        }


def main() -> None:
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [
            executor.submit(_one, model, run) for model in MODELS for run in range(1, 4)
        ]
        for future in concurrent.futures.as_completed(futures):
            records.append(future.result())

    aggregate: list[dict[str, Any]] = []
    for model in MODELS:
        items = [item for item in records if item["model"] == model]
        latencies = sorted(float(item["latency_ms"]) for item in items)
        aggregate.append(
            {
                "model": model,
                "runs": len(items),
                "successes": sum(bool(item["success"]) for item in items),
                "json_valid": sum(bool(item["json_valid"]) for item in items),
                "p50_ms": round(statistics.median(latencies), 1),
                "p95_ms": latencies[-1],
                "error_types": sorted(
                    {str(item["error_type"]) for item in items if item["error_type"]}
                ),
            }
        )
    print(json.dumps({"schema_version": "router-smoke-v1", "models": aggregate}))


if __name__ == "__main__":
    main()
