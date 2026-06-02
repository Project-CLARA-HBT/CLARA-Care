#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = ROOT / "data" / "demo" / "deepbeta_research_benchmark_cases.json"
DEFAULT_OUTPUT_ROOT = ROOT / "artifacts" / "deepbeta-research"
DEFAULT_ENV_CANDIDATES = [ROOT / ".env", Path("/opt/clara-care/.env")]


POSITIVE_RISK_TERMS = [
    "contraindicated",
    "avoid",
    "severe interaction",
    "major interaction",
    "increased risk",
    "bleeding",
    "chảy máu",
    "rhabdomyolysis",
    "nephrotoxicity",
    "hyperkalemia",
    "monitor closely",
    "tăng nguy cơ",
]

NEGATIVE_RISK_TERMS = [
    "no clinically significant interaction",
    "no significant interaction",
    "generally safe",
    "không có tương tác đáng kể",
    "không có tương tác lâm sàng đáng kể",
    "có thể dùng cùng",
    "minimal interaction",
]


@dataclass
class HttpResult:
    ok: bool
    status_code: int
    payload: dict[str, Any]
    elapsed_ms: float
    error: str | None = None


@dataclass
class CaseRun:
    case_id: str
    query: str
    expected_risk: bool
    predicted_risk: bool
    risk_probability: float
    classification_correct: bool
    keyword_hits: int
    keyword_total: int
    keyword_recall: float
    keyword_pass: bool
    latency_ms: float
    fallback_used: bool
    deep_pass_count: int | None
    citation_count: int
    topk_metrics: dict[str, dict[str, float]]
    status: str
    error: str | None
    answer_preview: str
    router_confidence: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark CLARA Deep Beta research with classification/retrieval/runtime metrics."
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH),
        help="Path to JSON benchmark case file.",
    )
    parser.add_argument(
        "--ml-base-url",
        default=os.getenv("CLARA_ML_BASE_URL", "http://127.0.0.1:8110"),
        help="ML base URL without trailing slash.",
    )
    parser.add_argument(
        "--endpoint",
        default="/v1/research/tier2",
        help="Research endpoint path.",
    )
    parser.add_argument(
        "--source-mode",
        default="hybrid",
        help="source_mode payload value.",
    )
    parser.add_argument(
        "--internal-key",
        default=os.getenv("ML_INTERNAL_API_KEY", ""),
        help="ML internal API key; auto-resolved from env files when omitted.",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional env file path used to resolve ML_INTERNAL_API_KEY.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=180.0,
        help="HTTP timeout per case.",
    )
    parser.add_argument(
        "--top-k",
        default="3,5,10",
        help="Comma-separated K values for precision@k/recall@k/F1@k.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run id for artifact directory.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Root output directory.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Maximum number of cases to run (0 = all).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any case fails or request errors occur.",
    )
    return parser.parse_args()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def parse_topk(value: str) -> list[int]:
    ks: list[int] = []
    for part in str(value).split(","):
        raw = part.strip()
        if not raw:
            continue
        parsed = int(raw)
        if parsed <= 0:
            continue
        ks.append(parsed)
    unique_sorted = sorted(set(ks))
    if not unique_sorted:
        return [3, 5, 10]
    return unique_sorted


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip("\"").strip("'")
        values[key] = value
    return values


def resolve_internal_key(cli_value: str, env_file_arg: str) -> str:
    if cli_value.strip():
        return cli_value.strip()
    direct_env = os.getenv("ML_INTERNAL_API_KEY", "").strip()
    if direct_env:
        return direct_env

    candidates: list[Path] = []
    if env_file_arg.strip():
        candidates.append(Path(env_file_arg).expanduser().resolve())
    candidates.extend(DEFAULT_ENV_CANDIDATES)

    for candidate in candidates:
        values = parse_env_file(candidate)
        key = values.get("ML_INTERNAL_API_KEY", "").strip()
        if key:
            return key
    return ""


def build_url(base_url: str, endpoint: str) -> str:
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


def http_post_json(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    internal_key: str,
) -> HttpResult:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if internal_key:
        headers["X-ML-Internal-Key"] = internal_key

    req = request.Request(url=url, data=body, method="POST", headers=headers)
    started = time.perf_counter()

    try:
        with request.urlopen(req, timeout=max(1.0, timeout_seconds)) as response:
            raw = response.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {"data": parsed}
            return HttpResult(
                ok=True,
                status_code=int(response.status),
                payload=parsed,
                elapsed_ms=elapsed_ms,
            )
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        try:
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {"data": parsed}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return HttpResult(
            ok=False,
            status_code=int(exc.code),
            payload=parsed,
            elapsed_ms=elapsed_ms,
            error=f"HTTPError:{exc.code}",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return HttpResult(
            ok=False,
            status_code=0,
            payload={},
            elapsed_ms=elapsed_ms,
            error=f"{type(exc).__name__}:{exc}",
        )


def safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def normalize_text(value: str) -> str:
    return " ".join(str(value).lower().split())


def count_term_hits(text: str, terms: list[str]) -> tuple[int, list[str]]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for term in terms:
        candidate = normalize_text(term)
        if candidate and candidate in normalized:
            hits.append(term)
    return len(hits), hits


def clamp_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def derive_risk_probability(answer_text: str, router_confidence: float | None) -> tuple[float, int, int]:
    pos_hits, _ = count_term_hits(answer_text, POSITIVE_RISK_TERMS)
    neg_hits, _ = count_term_hits(answer_text, NEGATIVE_RISK_TERMS)
    score = 0.5 + 0.12 * (pos_hits - neg_hits)
    if router_confidence is not None:
        score = 0.65 * score + 0.35 * router_confidence
    return clamp_probability(score), pos_hits, neg_hits


def extract_citations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    citations = payload.get("citations")
    if isinstance(citations, list):
        return [item for item in citations if isinstance(item, dict)]
    sources = payload.get("sources")
    if isinstance(sources, list):
        return [item for item in sources if isinstance(item, dict)]
    return []


def citation_blob(citation: dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            [
                str(citation.get("source") or ""),
                str(citation.get("source_id") or ""),
                str(citation.get("title") or ""),
                str(citation.get("url") or ""),
                str(citation.get("relevance") or ""),
            ]
        )
    )


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_classification_metrics(runs: list[CaseRun]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    probs: list[float] = []
    labels: list[int] = []

    for run in runs:
        y_true = 1 if run.expected_risk else 0
        y_pred = 1 if run.predicted_risk else 0
        labels.append(y_true)
        probs.append(run.risk_probability)

        if y_true == 1 and y_pred == 1:
            tp += 1
        elif y_true == 0 and y_pred == 1:
            fp += 1
        elif y_true == 0 and y_pred == 0:
            tn += 1
        else:
            fn += 1

    total = tp + fp + tn + fn
    accuracy = safe_ratio(tp + tn, total)
    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    specificity = safe_ratio(tn, tn + fp)
    f1 = safe_ratio(2 * tp, 2 * tp + fp + fn)
    balanced_accuracy = None
    if recall is not None and specificity is not None:
        balanced_accuracy = (recall + specificity) / 2.0

    log_losses: list[float] = []
    brier_losses: list[float] = []
    for y_true, prob in zip(labels, probs, strict=False):
        p = clamp_probability(prob)
        log_losses.append(-(y_true * math.log(p) + (1 - y_true) * math.log(1 - p)))
        brier_losses.append((p - y_true) ** 2)

    return {
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "total": total},
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1_score": f1,
        "balanced_accuracy": balanced_accuracy,
        "log_loss": mean(log_losses),
        "brier_score": mean(brier_losses),
    }


def compute_retrieval_metrics(runs: list[CaseRun], top_ks: list[int]) -> dict[str, Any]:
    by_k: dict[str, Any] = {}
    for k in top_ks:
        per_case_precision: list[float] = []
        per_case_recall: list[float] = []
        per_case_f1: list[float] = []
        total_relevant_hits = 0.0
        total_retrieved = 0.0
        total_hint_hits = 0.0
        total_hints = 0.0

        for run in runs:
            metrics = run.topk_metrics.get(str(k), {})
            precision_k = float(metrics.get("precision", 0.0) or 0.0)
            recall_k = float(metrics.get("recall", 0.0) or 0.0)
            f1_k = float(metrics.get("f1", 0.0) or 0.0)
            per_case_precision.append(precision_k)
            per_case_recall.append(recall_k)
            per_case_f1.append(f1_k)

            total_relevant_hits += float(metrics.get("relevant_hits", 0.0) or 0.0)
            total_retrieved += float(metrics.get("retrieved", 0.0) or 0.0)
            total_hint_hits += float(metrics.get("matched_hints", 0.0) or 0.0)
            total_hints += float(metrics.get("total_hints", 0.0) or 0.0)

        micro_precision = safe_ratio(total_relevant_hits, total_retrieved)
        micro_recall = safe_ratio(total_hint_hits, total_hints)
        micro_f1 = None
        if micro_precision is not None and micro_recall is not None:
            micro_f1 = safe_ratio(2 * micro_precision * micro_recall, micro_precision + micro_recall)

        by_k[str(k)] = {
            "macro": {
                "precision_at_k": mean(per_case_precision),
                "recall_at_k": mean(per_case_recall),
                "f1_at_k": mean(per_case_f1),
            },
            "micro": {
                "precision_at_k": micro_precision,
                "recall_at_k": micro_recall,
                "f1_at_k": micro_f1,
            },
        }
    return by_k


def compute_runtime_metrics(runs: list[CaseRun]) -> dict[str, Any]:
    latencies = sorted([run.latency_ms for run in runs])
    fallback_count = sum(1 for run in runs if run.fallback_used)
    keyword_pass_count = sum(1 for run in runs if run.keyword_pass)
    case_pass_count = sum(
        1
        for run in runs
        if run.status == "ok" and run.classification_correct and run.keyword_pass and not run.fallback_used
    )
    deep_pass_counts = [run.deep_pass_count for run in runs if isinstance(run.deep_pass_count, int)]

    return {
        "latency_ms": {
            "count": len(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "max": max(latencies) if latencies else 0.0,
            "mean": mean(latencies),
        },
        "fallback_rate": safe_ratio(fallback_count, len(runs)),
        "keyword_pass_rate": safe_ratio(keyword_pass_count, len(runs)),
        "case_pass_rate": safe_ratio(case_pass_count, len(runs)),
        "deep_pass_count": {
            "mean": mean([float(v) for v in deep_pass_counts]) if deep_pass_counts else 0.0,
            "max": max(deep_pass_counts) if deep_pass_counts else 0,
        },
    }


def format_rate(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def format_float(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def render_markdown(
    *,
    run_id: str,
    report_json_relpath: str,
    case_file_relpath: str,
    endpoint_url: str,
    top_ks: list[int],
    started_at: str,
    finished_at: str,
    classification: dict[str, Any],
    retrieval: dict[str, Any],
    runtime: dict[str, Any],
    runs: list[CaseRun],
) -> str:
    lines = [
        "# CLARA Deep Beta Research Benchmark",
        "",
        f"- run_id: `{run_id}`",
        f"- started_at_utc: `{started_at}`",
        f"- finished_at_utc: `{finished_at}`",
        f"- endpoint: `{endpoint_url}`",
        f"- cases: `{case_file_relpath}`",
        f"- report_json: `{report_json_relpath}`",
        "",
        "## Classification Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Accuracy | {format_rate(classification.get('accuracy'))} |",
        f"| Precision | {format_rate(classification.get('precision'))} |",
        f"| Recall | {format_rate(classification.get('recall'))} |",
        f"| Specificity | {format_rate(classification.get('specificity'))} |",
        f"| F1 Score | {format_rate(classification.get('f1_score'))} |",
        f"| Balanced Accuracy | {format_rate(classification.get('balanced_accuracy'))} |",
        f"| Log Loss | {format_float(classification.get('log_loss'))} |",
        f"| Brier Score | {format_float(classification.get('brier_score'))} |",
        "",
        "## Retrieval Metrics",
        "",
        "| K | Precision@K (macro) | Recall@K (macro) | F1@K (macro) | Precision@K (micro) | Recall@K (micro) | F1@K (micro) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for k in top_ks:
        bucket = retrieval.get(str(k), {})
        macro = bucket.get("macro", {})
        micro = bucket.get("micro", {})
        lines.append(
            "| {k} | {mp} | {mr} | {mf} | {ip} | {ir} | {if1} |".format(
                k=k,
                mp=format_rate(macro.get("precision_at_k")),
                mr=format_rate(macro.get("recall_at_k")),
                mf=format_rate(macro.get("f1_at_k")),
                ip=format_rate(micro.get("precision_at_k")),
                ir=format_rate(micro.get("recall_at_k")),
                if1=format_rate(micro.get("f1_at_k")),
            )
        )

    latency = runtime.get("latency_ms", {})
    lines.extend(
        [
            "",
            "## Runtime Metrics",
            "",
            f"- Latency p50: **{format_float(latency.get('p50'), 2)} ms**",
            f"- Latency p95: **{format_float(latency.get('p95'), 2)} ms**",
            f"- Latency max: **{format_float(latency.get('max'), 2)} ms**",
            f"- Fallback rate: **{format_rate(runtime.get('fallback_rate'))}**",
            f"- Keyword pass rate: **{format_rate(runtime.get('keyword_pass_rate'))}**",
            f"- End-to-end case pass rate: **{format_rate(runtime.get('case_pass_rate'))}**",
            "",
            "## Per-case",
            "",
            "| Case | Expected Risk | Pred Risk | P(risk) | Correct | Keyword Recall | Fallback | Latency (ms) | Citations | Status |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for run in runs:
        lines.append(
            "| {case_id} | {er} | {pr} | {prob} | {ok} | {kr} | {fb} | {lat} | {cit} | {status} |".format(
                case_id=run.case_id,
                er="1" if run.expected_risk else "0",
                pr="1" if run.predicted_risk else "0",
                prob=f"{run.risk_probability:.3f}",
                ok="1" if run.classification_correct else "0",
                kr=f"{run.keyword_recall * 100:.1f}%",
                fb="1" if run.fallback_used else "0",
                lat=f"{run.latency_ms:.1f}",
                cit=run.citation_count,
                status=run.status,
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `log_loss` ở đây là **evaluation loss** (binary cross-entropy trên xác suất dự đoán từ output runtime), không phải training loss nội bộ của model.",
            "- `recall@k` được tính theo coverage của `expected_source_hints` trong top-k citations.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    cases_path = Path(args.cases).expanduser().resolve()
    if not cases_path.exists():
        raise FileNotFoundError(f"Case file not found: {cases_path}")

    all_cases = read_json(cases_path)
    if not isinstance(all_cases, list):
        raise ValueError("Case file must be a JSON array.")

    cases = [item for item in all_cases if isinstance(item, dict)]
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("No runnable cases found.")

    top_ks = parse_topk(args.top_k)
    internal_key = resolve_internal_key(args.internal_key, args.env_file)
    endpoint_url = build_url(args.ml_base_url, args.endpoint)

    run_id = args.run_id.strip() or f"deepbeta-research-benchmark-{now_tag()}"
    output_root = Path(args.output_root).expanduser().resolve()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = utcnow()
    case_runs: list[CaseRun] = []
    raw_records: list[dict[str, Any]] = []

    for idx, case in enumerate(cases, start=1):
        case_id = str(case.get("case_id") or f"case_{idx:03d}")
        query = str(case.get("query") or "").strip()
        if not query:
            continue

        expected_risk = coerce_bool(case.get("expected_risk"))
        expected_terms = [str(v) for v in case.get("expected_terms_any", []) if str(v).strip()]
        min_expected_hits = int(case.get("min_expected_term_hits") or 1)
        source_hints = [str(v).lower().strip() for v in case.get("expected_source_hints", []) if str(v).strip()]

        payload = {
            "query": query,
            "research_mode": "deep_beta",
            "source_mode": args.source_mode,
        }

        result = http_post_json(
            url=endpoint_url,
            payload=payload,
            timeout_seconds=args.timeout_seconds,
            internal_key=internal_key,
        )

        response = result.payload if isinstance(result.payload, dict) else {}
        answer = str(response.get("answer_markdown") or response.get("answer") or "")
        answer_norm = normalize_text(answer)

        router_confidence = safe_float(response.get("router_confidence"))
        risk_probability, pos_hits, neg_hits = derive_risk_probability(answer_norm, router_confidence)
        predicted_risk = risk_probability >= 0.5
        classification_correct = predicted_risk == expected_risk

        keyword_hits, matched_terms = count_term_hits(answer_norm, expected_terms)
        keyword_total = len(expected_terms)
        keyword_recall = 0.0 if keyword_total == 0 else keyword_hits / keyword_total
        keyword_pass = keyword_hits >= max(0, min_expected_hits)

        citations = extract_citations(response)
        citation_count = len(citations)
        citation_blobs = [citation_blob(item) for item in citations]

        topk_metrics: dict[str, dict[str, float]] = {}
        for k in top_ks:
            topk = citation_blobs[:k]
            retrieved = float(len(topk))
            relevant_hits = 0
            for blob in topk:
                if any(hint and hint in blob for hint in source_hints):
                    relevant_hits += 1

            matched_hints = 0
            for hint in source_hints:
                if any(hint and hint in blob for blob in topk):
                    matched_hints += 1

            precision_k = 0.0 if retrieved == 0 else relevant_hits / retrieved
            total_hints = float(len(source_hints))
            recall_k = 0.0 if total_hints == 0 else matched_hints / total_hints
            f1_k = 0.0
            if precision_k + recall_k > 0:
                f1_k = (2 * precision_k * recall_k) / (precision_k + recall_k)

            topk_metrics[str(k)] = {
                "precision": precision_k,
                "recall": recall_k,
                "f1": f1_k,
                "relevant_hits": float(relevant_hits),
                "retrieved": retrieved,
                "matched_hints": float(matched_hints),
                "total_hints": total_hints,
            }

        fallback_used = coerce_bool(response.get("fallback_used"))
        deep_pass_count = response.get("deep_pass_count")
        if not isinstance(deep_pass_count, int):
            deep_pass_count = None

        status = "ok" if result.ok else "error"
        error_text = None if result.ok else (result.error or f"http_{result.status_code}")
        answer_preview = answer.strip().replace("\n", " ")[:240]

        run = CaseRun(
            case_id=case_id,
            query=query,
            expected_risk=expected_risk,
            predicted_risk=predicted_risk,
            risk_probability=risk_probability,
            classification_correct=classification_correct,
            keyword_hits=keyword_hits,
            keyword_total=keyword_total,
            keyword_recall=keyword_recall,
            keyword_pass=keyword_pass,
            latency_ms=result.elapsed_ms,
            fallback_used=fallback_used,
            deep_pass_count=deep_pass_count,
            citation_count=citation_count,
            topk_metrics=topk_metrics,
            status=status,
            error=error_text,
            answer_preview=answer_preview,
            router_confidence=router_confidence,
        )
        case_runs.append(run)

        raw_records.append(
            {
                "case_id": case_id,
                "query": query,
                "request_payload": payload,
                "http": {
                    "ok": result.ok,
                    "status_code": result.status_code,
                    "elapsed_ms": round(result.elapsed_ms, 3),
                    "error": result.error,
                },
                "evaluation": {
                    "expected_risk": expected_risk,
                    "predicted_risk": predicted_risk,
                    "risk_probability": round(risk_probability, 6),
                    "classification_correct": classification_correct,
                    "keyword_hits": keyword_hits,
                    "keyword_total": keyword_total,
                    "keyword_recall": round(keyword_recall, 6),
                    "keyword_pass": keyword_pass,
                    "matched_terms": matched_terms,
                    "pos_lexicon_hits": pos_hits,
                    "neg_lexicon_hits": neg_hits,
                },
                "response": response,
            }
        )

        print(
            "[deepbeta-benchmark] case={case_id} status={status} latency_ms={lat:.1f} "
            "fallback={fallback} correct={correct} citations={cit}".format(
                case_id=case_id,
                status=status,
                lat=result.elapsed_ms,
                fallback=int(fallback_used),
                correct=int(classification_correct),
                cit=citation_count,
            )
        )

    finished_at = utcnow()

    classification_metrics = compute_classification_metrics(case_runs)
    retrieval_metrics = compute_retrieval_metrics(case_runs, top_ks)
    runtime_metrics = compute_runtime_metrics(case_runs)

    run_summary = {
        "run_id": run_id,
        "generated_at_utc": finished_at,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "config": {
            "ml_base_url": args.ml_base_url,
            "endpoint": args.endpoint,
            "resolved_endpoint_url": endpoint_url,
            "source_mode": args.source_mode,
            "top_k": top_ks,
            "timeout_seconds": args.timeout_seconds,
            "case_file": str(cases_path),
            "internal_key_provided": bool(internal_key),
            "max_cases": args.max_cases,
        },
        "metrics": {
            "classification": classification_metrics,
            "retrieval": retrieval_metrics,
            "runtime": runtime_metrics,
        },
        "case_results": [
            {
                "case_id": run.case_id,
                "query": run.query,
                "status": run.status,
                "error": run.error,
                "expected_risk": run.expected_risk,
                "predicted_risk": run.predicted_risk,
                "risk_probability": round(run.risk_probability, 6),
                "classification_correct": run.classification_correct,
                "keyword_hits": run.keyword_hits,
                "keyword_total": run.keyword_total,
                "keyword_recall": round(run.keyword_recall, 6),
                "keyword_pass": run.keyword_pass,
                "fallback_used": run.fallback_used,
                "deep_pass_count": run.deep_pass_count,
                "router_confidence": run.router_confidence,
                "latency_ms": round(run.latency_ms, 3),
                "citation_count": run.citation_count,
                "topk_metrics": run.topk_metrics,
                "answer_preview": run.answer_preview,
            }
            for run in case_runs
        ],
    }

    report_json_path = run_dir / "deepbeta-research-benchmark-report.json"
    report_md_path = run_dir / "deepbeta-research-benchmark-report.md"
    raw_jsonl_path = run_dir / "deepbeta-research-benchmark-raw.jsonl"

    write_json(report_json_path, run_summary)
    raw_jsonl_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in raw_records) + "\n",
        encoding="utf-8",
    )

    report_md = render_markdown(
        run_id=run_id,
        report_json_relpath=str(report_json_path.relative_to(ROOT)),
        case_file_relpath=str(cases_path.relative_to(ROOT)),
        endpoint_url=endpoint_url,
        top_ks=top_ks,
        started_at=started_at,
        finished_at=finished_at,
        classification=classification_metrics,
        retrieval=retrieval_metrics,
        runtime=runtime_metrics,
        runs=case_runs,
    )
    write_text(report_md_path, report_md)

    print(f"[deepbeta-benchmark] report_json={report_json_path}")
    print(f"[deepbeta-benchmark] report_md={report_md_path}")

    if args.strict:
        has_error = any(run.status != "ok" for run in case_runs)
        has_fail = any(
            not (run.classification_correct and run.keyword_pass and not run.fallback_used)
            for run in case_runs
        )
        if has_error or has_fail:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
