from __future__ import annotations

COMPOUND_TERMS = {
    "đái tháo đường": "đái_tháo_đường",
    "huyết áp": "huyết_áp",
    "suy tim": "suy_tim",
}


def tokenize_vi_medical(text: str) -> list[str]:
    lowered = text.lower()
    for phrase, token in COMPOUND_TERMS.items():
        lowered = lowered.replace(phrase, token)
    return lowered.split()
