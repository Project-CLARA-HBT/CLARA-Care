"""Download pinned BEIR-maintainer corpus, queries and external test qrels."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

SOURCES = {
    "SciFact": (
        "scifact",
        "b3b5335604bf5ee3c4447671af975ea25143d4f5",
        "2938d17dc3b09882fdb8c12bbbe2e2dc0e75a029",
    ),
    "NFCorpus": (
        "nfcorpus",
        "b5026a0e96e8a7ac4f95f482a596389289d46269",
        "a451b3b26d3ae1358f259c1a3a4dd61fcea35a65",
    ),
}


def fetch(root):
    receipts = {}
    for name, (repo, rev, qrev) in SOURCES.items():
        paths = {
            f"{part}.parquet": f"{repo}/resolve/{rev}/{part}/{part}-00000-of-00001.parquet"
            for part in ("queries", "corpus")
        }
        paths["test.tsv"] = f"{repo}-qrels/resolve/{qrev}/test.tsv"
        for dest, remote in paths.items():
            url = f"https://huggingface.co/datasets/BeIR/{remote}"
            file = root / name / dest
            file.parent.mkdir(parents=True, exist_ok=True)
            if not file.is_file():
                with urlopen(url + "?download=true", timeout=90) as response:
                    data = response.read()
                file.write_bytes(data)
            data = file.read_bytes()
            receipts[f"{name}/{dest}"] = dict(
                url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
            )
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(json.dumps(fetch(parser.parse_args().root), indent=2))
