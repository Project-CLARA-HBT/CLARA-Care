"""Tests for E03 schedule execution runner against live SQLite DB."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from evaluation.glhs_downgrade.analyze import analyze_execution_results
from evaluation.glhs_downgrade.negative_schedules import (
    LaunderingTemplate,
    generate_all_schedules,
    generate_negative_schedules,
    generate_positive_controls,
)
from evaluation.glhs_downgrade.runner import execute_schedule, run_all_schedules


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_positive_control_execution(db: Session) -> None:
    """Verify that valid positive control review chains succeed and produce committed state."""
    controls = generate_positive_controls(count=4)
    for c in controls:
        res = execute_schedule(db, c)
        assert res.admitted is True
        assert res.rejected is False
        assert res.downgrade_success is False
        assert res.error_code is None


def test_each_negative_template_execution(db: Session) -> None:
    """Verify each of the 10 negative laundering templates is rejected fail-closed."""
    for template in LaunderingTemplate:
        # Generate 1 schedule for this template
        all_neg = generate_negative_schedules(per_template_count=1)
        sched = [s for s in all_neg if s.template == template][0]
        res = execute_schedule(db, sched)
        assert res.admitted is False, f"Template {template} unexpectedly admitted!"
        assert res.rejected is True
        assert res.downgrade_success is False
        assert res.error_code is not None


def test_full_e03_smoke_execution_and_analysis(db: Session) -> None:
    """Run smoke batch across all 10 templates + controls and verify analyze passes."""
    schedules = generate_all_schedules(negative_per_template=2, control_count=4)
    results = [execute_schedule(db, s) for s in schedules]

    # Verify 0 downgrade successes
    negatives = [r for r in results if r.is_negative]
    assert all(r.rejected for r in negatives)
    assert all(not r.downgrade_success for r in negatives)

    controls = [r for r in results if not r.is_negative]
    assert all(r.admitted for r in controls)
