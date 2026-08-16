"""Create a balanced GovRed development manifest for review before freezing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.governance_adversarial.protocol import build_development_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--statistics-plan-sha256", required=True)
    parser.add_argument("--repetitions", type=int, default=30)
    args = parser.parse_args()
    manifest = build_development_manifest(
        seed=args.seed,
        statistics_plan_sha256=args.statistics_plan_sha256,
        repetitions=args.repetitions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
