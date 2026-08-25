"""Tests for Zero-CoT sanitization, FIDES hard-veto, fail-closed suppression, and Council parallel execution."""

from __future__ import annotations

import json

import pytest

from clara_ml.agents.council import SUPPORTED_SPECIALISTS, run_council
from clara_ml.agents.research_tier2 import run_research_tier2
from clara_ml.factcheck.fides_lite import FactCheckResult, run_fides_lite
from clara_ml.factcheck.nli_verifier import (
    has_hard_veto_violation,
    infer_claim_type,
    is_safety_critical_claim_type,
)
from clara_ml.llm.deepseek_client import (
    DeepSeekClient,
)
from clara_ml.llm.deepseek_client import (
    sanitize_cot_content as sanitize_deepseek_cot,
)
from clara_ml.llm.provider_adapters import (
    filter_cot_stream,
)
from clara_ml.llm.provider_adapters import (
    sanitize_cot_content as sanitize_adapter_cot,
)
from clara_ml.rag.pipeline import RagResult
from clara_ml.streaming.chat_stream import (
    iter_answer_chunks,
    stream_chat_sse,
)

# ==============================================================================
# 1. Zero-CoT Sanitization Tests
# ==============================================================================


def test_sanitize_cot_content_strips_think_and_extracts_reasoning() -> None:
    raw = "<think>\nThinking about dosage.\nVerify renal function.\n</think>\nLiều dùng khuyến cáo là 500mg."
    clean, reasoning = sanitize_deepseek_cot(raw)
    assert clean == "Liều dùng khuyến cáo là 500mg."
    assert "Thinking about dosage." in reasoning
    assert "Verify renal function." in reasoning
    assert "<think>" not in clean
    assert "</think>" not in clean


def test_sanitize_cot_content_unclosed_think_tag() -> None:
    raw = "<think>Partial thinking that was cut off"
    clean, reasoning = sanitize_deepseek_cot(raw)
    assert clean == ""
    assert "Partial thinking" in reasoning


def test_sanitize_cot_content_multiple_think_blocks() -> None:
    raw = "<think>First thought</think>Part 1.<think>Second thought</think>Part 2."
    clean, reasoning = sanitize_adapter_cot(raw)
    assert clean == "Part 1.Part 2."
    assert "First thought" in reasoning
    assert "Second thought" in reasoning


def test_deepseek_client_extract_content_and_reasoning_from_payload() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "<think>Internal deliberation</think>Final clinical answer.",
                    "reasoning_content": "Explicit reasoning",
                }
            }
        ],
        "model": "deepseek-r1",
    }
    content, reasoning = DeepSeekClient._extract_content_and_reasoning_from_payload(payload)
    assert content == "Final clinical answer."
    assert "Explicit reasoning" in reasoning
    assert "Internal deliberation" in reasoning


def test_filter_cot_stream_filters_token_chunks() -> None:
    chunks = [
        "<th",
        "ink>Hidden CoT reasoning</th",
        "ink>Hello",
        " world!",
    ]
    streamed = list(filter_cot_stream(iter(chunks)))
    assert "".join(streamed) == "Hello world!"
    assert "Hidden CoT" not in "".join(streamed)


def test_chat_stream_sse_never_leaks_cot_tokens() -> None:
    result = {
        "answer": "<think>Secret internal chain of thought</think>Bệnh nhân nên nghỉ ngơi.",
        "flow_events": [],
        "model_used": "deepseek-r1",
    }
    frames = list(stream_chat_sse({"query": "x"}, infer=lambda _p: result, token_delay=0, step_delay=0, sleep=lambda _: None))
    
    tokens = []
    done_payload = None
    for frame in frames:
        if frame.startswith("event: token\n"):
            line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
            tokens.append(json.loads(line[6:])["text"])
        elif frame.startswith("event: done\n"):
            line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
            done_payload = json.loads(line[6:])

    full_typed = "".join(tokens)
    assert full_typed == "Bệnh nhân nên nghỉ ngơi."
    assert "Secret internal" not in full_typed
    assert done_payload is not None
    assert done_payload["answer"] == "Bệnh nhân nên nghỉ ngơi."
    assert "Secret internal" in done_payload.get("reasoning_content", "")


def test_iter_answer_chunks_sanitizes_cot() -> None:
    ans = "<think>Internal CoT</think>Toa thuốc an toàn."
    chunks = list(iter_answer_chunks(ans))
    assert "".join(chunks) == "Toa thuốc an toàn."


# ==============================================================================
# 2. FIDES Hard-Veto Tests
# ==============================================================================


def test_infer_claim_type_classifies_safety_critical_domains() -> None:
    assert infer_claim_type("Uống liều 10 mg mỗi ngày vào buổi sáng.") == "dosage"
    assert infer_claim_type("Tương tác thuốc giữa warfarin và NSAIDs làm tăng xuất huyết.") == "interaction"
    assert infer_claim_type("Chống chỉ định dùng thuốc cho phụ nữ có thai.") == "contraindication"
    assert infer_claim_type("Tập thể dục đều đặn giúp tăng cường sức khỏe.") == "general"


def test_safety_critical_types_and_hard_veto_violation() -> None:
    assert is_safety_critical_claim_type("dosage") is True
    assert is_safety_critical_claim_type("interaction") is True
    assert is_safety_critical_claim_type("contraindication") is True
    assert is_safety_critical_claim_type("general") is False

    matrix = [
        {"claim": "General claim", "claim_type": "general", "support_status": "insufficient"},
        {"claim": "Dose claim", "claim_type": "dosage", "support_status": "insufficient"},
    ]
    has_veto, claims = has_hard_veto_violation(matrix)
    assert has_veto is True
    assert claims == ["Dose claim"]


def test_fides_hard_veto_ungrounded_dosage_claim_fails_even_with_high_support_ratio() -> None:
    # 2 general claims supported, 1 dosage claim ungrounded
    retrieved_context = [
        {"id": "doc-1", "text": "Paracetamol là thuốc giảm đau hạ sốt phổ biến."},
        {"id": "doc-2", "text": "Thuốc được chuyển hóa chủ yếu qua gan."},
    ]
    answer = (
        "Paracetamol là thuốc giảm đau hạ sốt phổ biến. "
        "Thuốc được chuyển hóa chủ yếu qua gan. "
        "Nên uống liều 3000 mg mỗi lần để giảm đau nhanh."
    )
    result = run_fides_lite(
        answer=answer,
        retrieved_context=retrieved_context,
        nli_enabled=False,
    )
    # Hard-veto forces fail and block regardless of general claims passing
    assert result.verdict == "fail"
    assert result.severity == "high"
    assert result.policy_action == "block"


def test_fides_hard_veto_ungrounded_contraindication_forces_block() -> None:
    retrieved_context = [{"id": "doc-1", "text": "Aspirin được dùng để phòng ngừa huyết khối."}]
    answer = (
        "Aspirin được dùng để phòng ngừa huyết khối. "
        "Chống chỉ định hoàn toàn với tất cả bệnh nhân cao huyết áp."
    )
    result = run_fides_lite(
        answer=answer,
        retrieved_context=retrieved_context,
        nli_enabled=False,
    )
    assert result.verdict == "fail"
    assert result.severity == "high"
    assert result.policy_action == "block"


# ==============================================================================
# 3. Fail-Closed Suppression Tests
# ==============================================================================


def test_research_tier2_fails_closed_when_critical_claim_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["doc-1"],
            answer="Bệnh nhân nên dùng liều 500mg 4 lần mỗi ngày.",
            model_used="deepseek-v3.2",
            retrieved_context=[{"id": "doc-1", "source": "pubmed", "title": "Doc", "text": "Context without dosage.", "url": "https://pubmed.ncbi.nlm.nih.gov/1/", "score": 0.8}],
            context_debug={"relevance": 0.8},
            flow_events=[],
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]):  # noqa: ARG001
        return FactCheckResult(
            enabled=True,
            stage="fides-lite-v1.2",
            verdict="fail",
            confidence=0.2,
            supported_claims=0,
            total_claims=1,
            unsupported_claims=["Nên dùng liều 500mg."],
            evidence_count=1,
            severity="high",
            note="Hard-veto failure",
            policy_action="block",
            verification_matrix=[
                {
                    "claim": "Nên dùng liều 500mg.",
                    "claim_type": "dosage",
                    "support_status": "insufficient",
                    "confidence": 0.1,
                    "overlap_score": 0.0,
                    "evidence_ref": None,
                    "evidence_snippet": "",
                    "rationale": "Ungrounded dosage",
                }
            ],
        )

    monkeypatch.setattr("clara_ml.agents.research_tier2.RagPipelineP1.run", _fake_pipeline_run)
    monkeypatch.setattr("clara_ml.agents.research_tier2.run_fides_lite", _fake_factcheck)

    result = run_research_tier2(
        {
            "query": "Liều dùng thuốc",
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    assert result.get("policy_action") == "block"
    # Fails closed with safe escalation message, not the dangerous ungrounded dosage answer
    assert "tham vấn trực tiếp bác sĩ" in result.get("answer", "").lower()
    assert "500mg 4 lần" not in result.get("answer", "")


# ==============================================================================
# 4. Council Parallel Execution Tests
# ==============================================================================


def test_council_parallel_execution_returns_all_specialists() -> None:
    payload = {
        "symptoms": ["chest pain", "headache", "edema"],
        "labs": {"egfr": 45.0, "creatinine": 1.4, "blood_glucose": 140.0},
        "medications": ["aspirin", "lisinopril"],
        "history": ["hypertension", "type 2 diabetes"],
    }
    result = run_council(payload)
    assert "per_specialist_assessments" in result
    assessments = result["per_specialist_assessments"]
    assert len(assessments) == len(SUPPORTED_SPECIALISTS)
    specialist_names = [item["specialist"] for item in assessments]
    assert tuple(specialist_names) == SUPPORTED_SPECIALISTS
