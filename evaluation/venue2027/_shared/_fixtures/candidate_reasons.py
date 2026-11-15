"""Fixture candidate reason-code module — candidate-supplied codes are NOT truth.

Real module (not an oracle mock): candidate arms emit their own claimed reason
codes. Per INDEPENDENT_EVIDENCE_PROTOCOL.md rule 2, ground truth derives from
frozen oracle labels and persisted state, never from these codes; an oracle
importing this module must be refused with ``CANDIDATE_IMPORT``.
"""

from __future__ import annotations

CANDIDATE_REASONS_VERSION = "1.0.0"

CANDIDATE_CLAIMED_ADMIT = "CANDIDATE_CLAIMED_ADMIT"
CANDIDATE_CLAIMED_REJECT = "CANDIDATE_CLAIMED_REJECT"
