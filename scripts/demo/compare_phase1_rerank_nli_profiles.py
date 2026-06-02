#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ML_SRC = ROOT / "services" / "ml" / "src"
if str(ML_SRC) not in sys.path:
    sys.path.insert(0, str(ML_SRC))

from clara_ml.agents.research_tier2 import run_research_tier2  # noqa: E402
from clara_ml.config import settings  # noqa: E402


DEFAULT_QUERIES: list[str] = [
    "Tương tác warfarin với ibuprofen có nguy cơ gì?",
    "So sánh nguy cơ xuất huyết khi dùng aspirin và naproxen ở người cao tuổi.",
    "Khuyến cáo an toàn khi phối hợp clopidogrel với thuốc giảm đau không kê đơn.",
    "Yếu tố cần lưu ý khi bệnh nhân đa thuốc dùng warfarin điều trị kéo dài.",
]

DEFAULT_MODES: list[str] = ["deep", "deep_beta"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day7 Phase1 benchmark: compare baseline vs reranker+nli profiles."
    )
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "artifacts" / "round2" / "phase1-day7-compare.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "artifacts" / "round2" / "phase1-day7-compare.md"),
        help="Output Markdown path.",
    )
    parser.add_argument(
        "--queries-file",
        default="",
        help="Optional JSON file containing list[str] queries.",
    )
    parser.add_argument(
        "--query-limit",
        type=int,
        default=0,
        help="Optional limit to first N queries (0 = use all).",
    )
    parser.add_argument(
        "--modes",
        default="deep,deep_beta",
        help="Comma-separated research modes to run.",
    )
    parser.add_argument(
        "--reranker-top-n",
        type=int,
        default=12,
        help="Reranker top_n used for enhanced profile.",
    )
    parser.add_argument(
        "--reranker-timeout-ms",
        type=int,
        default=250,
        help="Reranker timeout for enhanced profile.",
    )
    parser.add_argument(
        "--strict-deepseek-required",
        action="store_true",
        help="Force strict_deepseek_required=true in benchmark payload.",
    )
    return parser.parse_args()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def _ratio(values: list[bool]) -> float:
    if not values:
        return 0.0
    return float(sum(1 for item in values if item) / len(values))


def _load_queries(args: argparse.Namespace) -> list[str]:
    if args.queries_file:
        payload = json.loads(Path(args.queries_file).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("queries-file must be list[str].")
        queries = [str(item).strip() for item in payload if str(item).strip()]
    else:
        queries = list(DEFAULT_QUERIES)

    if args.query_limit and args.query_limit > 0:
        queries = queries[: args.query_limit]
    if not queries:
        raise RuntimeError("No queries provided for benchmark.")
    return queries


def _load_modes(args: argparse.Namespace) -> list[str]:
    modes = [item.strip().lower() for item in str(args.modes).split(",") if item.strip()]
    allowed = {"fast", "deep", "deep_beta"}
    selected = [mode for mode in modes if mode in allowed]
    if not selected:
        raise RuntimeError("No valid modes selected.")
    return selected


@contextmanager
def _override_phase1_flags(
    *,
    reranker_enabled: bool,
    nli_enabled: bool,
    reranker_top_n: int,
    reranker_timeout_ms: int,
):
    snapshot = {
        "rag_reranker_enabled": settings.rag_reranker_enabled,
        "rag_nli_enabled": settings.rag_nli_enabled,
        "rag_reranker_top_n": settings.rag_reranker_top_n,
        "rag_reranker_timeout_ms": settings.rag_reranker_timeout_ms,
    }
    settings.rag_reranker_enabled = bool(reranker_enabled)
    settings.rag_nli_enabled = bool(nli_enabled)
    settings.rag_reranker_top_n = max(1, int(reranker_top_n))
    settings.rag_reranker_timeout_ms = max(50, int(reranker_timeout_ms))
    try:
        yield
    finally:
        settings.rag_reranker_enabled = bool(snapshot["rag_reranker_enabled"])
        settings.rag_nli_enabled = bool(snapshot["rag_nli_enabled"])
        settings.rag_reranker_top_n = int(snapshot["rag_reranker_top_n"])
        settings.rag_reranker_timeout_ms = int(snapshot["rag_reranker_timeout_ms"])


def _extract_run_metrics(result: dict[str, Any]) -> dict[str, Any]:
    verification_matrix = _safe_dict(result.get("verification_matrix"))
    summary = _safe_dict(verification_matrix.get("summary"))
    safety_override = _safe_dict(verification_matrix.get("safety_override"))
    telemetry = _safe_dict(result.get("telemetry"))
    index_summary = _safe_dict(telemetry.get("index_summary"))
    rerank = _safe_dict(index_summary.get("rerank"))

    support_ratio = _safe_float(summary.get("support_ratio"))
    unsupported_claims = _safe_int(summary.get("unsupported_claims"))
    contradicted_claims = _safe_int(summary.get("contradicted_claims"))
    policy_action = str(result.get("policy_action") or "").strip().lower() or None
    fallback_used = bool(result.get("fallback_used") or result.get("fallback_reason"))

    rerank_topn = _safe_int(rerank.get("rerank_topn"))
    rerank_latency_ms = _safe_float(rerank.get("rerank_latency_ms"))
    rerank_reason = str(rerank.get("rerank_reason") or "").strip() or None
    rerank_signal = bool(rerank_topn and rerank_topn > 0)

    return {
        "support_ratio": support_ratio,
        "unsupported_claims": unsupported_claims,
        "contradicted_claims": contradicted_claims,
        "policy_action": policy_action,
        "policy_warn_or_block": policy_action in {"warn", "block", "escalate"},
        "fallback_used": fallback_used,
        "safety_override_applied": bool(safety_override.get("applied")),
        "rerank_topn": rerank_topn,
        "rerank_latency_ms": rerank_latency_ms,
        "rerank_reason": rerank_reason,
        "rerank_signal": rerank_signal,
    }


def _aggregate_profile_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    support_values = [value for row in rows if (value := _safe_float(row.get("support_ratio"))) is not None]
    unsupported_values = [value for row in rows if (value := _safe_float(row.get("unsupported_claims"))) is not None]
    contradicted_values = [value for row in rows if (value := _safe_float(row.get("contradicted_claims"))) is not None]
    rerank_latency_values = [value for row in rows if (value := _safe_float(row.get("rerank_latency_ms"))) is not None]

    return {
        "runs": len(rows),
        "avg_support_ratio": _mean(support_values),
        "avg_unsupported_claims": _mean(unsupported_values),
        "avg_contradicted_claims": _mean(contradicted_values),
        "warn_block_rate": _ratio([bool(row.get("policy_warn_or_block")) for row in rows]),
        "fallback_rate": _ratio([bool(row.get("fallback_used")) for row in rows]),
        "safety_override_rate": _ratio([bool(row.get("safety_override_applied")) for row in rows]),
        "rerank_signal_rate": _ratio([bool(row.get("rerank_signal")) for row in rows]),
        "avg_rerank_latency_ms": _mean(rerank_latency_values),
    }


def _run_profile(
    *,
    profile_name: str,
    reranker_enabled: bool,
    nli_enabled: bool,
    reranker_top_n: int,
    reranker_timeout_ms: int,
    queries: list[str],
    modes: list[str],
    strict_deepseek_required: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_mode: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}

    with _override_phase1_flags(
        reranker_enabled=reranker_enabled,
        nli_enabled=nli_enabled,
        reranker_top_n=reranker_top_n,
        reranker_timeout_ms=reranker_timeout_ms,
    ):
        for mode in modes:
            for query in queries:
                payload = {
                    "query": query,
                    "research_mode": mode,
                    "strict_deepseek_required": strict_deepseek_required,
                }
                try:
                    result = run_research_tier2(payload)
                    metrics = _extract_run_metrics(result)
                    row = {
                        "mode": mode,
                        "query": query,
                        "ok": True,
                        **metrics,
                    }
                except Exception as exc:  # pragma: no cover - diagnostic path
                    row = {
                        "mode": mode,
                        "query": query,
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                rows.append(row)
                by_mode[mode].append(row)

    mode_summary = {
        mode: _aggregate_profile_runs([row for row in mode_rows if bool(row.get("ok"))])
        for mode, mode_rows in by_mode.items()
    }
    overall = _aggregate_profile_runs([row for row in rows if bool(row.get("ok"))])
    return {
        "profile": profile_name,
        "flags": {
            "rag_reranker_enabled": reranker_enabled,
            "rag_nli_enabled": nli_enabled,
            "rag_reranker_top_n": reranker_top_n,
            "rag_reranker_timeout_ms": reranker_timeout_ms,
        },
        "overall": overall,
        "by_mode": mode_summary,
        "rows": rows,
    }


def _delta(enhanced: float | None, baseline: float | None) -> float | None:
    if enhanced is None or baseline is None:
        return None
    return enhanced - baseline


def _format_num(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def _build_markdown_report(report: dict[str, Any]) -> str:
    baseline = _safe_dict(report.get("baseline"))
    enhanced = _safe_dict(report.get("enhanced"))
    baseline_by_mode = _safe_dict(baseline.get("by_mode"))
    enhanced_by_mode = _safe_dict(enhanced.get("by_mode"))

    lines: list[str] = [
        "# Day7 Phase1 Compare (Baseline vs Reranker+NLI)",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- query_count: `{report.get('query_count')}`",
        f"- modes: `{', '.join(report.get('modes', []))}`",
        "",
        "## Overall",
        "",
        "| Metric | Baseline | Enhanced | Delta (enhanced-baseline) |",
        "|---|---:|---:|---:|",
    ]

    metric_rows = [
        ("avg_support_ratio", 4),
        ("avg_unsupported_claims", 4),
        ("avg_contradicted_claims", 4),
        ("warn_block_rate", 4),
        ("fallback_rate", 4),
        ("safety_override_rate", 4),
        ("rerank_signal_rate", 4),
        ("avg_rerank_latency_ms", 2),
    ]
    baseline_overall = _safe_dict(baseline.get("overall"))
    enhanced_overall = _safe_dict(enhanced.get("overall"))
    for metric_name, digits in metric_rows:
        baseline_value = _safe_float(baseline_overall.get(metric_name))
        enhanced_value = _safe_float(enhanced_overall.get(metric_name))
        lines.append(
            "| "
            f"{metric_name} | "
            f"{_format_num(baseline_value, digits)} | "
            f"{_format_num(enhanced_value, digits)} | "
            f"{_format_num(_delta(enhanced_value, baseline_value), digits)} |"
        )

    lines.extend(["", "## By Mode", "", "| Mode | Metric | Baseline | Enhanced | Delta |", "|---|---|---:|---:|---:|"])
    for mode in report.get("modes", []):
        mode_baseline = _safe_dict(baseline_by_mode.get(mode))
        mode_enhanced = _safe_dict(enhanced_by_mode.get(mode))
        for metric_name, digits in metric_rows:
            baseline_value = _safe_float(mode_baseline.get(metric_name))
            enhanced_value = _safe_float(mode_enhanced.get(metric_name))
            lines.append(
                "| "
                f"{mode} | {metric_name} | "
                f"{_format_num(baseline_value, digits)} | "
                f"{_format_num(enhanced_value, digits)} | "
                f"{_format_num(_delta(enhanced_value, baseline_value), digits)} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    queries = _load_queries(args)
    modes = _load_modes(args)
    strict_deepseek_required = bool(args.strict_deepseek_required)

    baseline = _run_profile(
        profile_name="baseline",
        reranker_enabled=False,
        nli_enabled=False,
        reranker_top_n=args.reranker_top_n,
        reranker_timeout_ms=args.reranker_timeout_ms,
        queries=queries,
        modes=modes,
        strict_deepseek_required=strict_deepseek_required,
    )
    enhanced = _run_profile(
        profile_name="reranker_nli_enabled",
        reranker_enabled=True,
        nli_enabled=True,
        reranker_top_n=args.reranker_top_n,
        reranker_timeout_ms=args.reranker_timeout_ms,
        queries=queries,
        modes=modes,
        strict_deepseek_required=strict_deepseek_required,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query_count": len(queries),
        "modes": modes,
        "queries": queries,
        "baseline": baseline,
        "enhanced": enhanced,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(_build_markdown_report(report), encoding="utf-8")

    print("[phase1-compare] ok")
    print(f"- output_json: {output_json}")
    print(f"- output_md: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
