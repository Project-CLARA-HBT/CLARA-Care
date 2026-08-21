"""Frozen 120-case, three-seed model arm for GLHS Q2.

This runner sends synthetic structural cases only.  It never transmits patient
data and never falls back to another model or a heuristic answer.  The endpoint
must return normally; timeout/HTTP/schema failures are recorded per case.
"""

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

SEEDS = (20260808, 20260809, 20260810)
LABELS = {"state_current", "conflict", "withheld", "1000mg"}
STATE_CODES = {
    "state_current": "CURRENT",
    "1000mg": "STALE_REJECTED",
    "conflict": "CONFLICT",
    "withheld": "WITHHELD",
}
CODE_TO_STATE = {value: key for key, value in STATE_CODES.items()}

PROMPT_VERSION = "glhs-q2-model-arm-v2"


def _direct_selection_contract() -> dict[str, object]:
    """Freeze non-secret registry selection before the first provider call."""

    from clara_ml.config import settings
    from clara_ml.llm.model_registry import (
        ModelTask,
        resolve_model_selection,
        task_contract,
    )

    task = ModelTask.MEDICAL_SAFETY_ROUTER
    selection = resolve_model_selection(task, settings)
    contract = task_contract(task)
    if selection.fallback_model or selection.rollback_applied:
        raise RuntimeError("model_arm_no_fallback_contract_violated")
    return {
        "task": task.value,
        "provider": selection.provider,
        "configured_model": selection.model,
        "model_version": selection.model_version,
        "model_profile": selection.model_profile,
        "prompt_version": selection.prompt_version,
        "task_contract_schema_version": selection.contract_schema_version,
        "risk_level": selection.risk_level,
        "fallback_model": selection.fallback_model,
        "rollback_applied": selection.rollback_applied,
        "generation_temperature": contract.temperature,
        "generation_max_tokens": 100,
        "configured_base_url_sha256": hashlib.sha256(
            str(settings.deepseek_base_url or "").strip().encode("utf-8")
        ).hexdigest(),
    }


def _selected(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    # Fixed stratified selection: 30 direct, 72 compositional, 18 ambiguity.
    buckets = {"direct_conformance": 30, "compositional_stress": 72, "ambiguity_escalation": 18}
    selected: list[dict[str, str]] = []
    for experiment, target in buckets.items():
        chosen = [row for row in rows if row["experiment"] == experiment][:target]
        if len(chosen) != target:
            raise ValueError(f"frozen_subset_insufficient:{experiment}")
        selected.extend(chosen)
    if len(selected) != 120:
        raise ValueError("frozen_subset_must_have_120_cases")
    return selected


def _query(row: dict[str, str], seed: int) -> str:
    # Opaque labels avoid accidentally asking the medical hard guard to reason
    # about a dose string.  This is a structural benchmark, not a medication
    # task; the one-to-one label mapping is fixed above before any run.
    return (
        "Bạn là bộ phân loại cấu trúc cho bài tập tin học mô phỏng; đây không phải nội dung sức khỏe và không có người dùng thật. "
        f"Scenario={row['scenario']}; state_code phải là một trong {{CURRENT,STALE_REJECTED,CONFLICT,WITHHELD}}. "
        "Dựa duy nhất vào quy tắc an toàn: bằng chứng muộn không được reset hiện tại; "
        "mâu thuẫn phải giữ conflict; thiếu provenance hoặc sai consent phải withheld; "
        "stale/direct-write phải không được xác nhận. "
        "Chỉ trả một JSON object không markdown với keys state_code và decision. "
        "decision là keep, escalate, hoặc reject. "
        f"seed={seed}; case={row['case_id']}."
    )


def _request_http(
    url: str, key: str, row: dict[str, str], seed: int, timeout: float
) -> tuple[dict, float]:
    payload = {
        "query": _query(row, seed),
        "role": "admin",
        "protocol": "chat",
        "rag_flow": {
            "scientific_retrieval_enabled": False,
            "web_retrieval_enabled": False,
            "file_retrieval_enabled": False,
            "verification_enabled": False,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-ML-Internal-Key": key},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read()), (time.perf_counter() - started) * 1000


def _request_direct(row: dict[str, str], seed: int) -> tuple[dict, float]:
    """Call the configured task client directly, with no safety-router fallback.

    The model arm is a non-clinical structural experiment.  Running through the
    End_User medical route would invoke a medical-policy classifier first and
    would incorrectly turn opaque benchmark labels into a policy test.  The
    direct task client remains governed by the versioned model registry and
    has an empty ``fallback_model`` by contract; provider failures propagate as
    recorded errors rather than selecting another model or heuristic output.
    """

    from clara_ml.config import settings
    from clara_ml.llm.model_registry import ModelTask, build_task_client

    client, selection = build_task_client(ModelTask.MEDICAL_SAFETY_ROUTER, settings)
    if selection.fallback_model or selection.rollback_applied:
        raise RuntimeError("model_arm_no_fallback_contract_violated")
    started = time.perf_counter()
    response = client.generate(
        _query(row, seed),
        system_prompt=(
            "Bạn trả lời bài toán trạng thái máy tính. Không diễn giải; chỉ trả JSON hợp lệ "
            "với state_code và decision theo đúng vocabulary của câu hỏi."
        ),
        max_tokens=100,
    )
    return {
        "answer": response.content,
        "model_used": response.model,
        "policy_action": "direct_model_arm",
        "guard_reason": "",
        "selection_profile": selection.model_profile,
    }, (time.perf_counter() - started) * 1000


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--code-revision",
        required=True,
        help="Frozen git commit that owns this runner and protocol.",
    )
    p.add_argument("--transport", choices=("direct", "http"), default="direct")
    p.add_argument("--url", default="http://127.0.0.1:8010/v1/chat/routed")
    p.add_argument("--timeout", type=float, default=90.0)
    args = p.parse_args()
    key = os.environ.get("ML_INTERNAL_API_KEY", "")
    rows = _selected(list(csv.DictReader(args.cases.open(encoding="utf-8"))))
    args.output.mkdir(parents=True, exist_ok=True)
    if len(args.code_revision) < 7:
        raise ValueError("model_arm_code_revision_invalid")
    contract = {
        "version": PROMPT_VERSION,
        "code_revision": args.code_revision,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seeds": list(SEEDS),
        "case_count": len(rows),
        "case_ids_sha256": hashlib.sha256(
            "\n".join(r["case_id"] for r in rows).encode()
        ).hexdigest(),
        "transport": args.transport,
        "endpoint": args.url if args.transport == "http" else "governed_direct_task_client",
        "no_fallback": True,
        "synthetic_only": True,
    }
    if args.transport == "direct":
        contract["runtime_selection"] = _direct_selection_contract()
    (args.output / "model_arm_contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    results = []
    checkpoint = args.output / "model_per_run.partial.csv"
    fieldnames = [
        "case_id",
        "seed",
        "expected_state",
        "scenario",
        "experiment",
        "status",
        "latency_ms",
        "model_used",
        "policy_action",
        "guard_reason",
        "degraded",
        "json_valid",
        "state",
        "state_correct",
        "answer_sha256",
        "error_class",
    ]
    with checkpoint.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fieldnames).writeheader()
    for seed in SEEDS:
        for row in rows:
            record = {
                "case_id": row["case_id"],
                "seed": seed,
                "expected_state": row["expected_state"],
                "scenario": row["scenario"],
                "experiment": row["experiment"],
            }
            try:
                response, latency = (
                    _request_direct(row, seed)
                    if args.transport == "direct"
                    else _request_http(args.url, key, row, seed, args.timeout)
                )
                answer = str(response.get("answer") or "").strip()
                parsed = json.loads(answer) if answer.startswith("{") else {}
                code = parsed.get("state_code") if isinstance(parsed, dict) else None
                state = CODE_TO_STATE.get(code) if isinstance(code, str) else None
                model_used = str(response.get("model_used") or "")
                policy_action = str(response.get("policy_action") or "")
                # Missing provider provenance or a policy refusal invalidates
                # the run; neither can be silently counted as completion.
                completed = bool(model_used) and policy_action != "block"
                record.update(
                    {
                        "status": "completed" if completed else "invalid_runtime",
                        "latency_ms": round(latency, 3),
                        "model_used": model_used,
                        "policy_action": policy_action,
                        "guard_reason": str(response.get("guard_reason") or ""),
                        "degraded": model_used.startswith(("local-synth", "api-safe", "api-local")),
                        "json_valid": isinstance(parsed, dict),
                        "state": state or "",
                        "state_correct": state == row["expected_state"],
                        "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
                    }
                )
            except (
                OSError,
                ValueError,
                urllib.error.URLError,
                urllib.error.HTTPError,
                json.JSONDecodeError,
            ) as exc:
                record.update(
                    {
                        "status": "error",
                        "error_class": type(exc).__name__,
                        "latency_ms": "",
                        "model_used": "",
                        "policy_action": "",
                        "guard_reason": "",
                        "degraded": "",
                        "json_valid": False,
                        "state": "",
                        "state_correct": False,
                        "answer_sha256": "",
                    }
                )
            results.append(record)
            with checkpoint.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writerow({key: record.get(key, "") for key in fieldnames})
    with (args.output / "model_per_run.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{key: record.get(key, "") for key in fieldnames} for record in results])
    completed = [r for r in results if r["status"] == "completed"]
    summary = {
        "contract": contract,
        "total": len(results),
        "completed": len(completed),
        "errors": len(results) - len(completed),
        "json_valid": sum(bool(r["json_valid"]) for r in completed),
        "state_correct": sum(bool(r["state_correct"]) for r in completed),
        "latency_ms": {
            "p50": sorted([float(r["latency_ms"]) for r in completed])[len(completed) // 2]
            if completed
            else None
        },
    }
    (args.output / "model_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
