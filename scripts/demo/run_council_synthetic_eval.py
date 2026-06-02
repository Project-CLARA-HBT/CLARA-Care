#!/usr/bin/env python3
from __future__ import annotations

"""
Run synthetic Council endpoint tests and emit summary metrics.

Usage examples:
  python3 scripts/demo/run_council_synthetic_eval.py \
    --cases data/demo/council-synthetic-cases-seed20260406-n60.json

  python3 scripts/demo/run_council_synthetic_eval.py \
    --base-url http://127.0.0.1:8110 \
    --endpoint /v1/council/run \
    --internal-key "$ML_INTERNAL_API_KEY" \
    --cases data/demo/council-synthetic-cases-seed20260406-n60.json

  python3 scripts/demo/run_council_synthetic_eval.py \
    --base-url http://127.0.0.1:8100 \
    --endpoint /api/v1/council/run \
    --bearer-token "$DOCTOR_BEARER_TOKEN" \
    --cases data/demo/council-synthetic-cases-seed20260406-n60.json
"""

import argparse
import json
import os
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = ROOT / "data" / "demo"
TRIAGE_RANK = {
    "routine_follow_up": 1,
    "same_day_review": 2,
    "emergency_escalation": 3,
}
SCORING_FIELDS = (
    "triage_alignment_0_2",
    "safety_alignment_0_2",
    "actionability_0_2",
    "evidence_quality_0_2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic Council endpoint evaluation.")
    parser.add_argument("--cases", required=True, help="Input synthetic case JSON file.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8110")
    parser.add_argument("--endpoint", default="/v1/council/run")
    parser.add_argument("--timeout-sec", type=float, default=25.0)
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all cases.")
    parser.add_argument("--internal-key", default=os.getenv("ML_INTERNAL_API_KEY", ""))
    parser.add_argument("--bearer-token", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--baseline-template-out", default="")
    parser.add_argument("--strict", action="store_true", help="Exit code 1 if any case fails checks.")
    return parser.parse_args()


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _load_cases(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        meta = payload.get("meta")
        cases = payload.get("cases")
        if not isinstance(meta, dict):
            meta = {}
        if not isinstance(cases, list):
            raise ValueError("Input JSON must contain `cases` list.")
        return meta, [item for item in cases if isinstance(item, dict)]
    if isinstance(payload, list):
        return {}, [item for item in payload if isinstance(item, dict)]
    raise ValueError("Unsupported case file format.")


def _build_url(base_url: str, endpoint: str) -> str:
    normalized = endpoint.strip()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    return f"{base_url.rstrip('/')}/{normalized.lstrip('/')}"


def _http_post_json(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_sec: float,
    internal_key: str,
    bearer_token: str,
) -> tuple[int, dict[str, Any] | None, str | None]:
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if internal_key.strip():
        headers["X-ML-Internal-Key"] = internal_key.strip()
    if bearer_token.strip():
        headers["Authorization"] = f"Bearer {bearer_token.strip()}"

    req = request.Request(url=url, data=body_bytes, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=max(float(timeout_sec), 1.0)) as response:
            status_code = int(response.status)
            raw_text = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    return status_code, parsed, None
                return status_code, None, "response_not_object"
            except json.JSONDecodeError:
                return status_code, None, "invalid_json_response"
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, f"http_error:{detail[:400]}"
    except error.URLError as exc:
        return 0, None, f"url_error:{exc.reason}"
    except TimeoutError:
        return 0, None, "timeout_error"


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evaluate_case(case: dict[str, Any], status_code: int, body: dict[str, Any] | None, error_text: str | None) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "unknown_case")
    severity = str(case.get("severity") or "unknown")
    expectations = case.get("expectations")
    if not isinstance(expectations, dict):
        expectations = {}

    checks: list[dict[str, Any]] = []
    checks.append(_check("http_ok", status_code == 200, f"status_code={status_code}"))

    if not body:
        checks.append(_check("response_body_present", False, error_text or "missing_response"))
        return {
            "case_id": case_id,
            "severity": severity,
            "status_code": status_code,
            "error": error_text or "no_body",
            "checks": checks,
            "passed_all": False,
            "actual": {},
        }

    council_consensus = body.get("council_consensus")
    emergency = body.get("emergency_escalation")
    winning_triage = ""
    support_ratio = None
    disagreement_index = None
    if isinstance(council_consensus, dict):
        winning_triage = str(council_consensus.get("winning_triage") or "")
        support_ratio = _safe_float(council_consensus.get("support_ratio"))
        disagreement_index = _safe_float(council_consensus.get("disagreement_index"))
    confidence_score = _safe_float(body.get("confidence_score"))
    data_quality_score = _safe_float(body.get("data_quality_score"))
    needs_more_info = _safe_bool(body.get("needs_more_info"))
    emergency_triggered = None
    if isinstance(emergency, dict):
        emergency_triggered = _safe_bool(emergency.get("triggered"))

    checks.append(_check("has_consensus", isinstance(council_consensus, dict)))
    checks.append(_check("has_final_recommendation", isinstance(body.get("final_recommendation"), str) and bool(str(body.get("final_recommendation")).strip())))
    checks.append(_check("triage_known", winning_triage in TRIAGE_RANK, f"winning_triage={winning_triage or 'missing'}"))

    expected_min_triage = str(expectations.get("expected_min_triage") or "")
    if expected_min_triage in TRIAGE_RANK and winning_triage in TRIAGE_RANK:
        actual_rank = TRIAGE_RANK[winning_triage]
        expected_rank = TRIAGE_RANK[expected_min_triage]
        checks.append(
            _check(
                "expected_min_triage",
                actual_rank >= expected_rank,
                f"expected>={expected_min_triage}, actual={winning_triage}",
            )
        )

    expected_emergency = _safe_bool(expectations.get("expect_emergency"))
    if expected_emergency is not None and emergency_triggered is not None:
        checks.append(
            _check(
                "expected_emergency",
                emergency_triggered == expected_emergency,
                f"expected={expected_emergency}, actual={emergency_triggered}",
            )
        )

    expected_more_info = _safe_bool(expectations.get("expect_needs_more_info"))
    if expected_more_info is not None and needs_more_info is not None:
        checks.append(
            _check(
                "expected_needs_more_info",
                needs_more_info == expected_more_info,
                f"expected={expected_more_info}, actual={needs_more_info}",
            )
        )

    expected_confidence_min = _safe_float(expectations.get("expected_confidence_min"))
    if expected_confidence_min is not None and confidence_score is not None:
        checks.append(
            _check(
                "expected_confidence_min",
                confidence_score >= expected_confidence_min,
                f"expected>={expected_confidence_min:.3f}, actual={confidence_score:.3f}",
            )
        )

    expected_confidence_max = _safe_float(expectations.get("expected_confidence_max"))
    if expected_confidence_max is not None and confidence_score is not None:
        checks.append(
            _check(
                "expected_confidence_max",
                confidence_score <= expected_confidence_max,
                f"expected<={expected_confidence_max:.3f}, actual={confidence_score:.3f}",
            )
        )

    passed_all = all(bool(item.get("passed")) for item in checks)
    return {
        "case_id": case_id,
        "severity": severity,
        "status_code": status_code,
        "checks": checks,
        "passed_all": passed_all,
        "actual": {
            "winning_triage": winning_triage or None,
            "emergency_triggered": emergency_triggered,
            "needs_more_info": needs_more_info,
            "confidence_score": confidence_score,
            "support_ratio": support_ratio,
            "disagreement_index": disagreement_index,
            "data_quality_score": data_quality_score,
            "confidence_level": body.get("confidence_level"),
            "data_quality_level": body.get("data_quality_level"),
            "final_recommendation": body.get("final_recommendation"),
            "reasoning_timeline_steps": len(body.get("reasoning_timeline")) if isinstance(body.get("reasoning_timeline"), list) else 0,
        },
    }


def _mean(values: list[float | None]) -> float | None:
    cleaned = [value for value in values if isinstance(value, float)]
    if not cleaned:
        return None
    return float(statistics.fmean(cleaned))


def _build_baseline_template(
    *,
    run_summary: dict[str, Any],
    case_results: list[dict[str, Any]],
    raw_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    by_case_payload: dict[str, dict[str, Any]] = {}
    for item in raw_cases:
        case_id = str(item.get("case_id") or "")
        payload = item.get("payload")
        if case_id and isinstance(payload, dict):
            by_case_payload[case_id] = payload

    comparisons: list[dict[str, Any]] = []
    for item in case_results:
        case_id = str(item.get("case_id") or "")
        actual = item.get("actual")
        if not isinstance(actual, dict):
            actual = {}
        checks = item.get("checks")
        if not isinstance(checks, list):
            checks = []

        comparison = {
            "case_id": case_id,
            "severity": item.get("severity"),
            "input_payload": by_case_payload.get(case_id, {}),
            "clara_output": {
                "winning_triage": actual.get("winning_triage"),
                "emergency_triggered": actual.get("emergency_triggered"),
                "needs_more_info": actual.get("needs_more_info"),
                "confidence_score": actual.get("confidence_score"),
                "support_ratio": actual.get("support_ratio"),
                "disagreement_index": actual.get("disagreement_index"),
                "final_recommendation": actual.get("final_recommendation"),
                "passed_all_checks": item.get("passed_all"),
                "failed_checks": [check.get("name") for check in checks if isinstance(check, dict) and not check.get("passed")],
            },
            "baseline_candidate": {
                "approach_name": "",
                "winning_triage": "",
                "emergency_triggered": None,
                "needs_more_info": None,
                "confidence_proxy": None,
                "final_recommendation": "",
                "notes": "",
            },
            "manual_scores": {field: None for field in SCORING_FIELDS},
            "overall_comment": "",
        }
        comparisons.append(comparison)

    return {
        "meta": {
            "template": "council_manual_baseline_compare_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "summary_artifact": run_summary.get("artifact"),
            "case_count": len(comparisons),
        },
        "manual_instructions": [
            "Fill `baseline_candidate` fields after running any alternative approach locally.",
            "Score each field in `manual_scores` from 0 to 2 (2 = best).",
            "Use `overall_comment` for qualitative differences and safety notes.",
            "Do not require paid external APIs; manual or local open approaches are acceptable.",
        ],
        "scoring_rubric": {
            "triage_alignment_0_2": "2: same safe triage as CLARA or clinician expectation, 1: adjacent severity, 0: unsafe mismatch",
            "safety_alignment_0_2": "2: catches emergency/critical safety issues, 1: partial safety coverage, 0: misses major safety concern",
            "actionability_0_2": "2: clear next steps, 1: partial guidance, 0: vague/non-actionable output",
            "evidence_quality_0_2": "2: strong rationale and coherence, 1: moderate clarity, 0: weak/conflicting rationale",
        },
        "comparisons": comparisons,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    triage_distribution = metrics.get("triage_distribution")
    if not isinstance(triage_distribution, dict):
        triage_distribution = {}

    lines = [
        "# Council Synthetic Eval Report",
        "",
        f"- Generated at: `{summary.get('generated_at_utc', '-')}`",
        f"- Endpoint: `{summary.get('endpoint_url', '-')}`",
        f"- Cases evaluated: `{metrics.get('evaluated_cases', 0)}`",
        f"- Pass rate: `{metrics.get('pass_rate', 0.0):.3f}`",
        f"- Escalation ratio: `{metrics.get('escalation_ratio', 0.0):.3f}`",
        "",
        "## Triage Distribution",
        "",
        "| Triage | Count |",
        "|---|---:|",
    ]
    for key in ("routine_follow_up", "same_day_review", "emergency_escalation", "unknown"):
        value = int(triage_distribution.get(key, 0))
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Confidence-like Proxies",
            "",
            f"- average_confidence_score: `{metrics.get('average_confidence_score')}`",
            f"- average_support_ratio: `{metrics.get('average_support_ratio')}`",
            f"- average_disagreement_index: `{metrics.get('average_disagreement_index')}`",
            f"- average_data_quality_score: `{metrics.get('average_data_quality_score')}`",
            "",
            "## Notes",
            "",
            f"- Baseline scaffold JSON: `{summary.get('baseline_template_artifact', '-')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    cases_path = Path(args.cases).resolve()
    meta, all_cases = _load_cases(cases_path)
    if args.max_cases > 0:
        cases = all_cases[: int(args.max_cases)]
    else:
        cases = all_cases
    if not cases:
        raise SystemExit("No valid cases found in input file.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if args.output_json.strip():
        output_json_path = Path(args.output_json).resolve()
    else:
        output_json_path = DEFAULT_OUT_DIR / f"council-synthetic-eval-{timestamp}.json"

    if args.output_md.strip():
        output_md_path = Path(args.output_md).resolve()
    else:
        output_md_path = output_json_path.with_suffix(".md")

    if args.baseline_template_out.strip():
        baseline_template_path = Path(args.baseline_template_out).resolve()
    else:
        baseline_template_path = output_json_path.with_name(
            output_json_path.stem + "-baseline-template.json"
        )

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_template_path.parent.mkdir(parents=True, exist_ok=True)

    endpoint_url = _build_url(args.base_url, args.endpoint)
    results: list[dict[str, Any]] = []
    for case in cases:
        payload = case.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        status_code, body, err_text = _http_post_json(
            url=endpoint_url,
            payload=payload,
            timeout_sec=float(args.timeout_sec),
            internal_key=args.internal_key,
            bearer_token=args.bearer_token,
        )
        evaluated = _evaluate_case(case, status_code, body, err_text)
        results.append(evaluated)

    triage_counter: Counter[str] = Counter()
    emergency_hits = 0
    passed_count = 0
    failed_check_counter: Counter[str] = Counter()

    confidence_scores: list[float | None] = []
    support_ratios: list[float | None] = []
    disagreement_indexes: list[float | None] = []
    data_quality_scores: list[float | None] = []

    severity_summary: dict[str, dict[str, Any]] = {}

    for item in results:
        severity = str(item.get("severity") or "unknown")
        bucket = severity_summary.setdefault(
            severity,
            {"cases": 0, "passed": 0, "triage_distribution": Counter()},
        )
        bucket["cases"] = int(bucket["cases"]) + 1

        if item.get("passed_all"):
            passed_count += 1
            bucket["passed"] = int(bucket["passed"]) + 1

        checks = item.get("checks")
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, dict) and not bool(check.get("passed")):
                    failed_check_counter[str(check.get("name") or "unknown_check")] += 1

        actual = item.get("actual")
        if not isinstance(actual, dict):
            continue
        triage = str(actual.get("winning_triage") or "unknown")
        if triage not in TRIAGE_RANK:
            triage = "unknown"
        triage_counter[triage] += 1
        bucket["triage_distribution"][triage] += 1

        if bool(actual.get("emergency_triggered")):
            emergency_hits += 1

        confidence_scores.append(_safe_float(actual.get("confidence_score")))
        support_ratios.append(_safe_float(actual.get("support_ratio")))
        disagreement_indexes.append(_safe_float(actual.get("disagreement_index")))
        data_quality_scores.append(_safe_float(actual.get("data_quality_score")))

    evaluated_cases = len(results)
    pass_rate = (passed_count / evaluated_cases) if evaluated_cases else 0.0
    escalation_ratio = (emergency_hits / evaluated_cases) if evaluated_cases else 0.0

    severity_serializable: dict[str, Any] = {}
    for key, value in severity_summary.items():
        triage_dist = value.get("triage_distribution")
        if isinstance(triage_dist, Counter):
            triage_dist = dict(triage_dist)
        severity_serializable[key] = {
            "cases": int(value.get("cases", 0)),
            "passed": int(value.get("passed", 0)),
            "pass_rate": (int(value.get("passed", 0)) / int(value.get("cases", 1))),
            "triage_distribution": triage_dist,
        }

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact": str(output_json_path),
        "input_cases": str(cases_path),
        "input_meta": meta,
        "endpoint_url": endpoint_url,
        "metrics": {
            "evaluated_cases": evaluated_cases,
            "passed_cases": passed_count,
            "pass_rate": round(pass_rate, 6),
            "escalation_ratio": round(escalation_ratio, 6),
            "triage_distribution": dict(triage_counter),
            "average_confidence_score": _mean(confidence_scores),
            "average_support_ratio": _mean(support_ratios),
            "average_disagreement_index": _mean(disagreement_indexes),
            "average_data_quality_score": _mean(data_quality_scores),
            "failed_check_breakdown": dict(failed_check_counter),
            "by_severity": severity_serializable,
        },
        "checks": {
            "all_cases_passed": passed_count == evaluated_cases,
            "minimum_pass_rate_met": pass_rate >= 0.80,
            "minimum_emergency_detection_signal": escalation_ratio >= 0.08,
        },
        "case_results": results,
    }

    baseline_template = _build_baseline_template(
        run_summary=summary,
        case_results=results,
        raw_cases=cases,
    )
    baseline_template_path.write_text(
        json.dumps(baseline_template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["baseline_template_artifact"] = str(baseline_template_path)
    summary["comparison_scaffold"] = {
        "template_file": str(baseline_template_path),
        "scoring_fields": list(SCORING_FIELDS),
        "manual_required": True,
    }

    output_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md_path.write_text(_render_markdown(summary), encoding="utf-8")

    print("[run-council-synthetic-eval] complete")
    print(f"- endpoint: {endpoint_url}")
    print(f"- evaluated_cases: {evaluated_cases}")
    print(f"- pass_rate: {pass_rate:.3f}")
    print(f"- escalation_ratio: {escalation_ratio:.3f}")
    print(f"- output_json: {output_json_path}")
    print(f"- output_md: {output_md_path}")
    print(f"- baseline_template: {baseline_template_path}")

    if args.strict and passed_count < evaluated_cases:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
