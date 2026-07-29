"""Audience choices for a bounded renderer, kept separate from clinical facts."""

from __future__ import annotations

from .schemas import Audience


def is_english(audience: Audience) -> bool:
    return audience == "en"


def uncertainty_copy(*, english: bool, high: bool) -> str:
    if english:
        return (
            "Important information is still uncertain; this does not replace clinical assessment."
            if high
            else "This explanation is based on the available verified information."
        )
    return (
        "Một số thông tin quan trọng vẫn chưa chắc chắn; nội dung này không thay thế đánh giá y tế."
        if high
        else "Nội dung này dựa trên thông tin đã được kiểm tra hiện có."
    )
