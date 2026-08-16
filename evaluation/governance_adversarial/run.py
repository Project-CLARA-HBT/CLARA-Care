"""Retired legacy GovRed transport runner.

The former runner consumed an incompatible ``attacks``/``scenario`` manifest
and could have emitted transport observations that were not paired to the
current frozen logical case/arm contract. A real-boundary adapter must instead
implement the current manifest schema and DB/cache/audit observations.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError


def run(*, manifest_path: Path, base_url: str, output_path: Path, allow_network: bool) -> None:
    """Refuse legacy execution rather than emit protocol-incompatible output."""

    del manifest_path, base_url, output_path, allow_network
    raise FreezeError("govred_legacy_transport_runner_retired_requires_current_boundary_adapter")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    try:
        run(
            manifest_path=args.manifest,
            base_url=args.base_url,
            output_path=args.output,
            allow_network=args.allow_network,
        )
    except FreezeError as exc:
        parser.error(str(exc))
