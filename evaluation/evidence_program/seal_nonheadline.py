"""Hash a complete non-headline run without bypassing the headline seal."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def seal(run_dir: Path) -> Path:
    required = {
        "environment.json",
        "run-status.json",
        "report.md",
        "fhir-source-derived/cohort_manifest.json",
        "domain-source-derived/summary.json",
        "domain-source-derived/system_outputs.csv",
        "domain-source-derived/domain_results.csv",
        "q3-mimic-clinical-run/summary.json",
        "q3-mimic-ed-run/summary.json",
        "assurance/junit.xml",
    }
    missing = sorted(name for name in required if not (run_dir / name).is_file())
    if missing:
        raise ValueError("nonheadline_artifacts_missing:" + ",".join(missing))
    files = {}
    for path in sorted(candidate for candidate in run_dir.rglob("*") if candidate.is_file()):
        relative = str(path.relative_to(run_dir))
        if relative == "artifact-sha256.json":
            continue
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema_version": "evidence-program-nonheadline-seal-v1",
        "status": "sealed_nonheadline_not_claim_eligible",
        "headline_claims_permitted": False,
        "files": files,
    }
    target = run_dir / "artifact-sha256.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(seal(args.run_dir))
