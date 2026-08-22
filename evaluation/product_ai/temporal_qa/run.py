"""Runner for Personal Temporal QA Benchmark suite."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_SUITE_DIR = Path(__file__).resolve().parent
_PRODUCT_AI_DIR = _SUITE_DIR.parent
_REPO_ROOT = _PRODUCT_AI_DIR.parent.parent
_ML_SRC = _REPO_ROOT / "services" / "ml" / "src"
_API_SRC = _REPO_ROOT / "services" / "api" / "src"
for p in (str(_REPO_ROOT), str(_PRODUCT_AI_DIR), str(_ML_SRC), str(_API_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import os

from concurrent.futures import ThreadPoolExecutor

from clara_ml.llm.capabilities import RouteClass
from clara_ml.llm.model_gateway import ModelGateway
from clara_ml.llm.model_registry import ModelTask
from clara_ml.llm.provider_adapters import ModelRequest

from evaluation.product_ai.common import (
    CaseEvaluationResult,
    MockEvaluationAdapter,
    TaskCase,
    TaskReport,
    evaluate_thresholds,
    load_cases,
    load_locked_thresholds,
    load_manifest,
    save_report,
)
from evaluation.product_ai.temporal_qa.scorer import compute_suite_metrics, score_case


def run_benchmark(
    gateway: ModelGateway | None = None,
    provider: str = "deepseek",
    model: str = "deepseek-v4-pro",
    output_dir: Path | None = None,
    live: bool = False,
) -> TaskReport:
    manifest = load_manifest(_SUITE_DIR)
    cases = load_cases(_SUITE_DIR / manifest.cases_file)
    thresholds = load_locked_thresholds(_SUITE_DIR / manifest.locked_thresholds_file)

    if gateway is None:
        gateway = ModelGateway()
        if not live:
            gateway.register_adapter(
                provider, MockEvaluationAdapter(provider_alias=provider, model_name=model)
            )
    elif not live and provider not in gateway._custom_adapters:
        gateway.register_adapter(
            provider, MockEvaluationAdapter(provider_alias=provider, model_name=model)
        )

    os.environ["CLARA_MODEL_ROUTE_TASK_RAG_SYNTHESIS_PROVIDER"] = provider
    os.environ["CLARA_MODEL_ROUTE_TASK_RAG_SYNTHESIS_MODEL"] = model

    temporal_system_prompt = (
        "Bạn là trợ lý y tế CLARA theo dõi diễn tiến sức khỏe và hồ sơ cá nhân theo thời gian. "
        "Hãy trả lời chính xác dựa trên dữ liệu mới nhất/hiện tại, phân biệt rõ thuốc/chỉ số hiện tại "
        "với các dữ liệu cũ đã ngừng, thay đổi hoặc đã hoàn thành trong quá khứ."
    )

    def _eval_single_case(case: TaskCase) -> tuple[CaseEvaluationResult, float]:
        prompt_full = case.prompt
        if case.context:
            prompt_full = f"Context (Longitudinal Records):\n{case.context}\n\nUser Question:\n{case.prompt}"

        req = ModelRequest(
            prompt=prompt_full,
            system_prompt=case.system_prompt or temporal_system_prompt,
            task=ModelTask.RAG_SYNTHESIS,
            route_class=RouteClass.QUALITY_MULTIMODAL,
            model=model,
        )
        start = time.monotonic()
        try:
            resp, _ = gateway.execute(ModelTask.RAG_SYNTHESIS, req)
            lat = (time.monotonic() - start) * 1000
            res = score_case(case, resp.content, latency_ms=lat)
        except Exception as exc:
            lat = (time.monotonic() - start) * 1000
            res = score_case(case, f"ERROR: {exc}", latency_ms=lat)
        return res, lat

    try:
        max_workers = min(len(cases), 8) if (live and len(cases) > 1) else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            evaluated = list(executor.map(_eval_single_case, cases))
        case_results = [r for r, _ in evaluated]
        latencies = [l for _, l in evaluated]
    finally:
        os.environ.pop("CLARA_MODEL_ROUTE_TASK_RAG_SYNTHESIS_PROVIDER", None)
        os.environ.pop("CLARA_MODEL_ROUTE_TASK_RAG_SYNTHESIS_MODEL", None)

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
        route_class="quality_multimodal",
        total_cases=total_count,
        passed_cases=passed_count,
        failed_cases=total_count - passed_count,
        pass_rate=round(pass_rate, 4),
        metrics=metrics,
        threshold_checks=tuple(checks),
        overall_passed=overall_passed and (pass_rate >= 0.90),
        latency_p50_ms=round(p50, 2),
        latency_p95_ms=round(p95, 2),
        case_results=tuple(case_results),
    )

    if output_dir:
        if output_dir.suffix == ".json":
            report_file = output_dir
        else:
            report_file = output_dir / f"{manifest.task_id}_{provider}_{model}_report.json"
        save_report(report, report_file)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Personal Temporal QA Benchmark")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--output", default="artifacts/product_ai/reports")
    parser.add_argument("--live", action="store_true", help="Execute against live LLM router")
    args = parser.parse_args()

    report = run_benchmark(
        provider=args.provider,
        model=args.model,
        output_dir=Path(args.output),
        live=args.live,
    )
    print(
        f"[{report.task_id}] Provider: {report.provider} ({report.model}) | Passed: {report.overall_passed} | Pass Rate: {report.pass_rate * 100:.1f}%"
    )
    sys.exit(0 if report.overall_passed else 1)
