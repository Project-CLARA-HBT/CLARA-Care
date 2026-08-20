"""CareGuard-VN Multimodal OCR-to-DDI Module for Phase 2 Evaluation.

Re-exports multimodal OCR and DDI evaluation from evaluation.careguard_multimodal_ocr.evaluate_ocr_ddi.
"""

from __future__ import annotations

from evaluation.careguard_multimodal_ocr.evaluate_ocr_ddi import (
    OcrDdiMetricReport,
    generate_latex_table,
    run_careguard_multimodal_evaluation,
)

__all__ = [
    "OcrDdiMetricReport",
    "generate_latex_table",
    "run_careguard_multimodal_evaluation",
]
