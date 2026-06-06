"""Source connectors for offline ingestion (Epic P1).

API-first connectors (PubMed E-utilities, openFDA, DailyMed SPL, RxNorm,
Europe PMC) plus a single robots-respecting HTML gap-fill connector
(``vn_crawl``). Each connector implements the ``SourceConnector`` protocol
defined in ``base.py`` and yields ``RawRecord`` items with a resumable cursor.
"""
