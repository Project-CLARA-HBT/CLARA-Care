"""Execute operator-authored governance attacks through an explicitly authorized API boundary.

The harness records transport observations only. Human/operator adjudication is
required before producing adversarial_results.csv.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json
from evaluation.governance_adversarial.validate_results import SCENARIOS

REQUIRED_ATTACK_FIELDS = frozenset({"attack_id", "scenario", "method", "path"})


def _body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def run(manifest_path: Path, base_url: str, output_path: Path, *, allow_network: bool) -> None:
    if not allow_network:
        raise FreezeError("network_execution_requires_explicit_allow_network")
    manifest = load_frozen_json(manifest_path)
    if manifest.get("status") != "frozen":
        raise FreezeError("attack_manifest_not_frozen")
    attacks = manifest.get("attacks")
    if not isinstance(attacks, list) or {item.get("scenario") for item in attacks} != SCENARIOS:
        raise FreezeError("attack_manifest_scenarios_incomplete")
    if not base_url.startswith(("http://", "https://")):
        raise FreezeError("invalid_boundary_base_url")
    token = os.environ.get("CLARA_EVIDENCE_BOUNDARY_TOKEN", "")
    observations: list[dict[str, object]] = []
    for attack in attacks:
        if not isinstance(attack, dict) or REQUIRED_ATTACK_FIELDS - attack.keys():
            raise FreezeError("attack_manifest_item_incomplete")
        path = str(attack["path"])
        if not path.startswith("/") or "://" in path:
            raise FreezeError("attack_path_must_be_relative")
        raw_body = json.dumps(attack.get("body", {}), sort_keys=True).encode()
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=raw_body if attack["method"] in {"POST", "PUT", "PATCH"} else None,
            method=str(attack["method"]).upper(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
        )
        started = time.perf_counter_ns()
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                response_body = response.read()
                error = None
        except urllib.error.HTTPError as exc:
            status = exc.code
            response_body = exc.read()
            error = "http_error"
        except (OSError, TimeoutError) as exc:
            status = None
            response_body = b""
            error = type(exc).__name__
        observations.append({
            "attack_id": attack["attack_id"],
            "scenario": attack["scenario"],
            "status_code": status,
            "latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "response_body_sha256": _body_hash(response_body),
            "transport_error": error,
            "observed_at": datetime.now(UTC).isoformat(),
            "operator_label_required": True,
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "status": "transport_observations_only",
        "base_url": base_url,
        "observations": observations,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    try:
        run(args.manifest, args.base_url, args.output, allow_network=args.allow_network)
    except FreezeError as exc:
        parser.error(str(exc))
