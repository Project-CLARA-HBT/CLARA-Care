"""Safe, structured, patient-language rendering for clinical pipeline outputs.

This package deliberately renders from a constrained semantic contract.  It is
not a second clinical reasoner and it never receives authority to prescribe,
change severity, or remove a mandatory warning.
"""

from .careguard_draft import render_careguard_wording_draft
from .renderer import render_explanation
from .schemas import RenderedExplanation, RenderingInput

__all__ = [
    "RenderedExplanation",
    "RenderingInput",
    "render_careguard_wording_draft",
    "render_explanation",
]
