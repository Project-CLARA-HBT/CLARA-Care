"""Unit tests for the scribe_eval note-generation evaluation gate (task 9.1, Req 20).

Covers:
- flag gating (``RAG_SCRIBE_EVAL_GATE_ENABLED`` off ⇒ gate does not run / no
  generation / inert result) — Req 20.1;
- each metric computation (structural completeness, grounded-claim rate,
  no-fabrication, coding-precision proxy) — Req 20.2;
- pass when all metrics meet thresholds, and fail + named breaching metric when
  one does not — Req 20.3/20.4;
- non-PII golden data and non-PII report — Req 20.5/20.6.

The pure threshold-enforcement core (:func:`build_gate_result`) is exercised here
and is the seam property test P15 (task 9.2) builds on.
"""

from __future__ import annotations

import re

import pytest

from clara_ml.scribe.eval.golden_set import (
    DEFAULT_SCRIBE_GOLDEN_SET,
    ScribeGoldenItem,
    load_scribe_golden_set,
)
from clara_ml.scribe.eval.harness import (
    DEFAULT_THRESHOLDS,
    EvalGateResult,
    EvalMetric,
    ScribeEvalHarness,
    build_gate_result,
)
from clara_ml.scribe.generator import Note
from clara_ml.scribe.templates import get_template


# ---------------------------------------------------------------------------
# Pure value objects + threshold enforcement (Req 20.3/20.4)
# ---------------------------------------------------------------------------


def test_eval_metric_create_derives_passed() -> None:
    assert EvalMetric.create("m", 0.9, 0.8).passed is True
    assert EvalMetric.create("m", 0.8, 0.8).passed is True  # >= is a pass
    assert EvalMetric.create("m", 0.79, 0.8).passed is False


def test_build_gate_result_passes_iff_all_metrics_pass() -> None:
    metrics = [
        EvalMetric.create("a", 1.0, 1.0),
        EvalMetric.create("b", 0.7, 0.6),
    ]
    result = build_gate_result(metrics)
    assert result.passed is True
    assert result.failing == []


def test_build_gate_result_names_breaching_metrics_in_order() -> None:
    metrics = [
        EvalMetric.create("structural_completeness", 1.0, 1.0),
        EvalMetric.create("grounded_claim_rate", 0.40, 0.60),
        EvalMetric.create("no_fabrication", 1.0, 1.0),
        EvalMetric.create("coding_precision", 0.50, 0.80),
    ]
    result = build_gate_result(metrics)
    assert result.passed is False
    # Failure names exactly the breaching metric(s), preserving order (Req 20.4).
    assert result.failing == ["grounded_claim_rate", "coding_precision"]


# ---------------------------------------------------------------------------
# Flag gating (Req 20.1)
# ---------------------------------------------------------------------------


class _ExplodingGenerator:
    """A generator that fails the test if it is ever asked to generate."""

    def generate(self, transcript: str, template_id: str | None = None) -> Note:  # noqa: ARG002
        raise AssertionError("note generation must not run when the gate is disabled")


def test_flag_off_does_not_run_and_is_inert() -> None:
    harness = ScribeEvalHarness(enabled=False, generator=_ExplodingGenerator())
    result = harness.run()
    assert harness.enabled is False
    assert isinstance(result, EvalGateResult)
    # Inert: no metrics, no failures, passes (never blocks runtime) — Req 20.1.
    assert result.metrics == []
    assert result.failing == []
    assert result.passed is True


# ---------------------------------------------------------------------------
# Each metric computation (Req 20.2)
# ---------------------------------------------------------------------------


def _metrics_by_name(harness: ScribeEvalHarness, items: list[ScribeGoldenItem]) -> dict[str, EvalMetric]:
    return {m.name: m for m in harness.compute_metrics(items)}


def test_structural_completeness_full_on_golden_set() -> None:
    harness = ScribeEvalHarness(enabled=True)
    metrics = _metrics_by_name(harness, load_scribe_golden_set())
    # NoteGenerator guarantees exactly the template's section keys (Req 6.2/6.3).
    assert metrics["structural_completeness"].value == pytest.approx(1.0)
    assert metrics["structural_completeness"].passed is True


def test_structural_completeness_drops_when_keys_wrong() -> None:
    class _WrongKeysGenerator:
        def generate(self, transcript: str, template_id: str | None = None) -> Note:
            return Note(template_id="soap", sections={"OnlyOneKey": transcript})

    harness = ScribeEvalHarness(enabled=True, generator=_WrongKeysGenerator())
    item = ScribeGoldenItem(
        case_id="t",
        template_id="h_and_p",  # declares 8 sections, generator returns 1 wrong key
        transcript_segments=["Patient reports a cough."],
    )
    metrics = _metrics_by_name(harness, [item])
    assert metrics["structural_completeness"].value == pytest.approx(0.0)
    assert metrics["structural_completeness"].passed is False


def test_grounded_claim_rate_high_when_note_derived_from_transcript() -> None:
    harness = ScribeEvalHarness(enabled=True)
    metrics = _metrics_by_name(harness, load_scribe_golden_set())
    rate = metrics["grounded_claim_rate"]
    # The deterministic generator copies only transcript-derived text, so every
    # significant statement is entailed by a transcript span.
    assert rate.value >= DEFAULT_THRESHOLDS["grounded_claim_rate"]
    assert rate.passed is True


def test_no_fabrication_full_on_golden_set() -> None:
    harness = ScribeEvalHarness(enabled=True)
    metrics = _metrics_by_name(harness, load_scribe_golden_set())
    assert metrics["no_fabrication"].value == pytest.approx(1.0)
    assert metrics["no_fabrication"].passed is True


def test_no_fabrication_detects_ungrounded_critical_statement() -> None:
    """A generator that invents a medication not in the transcript fails the check."""

    class _FabricatingGenerator:
        def generate(self, transcript: str, template_id: str | None = None) -> Note:
            template = get_template(template_id, include_specialty=True)
            assert template is not None
            sections = {key: "" for key in template.section_keys}
            # Put the transcript in the first section (grounded) ...
            sections[template.section_keys[0]] = transcript
            # ... and fabricate an ungrounded critical-safety med in the last.
            sections[template.section_keys[-1]] = "Start metoprolol 50mg twice daily."
            return Note(template_id=template.id, sections=sections)

    harness = ScribeEvalHarness(enabled=True, generator=_FabricatingGenerator())
    item = ScribeGoldenItem(
        case_id="fab",
        template_id="soap",
        transcript_segments=["Patient reports a mild headache today."],
    )
    metrics = _metrics_by_name(harness, [item])
    # The fabricated, ungrounded dose statement is caught (Req 6.5 / Req 20.2).
    assert metrics["no_fabrication"].value == pytest.approx(0.0)
    assert metrics["no_fabrication"].passed is False


def test_coding_precision_proxy_scores_against_expected_codes() -> None:
    harness = ScribeEvalHarness(enabled=True)
    metrics = _metrics_by_name(harness, load_scribe_golden_set())
    # Every golden transcript names a condition whose advisory ICD code matches
    # the declared expected code, so the proxy precision is perfect.
    assert metrics["coding_precision"].value == pytest.approx(1.0)
    assert metrics["coding_precision"].passed is True


def test_coding_precision_drops_on_mismatched_expected_code() -> None:
    harness = ScribeEvalHarness(enabled=True)
    # Transcript documents hypertension (ICD I10) but the golden expects a
    # different code, so the suggested code is "incorrect" ⇒ precision 0.
    item = ScribeGoldenItem(
        case_id="mismatch",
        template_id="soap",
        transcript_segments=["Patient has hypertension and needs review."],
        expected_icd=["E11.9"],
        lang="en",
    )
    metrics = _metrics_by_name(harness, [item])
    assert metrics["coding_precision"].value == pytest.approx(0.0)
    assert metrics["coding_precision"].passed is False


# ---------------------------------------------------------------------------
# End-to-end gate verdict (Req 20.3/20.4)
# ---------------------------------------------------------------------------


def test_gate_passes_on_clean_golden_set() -> None:
    result = ScribeEvalHarness(enabled=True).run()
    assert result.passed is True
    assert result.failing == []
    assert {m.name for m in result.metrics} == set(DEFAULT_THRESHOLDS)


def test_gate_fails_and_names_metric_when_threshold_unmet() -> None:
    # Declare an impossible coding-precision floor so that one metric breaches.
    thresholds = dict(DEFAULT_THRESHOLDS)
    thresholds["coding_precision"] = 1.01
    result = ScribeEvalHarness(enabled=True, thresholds=thresholds).run()
    assert result.passed is False
    assert result.failing == ["coding_precision"]


# ---------------------------------------------------------------------------
# Non-PII golden data + report (Req 20.5/20.6)
# ---------------------------------------------------------------------------

# Patterns that would indicate raw PII leaking into golden data or reports.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")
_SSN_MRN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def test_golden_set_is_pii_free() -> None:
    for item in DEFAULT_SCRIBE_GOLDEN_SET:
        text = item.transcript
        assert not _EMAIL.search(text), f"email in {item.case_id}"
        assert not _PHONE.search(text), f"phone-like digits in {item.case_id}"
        assert not _SSN_MRN.search(text), f"ssn/mrn-like id in {item.case_id}"
        # Speaker labels (if any) stay within the bounded diarization set; the
        # golden transcripts use generic "Patient"/"Người bệnh" phrasing only.


def test_report_is_pii_free_and_emits_only_metrics() -> None:
    result = ScribeEvalHarness(enabled=True).run()
    report = result.as_dict()
    # The report carries only the verdict + metric names/values — no transcript.
    assert set(report) == {"version", "passed", "failing", "metrics"}
    flat = repr(report)
    for item in DEFAULT_SCRIBE_GOLDEN_SET:
        for segment in item.transcript_segments:
            assert segment not in flat
    # Metric names are the declared, non-PII metric vocabulary.
    assert {m["name"] for m in report["metrics"]} == set(DEFAULT_THRESHOLDS)
