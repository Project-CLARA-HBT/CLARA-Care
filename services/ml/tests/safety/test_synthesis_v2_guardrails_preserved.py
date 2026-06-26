"""Synthesis v2 guardrail preservation (clara-pro-answer-synthesis, task 8.1).

**Validates: Property P9 (Guardrail preservation)**

Design Property P9 (``clara-pro-answer-synthesis/design.md``):

    Guardrail preservation. Output never prescribes/diagnoses; emergency
    fast-path unaffected; no internal tags in body.

The CLARA Pro answer-synthesis rewrite ships behind ``SYNTHESIS_V2_ENABLED``
and changes only the ``deep_beta`` length budget, section planning, and
expansion loop in ``clara_ml.agents.research_tier2``. It must NOT touch any
medical-safety guardrail. This module re-asserts, with the synthesis v2 flag
**ON** (and at long ``deep_beta`` report length), that:

1. the legal/dosage guard still **blocks** prescribe / diagnose / personal-dosage
   requests (the system never prescribes or diagnoses) — and benign queries are
   still not blocked;
2. the **emergency fast-path** still triggers (and is byte-identical to the
   flag-OFF decision) — synthesis length never delays or alters routing; and
3. **FIDES CRITICAL** blocking is preserved — a contradiction verdict is
   identical whether synthesis v2 is off or on, including when the contradicting
   claim is embedded in a long, multi-section ``deep_beta``-style report body.

It also asserts Property P9's tag-hygiene clause directly: a long ``deep_beta``
report carrying internal pipeline tags (``deep_beta_scope``,
``retrieval_budgeting``, ``[scope_question]`` …) has those tags stripped by the
user-facing sanitizer while the substantive body is preserved.

Everything reuses the Epic 11 safety harness/fixtures and is network-free and
deterministic: the guardrails are pure text/rule classifiers and flag toggling
mutates only the in-process ``settings`` object (restored after each test).
"""

from __future__ import annotations

import pytest

# ``clara_ml.rag.store`` eagerly pulls in rag submodules; importing it before the
# harness (which imports other ``clara_ml`` modules) sidesteps the known rag
# circular-import quirk and keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as _settings

from . import fixtures as fx
from . import harness as hz

# ---------------------------------------------------------------------------
# Long deep_beta report fixture (carrying internal pipeline tags)
# ---------------------------------------------------------------------------

#: Internal pipeline tags that must NEVER appear in the user-facing answer body
#: (mirrors the labels the continuation prompt forbids and the reasoning-stage
#: identifiers in ``research_tier2``).
_INTERNAL_TAGS: tuple[str, ...] = (
    "deep_beta_scope",
    "retrieval_budgeting",
    "[scope_question]",
    "deep_beta_multi_pass_retrieval",
    "deep_beta_evidence_audit",
)

#: A clinically-neutral filler sentence (no prescribing/diagnosis/dosage), used
#: to pad the body past the deep_beta length guardrail so the sanitizer keeps the
#: long-form layout (exercising the long-output path, not the short-stabilizer).
_FILLER_SENTENCE = (
    "Tổng quan bằng chứng cho thấy cần cân nhắc lợi ích và rủi ro theo từng nhóm "
    "bệnh nhân, đồng thời tham khảo ý kiến bác sĩ điều trị trước khi áp dụng. "
)


def _long_dossier_body(*, repeats: int = 80) -> str:
    """Build a long, multi-section ``deep_beta`` report body.

    The body uses the real required dossier headings and benign clinical prose,
    then appends two *internal* sections — an H3 telemetry log and an H2 full
    execution plan — that carry the internal pipeline tags. The sanitizer is
    expected to drop those internal sections while preserving the dossier body.
    """

    headings = rt._resolve_deep_beta_dossier_headings("vi")
    blocks: list[str] = []
    for heading in headings:
        body = _FILLER_SENTENCE * max(1, repeats // max(1, len(headings)))
        blocks.append(f"{heading}\n{body.strip()}\n")
    dossier = "\n".join(blocks)

    # Internal telemetry H3 section (one of the keys the deep-mode sanitizer
    # strips) carrying internal tags.
    telemetry = (
        "### Nhật ký multi-pass retrieval\n"
        "deep_beta_scope -> retrieval_budgeting -> deep_beta_multi_pass_retrieval\n"
        "| Pass | Stage | Note |\n| --- | --- | --- |\n"
        "| 1 | deep_beta_evidence_audit | internal |\n"
    )
    # Internal full-execution-plan H2 section (stripped in deep modes) carrying
    # the bracketed planner tag.
    execution_plan = (
        "## Triển khai đầy đủ kế hoạch\n"
        "[scope_question] internal planner step that must never reach the reader.\n"
    )
    return f"{dossier}\n{telemetry}\n{execution_plan}"


# ---------------------------------------------------------------------------
# 1. Legal/dosage guard — system never prescribes/diagnoses (flag ON)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", fx.LEGAL_GUARD_QUERIES, ids=lambda c: c.label)
def test_legal_guard_blocks_under_synthesis_v2(
    case: fx.LegalGuardQuery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prescribe/diagnose/dosage request stays blocked with synthesis v2 ON,
    and the decision is byte-identical to the flag-OFF baseline (no drift)."""

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", False, raising=False)
    baseline = hz.capture_legal_guard(case.query)

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", True, raising=False)
    with_v2 = hz.capture_legal_guard(case.query)

    assert with_v2 == baseline
    assert with_v2["blocked"] is True
    assert with_v2["reason"] == case.reason


@pytest.mark.parametrize("query", fx.LEGAL_GUARD_SAFE_QUERIES)
def test_benign_queries_not_blocked_under_synthesis_v2(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: benign queries are not blocked, in either synthesis flag state."""

    for enabled in (False, True):
        monkeypatch.setattr(_settings, "synthesis_v2_enabled", enabled, raising=False)
        assert hz.capture_legal_guard(query)["blocked"] is False


# ---------------------------------------------------------------------------
# 2. Emergency fast-path intact (flag ON)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query", fx.EMERGENCY_QUERIES)
def test_emergency_fastpath_intact_under_synthesis_v2(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The emergency fast-path triggers identically with synthesis v2 ON; the
    synthesis-length rewrite can never suppress, delay, or alter routing."""

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", False, raising=False)
    baseline = hz.capture_emergency_route(query)

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", True, raising=False)
    with_v2 = hz.capture_emergency_route(query)

    assert with_v2 == baseline
    assert with_v2["emergency"] is True
    assert with_v2["intent"] == "emergency_triage"


# ---------------------------------------------------------------------------
# 3. FIDES CRITICAL blocking preserved (flag ON, incl. long report body)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", fx.CRITICAL_CLAIM_PAYLOADS, ids=lambda p: p.label)
def test_fides_critical_block_preserved_under_synthesis_v2(
    payload: fx.FidesPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CRITICAL/contradiction FIDES verdict is identical with synthesis v2 ON
    vs OFF, and still blocks (``verdict == 'fail'`` with a contradiction)."""

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", False, raising=False)
    baseline = hz.capture_fides_decision(payload.answer, payload.retrieved_context)

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", True, raising=False)
    with_v2 = hz.capture_fides_decision(payload.answer, payload.retrieved_context)

    assert with_v2 == baseline
    assert with_v2["verdict"] == "fail"
    assert with_v2["has_contradiction"] is True


@pytest.mark.parametrize("payload", fx.CRITICAL_CLAIM_PAYLOADS, ids=lambda p: p.label)
def test_fides_critical_block_preserved_at_long_report_length(
    payload: fx.FidesPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIDES still blocks a contradiction even when the contradicting claim is
    embedded in a long, multi-section ``deep_beta``-style answer body with
    synthesis v2 ON — length never dilutes the CRITICAL block."""

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", True, raising=False)

    # The contradiction claim leads a long report (benign filler appended). FIDES
    # extracts and verifies claims, so the contradicting sentence must still be
    # caught regardless of surrounding length.
    long_answer = payload.answer + "\n\n" + (_FILLER_SENTENCE * 60)
    decision = hz.capture_fides_decision(long_answer, payload.retrieved_context)

    assert decision["verdict"] == "fail"
    assert decision["has_contradiction"] is True


# ---------------------------------------------------------------------------
# 4. Tag hygiene — internal pipeline tags never reach the body (flag ON)
# ---------------------------------------------------------------------------


def test_long_deep_beta_output_strips_internal_tags_under_synthesis_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Property P9 tag-hygiene clause: a long ``deep_beta`` report carrying
    internal pipeline tags has those tags stripped by the user-facing sanitizer
    (with synthesis v2 ON), while the substantive dossier body is preserved."""

    monkeypatch.setattr(_settings, "synthesis_v2_enabled", True, raising=False)

    raw = _long_dossier_body()
    # Precondition (non-vacuity): the raw report really does carry the tags.
    for tag in _INTERNAL_TAGS:
        assert tag in raw, f"fixture missing internal tag {tag!r}"

    sanitized = rt._sanitize_user_facing_answer_markdown(
        raw,
        research_mode="deep_beta",
        answer_language="vi",
    )

    # No internal pipeline tag survives into the user-facing body.
    for tag in _INTERNAL_TAGS:
        assert tag not in sanitized, f"internal tag leaked into body: {tag!r}"

    # The substantive dossier body is preserved (a long report, not stabilized
    # down to a short stub) and the lead conclusion heading remains.
    assert rt._markdown_word_count(sanitized) >= 2500
    assert "## Kết luận nhanh" in sanitized
