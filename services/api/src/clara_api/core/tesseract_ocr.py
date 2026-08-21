"""Tesseract OCR integration for medication scanning.

Uses pytesseract + Pillow. Tesseract binaries and language packs (vie, eng)
must be installed in the container.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def detect_text(
    image_bytes: bytes,
    *,
    languages: str = "vie+eng",
    psm: int = 6,
) -> str:
    """
    Run Tesseract OCR on image bytes and return the extracted text.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, TIFF, etc.)
        languages: Tesseract language string (e.g. "vie+eng" for Vietnamese + English)
        psm: Page segmentation mode (6 = uniform block of text, good for prescriptions)

    Returns:
        Extracted text, or empty string on failure.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        logger.warning("Tesseract OCR dependencies not available: %s", exc)
        return ""

    try:
        raw_image = Image.open(io.BytesIO(image_bytes))
        # Convert to RGB if necessary (Tesseract handles RGB best)
        image = raw_image.convert("RGB") if raw_image.mode not in ("RGB", "L") else raw_image
        config = f"--psm {psm}"
        text = pytesseract.image_to_string(image, lang=languages, config=config)
        return text.strip()
    except Exception as exc:
        logger.warning("Tesseract OCR failed: %s", exc)
        return ""
