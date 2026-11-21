"""Rebuild the proceedings catalogue from XML with Expat event callbacks."""

import argparse
import gzip
import json
from pathlib import Path
from xml.parsers import expat


def rebuild(path):
    parser = expat.ParserCreate()
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_ALWAYS)
    depth = 0
    catalogue = {}
    key = None
    field = None
    chunks = []

    def external(context, base, system_id, public_id):
        if system_id not in {"dblp.dtd", "dblp-2023-06-28.dtd"}:
            raise ValueError(f"Unexpected external reference {system_id}")
        with path.with_name("dblp.dtd").open("rb") as f:
            parser.ExternalEntityParserCreate(context).ParseFile(f)
        return 1

    def start(tag, attrs):
        nonlocal depth, key, field
        depth += 1
        if depth == 2 and tag == "proceedings":
            key = attrs["key"]
            if key in catalogue:
                raise ValueError(f"Duplicate proceedings key {key}")
            catalogue[key] = {"year": [], "title": []}
        if key is not None and depth == 3 and tag in ("year", "title"):
            field = tag
            chunks.clear()
            parser.CharacterDataHandler = chunks.append

    def end(tag):
        nonlocal depth, key, field
        if depth == 3 and field is not None:
            catalogue[key][field].append("".join(chunks))
            parser.CharacterDataHandler = None
            field = None
        if depth == 2:
            key = None
        depth -= 1

    parser.ExternalEntityRefHandler = external
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    with gzip.open(path, "rb") as stream:
        parser.ParseFile(stream)
    return catalogue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_gz", type=Path)
    args = parser.parse_args()
    print(json.dumps(rebuild(args.xml_gz), sort_keys=True))
