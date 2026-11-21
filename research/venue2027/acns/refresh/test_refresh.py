"""Exercise adverse cases absent from the two observed projections."""

import gzip

from compare import assess, delta, replay
from extract import extract
from oracle import rebuild


def test_filtered_refresh_can_miss_edits():
    old = {
        "kept": ["2025-01-01", ["Old"], ["2020"]],
        "deleted": ["2026-11-01", ["Dropped"], []],
    }
    new = {
        "kept": ["2025-01-01", ["New"], ["2020"]],
        "added": ["2020-01-01", ["Added"], []],
    }
    oracle = {
        "added": {"title": ["Added"], "year": []},
        "kept": {"title": ["New"], "year": ["2020"]},
    }
    report = assess(old, new, oracle)
    assert report["arms"]["date_equality"]["wrong_value"] == 1
    assert report["arms"]["watermark"]["wrong_value"] == 1
    assert report["arms"]["exact_diff"]["row_writes"] == 3
    assert report["arms"]["frozen"]["extra"] == 1
    assert replay(old, delta(old, new)) == new


def test_xml_fields_and_independent_oracle(tmp_path):
    (tmp_path / "dblp.dtd").write_text('<!ENTITY accent "&#233;">')
    xml = tmp_path / "dump.gz"
    xml.write_bytes(
        gzip.compress(
            b'<!DOCTYPE dblp SYSTEM "dblp.dtd"><dblp>'
            b'<article key="a"><title>Ignored</title></article><proceedings key="p">'
            b"<title>A <i>B</i> &accent;</title><year>2001</year><year>2002</year>"
            b"</proceedings></dblp>"
        )
    )
    assert extract(xml) == {"p": [None, ["A B é"], ["2001", "2002"]]}
    assert rebuild(xml) == {"p": {"title": ["A B é"], "year": ["2001", "2002"]}}
