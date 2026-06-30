"""Convergence-loop tests for CLARA Pro synthesis v2 (Property P6).

Feature: clara-pro-answer-synthesis (task 5.2). These stub-LLM tests exercise the
expansion loop rewritten in :func:`research_tier2._synthesize_deep_beta_long_report`
(task 5.1) and assert two behaviors required by design Property P6 / Requirement
2.2 and 2.4:

  (a) On an empty *or* duplicate continuation the synthesis-v2 loop ROTATES
      through the next expansion directive instead of breaking immediately; it
      only stops once the round budget is exhausted (or a full rotation yields
      nothing new). The legacy (flags-off) loop still breaks on the first
      empty/duplicate continuation.
  (b) The loop honors its round and wall-clock bounds and returns the
      best-so-far synthesized report on timeout (rather than discarding the
      accumulated work and falling back to the raw baseline answer).

A recording stub LLM client returns a substantive first report, then a
configurable continuation (empty / duplicate / unique) so each scenario can be
driven deterministically. The stub records every prompt so the test can
distinguish "rotated through directives" from "broke immediately" and can verify
the bound on the number of expansion rounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as app_settings

# A substantive first report: long enough to clear the empty/sanitize guard, and
# carrying a distinctive phrase the timeout test uses to prove best-so-far is
# returned rather than the raw baseline answer.
_INITIAL_REPORT = (
    "## Kết luận nhanh\n"
    "Đây là một báo cáo cơ sở để kiểm thử vòng hội tụ của chế độ tổng hợp "
    "CLARA Pro với nội dung lâm sàng mẫu đủ dài để vượt qua bộ lọc rỗng.\n\n"
    "## Phân tích chi tiết\nNội dung phân tích mẫu cho mục đích kiểm thử.\n"
)

# Markers used to classify which generation pass produced a prompt. The
# append-only continuation prompt (expansion loop) and the section/length
# completion prompt (enrichment loop) carry distinct, stable phrases.
_CONTINUATION_MARKER = "APPENDING new content only"
_SECTION_FILL_MARKER = "satisfies its section and length contract"


@dataclass
class _StubResponse:
    content: str


class _RecordingStubClient:
    """Stub LLM client that records prompts and emits a configurable continuation.

    The first ``generate`` call returns a substantive report. Every subsequent
    call returns content controlled by ``continuation``:

    * ``"empty"``    -> empty string (forces the rotate-vs-break decision).
    * ``"duplicate"`` -> the exact initial report (already present -> duplicate).
    * ``"unique"``   -> distinct new content each call (never empty/duplicate).
    """

    def __init__(self, *, continuation: str) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self._continuation = continuation

    def generate(
        self, *, prompt: str, system_prompt: str, max_tokens: int = 0
    ) -> _StubResponse:
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls == 1:
            return _StubResponse(content=_INITIAL_REPORT)
        if self._continuation == "empty":
            return _StubResponse(content="")
        if self._continuation == "duplicate":
            # Identical to existing content -> treated as a duplicate pass.
            return _StubResponse(content=_INITIAL_REPORT)
        # "unique": distinct, non-duplicate content that never reaches target.
        return _StubResponse(
            content=(
                f"\n\n### Phần bổ sung số {self.calls}\n"
                f"Đoạn nội dung lâm sàng bổ sung duy nhất số {self.calls} phục vụ "
                "kiểm thử vòng hội tụ, không trùng lặp với nội dung trước đó.\n"
            )
        )


def _expansion_prompts(stub: _RecordingStubClient) -> list[str]:
    """Prompts produced by the directive-rotation expansion loop."""
    return [p for p in stub.prompts if _CONTINUATION_MARKER in p]


def _directives_used(stub: _RecordingStubClient) -> set[str]:
    """The set of distinct expansion directives that were actually attempted."""
    prompts = _expansion_prompts(stub)
    return {d for d in rt._EXPANSION_DIRECTIVES if any(d in p for p in prompts)}


def _run(
    monkeypatch: Any,
    *,
    flag: bool,
    continuation: str = "empty",
    perf_values: list[float] | None = None,
) -> tuple[_RecordingStubClient, str]:
    stub = _RecordingStubClient(continuation=continuation)
    # Force a high target so the loop wants to keep expanding (>= 8000 so the
    # synthesis-v2 path resolves expansion_rounds = max(configured, 2)).
    monkeypatch.setattr(
        rt,
        "_resolve_adaptive_report_word_budget",
        lambda **_kwargs: (8000, 10000, 12000),
    )
    # Provide a valid-looking LLM config so synthesis does not early-return.
    monkeypatch.setattr(
        rt,
        "_resolve_runtime_llm_config",
        lambda _runtime: ("deepseek", "test-key", "http://x/v1", "deepseek-test"),
    )
    monkeypatch.setattr(rt, "_build_reasoning_client", lambda **_kwargs: stub)

    if perf_values is not None:
        # Deterministic wall-clock: yield the provided values in order, then hold
        # the last value. Used to trip the timeout check after synthesis_start.
        sequence = iter(perf_values)
        held = {"value": perf_values[-1]}

        def _fake_perf_counter() -> float:
            try:
                held["value"] = next(sequence)
            except StopIteration:
                pass
            return held["value"]

        monkeypatch.setattr(rt, "perf_counter", _fake_perf_counter)

    previous_flag = app_settings.synthesis_v2_enabled
    previous_llm_enabled = app_settings.deep_beta_report_llm_enabled
    previous_rounds = app_settings.deep_beta_report_expansion_rounds
    app_settings.synthesis_v2_enabled = flag
    app_settings.deep_beta_report_llm_enabled = True
    # Pin the configured round budget so expansion_rounds is deterministic
    # (target >= 8000 -> expansion_rounds = max(4, 2) = 4 == len(directives)).
    app_settings.deep_beta_report_expansion_rounds = 4
    try:
        report = rt._synthesize_deep_beta_long_report(
            topic="So sánh hai thuốc điều trị tăng huyết áp",
            answer_markdown="## Kết luận nhanh\nCâu trả lời cơ sở.\n",
            citations=[],
            verification_matrix_payload={},
            reasoning_nodes=[],
            deep_pass_summaries=[],
            evidence_verification={},
            llm_runtime={"api_key": "test-key"},
            research_mode="deep_beta",
            answer_language="vi",
        )
    finally:
        app_settings.synthesis_v2_enabled = previous_flag
        app_settings.deep_beta_report_llm_enabled = previous_llm_enabled
        app_settings.deep_beta_report_expansion_rounds = previous_rounds
    return stub, report


# --- (a) Rotation, not early break --------------------------------------------


def test_p6_v2_rotates_directives_before_giving_up_on_empty(monkeypatch: Any) -> None:
    stub, _report = _run(monkeypatch, flag=True, continuation="empty")
    expansion = _expansion_prompts(stub)
    # 1 initial + 4 continuation attempts (one per rotated directive) before stop.
    assert stub.calls >= 5
    assert len(expansion) == len(rt._EXPANSION_DIRECTIVES)
    # Every directive was actually tried -> the loop rotated, not broke early.
    assert _directives_used(stub) == set(rt._EXPANSION_DIRECTIVES)


def test_p6_v2_rotates_directives_before_giving_up_on_duplicate(monkeypatch: Any) -> None:
    stub, _report = _run(monkeypatch, flag=True, continuation="duplicate")
    expansion = _expansion_prompts(stub)
    # A duplicate continuation must also trigger rotation, not an immediate break.
    assert len(expansion) == len(rt._EXPANSION_DIRECTIVES)
    assert _directives_used(stub) == set(rt._EXPANSION_DIRECTIVES)


def test_p6_legacy_breaks_on_first_empty_continuation(monkeypatch: Any) -> None:
    stub, _report = _run(monkeypatch, flag=False, continuation="empty")
    # 1 initial + exactly 1 continuation that is empty -> immediate break.
    assert stub.calls == 2
    assert len(_expansion_prompts(stub)) == 1


def test_p6_legacy_breaks_on_first_duplicate_continuation(monkeypatch: Any) -> None:
    stub, _report = _run(monkeypatch, flag=False, continuation="duplicate")
    # Legacy path breaks on the first duplicate continuation as well.
    assert len(_expansion_prompts(stub)) == 1


# --- (b) Round and wall-clock bounds, best-so-far on timeout -------------------


def test_p6_v2_expansion_round_bound_holds_when_target_never_met(monkeypatch: Any) -> None:
    # Unique continuations are always accepted but never reach the (high) target,
    # so the loop must terminate by its round budget rather than spinning.
    stub, report = _run(monkeypatch, flag=True, continuation="unique")
    expansion = _expansion_prompts(stub)
    # Bounded by expansion_rounds (== 4 here); never unbounded.
    assert len(expansion) == app_settings.deep_beta_report_expansion_rounds
    assert len(expansion) == len(rt._EXPANSION_DIRECTIVES)
    assert _directives_used(stub) == set(rt._EXPANSION_DIRECTIVES)
    # Best-so-far accumulates the accepted continuations (append-only growth).
    assert "Phần bổ sung" in report


def test_p6_v2_returns_best_so_far_on_timeout(monkeypatch: Any) -> None:
    # synthesis_start reads perf_counter once (0.0); the first loop check then
    # sees a value far beyond any timeout and must break before any continuation.
    stub, report = _run(
        monkeypatch,
        flag=True,
        continuation="unique",
        perf_values=[0.0, 1_000_000.0],
    )
    # No continuation/enrichment generation happened after the timeout tripped.
    assert stub.calls == 1
    assert _expansion_prompts(stub) == []
    # The best-so-far SYNTHESIZED report is returned, not the raw baseline answer:
    # this distinctive phrase exists only in the synthesized initial pass.
    assert "báo cáo cơ sở để kiểm thử" in report
