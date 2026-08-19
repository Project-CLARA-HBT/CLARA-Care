"""Model capabilities and route classes for Model Gateway v2.

Defines the normalized capability vocabulary and route class tiers for all
CLARA model tasks, abstracting provider-specific models behind capability contracts.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ModelCapability",
    "RouteClass",
]


class ModelCapability(StrEnum):
    """Declared capabilities supported by model adapters or required by task contracts."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    LONG_CONTEXT = "long_context"


class RouteClass(StrEnum):
    """Categorization of LLM workloads and routing classes."""

    FAST_MULTIMODAL = "fast_multimodal"
    QUALITY_MULTIMODAL = "quality_multimodal"
    TEXT_REASONING = "text_reasoning"
    ASR = "asr"
    EMBEDDING = "embedding"
