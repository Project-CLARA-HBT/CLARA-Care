from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.run import run


def test_legacy_transport_runner_fails_closed() -> None:
    with pytest.raises(
        FreezeError,
        match="govred_legacy_transport_runner_retired_requires_current_boundary_adapter",
    ):
        run(
            manifest_path=Path("manifest.json"),
            base_url="http://127.0.0.1:18101",
            output_path=Path("result.json"),
            allow_network=True,
        )
