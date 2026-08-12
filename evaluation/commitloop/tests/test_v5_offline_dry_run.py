from __future__ import annotations

import json

from evaluation.commitloop.v5_offline_dry_run import run_offline_v5_dry_run


def test_offline_v5_dry_run_has_no_provider_calls_and_is_valid(tmp_path) -> None:
    # One reduced deterministic subject is enough to exercise the orchestration;
    # the production CLI always builds the frozen 384-subject cohort.
    from evaluation.commitloop import v5_offline_dry_run
    from evaluation.commitloop.v5_cohort import build_cohort

    rows, manifest = build_cohort()
    monkeypatched = (rows[:1], {**manifest, "subject_count": 1, "subject_token_count": 1, "bundle_hash_count": 1})
    original = v5_offline_dry_run.write_cohort

    def write_one(output):
        output.mkdir(parents=True, exist_ok=True)
        cohort = output / "cohort.jsonl"
        manifest_path = output / "cohort_manifest.json"
        cohort.write_text(json.dumps(monkeypatched[0][0]) + "\n", encoding="utf-8")
        manifest_path.write_text(json.dumps(monkeypatched[1]), encoding="utf-8")
        return cohort, manifest_path

    v5_offline_dry_run.write_cohort = write_one
    try:
        report = run_offline_v5_dry_run(output_dir=tmp_path / "run", cohort_dir=tmp_path / "cohort")
    finally:
        v5_offline_dry_run.write_cohort = original
    assert report["status"] == "VALID"
    assert report["provider_calls"] == 0
    assert report["injected_transport_calls"] == 27
    assert json.loads((tmp_path / "run" / "run_manifest.json").read_text())["max_concurrency"] == 5
    assert json.loads((tmp_path / "run" / "run_manifest.json").read_text())["batch_size"] == 5
