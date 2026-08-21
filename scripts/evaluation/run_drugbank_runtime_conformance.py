#!/usr/bin/env python3
"""Exercise a running strict CareGuard deployment against a DrugBank artifact.

This is a source-conformance check: expected positive and negative pairs are
constructed from the *same immutable DrugBank artifact* that the runtime is
configured to use.  It proves that the HTTP path, manifest-verified SQLite
index, and pair lookup agree for a deterministic sample.  It is deliberately
not described as an independent clinical-accuracy benchmark.

The report contains aggregate counts, timings, source identity and failure
classes only.  It intentionally omits licensed DrugBank interaction text and
individual medication pairs.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_artifact(artifact_dir: Path) -> tuple[dict[str, Any], list[tuple[str, str]], list[str]]:
    manifest = _read_json(artifact_dir / "manifest.json")
    if manifest.get("source") != "drugbank":
        raise ValueError("Artifact manifest source must be drugbank")

    pairs: list[tuple[str, str]] = []
    for shard in manifest.get("ddi_shards", []):
        if not isinstance(shard, dict) or not isinstance(shard.get("file"), str):
            raise ValueError("Malformed DDI shard declaration")
        payload = _read_json(artifact_dir / shard["file"])
        for rule in payload.get("rules", []):
            meds = rule.get("medications") if isinstance(rule, dict) else None
            if not isinstance(meds, list) or len(meds) != 2:
                continue
            left, right = (str(meds[0]).strip().lower(), str(meds[1]).strip().lower())
            if left and right and left != right:
                pairs.append(tuple(sorted((left, right))))

    candidates: set[str] = set()
    for shard in manifest.get("dictionary_shards", []):
        if not isinstance(shard, dict) or not isinstance(shard.get("file"), str):
            raise ValueError("Malformed dictionary shard declaration")
        payload = _read_json(artifact_dir / shard["file"])
        for record in payload.get("records", []):
            if isinstance(record, dict):
                value = str(record.get("normalized_name") or "").strip().lower()
                if value:
                    candidates.add(value)

    unique_pairs = sorted(set(pairs))
    if not unique_pairs or len(candidates) < 2:
        raise ValueError("Artifact has insufficient DDI pairs or dictionary entries")
    return manifest, unique_pairs, sorted(candidates)


def _negative_pairs(candidates: list[str], known_pairs: set[tuple[str, str]], count: int, rng: random.Random) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    attempts = 0
    limit = max(count * 100, 10_000)
    while len(output) < count and attempts < limit:
        attempts += 1
        pair = tuple(sorted(rng.sample(candidates, 2)))
        if pair not in known_pairs and pair not in seen:
            output.append(pair)
            seen.add(pair)
    if len(output) != count:
        raise RuntimeError(f"Could not construct {count} non-interacting pairs")
    return output


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * quantile)))
    return round(ordered[index], 3)


def _call(base_url: str, api_key: str, pair: tuple[str, str], timeout: float) -> tuple[dict[str, Any], float]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/careguard/analyze",
        data=json.dumps(
            {
                "medications": list(pair),
                "symptoms": [],
                "allergies": [],
                "drugbank_required": True,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-ML-Internal-Key": api_key},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 -- controlled operator URL
        payload = json.loads(response.read().decode("utf-8"))
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not isinstance(payload, dict):
        raise ValueError("CareGuard response was not a JSON object")
    return payload, elapsed_ms


def _is_drugbank_ready(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return False
    drugbank = metadata.get("drugbank")
    return isinstance(drugbank, dict) and drugbank.get("state") == "ready"


def _positive_hit(payload: dict[str, Any], expected_pair: tuple[str, str]) -> bool:
    if not _is_drugbank_ready(payload):
        return False
    for alert in payload.get("ddi_alerts", []):
        if not isinstance(alert, dict) or alert.get("source") != "drugbank":
            continue
        medications = alert.get("medications")
        if isinstance(medications, list) and tuple(sorted(str(item).lower() for item in medications)) == expected_pair:
            return True
    return False


def _negative_clear(payload: dict[str, Any]) -> bool:
    if not _is_drugbank_ready(payload):
        return False
    return not any(
        isinstance(alert, dict) and alert.get("source") == "drugbank"
        for alert in payload.get("ddi_alerts", [])
    )


def _evaluate(kind: str, pairs: list[tuple[str, str]], base_url: str, api_key: str, timeout: float) -> dict[str, Any]:
    passed = 0
    latencies: list[float] = []
    failures: dict[str, int] = {}
    for pair in pairs:
        try:
            payload, elapsed_ms = _call(base_url, api_key, pair, timeout)
            latencies.append(elapsed_ms)
            ok = _positive_hit(payload, pair) if kind == "positive" else _negative_clear(payload)
            if ok:
                passed += 1
            else:
                # In strict identity mode, a many-to-one DrugBank alias is a
                # deliberate fail-closed clarification, not an all-clear and
                # not an HTTP/runtime defect.  Keep it separately visible;
                # this runner never auto-selects a candidate on the user's
                # behalf merely to inflate source-conformance coverage.
                if payload.get("status") == "requires_medication_clarification":
                    reason = "requires_medication_clarification"
                else:
                    status = payload.get("ddi_status")
                    reason = status.get("reason") if isinstance(status, dict) else ""
                    if not reason and _is_drugbank_ready(payload):
                        reason = "drugbank_ready_missing_expected_alert"
                    if not reason:
                        response_status = payload.get("status")
                        reason = (
                            f"response_status_{response_status}"
                            if isinstance(response_status, str) and response_status
                            else "response_mismatch"
                        )
                key = str(reason or "response_mismatch")
                failures[key] = failures.get(key, 0) + 1
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            key = type(exc).__name__
            failures[key] = failures.get(key, 0) + 1

    total = len(pairs)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 6) if total else None,
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 3) if latencies else None,
        },
        "failure_classes": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8110")
    parser.add_argument("--api-key-env", default="ML_INTERNAL_API_KEY")
    parser.add_argument("--positive-sample", type=int, default=250)
    parser.add_argument("--negative-sample", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        parser.error(f"Environment variable {args.api_key_env} is required")
    if args.positive_sample < 1 or args.negative_sample < 1:
        parser.error("Sample counts must be positive")

    manifest, known_pairs, candidates = _load_artifact(args.artifact_dir)
    if args.positive_sample > len(known_pairs):
        parser.error(f"positive sample exceeds available pair count ({len(known_pairs)})")
    rng = random.Random(args.seed)
    positives = rng.sample(known_pairs, args.positive_sample)
    negatives = _negative_pairs(candidates, set(known_pairs), args.negative_sample, rng)

    positive_result = _evaluate("positive", positives, args.base_url, api_key, args.timeout_seconds)
    negative_result = _evaluate("negative", negatives, args.base_url, api_key, args.timeout_seconds)
    report = {
        "schema_version": "clara.drugbank-runtime-conformance.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "study_type": "drugbank_runtime_conformance_not_independent_clinical_benchmark",
        "interpretation": (
            "This checks a strict running CareGuard deployment against deterministic samples "
            "from the same checksum-verified DrugBank artifact. It does not estimate clinical "
            "accuracy, generalization to another DrugBank release, or patient safety."
        ),
        "runtime": {"base_url": args.base_url, "strict_drugbank_required": True},
        "artifact": {
            key: manifest.get(key)
            for key in ("source", "source_version", "source_sha256", "manifest_sha256", "ddi_rule_count", "dictionary_record_count")
        },
        "sampling": {
            "seed": args.seed,
            "available_positive_pairs": len(known_pairs),
            "available_canonical_medications": len(candidates),
            "positive_sample": args.positive_sample,
            "negative_sample": args.negative_sample,
        },
        "positive_pair_lookup": positive_result,
        "negative_pair_lookup": negative_result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if positive_result["failed"] == 0 and negative_result["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
