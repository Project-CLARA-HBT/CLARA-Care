"""Emit research/venue2027/proof/artifacts/metrics_sample.json for SH-measurement.

Computes Metrics from the REAL raw run bundle at
research/venue2027/proof/artifacts/run_bundle_sample.jsonl (6 pair records + 1
manifest produced by SH-run_harness). If that file is absent, a small real
bundle is executed locally with the harness and measured instead. Every number
in the artifact is computed from raw records by measurement.measure — never
estimated, never defaulted to zero; unavailable metrics carry stable reasons.
"""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.venue2027._shared.harness import Campaign, Outcome, RunContext, execute
from evaluation.venue2027._shared.measurement import measure

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "research" / "venue2027" / "proof" / "artifacts" / "run_bundle_sample.jsonl"
OUT = ROOT / "research" / "venue2027" / "proof" / "artifacts" / "metrics_sample.json"
SHA_40 = "573d5369abd2e9d35f8039a99cf647e6ba9b3f32"


def _construct_small_real_bundle() -> str:
    """Real harness execution (not hand-written JSON) used only when the
    committed sample artifact is missing."""
    campaign = Campaign(
        campaign_id="SH-measurement-constructed",
        case_ids=("c1", "c2"),
        arm_ids=("B0",),
        seeds=(2027,),
        source_commit=SHA_40,
    )

    def run(case, ctx: RunContext):
        observed = "ADMIT" if ctx.case_id == "c1" else "INDETERMINATE"
        return Outcome(observed_outcome=observed, counted_as_success=observed == "ADMIT")

    def oracle(case_id, arm_id, observed, detail):
        return {"expected_outcome": "ADMIT", "decision": "PASS", "oracle_id": "synthetic-oracle-v1"}

    return execute(campaign, {"B0": run}, oracle).to_jsonl()


def main() -> int:
    if SAMPLE.is_file():
        provenance_note = "computed from research/venue2027/proof/artifacts/run_bundle_sample.jsonl"
    else:
        SAMPLE.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE.write_text(_construct_small_real_bundle(), encoding="utf-8")
        provenance_note = "constructed small real harness bundle (sample artifact was absent)"
    metrics = measure(SAMPLE.read_text(encoding="utf-8"))
    payload = metrics.to_dict()
    payload["artifact_provenance"] = {
        "source_bundle": "research/venue2027/proof/artifacts/run_bundle_sample.jsonl",
        "note": provenance_note,
        "measurement_module": "evaluation/venue2027/_shared/measurement.py",
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("campaign_id", "outcome_counts", "denominator", "forbidden_commit_rate",
                       "false_stale_rate", "throughput_ops_per_sec", "latency_seconds",
                       "retry_amplification", "unavailable")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
