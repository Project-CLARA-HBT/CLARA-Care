"""One command for a dated, resumable DAV-only acquisition snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .crawl_publications import crawl as crawl_publications
from .crawl_registration import crawl as crawl_registration
from .discovery import discover
from .download_attachments import download
from .normalize import normalize
from .parse_attachments import parse
from .reconcile import reconcile
from .status_reconstruction import reconstruct
from .validate import validate


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path("data/restricted/dav")); parser.add_argument("--date", default=datetime.now(UTC).date().isoformat()); args = parser.parse_args()
    started = datetime.now(UTC); discover(args.root, args.date); crawl_publications(args.root, args.date); crawl_registration(args.root, args.date); download(args.root, args.date); parse(args.root, args.date)
    products, events = normalize(args.root, args.date); sources, unresolved = reconcile(args.root, events); statuses = reconstruct(args.root, args.date, events, unresolved); validation = validate(args.root, args.date)
    manifests = args.root / "manifests"; inventory = manifests / "source_inventory.jsonl"; digest = hashlib.sha256(inventory.read_bytes()).hexdigest()
    (manifests / "files.sha256").write_text("".join(f"{row['sha256']}  {row['raw_path']}\n" for row in [json.loads(line) for line in inventory.read_text(encoding='utf-8').splitlines()]), encoding="utf-8")
    manifest = {"schema_version":"dav.acquisition.v1", "scope":"DAV public medication-product records only", "crawl_started_at_utc":started.isoformat(), "crawl_ended_at_utc":datetime.now(UTC).isoformat(), "retrieval_date":args.date, "inventory_sha256":digest, "counts":{"products":len(products),"events":len(events),"sources":len(sources),"unresolved_links":len(unresolved),"statuses":len(statuses)}, "validation":validation}
    (manifests / "acquisition_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
