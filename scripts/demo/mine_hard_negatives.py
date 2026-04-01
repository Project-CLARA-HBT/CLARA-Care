#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data/demo/hard-negative-seed.jsonl"
DEFAULT_CASESETS = {
    "ddi_cases": ROOT / "data/demo/ddi-goldset.jsonl",
    "refusal_cases": ROOT / "data/demo/refusal-scenarios.jsonl",
    "fallback_cases": ROOT / "data/demo/fallback-scenarios.jsonl",
    "latency_cases": ROOT / "data/demo/latency-scenarios.jsonl",
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class Candidate:
    query: str
    expected_behavior: str
    reason: str
    source_run: str
    severity: str
    tags: list[str]

    def dedupe_key(self) -> tuple[str, str]:
        return (self._norm(self.query), self._norm(self.reason))

    def score(self) -> int:
        return SEVERITY_RANK.get(self.severity, 2)

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.strip().lower().split())

    def to_record(self) -> dict[str, Any]:
        digest = hashlib.sha1(
            f"{self.query}|{self.reason}|{self.source_run}".encode("utf-8")
        ).hexdigest()[:12]
        return {
            "id": f"HN-{digest}",
            "query": self.query,
            "expected_behavior": self.expected_behavior,
            "reason": self.reason,
            "source_run": self.source_run,
            "severity": self.severity,
            "tags": self.tags,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mine hard negatives from one round2 artifact run."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to run artifact directory containing kpi-report/test-report/fallback-proof.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSONL with normalized hard negatives.",
    )
    parser.add_argument(
        "--conversation-log",
        action="append",
        default=[],
        help="Optional JSON file/dir with conversation traces (can be repeated).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Maximum number of records after dedupe.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"cannot parse json: {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        rows.append(json.loads(raw))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _first_text(payload: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_source_errors(payload: dict[str, Any]) -> dict[str, Any]:
    direct = payload.get("source_errors")
    if isinstance(direct, dict) and direct:
        return direct

    response = payload.get("response_summary")
    if isinstance(response, dict):
        summary_direct = response.get("source_errors")
        if isinstance(summary_direct, dict) and summary_direct:
            return summary_direct
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            md_errors = metadata.get("source_errors")
            if isinstance(md_errors, dict) and md_errors:
                return md_errors

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        md_errors = metadata.get("source_errors")
        if isinstance(md_errors, dict) and md_errors:
            return md_errors
    return {}


def _extract_verification_matrix(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        payload.get("verification_matrix"),
        payload.get("claim_verification_matrix"),
    ]
    response = payload.get("response_summary")
    if isinstance(response, dict):
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            candidates.append(metadata.get("verification_matrix"))
            candidates.append(metadata.get("claim_verification_matrix"))

    for value in candidates:
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            rows = value.get("rows")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _extract_unsupported_claim_count(payload: dict[str, Any]) -> int:
    count = 0
    direct = payload.get("unsupported_claims")
    if isinstance(direct, list):
        count = max(count, len([x for x in direct if str(x).strip()]))
    elif isinstance(direct, int):
        count = max(count, direct)

    response = payload.get("response_summary")
    if isinstance(response, dict):
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            value = metadata.get("unsupported_claims")
            if isinstance(value, list):
                count = max(count, len([x for x in value if str(x).strip()]))
            elif isinstance(value, int):
                count = max(count, value)
            summary = metadata.get("verification_matrix_summary")
            if isinstance(summary, dict):
                unsupported = summary.get("unsupported_claims")
                if isinstance(unsupported, int):
                    count = max(count, unsupported)

    matrix = _extract_verification_matrix(payload)
    if matrix:
        unsupported_rows = [
            row
            for row in matrix
            if str(row.get("verdict") or "").strip().lower() in {"unsupported", "fail"}
        ]
        count = max(count, len(unsupported_rows))
    return count


def _is_low_context(payload: dict[str, Any]) -> bool:
    flags = [
        payload.get("low_context"),
        payload.get("degraded"),
        payload.get("degraded_path"),
        payload.get("low_context_browse"),
    ]
    response = payload.get("response_summary")
    if isinstance(response, dict):
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            flags.extend(
                [
                    metadata.get("low_context"),
                    metadata.get("degraded"),
                    metadata.get("degraded_path"),
                    metadata.get("low_context_browse"),
                ]
            )
    return any(_coerce_bool(value) for value in flags)


def _extract_source_used(payload: dict[str, Any]) -> list[str]:
    used = payload.get("source_used")
    if isinstance(used, list):
        return [str(item).strip().lower() for item in used if str(item).strip()]
    response = payload.get("response_summary")
    if isinstance(response, dict):
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            md_used = metadata.get("source_used")
            if isinstance(md_used, list):
                return [str(item).strip().lower() for item in md_used if str(item).strip()]
    return []


def load_case_lookup() -> dict[str, dict[str, dict[str, Any]]]:
    mapping: dict[str, dict[str, dict[str, Any]]] = {k: {} for k in DEFAULT_CASESETS}
    for case_group, path in DEFAULT_CASESETS.items():
        for row in read_jsonl(path):
            case_id = str(row.get("case_id") or "").strip()
            if case_id:
                mapping[case_group][case_id] = row
    return mapping


def scenario_query(case_group: str, row: dict[str, Any], scenario: dict[str, Any]) -> str:
    text = _first_text(
        row,
        ["query", "question", "prompt", "user_query", "input", "message"],
    )
    if text:
        return text

    text = _first_text(
        scenario,
        ["query", "question", "prompt", "user_query", "input", "message"],
    )
    if text:
        return text

    meds = scenario.get("medications") or row.get("medications")
    if isinstance(meds, list) and meds:
        med_names = [str(item).strip() for item in meds if str(item).strip()]
        if med_names:
            if len(med_names) == 1:
                return f"Kiểm tra an toàn thuốc {med_names[0]}"
            return "Tương tác thuốc " + " + ".join(med_names)

    payload = scenario.get("payload") if isinstance(scenario.get("payload"), dict) else row.get("payload")
    if isinstance(payload, dict):
        payload_query = _first_text(payload, ["query", "question", "prompt"])
        if payload_query:
            return payload_query

    case_id = str(row.get("case_id") or scenario.get("case_id") or "unknown").strip()
    return f"case:{case_group}:{case_id}"


def expected_behavior_for(reason_kind: str, case_group: str, scenario: dict[str, Any]) -> str:
    if reason_kind == "unsupported_claims":
        return "Chỉ trả lời claim có bằng chứng; thiếu bằng chứng thì warn/escalate, không khẳng định mạnh."
    if reason_kind == "source_errors":
        return "Khi nguồn lỗi phải degrade an toàn, ghi rõ source_errors và tránh kết luận vượt quá evidence."
    if reason_kind == "low_context":
        return "Thiếu ngữ cảnh thì yêu cầu làm rõ hoặc hạ confidence, không trả lời quá tự tin."
    if reason_kind == "wrong_source_match":
        return "Ưu tiên nguồn đúng chủ đề; loại nguồn lệch domain hoặc mismatch citation."
    if reason_kind == "critical_ddi_miss":
        return "Không bỏ sót tương tác DDI mức high/critical ở positive case."

    if case_group == "ddi_cases":
        expected_alert = _coerce_bool(scenario.get("expected_alert"))
        severity = str(scenario.get("expected_min_severity") or "none").strip().lower()
        return f"DDI alert={str(expected_alert).lower()} min_severity={severity}."
    if case_group == "refusal_cases":
        action = str(scenario.get("expected_policy_action") or "block").strip().lower()
        return f"Policy action phải là {action} đúng legal guard."
    if case_group == "fallback_cases":
        fallback = _coerce_bool(scenario.get("expect_fallback_used"))
        return f"Fallback_used={str(fallback).lower()} và source-errors metadata nhất quán."
    if case_group == "latency_cases":
        budget = int(scenario.get("budget_ms") or 0)
        return f"Đáp ứng budget latency <= {budget}ms."
    return "Hành vi phải ổn định, có evidence và đúng policy."


def mine_from_case_row(
    *,
    row: dict[str, Any],
    case_group: str,
    scenario: dict[str, Any],
    source_run: str,
) -> list[Candidate]:
    query = scenario_query(case_group, row, scenario)
    status = str(row.get("status") or "").strip().lower()
    failure_reason = str(row.get("failure_reason") or "").strip()
    source_errors = _extract_source_errors(row)
    unsupported_count = _extract_unsupported_claim_count(row)
    low_context = _is_low_context(row)

    expected_sources = scenario.get("expected_source_any")
    source_used = _extract_source_used(row)
    wrong_source = False
    if isinstance(expected_sources, list) and expected_sources and source_used:
        expected_tokens = [str(item).strip().lower() for item in expected_sources if str(item).strip()]
        if expected_tokens and not any(
            any(token in actual for token in expected_tokens) for actual in source_used
        ):
            wrong_source = True

    severe_miss = False
    if case_group == "ddi_cases":
        expected_alert = _coerce_bool(row.get("expected_alert") if "expected_alert" in row else scenario.get("expected_alert"))
        actual_alert = _coerce_bool(row.get("actual_alert"))
        min_severity = str(
            row.get("expected_min_severity") if "expected_min_severity" in row else scenario.get("expected_min_severity")
        ).strip().lower()
        if expected_alert and not actual_alert and min_severity in {"high", "critical", "severe", "contraindicated"}:
            severe_miss = True

    output: list[Candidate] = []

    if severe_miss:
        output.append(
            Candidate(
                query=query,
                expected_behavior=expected_behavior_for("critical_ddi_miss", case_group, scenario),
                reason="critical_ddi_miss",
                source_run=source_run,
                severity="critical",
                tags=["critical_ddi_miss", case_group, f"case:{row.get('case_id') or 'unknown'}"],
            )
        )

    if failure_reason or status in {"failed", "error", "blocked"}:
        detail = failure_reason or f"status={status or 'unknown'}"
        output.append(
            Candidate(
                query=query,
                expected_behavior=expected_behavior_for("failed_case", case_group, scenario),
                reason=f"failed_case:{detail}",
                source_run=source_run,
                severity="high",
                tags=["failed_case", case_group, f"case:{row.get('case_id') or 'unknown'}"],
            )
        )

    if source_errors:
        sources = sorted(source_errors.keys())
        sev = "high" if any(name in {"openfda", "rxnav", "dailymed", "clinicaltrials", "searxng"} for name in sources) else "medium"
        output.append(
            Candidate(
                query=query,
                expected_behavior=expected_behavior_for("source_errors", case_group, scenario),
                reason=f"source_errors:{','.join(sources)}",
                source_run=source_run,
                severity=sev,
                tags=["source_errors", case_group, *[f"source:{s}" for s in sources]],
            )
        )

    if unsupported_count > 0:
        output.append(
            Candidate(
                query=query,
                expected_behavior=expected_behavior_for("unsupported_claims", case_group, scenario),
                reason=f"unsupported_claims:{unsupported_count}",
                source_run=source_run,
                severity="high",
                tags=["unsupported_claims", case_group, f"count:{unsupported_count}"],
            )
        )

    if low_context:
        output.append(
            Candidate(
                query=query,
                expected_behavior=expected_behavior_for("low_context", case_group, scenario),
                reason="low_context",
                source_run=source_run,
                severity="medium",
                tags=["low_context", case_group],
            )
        )

    if wrong_source:
        output.append(
            Candidate(
                query=query,
                expected_behavior=expected_behavior_for("wrong_source_match", case_group, scenario),
                reason="wrong_source_match",
                source_run=source_run,
                severity="high",
                tags=["wrong_source_match", case_group],
            )
        )

    return output


def iter_case_rows(test_report: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    cases = test_report.get("cases")
    if isinstance(cases, list):
        for row in cases:
            if isinstance(row, dict):
                rows.append(("cases", row))
        return rows

    if isinstance(cases, dict):
        for group, group_rows in cases.items():
            if isinstance(group_rows, list):
                for row in group_rows:
                    if isinstance(row, dict):
                        rows.append((str(group), row))
    return rows


def mine_from_test_report(
    run_dir: Path,
    case_lookup: dict[str, dict[str, dict[str, Any]]],
) -> list[Candidate]:
    path = run_dir / "test-report/test-report.json"
    if not path.exists():
        return []

    payload = read_json(path)
    run_name = run_dir.name
    out: list[Candidate] = []
    for case_group, row in iter_case_rows(payload):
        case_id = str(row.get("case_id") or "").strip()
        scenario = case_lookup.get(case_group, {}).get(case_id, {})
        out.extend(
            mine_from_case_row(
                row=row,
                case_group=case_group,
                scenario=scenario,
                source_run=run_name,
            )
        )
    return out


def mine_from_fallback_proof(
    run_dir: Path,
    case_lookup: dict[str, dict[str, dict[str, Any]]],
) -> list[Candidate]:
    path = run_dir / "fallback-proof/fallback-proof.json"
    if not path.exists():
        return []

    payload = read_json(path)
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return []

    run_name = run_dir.name
    out: list[Candidate] = []
    for row in cases:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        scenario = case_lookup.get("fallback_cases", {}).get(case_id, {})
        out.extend(
            mine_from_case_row(
                row=row,
                case_group="fallback_cases",
                scenario=scenario,
                source_run=run_name,
            )
        )
    return out


def mine_from_kpi_report(run_dir: Path) -> list[Candidate]:
    path = run_dir / "kpi-report/kpi-report.json"
    if not path.exists():
        return []

    payload = read_json(path)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    scientific = metrics.get("ddi_scientific") if isinstance(metrics.get("ddi_scientific"), dict) else {}
    confusion = scientific.get("confusion_matrix") if isinstance(scientific.get("confusion_matrix"), dict) else {}

    fn = int(confusion.get("fn") or 0)
    fp = int(confusion.get("fp") or 0)
    out: list[Candidate] = []
    if fn > 0:
        out.append(
            Candidate(
                query="Bộ ca DDI positive bị bỏ sót trong KPI run",
                expected_behavior="Giảm false negative DDI, đặc biệt ở ca high/critical.",
                reason=f"kpi_false_negative:{fn}",
                source_run=run_dir.name,
                severity="critical",
                tags=["kpi", "critical_ddi_miss", f"fn:{fn}"],
            )
        )
    if fp > 0:
        out.append(
            Candidate(
                query="Bộ ca DDI negative bị cảnh báo sai trong KPI run",
                expected_behavior="Giảm false positive để tránh cảnh báo giả gây nhiễu.",
                reason=f"kpi_false_positive:{fp}",
                source_run=run_dir.name,
                severity="medium",
                tags=["kpi", "false_positive", f"fp:{fp}"],
            )
        )
    return out


def _collect_json_files(path_str: str) -> list[Path]:
    candidate = Path(path_str)
    if candidate.is_file() and candidate.suffix.lower() == ".json":
        return [candidate]
    if candidate.is_dir():
        return sorted(candidate.rglob("*.json"))
    return []


def _walk_for_candidates(
    node: Any,
    *,
    source_run: str,
    current_query: str,
    sink: list[Candidate],
) -> None:
    if isinstance(node, dict):
        query = _first_text(node, ["query", "question", "prompt", "user_query", "message"]) or current_query

        unsupported_count = _extract_unsupported_claim_count(node)
        if unsupported_count > 0 and query:
            sink.append(
                Candidate(
                    query=query,
                    expected_behavior=expected_behavior_for("unsupported_claims", "conversation", {}),
                    reason=f"unsupported_claims:{unsupported_count}",
                    source_run=source_run,
                    severity="high",
                    tags=["conversation", "unsupported_claims", f"count:{unsupported_count}"],
                )
            )

        source_errors = _extract_source_errors(node)
        if source_errors and query:
            sources = sorted(source_errors.keys())
            sink.append(
                Candidate(
                    query=query,
                    expected_behavior=expected_behavior_for("source_errors", "conversation", {}),
                    reason=f"source_errors:{','.join(sources)}",
                    source_run=source_run,
                    severity="high",
                    tags=["conversation", "source_errors", *[f"source:{s}" for s in sources]],
                )
            )

        if _is_low_context(node) and query:
            sink.append(
                Candidate(
                    query=query,
                    expected_behavior=expected_behavior_for("low_context", "conversation", {}),
                    reason="low_context",
                    source_run=source_run,
                    severity="medium",
                    tags=["conversation", "low_context"],
                )
            )

        mismatch = node.get("wrong_source_match")
        mismatch = mismatch if mismatch is not None else node.get("citation_mismatch")
        if _coerce_bool(mismatch) and query:
            sink.append(
                Candidate(
                    query=query,
                    expected_behavior=expected_behavior_for("wrong_source_match", "conversation", {}),
                    reason="wrong_source_match",
                    source_run=source_run,
                    severity="high",
                    tags=["conversation", "wrong_source_match"],
                )
            )

        for value in node.values():
            _walk_for_candidates(value, source_run=source_run, current_query=query, sink=sink)
        return

    if isinstance(node, list):
        for item in node:
            _walk_for_candidates(item, source_run=source_run, current_query=current_query, sink=sink)


def mine_from_conversation_logs(
    run_dir: Path,
    additional_logs: list[str],
) -> list[Candidate]:
    files: list[Path] = []
    auto_logs = [
        run_dir / "conversations.json",
        run_dir / "conversation-logs.json",
        run_dir / "research-logs.json",
        run_dir / "research-trace.json",
    ]
    files.extend([path for path in auto_logs if path.exists()])
    for path_str in additional_logs:
        files.extend(_collect_json_files(path_str))

    # dedupe file list while preserving order
    unique_files: list[Path] = []
    seen: set[str] = set()
    for path in files:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique_files.append(path)

    out: list[Candidate] = []
    for path in unique_files:
        payload = read_json(path)
        _walk_for_candidates(
            payload,
            source_run=run_dir.name,
            current_query="",
            sink=out,
        )
    return out


def dedupe_and_limit(candidates: list[Candidate], limit: int) -> list[Candidate]:
    best: dict[tuple[str, str], Candidate] = {}
    for item in candidates:
        key = item.dedupe_key()
        existing = best.get(key)
        if existing is None or item.score() > existing.score():
            best[key] = item

    deduped = list(best.values())
    deduped.sort(
        key=lambda item: (
            -item.score(),
            item.reason.lower(),
            item.query.lower(),
        )
    )
    return deduped[: max(limit, 1)]


def ensure_run_inputs(run_dir: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir():
        raise RuntimeError(f"run-dir not found: {run_dir}")

    test_report = run_dir / "test-report/test-report.json"
    kpi_report = run_dir / "kpi-report/kpi-report.json"
    fallback_report = run_dir / "fallback-proof/fallback-proof.json"
    if not (test_report.exists() or kpi_report.exists() or fallback_report.exists()):
        raise RuntimeError(
            "missing required artifacts under run-dir; expected at least one of "
            "test-report/test-report.json, kpi-report/kpi-report.json, fallback-proof/fallback-proof.json"
        )


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    output_path = Path(args.output)

    try:
        ensure_run_inputs(run_dir)
        case_lookup = load_case_lookup()

        mined: list[Candidate] = []
        mined.extend(mine_from_test_report(run_dir, case_lookup))
        mined.extend(mine_from_fallback_proof(run_dir, case_lookup))
        mined.extend(mine_from_kpi_report(run_dir))
        mined.extend(mine_from_conversation_logs(run_dir, args.conversation_log))

        deduped = dedupe_and_limit(mined, int(args.limit))
        records = [item.to_record() for item in deduped]
        write_jsonl(output_path, records)

        by_reason: dict[str, int] = {}
        for item in deduped:
            bucket = item.reason.split(":", 1)[0]
            by_reason[bucket] = by_reason.get(bucket, 0) + 1

        summary = {
            "run_dir": str(run_dir),
            "source_run": run_dir.name,
            "input_candidates": len(mined),
            "output_count": len(records),
            "limit": int(args.limit),
            "output_path": str(output_path),
            "reason_breakdown": by_reason,
            "conversation_log_inputs": args.conversation_log,
        }
        write_json(output_path.with_suffix(output_path.suffix + ".summary.json"), summary)

        print("[mine-hard-negatives] ok")
        print(f"- run_dir: {run_dir}")
        print(f"- input_candidates: {len(mined)}")
        print(f"- output_count: {len(records)}")
        print(f"- output: {output_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[mine-hard-negatives] failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
