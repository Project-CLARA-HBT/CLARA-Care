from __future__ import annotations

import pytest

from clara_api.core.govred_research import isolated_govred_arm, isolated_govred_endpoint_enabled


def test_absent_research_configuration_preserves_strict_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "CLARA_GOVRED_ISOLATED_RESEARCH",
        "GOVRED_RESEARCH_ARM",
        "GOVRED_RESEARCH_PROJECT",
    ):
        monkeypatch.delenv(name, raising=False)
    assert isolated_govred_arm() is None
    assert not isolated_govred_endpoint_enabled()


def test_research_arm_requires_isolated_nonproduction_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "UNBOUND")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError, match="govred_research_forbidden_in_production"):
        isolated_govred_arm()
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-app")
    with pytest.raises(RuntimeError, match="govred_research_project_attestation_invalid"):
        isolated_govred_arm()


def test_isolated_project_without_selected_arm_retains_strict_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.delenv("GOVRED_RESEARCH_ARM", raising=False)
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "development")

    assert isolated_govred_arm() is None
    assert not isolated_govred_endpoint_enabled()


def test_isolated_arm_has_prespecified_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "SNAPSHOT_BOUND_STATE_ONLY")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "development")
    arm = isolated_govred_arm()
    assert arm is not None
    assert (arm.bind_snapshot, arm.revalidate_state, arm.revalidate_governance) == (
        True,
        True,
        False,
    )
    assert isolated_govred_endpoint_enabled()
