"""Isolated compatibility helpers for data imported before LifeMap V2.

Nothing in this package participates in live LifeMap decisions.  It exists so
operators can reconcile historical imports without coupling that work to the
current truth-state and provenance domain modules.
"""

from clara_api.lifemap.legacy.provenance import (
    REPORT_CATEGORIES,
    legacy_provenance_counts,
)

__all__ = ["REPORT_CATEGORIES", "legacy_provenance_counts"]
