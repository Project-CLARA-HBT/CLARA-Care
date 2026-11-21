"""Download pinned CC BY NanoBEIR collections and Apache-2.0 MiniLM assets."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

SETS = {
    "NanoArguAna": "8f4a982d470a32c45817738b9d29042ca55d75ad",
    "NanoFiQA2018": "4163ba032953d5044a7a6244261413f609c14342",
    "NanoSCIDOCS": "484eb90549fc3f0b9c42b3551e80ceb999515537",
}
MODEL = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def fetch(cache):
    assets = {}
    for name, rev in SETS.items():
        for table in ("corpus", "queries", "qrels"):
            assets[f"{name}/{table}.parquet"] = (
                f"datasets/zeta-alpha-ai/{name}/resolve/{rev}/{table}/train-00000-of-00001.parquet"
            )
    for name in (
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
    ):
        assets[f"model/{name}"] = f"sentence-transformers/all-MiniLM-L6-v2/resolve/{MODEL}/{name}"
    manifest = {}
    for rel, route in assets.items():
        path = cache / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        url = "https://huggingface.co/" + route
        if not path.exists():
            with urllib.request.urlopen(url + "?download=true", timeout=90) as response:
                data = response.read()
            path.write_bytes(data)
        manifest[rel] = {
            "url": url,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cache", type=Path)
    print(json.dumps(fetch(p.parse_args().cache), indent=2))
