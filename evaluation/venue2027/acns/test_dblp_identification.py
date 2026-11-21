"""Check registered title-query identification against a small XML snapshot."""

import gzip

from evaluation.venue2027.acns.dblp_identification import scan


def test_time_phrase_and_boolean_boundaries(tmp_path):
    xml = tmp_path / "sample.gz"
    dtd = tmp_path / "dblp.dtd"
    dtd.write_text('<!ENTITY aacute "&#225;">')
    entries = [
        ("a", "2026", "Remote <i>attestation</i> and LLM auditability"),
        ("b", "2026", "An LLM receipt"),
        ("c", "2018", "Provenance in an AI Agent"),
        ("d", "2025", "provenance over LLMs"),
        ("e", "2024", "Tool call acknowledgment for M&aacute;laga"),
        ("f", "2024", "Verification of prompt injection"),
    ]
    body = "".join(
        f'<article key="{key}"><year>{year}</year><title>{title}</title></article>'
        for key, year, title in entries
    )
    xml.write_bytes(gzip.compress(f'<!DOCTYPE dblp SYSTEM "dblp.dtd"><dblp>{body}</dblp>'.encode()))
    result = scan(xml, dtd)
    assert result["counts"] == {
        "records_scanned": 6,
        "records_in_window": 5,
        "titled_records_in_window": 5,
        "unique_matching_dblp_keys": 3,
    }
    assert result["hits_by_query"] == {
        "S1_attestation": 1,
        "S2_provenance": 1,
        "S3_receipts": 1,
        "S4_benchmark_observability": 0,
        "S5_supply_chain_verification": 1,
    }
    assert result["rows"][1]["title"].endswith("Málaga")
