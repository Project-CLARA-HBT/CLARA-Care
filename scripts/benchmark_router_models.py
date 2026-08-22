"""Minimal non-clinical stability benchmark for OpenAI-compatible model routers.

It deliberately stores only aggregate latency, success and JSON-contract
metrics.  No patient data, free-text answer or credential is written.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# Ensure project modules are importable
REPO_ROOT = Path(__file__).resolve().parent.parent
ML_SRC = REPO_ROOT / "services" / "ml" / "src"
if str(ML_SRC) not in sys.path:
    sys.path.insert(0, str(ML_SRC))

# Auto-reexec with local venv python if running on system python lacking dependencies
VENV_PYTHON = REPO_ROOT / "services" / "ml" / ".venv" / "bin" / "python3"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    try:
        import pydantic_settings  # noqa: F401
    except ImportError:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

from clara_ml.config import Settings  # noqa: E402
from clara_ml.llm.deepseek_client import DeepSeekClient  # noqa: E402

DEFAULT_MODELS = (
    "gemini-3.7-flash-tiered",
    "gemini-3.6-flash-high",
    "gemini-3.1-pro",
    "claude-sonnet-4.6",
    "antigravity/gemini-3.7-flash-tiered",
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
    "antigravity/gpt-oss-120b-medium",
    "antigravity/claude-sonnet-4-6-low",
    "antigravity/claude-sonnet-4-6-medium",
    "antigravity/claude-sonnet-4-6-high",
    "antigravity/claude-opus-4-6-thinking-low",
    "antigravity/claude-opus-4-6-thinking-medium",
    "antigravity/claude-opus-4-6-thinking-high",
    "no-think/antigravity/claude-sonnet-4-6",
    "no-think/antigravity/claude-opus-4-6-thinking",
)


def get_models(
    cli_models: list[str] | None = None,
    api_key: str = "",
    base_url: str = "",
) -> list[str]:
    if cli_models:
        models = []
        for m in cli_models:
            for part in m.split(","):
                if part.strip():
                    models.append(part.strip())
        if models:
            return models

    raw = os.environ.get("BENCHMARK_MODELS", "").strip()
    if raw.lower() == "all":
        base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL", "")).rstrip("/")
        api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if base_url and api_key:
            req = urllib.request.Request(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    return [str(m["id"]) for m in data.get("data", [])]
            except Exception:
                pass
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return list(DEFAULT_MODELS)


def _one(
    model: str,
    run: int,
    api_key: str,
    base_url: str,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        client = DeepSeekClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            fallback_model="",
            timeout_seconds=timeout_seconds,
            retries_per_base=0,
            max_concurrency=8,
            min_interval_seconds=0,
            request_jitter_seconds=0,
        )
        response = client.generate('Return valid JSON only: {"ok": true}', max_tokens=32)
        content = response.content.strip()
        try:
            cleaned = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            json_valid = isinstance(json.loads(cleaned), dict)
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
    parser = argparse.ArgumentParser(
        description="Benchmark OpenAI-compatible model routers for stability, latency, and conformance."
    )
    parser.add_argument(
        "--model",
        "--models",
        dest="models",
        action="append",
        help="Target model(s) to benchmark. Can be specified multiple times or comma-separated.",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output",
        type=str,
        default=os.environ.get("BENCHMARK_OUTPUT", ""),
        help="Path to write the JSON results file.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=int(os.environ.get("BENCHMARK_RUNS", "3")),
        help="Number of benchmark runs per model (default: 3).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("BENCHMARK_WORKERS", "6")),
        help="Max concurrent worker threads (default: 6).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("BENCHMARK_TIMEOUT", "15")),
        help="Request timeout in seconds (default: 15).",
    )
    args = parser.parse_args()

    settings = Settings()
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ROUTER_API_KEY") or settings.deepseek_api_key
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("ROUTER_BASE_URL") or settings.deepseek_base_url

    models = get_models(cli_models=args.models, api_key=api_key, base_url=base_url)
    runs_per_model = args.runs
    max_workers = args.workers
    timeout_seconds = args.timeout

    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_one, model, run, api_key, base_url, timeout_seconds)
            for model in models
            for run in range(1, runs_per_model + 1)
        ]
        for future in concurrent.futures.as_completed(futures):
            records.append(future.result())

    aggregate: list[dict[str, Any]] = []
    for model in models:
        items = [item for item in records if item["model"] == model]
        latencies = sorted(float(item["latency_ms"]) for item in items)
        successes = sum(bool(item["success"]) for item in items)
        json_valid = sum(bool(item["json_valid"]) for item in items)
        p50 = round(statistics.median(latencies), 1) if latencies else 0.0
        p95 = latencies[-1] if latencies else 0.0
        aggregate.append(
            {
                "model": model,
                "runs": len(items),
                "successes": successes,
                "json_valid": json_valid,
                "p50_ms": p50,
                "p95_ms": p95,
                "error_types": sorted(
                    {str(item["error_type"]) for item in items if item["error_type"]}
                ),
            }
        )

    output_data = {"schema_version": "router-smoke-v1", "models": aggregate}
    output_json = json.dumps(output_data, indent=2)

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json + "\n", encoding="utf-8")

    print(output_json)


if __name__ == "__main__":
    main()
