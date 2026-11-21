"""Execute the registered S1–S5 title search over a complete DBLP XML snapshot.

Supply the gzip distribution and its DTD. Only public bibliographic metadata
of matching records is retained. Stream all top-level records before emitting
a result. Search hits are identification records awaiting independent review.
"""

import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

PROTOCOL = (
    Path(__file__).resolve().parents[3] / "research/venue2027/acns/design/sok_review_protocol.md"
)
GROUPS = re.compile(r"(S[1-5]_\w+):\s*\(([^()]+)\)\s*AND\s*\(([^()]+)\)")
RECORDS = (
    "article",
    "inproceedings",
    "proceedings",
    "book",
    "incollection",
    "phdthesis",
    "mastersthesis",
    "www",
    "person",
    "data",
)


def terms(expression):
    # Whitespace can split the OR keyword across lines in Markdown.
    alternatives = re.split(r"\s+OR\s+", expression.strip())
    if any(re.fullmatch(r'"[^"]+"', term) is None for term in alternatives):
        raise ValueError("unexpected_registered_term")
    return [term[1:-1].casefold() for term in alternatives]


def queries():
    block = PROTOCOL.read_text().split("### 4.2", 1)[1].split("### 4.3", 1)[0]
    result = {key: (terms(left), terms(right)) for key, left, right in GROUPS.findall(block)}
    if [key[:2] for key in result] != [f"S{i}" for i in range(1, 6)]:
        raise ValueError("incomplete_registered_queries")
    return result


def scan(xml, dtd):
    registered = queries()
    all_terms = {term for halves in registered.values() for half in halves for term in half}
    # Each term gets a separate match so that overlapping phrases remain
    # observable (e.g. both "remote attestation" and "attestation").
    term_patterns = {
        term: re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)") for term in all_terms
    }
    fast = re.compile("|".join(map(re.escape, sorted(all_terms))))
    rows = []
    counts = Counter()
    with gzip.open(xml, "rb") as stream:
        events = etree.iterparse(
            stream,
            events=("end",),
            tag=RECORDS,
            no_network=True,
            load_dtd=True,
            resolve_entities=True,
        )

        class LocalDTD(etree.Resolver):
            def resolve(self, url, public_id, context):
                if Path(url).name not in {"dblp.dtd", "dblp-2023-06-28.dtd"}:
                    raise ValueError("unexpected_dtd")
                return self.resolve_filename(str(dtd.resolve()), context)

        events.resolvers.add(LocalDTD())
        for _, record in events:
            if record.getparent().tag != "dblp":
                continue
            counts["records_scanned"] += 1
            year = record.findtext("year", "")
            if year.isdigit() and 2019 <= int(year) <= 2026:
                counts["records_in_window"] += 1
                title_node = record.find("title")
                if title_node is not None:
                    counts["titled_records_in_window"] += 1
                    title = " ".join("".join(title_node.itertext()).split())
                    normalized = title.casefold()
                    if fast.search(normalized):
                        found = {
                            t for t, pattern in term_patterns.items() if pattern.search(normalized)
                        }
                        matched = [
                            key
                            for key, (left, right) in registered.items()
                            if found.intersection(left) and found.intersection(right)
                        ]
                        if matched:
                            rows.append(
                                dict(
                                    key=record.get("key"),
                                    year=int(year),
                                    title=title,
                                    first_author=record.findtext("author"),
                                    venue=record.findtext("booktitle")
                                    or record.findtext("journal"),
                                    electronic_editions=record.xpath("ee/text()"),
                                    query_ids=matched,
                                )
                            )
            parent = record.getparent()
            record.clear()
            while record.getprevious() is not None:
                del parent[0]
    rows.sort(key=lambda row: row["key"])
    if len({r["key"] for r in rows}) != len(rows):
        raise ValueError("duplicate_dblp_key")
    counts["unique_matching_dblp_keys"] = len(rows)
    hits = Counter(k for r in rows for k in r["query_ids"])
    return {"counts": dict(counts), "hits_by_query": {k: hits[k] for k in registered}, "rows": rows}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if __name__ == "__main__":
    xml, dtd = map(Path, sys.argv[1:3])
    result = scan(xml, dtd)
    print(
        json.dumps(
            {
                "scope": "DBLP title-field identification; pre-cutoff interim run",
                "distribution": xml.name,
                "xml_gz_sha256": digest(xml),
                "dtd_sha256": digest(dtd),
                "selection_protocol_sha256": digest(PROTOCOL),
                **result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
