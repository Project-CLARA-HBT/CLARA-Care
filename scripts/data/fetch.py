"""Fetch an explicitly registered open archive into the gitignored raw tree."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    get_dataset,
    load_registry,
    repository_root,
)


def fetch_dataset(
    dataset_id: str,
    *,
    accept_license: bool,
    registry_path: Path | None = None,
) -> dict[str, object]:
    dataset = get_dataset(load_registry(registry_path), dataset_id)
    if dataset["access_class"] == "credentialed":
        raise DatasetRegistryError("ACCESS_REQUIRED")
    if dataset["access_class"] == "not_available":
        raise DatasetRegistryError("NOT_AVAILABLE")
    if not accept_license:
        raise DatasetRegistryError("LICENSE_REVIEW_REQUIRED")
    if dataset["download_method"] != "https_archive":
        raise DatasetRegistryError("MANUAL_DOWNLOAD_REQUIRED")
    url = str(dataset.get("download_url") or "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise DatasetRegistryError("DOWNLOAD_URL_INVALID")
    filename = Path(urllib.parse.unquote(parsed.path)).name
    if not filename:
        raise DatasetRegistryError("DOWNLOAD_FILENAME_INVALID")
    raw_dir = (repository_root() / dataset["raw_path"]).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / filename
    temporary = raw_dir / f".{filename}.part"
    if destination.exists() or temporary.exists():
        raise DatasetRegistryError("DOWNLOAD_TARGET_EXISTS")
    request = urllib.request.Request(url, headers={"User-Agent": "CLARA-evidence-program/1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("xb") as out:
            final = urllib.parse.urlparse(response.geturl())
            if final.scheme != "https":
                raise DatasetRegistryError("DOWNLOAD_REDIRECT_NOT_HTTPS")
            while chunk := response.read(8 * 1024 * 1024):
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        temporary.replace(destination)
    except (OSError, urllib.error.URLError):
        temporary.unlink(missing_ok=True)
        raise
    return {
        "schema_version": "clara-dataset-fetch.v1",
        "dataset_id": dataset_id,
        "status": "DOWNLOADED_UNVERIFIED",
        "source_url": url,
        "destination": str(destination),
        "bytes": destination.stat().st_size,
        "next_action": f"python scripts/data/verify.py --dataset {dataset_id}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--accept-license", action="store_true")
    args = parser.parse_args()
    try:
        report = fetch_dataset(
            args.dataset,
            accept_license=args.accept_license,
            registry_path=args.registry,
        )
    except DatasetRegistryError as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
