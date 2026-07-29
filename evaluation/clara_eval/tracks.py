"""Stable identifiers and human-readable metadata for CLARA-Eval VN.

The evaluation layer deliberately keeps these names independent from product
routes.  A track is an evidence boundary, not a claim that its target metric
has been measured or that the corresponding model is clinically validated.
"""

from __future__ import annotations

from enum import StrEnum


class EvalTrack(StrEnum):
    """The nine required CLARA-Eval VN tracks."""

    VIETNAMESE_CLINICAL_UNDERSTANDING = "vietnamese_clinical_understanding"
    MEDICAL_QA_PATIENT_COMMUNICATION = "medical_qa_patient_communication"
    RESEARCH_RAG = "research_rag"
    CAREGUARD_DRUGBANK = "careguard_drugbank"
    SCRIBE_ASR = "scribe_asr"
    LIFEMAP_INVARIANTS = "lifemap_invariants"
    COUNCIL_ABLATION = "council_ablation"
    WORDING_USABILITY = "wording_usability"
    MODEL_ROUTING_LATENCY_COST = "model_routing_latency_cost"


TRACK_METADATA: dict[EvalTrack, dict[str, str]] = {
    EvalTrack.VIETNAMESE_CLINICAL_UNDERSTANDING: {
        "label_vi": "Hiểu lâm sàng tiếng Việt",
        "scope": "Intent, thực thể, phủ định, người trải nghiệm, thời gian và emergency wording.",
    },
    EvalTrack.MEDICAL_QA_PATIENT_COMMUNICATION: {
        "label_vi": "Hỏi đáp y khoa và giao tiếp người bệnh",
        "scope": "An toàn, chuyển cấp cứu, từ chối phù hợp và ngôn ngữ dễ hiểu.",
    },
    EvalTrack.RESEARCH_RAG: {
        "label_vi": "Nghiên cứu RAG",
        "scope": "Truy xuất, trích dẫn, hỗ trợ claim, mâu thuẫn và abstention.",
    },
    EvalTrack.CAREGUARD_DRUGBANK: {
        "label_vi": "CareGuard với DrugBank",
        "scope": "Index integrity, fail-closed DDI và chuẩn hóa thuốc tiếng Việt.",
    },
    EvalTrack.SCRIBE_ASR: {
        "label_vi": "Scribe và ASR",
        "scope": "ASR, draft SOAP, groundedness và yêu cầu duyệt chuyên môn.",
    },
    EvalTrack.LIFEMAP_INVARIANTS: {
        "label_vi": "Bất biến LifeMap",
        "scope": "Revision, consent, profile isolation, provenance và trạng thái draft.",
    },
    EvalTrack.COUNCIL_ABLATION: {
        "label_vi": "Council ablation",
        "scope": "So sánh C0–C4 với red-flag, verifier và human review.",
    },
    EvalTrack.WORDING_USABILITY: {
        "label_vi": "Câu chữ và khả dụng",
        "scope": "Bảo toàn ý nghĩa/severity/action và kiểm thử mù với người dùng.",
    },
    EvalTrack.MODEL_ROUTING_LATENCY_COST: {
        "label_vi": "Routing, độ trễ và chi phí model",
        "scope": "Tier routing, latency, token, cost, fallback và under-routing.",
    },
}


REQUIRED_TRACK_IDS: frozenset[str] = frozenset(track.value for track in EvalTrack)
