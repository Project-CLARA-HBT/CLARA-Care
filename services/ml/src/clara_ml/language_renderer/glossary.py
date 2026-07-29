"""Small deterministic wording glossary; no clinical inference lives here."""

from __future__ import annotations

from .schemas import Severity

VI_HEADLINES: dict[Severity, str] = {
    "emergency": "Cần hỗ trợ khẩn cấp ngay",
    "urgent_review": "Nên được nhân viên y tế đánh giá sớm",
    "clinical_review": "Nên trao đổi với nhân viên y tế",
    "routine": "Thông tin cần theo dõi thêm",
}

EN_HEADLINES: dict[Severity, str] = {
    "emergency": "Get emergency help now",
    "urgent_review": "Seek prompt clinical review",
    "clinical_review": "Discuss this with a clinician",
    "routine": "More information is needed",
}

VI_ACTIONS = {
    "seek_emergency": "Gọi cấp cứu tại địa phương hoặc đến khoa Cấp cứu gần nhất ngay.",
    "contact_clinician": "Liên hệ bác sĩ hoặc cơ sở y tế để được đánh giá phù hợp.",
    "monitor": "Theo dõi diễn biến và ghi lại thay đổi để trao đổi khi cần.",
    "none": "",
}

EN_ACTIONS = {
    "seek_emergency": "Call local emergency services or go to the nearest emergency department now.",
    "contact_clinician": "Contact a clinician or health service for an appropriate assessment.",
    "monitor": "Monitor changes and record them for a future discussion if needed.",
    "none": "",
}
