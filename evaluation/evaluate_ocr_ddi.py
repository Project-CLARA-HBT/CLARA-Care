"""CareGuard-VN Multimodal OCR-to-DDI Module for Phase 2 Evaluation.

Re-exports multimodal OCR and DDI evaluation from evaluation.careguard_multimodal_ocr.evaluate_ocr_ddi.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.careguard_multimodal_ocr.evaluate_ocr_ddi import (  # noqa: E402
    OcrDdiMetricReport,
    generate_latex_table,
    run_careguard_multimodal_evaluation,
)

__all__ = [
    "OcrDdiMetricReport",
    "generate_latex_table",
    "run_careguard_multimodal_evaluation",
]

if __name__ == "__main__":
    report = run_careguard_multimodal_evaluation()
    print("CareGuard-VN Multimodal OCR-to-DDI Evaluation:")
    print(f"Total Cases: {report.total_test_cases}")
    print(f"Drug Name F1: {report.drug_name_metrics['f1'] * 100:.1f}%")
    print(f"Strength F1:  {report.strength_metrics['f1'] * 100:.1f}%")
    print(f"Freq Accuracy:{report.frequency_metrics['accuracy'] * 100:.1f}%")
    print(f"DDI Sens:     {report.ddi_metrics['sensitivity'] * 100:.1f}%")
    print(f"FIDES Gate:   {report.fides_gate_blocking_rate * 100:.1f}%")
