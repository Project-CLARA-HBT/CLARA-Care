#!/usr/bin/env python3
"""Run live provider probe across model families and record the real execution ledger."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "services/api/src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "services/api/src"))
if str(REPO_ROOT / "services/ml/src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "services/ml/src"))

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import controlled_benchmark_bundles
from evaluation.commitloop.oracle import compile_construction_gold
from evaluation.commitloop.malformed_sensitivity import (
    classify_error_12_class,
    normalize_error_class,
    repair_local_json_r1,
    validate_prediction_schema,
)
from evaluation.commitloop.provider import parse_json_object_content
from evaluation.commitloop.solver_packets import build_solver_packets

BASE_URL = "https://router.theclaracare.com/v1"
API_KEY = "sk-2a0a31f1216bad84-66fc8c-5b3da166"

SYSTEM_PROMPT_PATH = REPO_ROOT / "evaluation/commitloop/prompts/solver_system.txt"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

MODELS = [
    "claude-sonnet-4.6",
    "gemini-3.6-flash-high",
    "gemini-3.8-flash-tiered",
]

CONDITIONS = ("glhs_hybrid_thss_strict", "full_authorized_history")


def execute_single_request(item: tuple[str, str, str, dict, dict]) -> dict:
    model, case_id, cond, pkt, gold = item
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(pkt, sort_keys=True)},
        ],
        "temperature": 0,
        "max_tokens": 256,
    }

    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    start_t = time.perf_counter()
    raw_output = ""
    reported_model_id = "unknown"
    request_id = f"req_{hashlib.sha256(f'{model}:{cond}:{case_id}'.encode()).hexdigest()[:16]}"
    provider = "Anthropic" if "claude" in model.lower() else ("Google" if "gemini" in model.lower() else "Unknown")
    usage: dict[str, int | float | None] = {}
    error_cls = None
    parsed_out = None
    err_msg = None

    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            if resp_data.get("id"):
                request_id = str(resp_data["id"])
            reported_model_id = resp_data.get("model", "unknown")
            usage_raw = resp_data.get("usage")
            usage = usage_raw if isinstance(usage_raw, dict) else {}
            choices = resp_data.get("choices", [])
            if choices and isinstance(choices[0], dict) and "message" in choices[0]:
                raw_output = choices[0]["message"].get("content", "")

            try:
                parsed_out = parse_json_object_content(raw_output)
                if not validate_prediction_schema(parsed_out):
                    error_cls = "schema_mismatch"
                    err_msg = "Prediction dictionary missing required keys or invalid values"
            except Exception as parse_err:
                err_msg = str(parse_err)
                error_cls = classify_error_12_class("JSONDecodeError", err_msg, raw_output)

    except Exception as net_err:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        err_msg = str(net_err)
        error_cls = classify_error_12_class("ProviderError", err_msg, "")

    is_itt_correct = False
    if parsed_out and validate_prediction_schema(parsed_out) and not error_cls and gold:
        is_itt_correct = (
            parsed_out.get("lifecycle_state") == gold.get("lifecycle_state")
            and parsed_out.get("evidence_state") == gold.get("evidence_state")
            and parsed_out.get("timeliness_state") == gold.get("timeliness_state")
        )

    return {
        "request_id": request_id,
        "requested_model_id": model,
        "reported_model_id": reported_model_id,
        "provider": provider,
        "case_id": case_id,
        "condition": cond,
        "key": f"{model}:{cond}:{case_id}",
        "raw_output": raw_output,
        "parsed_output": parsed_out,
        "error_class": error_cls,
        "error_classification": error_cls,
        "error_detail": err_msg,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "latency_ms": round(elapsed_ms, 2),
        "is_itt_correct": is_itt_correct,
    }


def save_ledger(ledger: list, error_counts: dict) -> None:
    out_ledger_path = REPO_ROOT / "protocols/commitloop/v8-glhs-q2-r2/provider_run_ledger.json"
    summary_data = {
        "schema_version": "commitloop-provider-run-ledger.v8-q2-r2",
        "recorded_utc": datetime.now(UTC).isoformat(),
        "total_requests": len(ledger),
        "models_tested": MODELS,
        "conditions_tested": list(CONDITIONS),
        "error_taxonomy_breakdown": error_counts,
        "ledger": ledger,
    }
    out_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    out_ledger_path.write_text(json.dumps(summary_data, indent=2) + "\n", encoding="utf-8")


def run_probe_and_record() -> dict:
    valid_cutoff = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    known_cutoff = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)

    bundles = controlled_benchmark_bundles()
    work_items = []

    for bundle in bundles:
        token, events = ingest_bundle(
            bundle, fhir_version="R4", ingested_at=datetime(2026, 1, 4, tzinfo=UTC)
        )
        candidates = mine_candidates(token, events)
        if not candidates:
            continue
        case = candidates[0]
        gold = compile_construction_gold(
            case, events, valid_cutoff=valid_cutoff, known_cutoff=known_cutoff
        )
        packets = build_solver_packets(
            case,
            events,
            valid_cutoff=valid_cutoff,
            known_cutoff=known_cutoff,
            conditions=CONDITIONS,
        )
        for cond in CONDITIONS:
            for model in MODELS:
                work_items.append((model, case.case_id, cond, packets[cond], gold))

    print(f"Executing {len(work_items)} total live provider requests with concurrency=6...", flush=True)

    ledger = []
    error_counts: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(execute_single_request, item): item for item in work_items}
        for future in as_completed(futures):
            res = future.result()
            ledger.append(res)
            err_cls = res["error_classification"]
            if err_cls:
                error_counts[err_cls] = error_counts.get(err_cls, 0) + 1
            print(
                f"  [{res['requested_model_id']}] {res['case_id']} ({res['condition']}) -> {res['reported_model_id']} | err={err_cls} | {res['latency_ms']}ms | toks={res['total_tokens']}",
                flush=True,
            )
            save_ledger(ledger, error_counts)

    print(f"\nSaved provider run ledger to protocols/commitloop/v8-glhs-q2-r2/provider_run_ledger.json (Total = {len(ledger)})", flush=True)
    return {
        "total_requests": len(ledger),
        "error_taxonomy_breakdown": error_counts,
    }


if __name__ == "__main__":
    run_probe_and_record()
