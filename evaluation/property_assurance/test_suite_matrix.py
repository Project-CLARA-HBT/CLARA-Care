from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.property_assurance.suite_matrix import (
    METHOD_IDS,
    load_development_suite_matrix,
)


def test_development_matrix_has_all_prespecified_methods() -> None:
    root = Path(__file__).resolve().parents[2]
    matrix = load_development_suite_matrix(
        root / "research/assurance_soict/development_suite_matrix.json"
    )
    assert tuple(matrix) == METHOD_IDS
    assert matrix["M3_combined"] == [
        *matrix["M0_regression"],
        *matrix["M1_stateless_property"],
        *matrix["M2_state_machine"],
    ]


def test_matrix_rejects_a_combined_suite_with_missing_method_target(tmp_path: Path) -> None:
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            {
                "status": "development_only_not_frozen",
                "suites": {
                    "M0_regression": ["m0.py"],
                    "M1_stateless_property": ["m1.py"],
                    "M2_state_machine": ["m2.py"],
                    "M3_combined": ["m0.py", "m1.py"],
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="govmut_suite_matrix_combined_invalid"):
        load_development_suite_matrix(path)
