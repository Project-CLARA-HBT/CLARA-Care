from __future__ import annotations

import unicodedata

VIET_TONE_MARKS = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}


def normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def has_tone_marks(text: str) -> bool:
    decomp = unicodedata.normalize("NFD", text)
    return any(ch in VIET_TONE_MARKS for ch in decomp)


def validate_tone_marks(text: str) -> tuple[bool, str]:
    """Helper kiểm tra hợp lệ cơ bản cho dấu thanh tiếng Việt.

    P0 chỉ kiểm tra lỗi dễ gặp:
    - Chuỗi chưa normalize NFC
    - Có hơn 1 dấu thanh liên tiếp trên cùng cụm ký tự
    """
    if text != normalize_nfc(text):
        return False, "Text chưa ở dạng NFC."

    decomp = unicodedata.normalize("NFD", text)
    in_cluster = False
    tone_count_in_cluster = 0

    for ch in decomp:
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            in_cluster = True
            tone_count_in_cluster = 0
            continue

        if not in_cluster:
            continue

        if ch in VIET_TONE_MARKS:
            tone_count_in_cluster += 1
            if tone_count_in_cluster > 1:
                return False, "Phát hiện nhiều hơn 1 dấu thanh trong cùng cụm ký tự."
            continue

        # Gặp ký tự không phải combining mark thì reset cluster
        if not cat.startswith("M"):
            in_cluster = False
            tone_count_in_cluster = 0

    return True, "OK"
