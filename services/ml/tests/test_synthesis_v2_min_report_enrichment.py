"""Substantive enrichment for sub-minimum deep_beta reports (Requirement 2.3, P5).

Feature: clara-pro-answer-synthesis, task 6.1.

``_ensure_min_deep_beta_report`` must, when ``SYNTHESIS_V2_ENABLED`` is on and an
LLM client is available, first request ONE targeted, evidence-grounded section
to grow a too-short report — only falling back to the static auto-appendix log
table when that enrichment is unavailable or insufficient. With the flag off (or
no client) it must stay byte-for-byte the legacy appendix-padding behavior
(Property P8 / Requirement 6.2).

Everything here is pure and network-free (a stub client stands in for the LLM).
"""

from __future__ import annotations

from dataclasses import dataclass

from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as app_settings

_SHORT_REPORT = "## Kết luận nhanh\nMột báo cáo quá ngắn.\n"
_TOPIC = "So sánh hiệu quả hai thuốc điều trị tăng huyết áp"
_MIN_CHARS = 4000


@dataclass
class _StubResponse:
    content: str


class _EnrichingStubClient:
    """Returns a long substantive section on first generate call."""

    def __init__(self, *, content: str) -> None:
        self.calls = 0
        self._content = content

    def generate(self, *, prompt: str, system_prompt: str, max_tokens: int = 0) -> _StubResponse:
        self.calls += 1
        return _StubResponse(content=self._content)


class _EmptyStubClient:
    """Always returns empty content (LLM enrichment unavailable)."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, prompt: str, system_prompt: str, max_tokens: int = 0) -> _StubResponse:
        self.calls += 1
        return _StubResponse(content="")


def _set_flag(value: bool) -> bool:
    previous = app_settings.synthesis_v2_enabled
    app_settings.synthesis_v2_enabled = value
    return previous


def test_flag_on_requests_evidence_grounded_section_before_appendix() -> None:
    """Flag on + client ⇒ the enriched section is appended and the report no
    longer falls back to the static auto-appendix log table."""

    enrichment_body = (
        "## Phân tích so sánh hiệu quả\n" + ("Phân tích bằng chứng chi tiết. " * 400)
    )
    stub = _EnrichingStubClient(content=enrichment_body)
    previous = _set_flag(True)
    try:
        result = rt._ensure_min_deep_beta_report(
            report_markdown=_SHORT_REPORT,
            topic=_TOPIC,
            citations=[],
            deep_pass_summaries=[],
            min_chars=_MIN_CHARS,
            client=stub,
            system_prompt="sys",
            answer_language="vi",
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert stub.calls == 1
    assert "Phân tích so sánh hiệu quả" in result
    # Substantive enrichment reached the threshold, so the static appendix log
    # table is NOT used.
    assert "Phụ lục Deep Beta (Auto-Expanded)" not in result
    assert len(result) >= _MIN_CHARS


def test_flag_on_falls_back_to_appendix_when_enrichment_empty() -> None:
    """Flag on but the LLM returns nothing ⇒ the legacy appendix fallback is
    used so the report is still grown to the minimum."""

    stub = _EmptyStubClient()
    previous = _set_flag(True)
    try:
        result = rt._ensure_min_deep_beta_report(
            report_markdown=_SHORT_REPORT,
            topic=_TOPIC,
            citations=[],
            deep_pass_summaries=[],
            min_chars=_MIN_CHARS,
            client=stub,
            system_prompt="sys",
            answer_language="vi",
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert stub.calls == 1
    assert "Phụ lục Deep Beta (Auto-Expanded)" in result


def test_flags_off_is_byte_identical_to_legacy_appendix() -> None:
    """Flag off ⇒ even with a client supplied, the function never calls the LLM
    and produces exactly the legacy appendix-padded output (Property P8)."""

    stub = _EnrichingStubClient(content="## Sẽ không bao giờ được gọi\n")
    previous = _set_flag(False)
    try:
        with_client = rt._ensure_min_deep_beta_report(
            report_markdown=_SHORT_REPORT,
            topic=_TOPIC,
            citations=[],
            deep_pass_summaries=[],
            min_chars=_MIN_CHARS,
            client=stub,
            system_prompt="sys",
            answer_language="vi",
        )
        # The legacy call shape (no enrichment args) must match exactly.
        legacy = rt._ensure_min_deep_beta_report(
            report_markdown=_SHORT_REPORT,
            topic=_TOPIC,
            citations=[],
            deep_pass_summaries=[],
            min_chars=_MIN_CHARS,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert stub.calls == 0
    assert with_client == legacy
    assert "Phụ lục Deep Beta (Auto-Expanded)" in legacy


def test_already_long_report_is_returned_unchanged() -> None:
    """A report already at/above the minimum is returned untouched, with no LLM
    call, in either flag state."""

    long_report = "## Kết luận\n" + ("nội dung " * 2000)
    stub = _EnrichingStubClient(content="## Không gọi\n")
    previous = _set_flag(True)
    try:
        result = rt._ensure_min_deep_beta_report(
            report_markdown=long_report,
            topic=_TOPIC,
            citations=[],
            deep_pass_summaries=[],
            min_chars=_MIN_CHARS,
            client=stub,
            system_prompt="sys",
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert stub.calls == 0
    assert result == long_report.strip()
