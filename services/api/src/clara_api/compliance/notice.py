"""Versioned AI Transparency Notice content + model disclosure (Req 1).

The notice tells the user they are interacting with an AI medical assistant,
its intended purpose, limitations, and that it does not replace a licensed
clinician (Req 1.1). The version is config-driven; bumping it forces
re-acknowledgement on next access (Req 1.6).
"""

from __future__ import annotations

from clara_api.core.config import get_settings

# Model identity used for the response-envelope disclosure (Req 1.3). The
# fallback sentinel comes from the ML local deterministic synthesiser.
_FALLBACK_PREFIX = "local-synth"


def current_notice_version() -> str:
    return get_settings().compliance_transparency_notice_version.strip() or "2026-03-v1"


def transparency_notice() -> dict[str, object]:
    """Return the bilingual (vi/en) transparency-notice payload."""

    version = current_notice_version()
    return {
        "version": version,
        "vi": {
            "title": "Thông báo về hệ thống Trí tuệ nhân tạo",
            "body": (
                "Bạn đang tương tác với CLARA, một trợ lý y tế sử dụng Trí tuệ "
                "nhân tạo. CLARA hỗ trợ tra cứu và phân tích thông tin y khoa, "
                "KHÔNG thay thế bác sĩ và không đưa ra chẩn đoán hay kê đơn. Hãy "
                "luôn tham khảo ý kiến của nhân viên y tế có chuyên môn."
            ),
            "limitations": [
                "Không thay thế chẩn đoán hoặc điều trị của bác sĩ.",
                "Câu trả lời có thể chưa đầy đủ hoặc chưa cập nhật.",
                "Trong trường hợp khẩn cấp, hãy gọi cấp cứu ngay.",
            ],
        },
        "en": {
            "title": "Artificial Intelligence system notice",
            "body": (
                "You are interacting with CLARA, an AI-powered medical assistant. "
                "CLARA helps retrieve and analyse medical information; it does NOT "
                "replace a licensed clinician and does not diagnose or prescribe. "
                "Always review with a qualified healthcare professional."
            ),
            "limitations": [
                "Does not replace a clinician's diagnosis or treatment.",
                "Answers may be incomplete or not fully up to date.",
                "In an emergency, call emergency services immediately.",
            ],
        },
    }


def model_disclosure(model_used: str | None) -> dict[str, object]:
    """Build the ``ai_disclosure`` envelope field from ``model_used``.

    ``is_fallback`` is true iff the answer came from the local deterministic
    synthesiser (``local-synth-*``) (Correctness Property 8).
    """

    raw = (model_used or "").strip()
    is_fallback = raw.lower().startswith(_FALLBACK_PREFIX)
    if not raw:
        family, version = "unknown", "unknown"
    elif "-" in raw:
        # e.g. "deepseek-v4-pro" -> family "deepseek", version "v4-pro"
        head, _, tail = raw.partition("-")
        family, version = head, tail or "unknown"
    else:
        family, version = raw, "unknown"
    return {
        "model_family": family,
        "model_version": version,
        "is_fallback": is_fallback,
    }
