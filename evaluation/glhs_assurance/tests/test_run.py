from __future__ import annotations

import hashlib
import json

from evaluation.glhs_assurance.run import run_assurance


def test_network_free_assurance_emits_reconstructable_metrics(tmp_path) -> None:
    output = tmp_path / "assurance"
    metrics = run_assurance(output=output, subjects=3)
    assert metrics["external_calls"] == 0
    assert metrics["final_state_version"] == 3
    assert metrics["reconstructed_commitments"] == 3
    assert metrics["thss_pipeline_order"] == [
        "authorization",
        "temporal_lifecycle",
        "conflict",
        "relevance_freshness",
        "minimization",
    ]
    assert metrics["throughput_transitions_per_second"] > 0
    assert metrics["storage"]["incremental_bytes_per_transition"] > 0
    payload = output / "metrics.json"
    declared = (output / "checksums.sha256").read_text(encoding="utf-8").split()[0]
    assert declared == hashlib.sha256(payload.read_bytes()).hexdigest()
    assert json.loads(payload.read_text(encoding="utf-8")) == metrics
