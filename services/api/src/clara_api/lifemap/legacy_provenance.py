"""Compatibility import for a LifeMap V1 provenance reconciliation helper.

New code must import :mod:`clara_api.lifemap.legacy.provenance`.  This module
stays deliberately tiny because a few external/operator scripts may still use
the pre-isolation import path.
"""

from clara_api.lifemap.legacy.provenance import (
    REPORT_CATEGORIES,
    legacy_provenance_counts,
)

__all__ = ["REPORT_CATEGORIES", "legacy_provenance_counts"]
