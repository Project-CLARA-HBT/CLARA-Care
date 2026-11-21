"""Replay the v2 PoPETs synthetic development pilot and bind the proof to its source commit."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from evaluation.venue2027.popets.pilot_executor import (  # noqa: E402
    PilotConfig,
    load_pilot_plan,
    run_development,
    serialize_cases,
)
from research.venue2027._shared.tools import agent_protocol as ap  # noqa: E402

PROOF = Path("research/venue2027/proof")
LOG = PROOF / "logs"
OUT = PROOF / "artifacts"
SOURCE = [
    Path("evaluation/venue2027/popets/pilot_executor.py"),
    Path("evaluation/venue2027/popets/test_pilot_executor.py"),
    Path("research/venue2027/popets/protocols/pilot_plan.yaml"),
    PROOF / "emit_POPETS-pilot_report.py",
]
BASE_SHA = "a80a2bb2"


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def run_logged(argv: list[str], path: Path) -> dict:
    command = shlex.join(argv)
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    path.write_text(f"$ {command}\n{proc.stdout}{proc.stderr}")
    proc.check_returncode()
    return {"argv": command, "exit_code": proc.returncode, "log_path": str(path)}


def main() -> None:
    os.chdir(ROOT)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    for source in SOURCE:
        committed = subprocess.check_output(["git", "show", f"{sha}:{source}"])
        if committed != source.read_bytes():
            raise SystemExit(f"Commit the generating source before recording a proof: {source}")
    tests = run_logged(
        [
            "python3",
            "-m",
            "pytest",
            "-q",
            str(SOURCE[1]),
            "evaluation/venue2027/popets/test_runner.py",
        ],
        LOG / "POPETS-pilot.pytest.log",
    )
    lint = run_logged(
        ["ruff", "check", *(str(p) for p in SOURCE if p.suffix == ".py")],
        LOG / "POPETS-pilot.ruff.log",
    )
    design = load_pilot_plan()["proof_run"]
    cfg = PilotConfig(
        pilot_id="popets-pilot-proof",
        n=design["sampling_frame_n"],
        seed=design["seed"],
        arm_ids=tuple(design["arms"]),
        backend=design["backend"],
        retry_budget=design["retries"],
        per_pair_timeout_seconds=design["per_pair_timeout_seconds"],
    )
    summary, bundle, cases = run_development(cfg)
    raw, inputs = OUT / "popets_pilot_attempts.jsonl", OUT / "popets_pilot_cases.jsonl"
    artifact = OUT / "popets_pilot_report.json"
    raw.write_text(bundle.to_jsonl())
    inputs.write_text(serialize_cases(cases))
    write_json(artifact, summary.to_dict())
    for path, field in [(raw, "raw_sha256"), (inputs, "cases_sha256")]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != summary.provenance[field]:
            raise SystemExit(f"Artifact digest mismatch: {path}")

    manifest = {
        "scope": "synthetic_dev_only",
        "status": "BLOCKED",
        "source_commit": sha,
        "pilot_id": cfg.pilot_id,
        "coverage": summary.coverage,
        "runner_manifest": bundle.manifest,
        "files_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw, inputs, artifact)
        },
    }
    tracked_manifest = OUT / "popets_pilot_manifest.json"
    write_json(tracked_manifest, manifest)
    run_dir = Path("artifacts/venue2027/popets") / cfg.pilot_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "manifest.json", manifest)
    unresolved = list(load_pilot_plan()["freeze_requirements"])
    notes = (
        f"Synthetic dev split, {summary.n_cases} distinct one-query cases. "
        f"{summary.planned_pairs} cells planned, {summary.coverage['recorded']} recorded, "
        f"{summary.coverage['executed']} executed, {summary.coverage['comparable']} eligible "
        "for comparison with the family oracle. Primary leakage and clustered power remain unmeasured."
    )
    path = PROOF / "POPETS-pilot.json"
    validation_log = LOG / "POPETS-pilot.validator.log"
    paths = [*SOURCE, raw, inputs, artifact, Path(tests["log_path"]), Path(lint["log_path"])]

    def build(artifacts):
        return ap.build_report(
            task_id="POPETS-pilot",
            status="BLOCKED",
            source_sha_before=subprocess.check_output(
                ["git", "rev-parse", BASE_SHA], text=True
            ).strip(),
            source_sha_after=sha,
            changed_paths=[str(p) for p in [*paths, path, validation_log]],
            commands=[tests, lint],
            artifact_paths=[str(p) for p in artifacts],
            repo=ROOT,
            unresolved=unresolved,
            oracle_disagreement_count=summary.oracle_disagreements,
            baseline_parity="BLOCKED",
            notes=notes,
        )

    proof = build(paths)
    schema = json.loads(Path("research/venue2027/AGENTS/TASK_REPORT_SCHEMA.json").read_text())
    validate(proof, schema)
    validation = ap.validate_report(proof, repo=ROOT, expected_task_id="POPETS-pilot")
    if not validation.ok:
        raise SystemExit(validation.to_dict())
    write_json(
        validation_log, {"source_commit": sha, "validation": validation.to_dict(), "summary": notes}
    )
    proof = build([*paths, validation_log])
    validate(proof, schema)
    for file, expected in proof["artifacts_sha256"].items():
        if hashlib.sha256(Path(file).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Artifact digest mismatch: {file}")
    write_json(path, proof)
    print(notes)


if __name__ == "__main__":
    main()
