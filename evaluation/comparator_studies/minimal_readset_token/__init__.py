"""Minimal Alternative Binding Baseline package for E02 comparator studies.

Provides minimal read-set / disclosure token implementations:
- `MinReadsetToken`: Minimal unsigned read-set token testing representation minimality.
- `HmacReadsetToken`: HMAC-SHA256 signed read-set token for untrusted transport integrity.
- `validate_readset_token`: Complete coordinate, freshness, state version, policy, consent, and evidence commitment validator.
- `MinReadsetTokenPostgresAdapter`: Execution adapter evaluating schedules in PostgreSQL or SQLite.
- `run_minimal_token_experiment`: Runner replaying the 352-schedule E01 corpus across comparator arms.
- `analyze_minimal_token_results`: Statistical analysis computing decision concordance, error rates, and byte overhead.

Evaluation-only package; refuses import from production services/ (GR-03, C-004).
"""

from __future__ import annotations

import sys

FORBIDDEN_PRODUCTION_IMPORT_MESSAGE = (
    "minimal_readset_token is an evaluation-only package (E02 baseline); "
    "production code under services/ must not import it (GR-03, C-004)"
)

_TOOLING_PATH_MARKERS = (
    "/.venv/",
    "/site-packages/",
    "/__pycache__/",
    "/.local/",
    "/node_modules/",
)


def _guard_production_import() -> None:
    frame = sys._getframe(1)
    while frame is not None:
        filename = (frame.f_code.co_filename or "").replace("\\", "/")
        parts = filename.split("/")
        if "services" in parts and not any(marker in filename for marker in _TOOLING_PATH_MARKERS):
            raise RuntimeError(FORBIDDEN_PRODUCTION_IMPORT_MESSAGE)
        frame = frame.f_back


_guard_production_import()

from evaluation.comparator_studies.minimal_readset_token.analyze import (
    analyze_minimal_token_results,
    generate_markdown_report,
)
from evaluation.comparator_studies.minimal_readset_token.postgres_adapter import (
    DEFAULT_HMAC_SECRET,
    E02_ARMS,
    MinReadsetTokenPostgresAdapter,
    ScheduleExecutionOutcome,
)
from evaluation.comparator_studies.minimal_readset_token.runner import (
    run_minimal_token_experiment,
)
from evaluation.comparator_studies.minimal_readset_token.token import (
    HMAC_TOKEN_SCHEMA,
    MIN_TOKEN_SCHEMA,
    HmacReadsetToken,
    MinReadsetToken,
    StateDependency,
    compute_evidence_commitment,
    generate_hmac_readset_token,
    generate_min_readset_token,
)
from evaluation.comparator_studies.minimal_readset_token.validator import (
    TokenValidationResult,
    validate_readset_token,
)

__all__ = [
    "MinReadsetToken",
    "HmacReadsetToken",
    "StateDependency",
    "MIN_TOKEN_SCHEMA",
    "HMAC_TOKEN_SCHEMA",
    "compute_evidence_commitment",
    "generate_min_readset_token",
    "generate_hmac_readset_token",
    "validate_readset_token",
    "TokenValidationResult",
    "MinReadsetTokenPostgresAdapter",
    "ScheduleExecutionOutcome",
    "E02_ARMS",
    "DEFAULT_HMAC_SECRET",
    "run_minimal_token_experiment",
    "analyze_minimal_token_results",
    "generate_markdown_report",
]
