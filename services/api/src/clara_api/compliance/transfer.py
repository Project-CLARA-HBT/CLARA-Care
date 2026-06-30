"""Cross-border transfer registry + Transfer Impact Assessment seeds (Req 4).

The registry records every offshore processor that may receive personal data,
its jurisdiction, processing purpose, and the path to its TIA document under
``docs/compliance/``. It is seeded idempotently and served read-only to admins;
the privacy policy summarises it (Req 4.1, 4.5).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import TransferAssessment


@dataclass(frozen=True)
class ProcessorSeed:
    processor: str
    jurisdiction: str
    purpose: str
    tia_doc_ref: str


# Bounded processor-identity / purpose constants for the offshore LLM path. They
# are the single source of truth shared by the registry seeds and the no-PII
# transfer-event logging at the ML proxy consult point (Req 4.4), so the
# ``processor``/``purpose`` recorded on an event always matches a registry row.
LLM_PROCESSOR = "yescale-deepseek"
LLM_PURPOSE = "llm_inference"
EMBEDDING_PROCESSOR = "yescale-embeddings"
EMBEDDING_PURPOSE = "embedding_generation"


# Static seeds for the offshore processors CLARA uses today. Kept in code so the
# privacy policy + admin records view derive from a single source of truth.
PROCESSOR_SEEDS: tuple[ProcessorSeed, ...] = (
    ProcessorSeed(
        processor=LLM_PROCESSOR,
        jurisdiction="offshore (non-VN)",
        purpose=LLM_PURPOSE,
        tia_doc_ref="docs/compliance/transfer-impact-assessments.md#yescale-deepseek",
    ),
    ProcessorSeed(
        # Embeddings are produced via the YEScale-hosted, OpenAI-compatible
        # endpoint (``EMBEDDING_BASE_URL`` defaults to ``https://api.yescale.io/v1``).
        # The registry records the actual offshore *recipient* of the data
        # (YEScale), which is what the cross-border TIA gates on (Req 4.1).
        processor=EMBEDDING_PROCESSOR,
        jurisdiction="offshore (non-VN)",
        purpose=EMBEDDING_PURPOSE,
        tia_doc_ref="docs/compliance/transfer-impact-assessments.md#yescale-embeddings",
    ),
)


def seed_registry(db: Session) -> int:
    """Insert any missing processor seeds. Returns the number inserted."""

    existing = {row[0] for row in db.execute(select(TransferAssessment.processor)).all()}
    inserted = 0
    for seed in PROCESSOR_SEEDS:
        if seed.processor in existing:
            continue
        db.add(
            TransferAssessment(
                processor=seed.processor,
                jurisdiction=seed.jurisdiction,
                purpose=seed.purpose,
                tia_doc_ref=seed.tia_doc_ref,
                active=True,
            )
        )
        inserted += 1
    if inserted:
        db.flush()
    return inserted


def list_processors(db: Session, *, active_only: bool = True) -> list[dict[str, object]]:
    """Return registry rows as plain dicts (seeding from code if empty)."""

    rows = db.execute(select(TransferAssessment)).scalars().all()
    if not rows:
        seed_registry(db)
        rows = db.execute(select(TransferAssessment)).scalars().all()
    out: list[dict[str, object]] = []
    for row in rows:
        if active_only and not row.active:
            continue
        out.append(
            {
                "processor": row.processor,
                "jurisdiction": row.jurisdiction,
                "purpose": row.purpose,
                "tia_doc_ref": row.tia_doc_ref,
                "active": bool(row.active),
            }
        )
    return out
