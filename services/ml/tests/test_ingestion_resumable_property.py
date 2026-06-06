"""Property-based test for resumable ingestion (Property 6).

Feature: rag-knowledge-pipeline, task 3.18 (optional test).

**Validates: Requirements 4.3**

Design reference (design.md -> Correctness Properties):
    Property 6: Resumable ingestion. An ingestion run interrupted after a
    checkpoint can be resumed from the persisted watermark without reprocessing
    already-committed records and without losing un-processed records -- the
    final persisted corpus equals an uninterrupted run.

Requirement exercised:
    4.3  IF ingestion is interrupted, THEN upon restart THE
         Ingestion_Orchestrator SHALL resume from the persisted watermark and
         SHALL reprocess no record already committed, eventually persisting the
         same corpus as an uninterrupted run.

How this exercises the REAL orchestrator
----------------------------------------
This drives the real
:class:`clara_ml.ingestion.orchestrator.IngestionOrchestrator` (real cleaner,
real ``content_hash``, real Structure_Aware_Chunker) against fully in-memory
doubles for the injected collaborators -- so no DB connection or network request
is made. For consistency with the idempotency property test (task 3.17) it
reuses that module's faithful in-memory ``FakeDocumentStore`` /
``FakeEmbeddingBuilder`` and its record generators, and adds a *cursor-paged*
connector that can deterministically interrupt at a batch boundary.

The resumable contract lives entirely in the orchestrator's run loop: after each
fetched batch it persists the next cursor via
``DocumentStore.checkpoint(source_id, cursor)`` (the per-source watermark in
``kb_source_registry``); a crash/restart resolves the source again, reads that
persisted watermark, and hands it back to the connector as the starting cursor.
We model a crash as the connector raising at the start of the fetch for the
*next* batch (i.e. strictly after the previous batch was processed and its
watermark checkpointed), then build a fresh orchestrator over the *same* store to
"restart". A watermark-reading source resolver mirrors the real registry lookup
(``kb_source_registry.last_watermark``), so resume genuinely depends on the
checkpoint the orchestrator wrote.
"""

from __future__ import annotations

import math
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.connectors.base import ConnectorContext, FetchWindow, RawRecord
from clara_ml.ingestion.orchestrator import IngestionOrchestrator, SourceResolution

# Reuse the task 3.17 in-memory doubles + record generators verbatim so the two
# ingestion property tests model the Document_Store / embedding-builder contract
# identically (the instruction for task 3.18).
from test_ingestion_idempotent_property import (
    _SOURCE_ID,
    _SOURCE_KEY,
    FakeDocumentStore,
    FakeEmbeddingBuilder,
    _record_specs,
    _records_from_specs,
)

_CONTEXT = ConnectorContext(source_key=_SOURCE_KEY, trust_tier=1)


# ---------------------------------------------------------------------------
# Cursor-paged connector with a deterministic batch-boundary interruption
# ---------------------------------------------------------------------------


class _SimulatedInterruption(RuntimeError):
    """Raised by :class:`PagingConnector` to model a crash before the next batch.

    This is *not* an ``EmbeddingUnavailableError`` and is *not* raised from
    ``_process_record``: it propagates straight out of
    :meth:`IngestionOrchestrator.run`, which is exactly how an uncaught
    crash/kill between batches would surface.
    """


class PagingConnector:
    """Connector double that pages a fixed record set by an integer offset cursor.

    The cursor is the string offset of the next record to emit -- the orchestrator
    threads it through ``checkpoint`` -> ``last_watermark`` -> back into ``fetch``,
    so a fresh connector built on "restart" resumes exactly where the previous one
    left off. ``next_cursor`` is ``None`` on the final page (signals exhaustion).

    When ``fail_after_batches`` is set, the connector raises
    :class:`_SimulatedInterruption` at the *start* of the fetch that would serve
    the ``(fail_after_batches + 1)``-th batch -- i.e. strictly after the prior
    batch's watermark was checkpointed. ``None`` runs to exhaustion (no crash).
    """

    def __init__(
        self,
        context: ConnectorContext,
        records: list[RawRecord],
        *,
        page_size: int,
        fail_after_batches: int | None = None,
    ) -> None:
        self.context = context
        self._records = list(records)
        self._page_size = max(1, int(page_size))
        self._fail_after_batches = fail_after_batches
        self._batches_served = 0
        # Order-preserving log of every external_id this connector emitted, used
        # to assert resume reprocessed nothing already committed.
        self.emitted_external_ids: list[str] = []

    def fetch(
        self, window: FetchWindow, cursor: str | None = None
    ) -> tuple[list[RawRecord], str | None]:
        # Crash before serving the next batch (after the previous checkpoint).
        if (
            self._fail_after_batches is not None
            and self._batches_served >= self._fail_after_batches
        ):
            raise _SimulatedInterruption(
                f"simulated crash after {self._batches_served} batch(es)"
            )

        offset = int(cursor) if cursor not in (None, "") else 0
        page = self._records[offset : offset + self._page_size]
        if not page:
            return ([], None)

        self._batches_served += 1
        next_offset = offset + len(page)
        next_cursor = str(next_offset) if next_offset < len(self._records) else None
        self.emitted_external_ids.extend(r.external_id for r in page)
        return (list(page), next_cursor)


def _watermark_resolver(store: FakeDocumentStore):
    """Source resolver that reads the *persisted* watermark from ``store``.

    Mirrors the real registry lookup (``kb_source_registry.last_watermark``): on
    restart the orchestrator gets back exactly the cursor it last checkpointed,
    which is the signal the resume path depends on.
    """

    def resolver(source_key: str) -> SourceResolution:
        return SourceResolution(
            source_id=_SOURCE_ID,
            context=_CONTEXT,
            watermark=store.watermarks.get(_SOURCE_ID, ""),
            enabled=True,
            display_name="Fake Source",
        )

    return resolver


def _build_orchestrator(
    store: FakeDocumentStore, connector: PagingConnector, resolver
) -> IngestionOrchestrator:
    return IngestionOrchestrator(
        store,
        FakeEmbeddingBuilder(),
        connectors={_SOURCE_KEY: connector},
        source_resolver=resolver,
    )


def _committed_external_ids(store: FakeDocumentStore) -> set[str]:
    return {external_id for (_source_id, external_id) in store.documents}


def _run_uninterrupted(records: list[RawRecord], page_size: int) -> FakeDocumentStore:
    """Build the reference corpus via a single uninterrupted run."""

    store = FakeDocumentStore()
    connector = PagingConnector(_CONTEXT, records, page_size=page_size)
    orchestrator = _build_orchestrator(store, connector, _watermark_resolver(store))
    orchestrator.run(_SOURCE_KEY, batch_size=page_size)
    return store


# ---------------------------------------------------------------------------
# Property 6
# ---------------------------------------------------------------------------


@settings(max_examples=150, deadline=None)
@given(specs=_record_specs, data=st.data())
def test_resumable_ingestion_equals_uninterrupted_run(
    specs: list[dict[str, Any]], data: st.DataObject
) -> None:
    """Property 6 / Req 4.3: crash-and-resume converges to the uninterrupted corpus.

    For a record set and page size, we first build the reference corpus with one
    uninterrupted run. We then ingest the *same* records into a fresh store while
    repeatedly crashing at hypothesis-chosen batch boundaries, restarting each
    time from the persisted watermark. We assert:

    * every (re)started attempt re-fetches **no** already-committed record
      (``emitted ∩ committed_before == ∅``) -- resume starts from the watermark,
      so nothing committed is reprocessed (Req 4.3);
    * the resumed corpus is **byte-for-byte identical** to the uninterrupted one
      (no un-processed record is lost, none is duplicated).
    """

    records = _records_from_specs(specs)
    page_size = data.draw(st.integers(min_value=1, max_value=4), label="page_size")
    total_batches = math.ceil(len(records) / page_size) if records else 0

    # Reference corpus: a single uninterrupted ingestion run.
    reference_store = _run_uninterrupted(records, page_size)
    reference_snapshot = reference_store.snapshot()
    assert len(reference_store.documents) == len(records)

    # A bounded sequence of crash points (batches to serve before crashing).
    # Drawing in [0, total_batches - 1] guarantees a real mid-stream interruption
    # whenever there is at least one batch; an empty list means "no crash".
    crash_upper = max(0, total_batches - 1)
    crash_points = data.draw(
        st.lists(st.integers(min_value=0, max_value=crash_upper), max_size=4),
        label="crash_points",
    )

    store = FakeDocumentStore()
    resolver = _watermark_resolver(store)
    completed = False

    for fail_after in crash_points:
        if completed:
            break
        committed_before = _committed_external_ids(store)
        connector = PagingConnector(
            _CONTEXT, records, page_size=page_size, fail_after_batches=fail_after
        )
        orchestrator = _build_orchestrator(store, connector, resolver)
        try:
            orchestrator.run(_SOURCE_KEY, batch_size=page_size)
            completed = True
        except _SimulatedInterruption:
            pass
        # Req 4.3: an interrupted-then-resumed attempt reprocesses nothing that
        # was already committed (it resumed from the persisted watermark).
        assert set(connector.emitted_external_ids).isdisjoint(committed_before), (
            "resumed run re-fetched an already-committed record; it did not "
            "resume from the persisted watermark"
        )

    # Final guaranteed-complete run (resumes from wherever the last crash left
    # off). Skipped only when an earlier attempt already ran to completion.
    if not completed:
        committed_before = _committed_external_ids(store)
        connector = PagingConnector(_CONTEXT, records, page_size=page_size)
        orchestrator = _build_orchestrator(store, connector, resolver)
        orchestrator.run(_SOURCE_KEY, batch_size=page_size)
        assert set(connector.emitted_external_ids).isdisjoint(committed_before), (
            "final resume re-fetched an already-committed record"
        )

    # Property 6: the resumed corpus equals the uninterrupted corpus exactly --
    # no committed record was duplicated and no un-processed record was lost.
    assert len(store.documents) == len(records)
    assert store.total_chunks() == reference_store.total_chunks()
    assert store.snapshot() == reference_snapshot


# ---------------------------------------------------------------------------
# Concrete, deterministic example (complements the property)
# ---------------------------------------------------------------------------


def test_resumable_ingestion_concrete_example() -> None:
    """A 5-document source crashed after the first batch resumes to an identical corpus.

    Pins the exact resume behaviour: with ``page_size == 2`` the first attempt
    commits batch 1 (docs 0-1), checkpoints watermark ``"2"``, then crashes; the
    restart resolves watermark ``"2"`` and ingests only docs 2-4 (never re-touching
    docs 0-1), yielding the same corpus as an uninterrupted run.
    """

    records = [
        RawRecord(
            source_key=_SOURCE_KEY,
            external_id=f"doc-{i}",
            title=f"Label {i}",
            url=f"https://example.test/doc-{i}",
            lang="en",
            doc_type="spl_label",
            raw_text=(
                "INDICATIONS AND USAGE\n"
                f"Drug {i} is indicated for a condition.\n"
                "DRUG INTERACTIONS\n"
                f"Drug {i} may interact with another drug.\n"
            ),
            effective_date="2022-01-01",
            trust_tier=1,
        )
        for i in range(5)
    ]
    page_size = 2

    reference_store = _run_uninterrupted(records, page_size)
    assert len(reference_store.documents) == 5

    # Interrupted run: crash strictly after the first batch is checkpointed.
    store = FakeDocumentStore()
    resolver = _watermark_resolver(store)
    first_connector = PagingConnector(
        _CONTEXT, records, page_size=page_size, fail_after_batches=1
    )
    crashed = False
    try:
        _build_orchestrator(store, first_connector, resolver).run(
            _SOURCE_KEY, batch_size=page_size
        )
    except _SimulatedInterruption:
        crashed = True

    assert crashed, "the first attempt must be interrupted"
    # Exactly the first batch committed; watermark advanced to offset 2.
    assert _committed_external_ids(store) == {"doc-0", "doc-1"}
    assert store.watermarks[_SOURCE_ID] == "2"

    # Restart: resumes from watermark "2" and ingests only the remaining docs.
    resume_connector = PagingConnector(_CONTEXT, records, page_size=page_size)
    resume_report = _build_orchestrator(store, resume_connector, resolver).run(
        _SOURCE_KEY, batch_size=page_size
    )

    # Resume reprocessed none of the already-committed records.
    assert resume_connector.emitted_external_ids == ["doc-2", "doc-3", "doc-4"]
    assert resume_report.skipped == 0
    assert resume_report.inserted == 3
    assert resume_report.fetched == 3

    # Final corpus equals the uninterrupted run.
    assert len(store.documents) == 5
    assert store.total_chunks() == reference_store.total_chunks()
    assert store.snapshot() == reference_store.snapshot()
