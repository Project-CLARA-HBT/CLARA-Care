"""Fixture in-package alias module re-exporting the candidate arm.

Exercises transitive detection: an oracle importing this harmless-looking
alias still transitively names the candidate module and must be refused with
``CANDIDATE_IMPORT``.
"""

from __future__ import annotations

from evaluation.venue2027._shared._fixtures import candidate_arm

CANDIDATE_ALIAS_VERSION = candidate_arm.CANDIDATE_ARM_VERSION
