"""Flag-toggling + baseline-capture harness for CLARA Pro synthesis v2.

The harness has two jobs, mirroring ``tests/safety/harness.py``:

1. **Toggle the ``SYNTHESIS_V2_ENABLED`` flag** on the live ``settings`` object
   for the duration of a ``with`` block so a single test can evaluate the
   synthesis path with v2 OFF (legacy) and ON, and always restore the previous
   value (so the suite is order- and ambient-config independent).

2. **Capture the pure budget / section-contract decisions** in a small,
   comparable shape so "flag off == pre-feature behavior" (design Property P8)
   reduces to a plain equality assertion.

Everything here is deterministic and network-free: only the *pure* resolvers
(`_resolve_adaptive_report_word_budget`, `_resolve_report_section_contract`) are
exercised; nothing touches an LLM client.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as _settings

# ---------------------------------------------------------------------------
# Design Correctness Properties (P1..P10) — single source of truth.
# ---------------------------------------------------------------------------

#: Maps each design property tag to its plain-language statement. Property-test
#: modules reference these so the tags never drift from the design document.
PROPERTY_TAGS: dict[str, str] = {
    "P1": "Budget invariant: min_words <= target <= max_words <= 15000 for all inputs/config.",
    "P2": "Scope monotonicity: broader scope => target non-decreasing, all else equal.",
    "P3": "Density monotonicity: more evidence => target non-decreasing, all else equal.",
    "P4": "Broad-query band: broad + high-density deep_beta yields target >= 8000.",
    "P5": "No-pad floor: narrow + sparse query yields target < floor, not appendix-padded.",
    "P6": "Convergence: expansion stops only on target-met OR round/timeout exhaustion.",
    "P7": "Word-count consistency: one counter used in budget, expansion, and enforcement.",
    "P8": "Flags-off equivalence: with the flag off, budget/contract/expansion equal baseline.",
    "P9": "Guardrail preservation: never prescribe/diagnose; emergency fast-path intact; no internal tags.",
    "P10": "deep != deep_beta: deep mode budget stays the dense-briefing band.",
}

#: Hard ceiling enforced by the budget invariant (design Property P1).
HARD_MAX_WORDS = 15000

# ---------------------------------------------------------------------------
# Representative topics by query scope (reused by the property/unit modules).
# ---------------------------------------------------------------------------

#: A broad, comparative, multi-part query: high scope_factor on the v2 path.
BROAD_COMPARATIVE_TOPIC = (
    "So sánh hiệu quả, an toàn, tuân thủ và chi phí giữa các thuốc điều trị "
    "tăng huyết áp và đái tháo đường ở bệnh nhân cao tuổi có bệnh thận mạn, "
    "đồng thời phân tích tương tác thuốc và theo dõi dài hạn?"
)
#: A standard, single-intervention clinical query.
STANDARD_TOPIC = "Điều trị viêm họng cấp ở người lớn"
#: A narrow, definitional query: low scope_factor, must not be padded.
NARROW_TOPIC = "Paracetamol là gì?"

#: All representative topics, smallest-to-largest expected scope.
SCOPE_TOPICS: tuple[str, ...] = (NARROW_TOPIC, STANDARD_TOPIC, BROAD_COMPARATIVE_TOPIC)


# ---------------------------------------------------------------------------
# Flag toggling
# ---------------------------------------------------------------------------


@contextmanager
def synthesis_v2_flag(enabled: bool) -> Iterator[None]:
    """Set ``settings.synthesis_v2_enabled`` for the block, then restore it.

    Usage::

        with synthesis_v2_flag(True):
            ...  # v2 path active

    The previous value is always restored, even on exception, so tests never
    leak the flag into one another.
    """

    previous = _settings.synthesis_v2_enabled
    _settings.synthesis_v2_enabled = enabled
    try:
        yield
    finally:
        _settings.synthesis_v2_enabled = previous


# ---------------------------------------------------------------------------
# Pure decision capture (network-free, comparable shapes)
# ---------------------------------------------------------------------------


def capture_budget(
    *,
    research_mode: str = "deep_beta",
    citation_count: int = 0,
    deep_pass_count: int = 0,
    reasoning_node_count: int = 0,
    topic: str = "",
) -> tuple[int, int, int]:
    """Capture the resolved ``(min, target, max)`` word budget.

    Thin wrapper over ``_resolve_adaptive_report_word_budget`` so a test reads
    as a decision snapshot. The caller is responsible for setting the flag
    (use :func:`synthesis_v2_flag`).
    """

    return rt._resolve_adaptive_report_word_budget(
        research_mode=research_mode,
        citation_count=citation_count,
        deep_pass_count=deep_pass_count,
        reasoning_node_count=reasoning_node_count,
        topic=topic,
    )


def capture_section_contract(
    *,
    research_mode: str = "deep_beta",
    answer_language: str = "vi",
    topic: str = "",
) -> tuple[Any, Any]:
    """Capture the ``(sections, requirements)`` section contract decision."""

    return rt._resolve_report_section_contract(
        research_mode,
        answer_language=answer_language,
        topic=topic,
    )


def budget_invariant_holds(budget: tuple[int, int, int]) -> bool:
    """True iff ``0 <= min <= target <= max <= 15000`` (design Property P1)."""

    min_w, target_w, max_w = budget
    return 0 <= min_w <= target_w <= max_w <= HARD_MAX_WORDS
