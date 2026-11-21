"""Fetch a pinned release prefix and decode only WILDS OOD validation frames."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

REV = "78b5e7d858adb01cb5661c7b5f8666a4e91be2cb"
URL = f"https://huggingface.co/datasets/pangwei/wilds-iwildcam/resolve/{REV}/iwildcam_v2.0.tar.gz"
META = "1886a57eddee108aeaabc9d4b79562374baee1b79d37dd782aa1a26a6d4706b6"
CHUNK = 8 * 1024**2
N = 64
SIZE = 11957415473


def fetch(i):
    lo, hi = i * CHUNK, (i + 1) * CHUNK - 1
    r = requests.get(f"{URL}?chunk={i}", headers={"Range": f"bytes={lo}-{hi}"}, timeout=120)
    r.raise_for_status()
    if r.headers.get("Content-Range") != f"bytes {lo}-{hi}/{SIZE}" or len(r.content) != CHUNK:
        raise ValueError("Unexpected range")
    return r.content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.metadata.read_bytes()).hexdigest() != META:
        raise ValueError("Metadata digest mismatch")
    with args.metadata.open() as f:
        rows = {r["filename"]: r for r in csv.DictReader(f) if r["split"] == "val"}
    args.out.mkdir(parents=True, exist_ok=True)
    prefix = args.out / "prefix.gz"
    with ThreadPoolExecutor(max_workers=4) as pool, prefix.open("wb") as f:
        for block in pool.map(fetch, range(N)):
            f.write(block)
    records = []
    with gzip.open(prefix) as gz, tarfile.open(fileobj=gz, mode="r|") as archive:
        try:
            for member in archive:
                name = Path(member.name).name
                if member.name != f"./train/{name}" or name not in rows:
                    continue
                data = archive.extractfile(member).read()
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    dims = image.size
                (args.out / name).write_bytes(data)
                row = rows[name]
                records.append(
                    dict(
                        file=name,
                        camera=row["location_remapped"],
                        burst=row["sequence_remapped"],
                        y=int(row["y"]),
                        dims=dims,
                        sha256=hashlib.sha256(data).hexdigest(),
                    )
                )
        except (EOFError, tarfile.ReadError) as err:
            if prefix.stat().st_size != N * CHUNK or "end" not in str(err).lower():
                raise
    with prefix.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    (args.out / "manifest.json").write_text(json.dumps(dict(prefix_sha256=digest, frames=records)))


if __name__ == "__main__":
    main()
