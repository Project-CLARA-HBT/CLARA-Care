"""Ground the golden Q&A set against the live corpus (task 9.1 follow-up).

The in-code :data:`~clara_ml.rag.eval.golden_set.DEFAULT_GOLDEN_SET` carries
*symbolic* ``relevant_doc_ids`` (e.g. ``"dailymed:warfarin-spl"``) authored
before any corpus existed. The persistent :class:`~clara_ml.rag.store.hybrid_retriever.HybridRetriever`
surfaces a stable ``doc_ref = "{source}:{external_id}"`` for every retrieved
document, so recall can only be scored once each golden item's
``relevant_doc_ids`` are *grounded* to the real ``doc_ref`` values of the
corpus documents that actually answer the question.

This module performs that grounding deterministically and idempotently:

* :data:`QID_DRUG_KEYWORDS` maps each golden ``qid`` to the drug-name keyword(s)
  whose label documents are relevant to that question (derived from the golden
  questions themselves).
* :func:`ground_golden_set` looks up, per ``qid``, the corpus documents whose
  ``title`` matches any keyword (case-insensitive) within the configured
  ``source_keys`` (drug-label sources by default), then UPDATEs that golden
  item's ``relevant_doc_ids`` (and ``must_cite``) in the ``eval_set`` table with
  the resulting real ``doc_ref`` list.

It only writes to ``eval_set`` (never the ``kb_*`` corpus), is parameterized
(no SQL interpolation), and is import-safe (the ORM is imported lazily inside
the function).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["QID_DRUG_KEYWORDS", "ground_golden_set"]


# Per-question relevant drug keywords. Each keyword is matched (case-insensitive
# substring) against a corpus document's ``title`` (drug-label titles are the
# drug name, e.g. "WARFARIN SODIUM"). Both generic and common alternate names
# are listed so either an openFDA or a DailyMed label is captured.
QID_DRUG_KEYWORDS: dict[str, list[str]] = {
    "ddi-aspirin-warfarin": ["aspirin", "warfarin"],
    "ddi-clopidogrel-omeprazole": ["clopidogrel", "omeprazole"],
    "ddi-acei-potassium-hyperkalemia": ["lisinopril"],
    "ddi-sildenafil-nitrate": ["sildenafil", "nitroglycerin"],
    "dosage-metformin-adult": ["metformin"],
    "dosage-amoxicillin-pediatric": ["amoxicillin"],
    "contraindication-metformin-renal": ["metformin"],
    "contraindication-nsaid-peptic-ulcer": ["ibuprofen"],
    "indication-amoxicillin": ["amoxicillin"],
    "indication-aspirin-secondary-prevention": ["aspirin"],
    "adverse-statin-myopathy": ["simvastatin"],
    "adverse-acei-cough": ["lisinopril"],
    "safety-paracetamol-overdose": ["acetaminophen", "paracetamol"],
    "safety-warfarin-inr-monitoring": ["warfarin"],
}

# Default corpus sources to ground against (the tier-1 drug-label sources whose
# documents are SPL labels titled by drug name).
DEFAULT_GROUNDING_SOURCES: tuple[str, ...] = ("openfda", "dailymed")


def _resolve_doc_refs(
    session: Any,
    keywords: Sequence[str],
    source_keys: Sequence[str],
) -> list[str]:
    """Return the ``source:external_id`` doc_refs whose title matches a keyword.

    Pure read over ``kb_documents`` JOIN ``kb_source_registry``; every value is
    a bound parameter. Ordered for determinism and de-duplicated.
    """

    from sqlalchemy import select

    from clara_ml.rag.store.schema import KbDocument, KbSourceRegistry

    stmt = (
        select(KbSourceRegistry.source_key, KbDocument.external_id, KbDocument.title)
        .join(KbSourceRegistry, KbSourceRegistry.id == KbDocument.source_id)
        .where(KbSourceRegistry.source_key.in_(list(source_keys)))
        .order_by(KbDocument.id)
    )
    refs: list[str] = []
    seen: set[str] = set()
    lowered = [k.lower() for k in keywords]
    for source_key, external_id, title in session.execute(stmt).all():
        title_l = str(title or "").lower()
        if not external_id:
            continue
        if any(kw in title_l for kw in lowered):
            ref = f"{source_key}:{external_id}"
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _ground(
    session: Any,
    keyword_map: Mapping[str, Sequence[str]],
    source_keys: Sequence[str],
) -> dict[str, int]:
    from sqlalchemy import select

    from clara_ml.rag.store.schema import EvalSet

    summary: dict[str, int] = {}
    for qid, keywords in keyword_map.items():
        refs = _resolve_doc_refs(session, keywords, source_keys)
        row = session.execute(
            select(EvalSet).where(EvalSet.qid == qid)
        ).scalar_one_or_none()
        if row is None:
            summary[qid] = 0
            continue
        row.relevant_doc_ids = list(refs)
        # Citation targets are a subset of the relevant docs; ground them to the
        # same real doc_refs so citation_acc is measurable too.
        row.must_cite = list(refs)
        summary[qid] = len(refs)
    session.flush()
    return summary


def ground_golden_set(
    store_or_session: Any,
    *,
    keyword_map: Mapping[str, Sequence[str]] | None = None,
    source_keys: Sequence[str] = DEFAULT_GROUNDING_SOURCES,
) -> dict[str, int]:
    """Ground every golden item's ``relevant_doc_ids`` to real corpus doc_refs.

    For each ``qid`` in ``keyword_map`` (default :data:`QID_DRUG_KEYWORDS`),
    resolve the corpus documents whose title matches a keyword and UPDATE that
    ``eval_set`` row's ``relevant_doc_ids`` + ``must_cite`` to the resulting
    ``doc_ref`` list. Idempotent (re-running with the same corpus yields the same
    grounding). Returns a ``{qid: n_relevant_docs}`` summary.

    Accepts the same handle shapes as
    :func:`~clara_ml.rag.eval.golden_set.seed_eval_set` (a DocumentStore, a live
    ``Session``, or a zero-arg session factory).
    """

    from sqlalchemy.orm import Session

    kmap = dict(QID_DRUG_KEYWORDS if keyword_map is None else keyword_map)

    transaction = getattr(store_or_session, "transaction", None)
    if callable(transaction) and not isinstance(store_or_session, Session):
        with transaction() as session:
            return _ground(session, kmap, source_keys)
    if isinstance(store_or_session, Session):
        summary = _ground(store_or_session, kmap, source_keys)
        store_or_session.commit()
        return summary
    if callable(store_or_session):
        session = store_or_session()
        try:
            summary = _ground(session, kmap, source_keys)
            session.commit()
            return summary
        finally:
            session.close()

    raise TypeError(
        "ground_golden_set expects a DocumentStore, a SQLAlchemy Session, or a "
        f"zero-argument session factory; got {type(store_or_session)!r}"
    )
