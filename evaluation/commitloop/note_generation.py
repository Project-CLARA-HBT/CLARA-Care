"""Anchor-time-only synthetic note projection from already grounded fields."""

from __future__ import annotations

import json

from evaluation.commitloop.schema import ConstructedCase


def render_anchor_note(case: ConstructedCase) -> str | None:
    if case.status != "ELIGIBLE" or case.target is None or case.anchor_valid_time is None:
        return None
    payload = {
        "action": case.action,
        "anchor_evidence_id": case.anchor_evidence_id,
        "anchor_time": case.anchor_valid_time.isoformat(),
        "due_time": case.due_time.isoformat() if case.due_time else None,
        "target": case.target,
    }
    return "SYNTHETIC_ANCHOR_NOTE " + json.dumps(payload, sort_keys=True, separators=(",", ":"))
