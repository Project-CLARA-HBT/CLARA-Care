"""Stream all proceedings, retaining the modification date and display fields."""

import argparse
import gzip
import json
from pathlib import Path

from lxml import etree

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


class LocalDTD(etree.Resolver):
    def __init__(self, directory):
        self.directory = directory

    def resolve(self, url, public_id, context):
        if Path(url).name not in {"dblp.dtd", "dblp-2023-06-28.dtd"}:
            raise ValueError(f"Unexpected external reference {url}")
        return self.resolve_filename(str(self.directory / "dblp.dtd"), context)


def extract(path):
    rows = {}
    with gzip.open(path, "rb") as stream:
        records = etree.iterparse(
            stream, tag=RECORDS, load_dtd=True, resolve_entities=True, no_network=True
        )
        records.resolvers.add(LocalDTD(path.resolve().parent))
        for _, node in records:
            root = node.getparent()
            if root.tag != "dblp":
                continue
            if node.tag == "proceedings":
                key = node.attrib["key"]
                if key in rows:
                    raise ValueError(f"Duplicate proceedings key {key}")
                rows[key] = [
                    node.get("mdate"),
                    *[
                        ["".join(el.itertext()) for el in node.findall(field)]
                        for field in ("title", "year")
                    ],
                ]
            node.clear()
            while node.getprevious() is not None:
                del root[0]
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_gz", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.xml_gz), sort_keys=True))
