"""Machine-checked tests for the DSN 2027 threat model deliverable.

Purpose
-------
Enforce the ``research/venue2027/dsn/threat_model.md`` contract for task
``DSN-threat``: the document must pass the shared threat-model coverage
validator (``research/venue2027/_shared/tools/threat_model.py``), an
incomplete/truncated model must fail with stable reason codes, and the
crash-consistency attack family must be registered with a genuine paired
clean + adversarial control case so crash-window threats can never be
documented without their clean baseline.

Allowed input
-------------
The threat-model markdown file at repository-relative path
``research/venue2027/dsn/threat_model.md``, located from this test file's
position on disk, plus the shared validator module (imported read-only).

Failure semantics
-----------------
Each check raises ``AssertionError`` (or a ``pytest.fail``) with a stable
message naming the violated contract element. No random, network, or
filesystem writes; no live backend required.

Version
-------
``THREAT_MODEL_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import sys

import pytest

SHARED_TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import threat_model as tm  # noqa: E402

THREAT_MODEL_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
THREAT_MODEL_PATH = REPO_ROOT / "research" / "venue2027" / "dsn" / "threat_model.md"

CRASH_FAMILY = "crash_consistency"


def load_threat_model_text() -> str:
    assert THREAT_MODEL_PATH.is_file(), f"threat model missing: {THREAT_MODEL_PATH}"
    return THREAT_MODEL_PATH.read_text(encoding="utf-8")


def test_real_threat_model_passes_shared_validator() -> None:
    """The committed deliverable must satisfy the REQUIRED validator."""
    text = load_threat_model_text()
    result = tm.validate_threat(text)
    assert result.ok is True, (
        f"shared validator refused the DSN threat model: "
        f"reason_codes={result.reason_codes} "
        f"missing_sections={result.missing_sections} "
        f"families_without_pair={result.families_without_pair}"
    )
    assert set(tm.ATTACK_FAMILIES) <= set(result.families_covered)
    assert result.missing_sections == ()
    assert result.families_without_pair == ()


def test_incomplete_model_missing_sections_fails() -> None:
    """A model stripped of required sections must be refused, never pass."""
    text = load_threat_model_text()
    truncated = text.split("## 3. Trusted components", 1)[0]
    result = tm.validate_threat(truncated)
    assert result.ok is False
    assert "MISSING_SECTION" in result.reason_codes


def test_incomplete_model_family_without_pair_fails() -> None:
    """Dropping a family's matrix row must trip FAMILY_WITHOUT_PAIR."""
    text = load_threat_model_text()
    lines = [ln for ln in text.splitlines() if "| `model_agency` |" not in ln]
    result = tm.validate_threat("\n".join(lines))
    assert result.ok is False
    assert "model_agency" in result.families_without_pair


def test_incomplete_model_missing_authority_section_fails() -> None:
    """Removing the authority section must trip MISSING_SECTION."""
    text = load_threat_model_text()
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 8. Oracle"))
    end = next(i for i, ln in enumerate(lines) if ln.startswith("## 9."))
    result = tm.validate_threat("\n".join(lines[:start] + lines[end:]))
    assert result.ok is False
    assert "MISSING_SECTION" in result.reason_codes


def test_authority_is_explicitly_defined_never_undefined() -> None:
    """The deliverable must declare oracle/actor authority; no default trust."""
    text = load_threat_model_text()
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 8. Oracle"))
    end = next(i for i, ln in enumerate(lines) if ln.startswith("## 9."))
    section = "\n".join(lines[start:end])
    first_body = next(ln for ln in lines[start + 1 :] if ln.strip())
    assert first_body.strip().startswith("Defined"), (
        "oracle/actor authority must open with an explicit 'Defined' declaration"
    )
    assert "undefined:" not in section.lower(), (
        "authority section must not leave authority undefined"
    )
    for actor in (
        "Oracle",
        "Reconciler",
        "Consent epoch service",
        "AI model",
        "Human adjudicator",
        "Unassigned authority",
    ):
        assert actor.lower() in section.lower(), f"authority not assigned: {actor}"


def _crash_matrix_rows(text: str) -> list[str]:
    matrix_lines = [
        ln
        for ln in text.splitlines()
        if ln.startswith("| `") and "clean" in ln.lower() and "adversarial" in ln.lower()
    ]
    return [ln for ln in matrix_lines if CRASH_FAMILY in ln.lower()]


def test_crash_consistency_family_exists_with_pair() -> None:
    """A crash-consistency family must exist with clean + adversarial cells."""
    text = load_threat_model_text()
    rows = _crash_matrix_rows(text)
    assert rows, f"no matrix row registers the '{CRASH_FAMILY}' family with both control cells"
    row = rows[0].lower()
    assert "clean:" in row, "crash-consistency row lacks a 'clean:' control cell"
    assert "adversarial:" in row, "crash-consistency row lacks an 'adversarial:' case cell"


def test_crash_family_covers_core_threats() -> None:
    """The crash-consistency row must name the DSN-specific crash threats."""
    row = "\n".join(_crash_matrix_rows(load_threat_model_text())).lower()
    for threat in (
        "sigkill",
        "torn",
        "fsync",
        "mid-mutation",
        "crash before sql commit",
        "crash between commit and response",
    ):
        assert threat in row, f"crash-consistency row omits threat keyword: {threat}"


def test_clean_and_adversarial_expected_verdicts_distinct() -> None:
    """Paired cells must expect distinct outcomes, else pairing is vacuous."""
    row = _crash_matrix_rows(load_threat_model_text())[0].lower()
    clean_cell = row.split("clean:")[1].split("adversarial:")[0]
    adversarial_cell = row.split("adversarial:")[1]
    assert "governed commit" in clean_cell and "same operation id" in clean_cell
    assert any(verdict in adversarial_cell for verdict in ("rejected", "indeterminate")), (
        "adversarial cell must expect a non-positive verdict"
    )


def test_dsns_specific_threats_documented() -> None:
    """DSN-specific threat surfaces must appear in the capability section."""
    text = load_threat_model_text().lower()
    for threat in (
        "crash mid-mutation",
        "torn or partial journal append",
        "duplicate or lost transition",
        "journal tampering",
        "fsync",
        "non-idempotent retry after a crash",
        "at-least-once",
    ):
        assert threat in text, f"DSN-specific threat missing from model: {threat}"


def test_matrix_template_also_passes() -> None:
    """Sanity: the validator's own rendered template must still validate."""
    template_doc = (
        "# T\n## Attacker and observer capabilities\n## Trusted components\n"
        "## Excluded domains\n## Attack family and control matrix\n"
        + tm.render_matrix_template()
        + "\n## Oracle and actor authority\nDefined.\n"
    )
    assert tm.validate_threat(template_doc).ok is True


@pytest.mark.parametrize("family", tm.ATTACK_FAMILIES)
def test_every_family_row_carries_both_cells(family: str) -> None:
    """Each canonical family must appear in a row with both control cells."""
    text = load_threat_model_text()
    row = next(
        (ln for ln in text.splitlines() if family in ln.lower()),
        None,
    )
    assert row is not None, f"family absent from model: {family}"
    lower = row.lower()
    assert "clean" in lower and "adversarial" in lower, (
        f"family row lacks paired controls: {family}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
