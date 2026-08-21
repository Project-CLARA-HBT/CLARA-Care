"""Reconcile only evidence-backed registration histories; ambiguity remains explicit."""

from __future__ import annotations

import argparse
from pathlib import Path

from .normalize import write_parquet


def reconcile(root: Path, events: list[dict]) -> tuple[list[dict], list[dict]]:
    by_number: dict[str, list[dict]] = {}
    for event in events:
        by_number.setdefault(event["registration_number"], []).append(event)
    sources, unresolved = [], []
    for number, chain in sorted(by_number.items()):
        sources.extend(
            {
                "registration_number": number,
                "raw_artifact_sha256": event["raw_artifact_sha256"],
                "source_url": event["source_url"],
            }
            for event in chain
        )
        if len({event["event_type"] for event in chain}) > 1:
            unresolved.append(
                {
                    "registration_number": number,
                    "relationship": "IDENTITY_LINK_UNCERTAIN",
                    "evidence_document_ids": [event["evidence_document_id"] for event in chain],
                    "reason": "multiple_event_types_require_document_level_linking",
                }
            )
    write_parquet(sources, root / "normalized" / "product_sources.parquet")
    write_parquet(unresolved, root / "normalized" / "unresolved_links.parquet")
    return sources, unresolved


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    args = parser.parse_args()
    print("Use status_reconstruction.py through run.py")
