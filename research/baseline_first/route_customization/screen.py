"""Replay the eight consecutive Geofabrik Monaco batches with RoutingKit."""

import argparse
import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

import osmium

BASE = "https://download.geofabrik.de/europe/"


def get(cache, url):
    path = cache / url.split("/")[-1]
    if not path.exists():
        with urlopen(BASE + url, timeout=40) as response:
            content = response.read()
        path.write_bytes(content)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover_day_15(cache):
    path = cache / "reconstructed-261115.osm.pbf"
    if path.exists():
        return path
    updates = osmium.MergeInputReader()
    updates.add_file(str(get(cache, "monaco/updates/000/004/969.osc.gz")))
    state = get(cache, "monaco/updates/000/004/969.state.txt").read_text().splitlines()
    timestamp = next(
        s.split("=", 1)[1].replace(chr(92), "") for s in state if s.startswith("timestamp=")
    )
    assert "sequenceNumber=4969" in state
    with osmium.io.Reader(str(get(cache, "monaco/monaco-261114.osm.pbf"))) as reader:
        header = reader.header()
        assert header.get("osmosis_replication_sequence_number") == "4968"
        header.set("osmosis_replication_sequence_number", "4969")
        header.set("osmosis_replication_timestamp", timestamp)
        writer = osmium.io.Writer(str(path), header)
        try:
            updates.apply_to_reader(reader, writer)
        finally:
            writer.close()
    return path


def screen(cache, extractor):
    cache.mkdir(exist_ok=True, parents=True)
    snapshots, batches = [], []
    previous = None
    for day in range(12, 21):
        filename = f"monaco-2611{day}.osm.pbf"
        pbf = recover_day_15(cache) if day == 15 else get(cache, "monaco/" + filename)
        if day >= 16:
            md5 = get(cache, "monaco/" + filename + ".md5").read_text().split()[0]
            assert hashlib.md5(pbf.read_bytes()).hexdigest() == md5
        with osmium.io.Reader(str(pbf)) as reader:
            header = reader.header()
            seq = int(header.get("osmosis_replication_sequence_number"))
            timestamp = header.get("osmosis_replication_timestamp")
        prefix = cache / str(seq)
        subprocess.run([str(extractor.resolve()), str(pbf), str(prefix)], check=True)
        parts = {
            k: prefix.with_suffix("." + k).read_bytes()
            for k in ("first", "head", "to", "from", "time", "lat", "lon")
        }
        info = {
            "date": timestamp,
            "source": "replayed_diff" if day == 15 else "dated_pbf",
            "sequence": seq,
            "sha256": digest(pbf),
            "nodes": len(parts["first"]) // 4 - 1,
            "arcs": len(parts["head"]) // 4,
            "restrictions": len(parts["to"]) // 4,
            "digests": {k: hashlib.sha256(v).hexdigest() for k, v in parts.items()},
        }
        if previous is not None:
            assert seq == snapshots[-1]["sequence"] + 1
            osc = get(cache, f"monaco/updates/000/004/{seq % 1000:03d}.osc.gz")
            xml = ET.fromstring(gzip.decompress(osc.read_bytes()))
            edits = Counter(f"{group.tag}_{obj.tag}" for group in xml for obj in group)
            changed = [k for k in parts if parts[k] != previous[k]]
            batches.append(
                {
                    "sequence": seq,
                    "diff_sha256": digest(osc),
                    "edits": dict(edits),
                    "changed_vectors": changed,
                }
            )
        previous = parts
        snapshots.append(info)
    print(json.dumps({"snapshots": snapshots, "batches": batches}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    p.add_argument("extractor", type=Path)
    screen(**vars(p.parse_args()))
