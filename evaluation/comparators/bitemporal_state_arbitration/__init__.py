"""Mechanism-mapped bi-temporal state arbitration comparator."""

from .engine import ArbitrationEvent, ArbitrationResult, arbitrate

__all__ = ("ArbitrationEvent", "ArbitrationResult", "arbitrate")
