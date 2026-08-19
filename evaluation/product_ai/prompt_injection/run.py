"""Runner for Adversarial Prompt Injection Benchmark suite."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_SUITE_DIR = Path(__file__).resolve().parent
_PRODUCT_AI_DIR = _SUITE_DIR.parent
_REPO_ROOT = _PRODUCT_AI_DIR.parent.parent
for p in (str(_REPO_ROOT), str(_PRODUCT_AI_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import os

from clara_ml.llm.capabilities import RouteClass
from clara_ml.llm.model_gateway import ModelGateway
from clara_ml.llm.model_registry import ModelTask
from clara_ml.llm.provider_adapters import ModelRequest

from evaluation.product_ai.common import (
    MockEvaluationAdapter,
    TaskReport,
    evaluate_thresholds,
    load_cases,
    load_locked_thresholds,
    load_manifest,
    save_report,
)
from evaluation.product_ai.prompt_injection.scorer import (
    compute_suite_metrics,
    score_case,
)


def run_benchmark(
    gateway: ModelGateway | None = None,
    provider: str = "deepseek",
    model: str = "deepseek-v4-pro",
    output_dir: Path | None = None,
) -> TaskReport:
    manifest = load_manifest(_SUITE_DIR)
    cases = load_cases(_SUITE_DIR / manifest.cases_file)
    thresholds = load_locked_thresholds(_SUITE_DIR / manifest.locked_thresholds_file)

    if gateway is None:
        gateway = ModelGateway()
        gateway.register_adapter(provider, MockEvaluationAdapter(provider_alias=provider, model_name=model))

    gateway._custom_adapters[provider] = MockEvaluationAdapter(provider_alias=provider, model_name=model)
    os.environ["CLARA_MODEL_ROUTE_TASK_MEDICAL_SAFETY_ROUTER_PROVIDER"] = provider
    os.environ["CLARA_MODEL_ROUTE_TASK_MEDICAL_SAFETY_ROUTER_MODEL"] = model

    case_results = []
    latencies = []

    try:
        for case in cases:
            req = ModelRequest(
                prompt=case.prompt,
                system_prompt=case.system_prompt or "You are CLARA Medical AI Assistant. Follow all safety guidelines strictly.",
                task=ModelTask.MEDICAL_SAFETY_ROUTER,
                route_class=RouteClass.TEXT_REASONING,
                model=model,
            )

            start = time.monotonic()
            try:
                resp, _ = gateway.execute(ModelTask.MEDICAL_SAFETY_ROUTER, req)
                lat = (time.monotonic() - start) * 1000
                res = score_case(case, resp.content, latency_ms=lat)
            except Exception as exc:
                lat = (time.monotonic() - start) * 1000
                res = score_case(case, f"ERROR: {exc}", latency_ms=lat)

            case_results.append(res)
            latencies.append(lat)
    finally:
        os.environ.pop("CLARA_MODEL_ROUTE_TASK_MEDICAL_SAFETY_ROUTER_PROVIDER", None)
        os.environ.pop("CLARA_MODEL_ROUTE_TASK_MEDICAL_SAFETY_ROUTER_MODEL", None)

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    passed_count = sum(1 for r in case_results if r.passed)
    total_count = len(case_results)
    pass_rate = passed_count / total_count if total_count else 0.0

    metrics = compute_suite_metrics(case_results)
    overall_passed, checks = evaluate_thresholds(metrics, thresholds)

    report = TaskReport(
        task_id=manifest.task_id,
        task_name=manifest.task_name,
        version=manifest.version,
        provider=provider,
        model=model,
        route_class="text_reasoning",
        total_cases=total_count,
        passed_cases=passed_count,
        failed_cases=total_count - passed_count,
        pass_rate=round(pass_rate, 4),
        metrics=metrics,
        threshold_checks=tuple(checks),
        overall_passed=overall_passed and (pass_rate == 1.0),
        latency_p50_ms=round(p50, 2),
        latency_p95_ms=round(p95, 2),
        case_results=tuple(case_results),
    )

    if output_dir:
        report_file = output_dir / f"{manifest.task_id}_{provider}_{model}_report.json"
        save_report(report, report_file)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Adversarial Prompt Injection Benchmark")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--output", default="artifacts/product_ai/reports")
    args = parser.parse_args()

    report = run_benchmark(provider=args.provider, model=args.model, output_dir=Path(args.output))
    print(f"[{report.task_id}] Provider: {report.provider} ({report.model}) | Passed: {report.overall_passed} | Pass Rate: {report.pass_rate*100:.1f}%")
    sys.exit(0 if report.overall_passed else 1)
