from __future__ import annotations

from pathlib import Path

from evaluation.property_assurance import budget_fair_runner
from evaluation.property_assurance.mutation_overlay import MutantOverlay


def test_budget_runner_passes_remaining_budget_to_each_seed(monkeypatch) -> None:
    calls: list[int] = []
    outcomes = iter(("SURVIVED", "KILLED_TEST_ASSERTION"))

    def fake_execute_mutant(**kwargs):
        calls.append(kwargs["pytest_timeout_seconds"])
        return {"classification": next(outcomes), "runtime_ms": 1200}

    monkeypatch.setattr(budget_fair_runner, "execute_mutant", fake_execute_mutant)
    result = budget_fair_runner._run_strategy(
        repository_root=Path("."),
        mutant=MutantOverlay(
            mutant_id="W9-C01", source_path="a.py", anchor="a", replacement="b"
        ),
        method="M1_stateless_property",
        targets=["tests/test_contract.py"],
        seeds=[17, 23, 41],
        budget_ms=2500,
        pytest_timeout_seconds=600,
    )

    assert calls == [3, 2]
    assert result["used_ms"] == 2400
    assert result["time_to_first_kill_ms"] == 2400
    assert result["unused_budget_ms"] == 100
    assert result["seeds_consumed"] == 2
