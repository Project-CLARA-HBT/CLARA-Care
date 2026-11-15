"""Fixture baseline label module — frozen baseline truth labels, oracle-off-limits.

Real module (not an oracle mock): holds the strong baseline's frozen expected
labels. An oracle may reuse a baseline's *results* only via frozen label
tables loaded as data; importing this module would exchange labels with the
baseline arm and must be refused with ``BASELINE_LABEL_EXCHANGE``.
"""

from __future__ import annotations

BASELINE_LABELS_VERSION = "1.0.0"

BASELINE_FROZEN_LABELS: dict[tuple[str, str], str] = {
    ("sepsis_triage_v1", "case_admit"): "ADMIT",
    ("sepsis_triage_v1", "case_reject"): "REJECT",
}
