"""Validate DAV raw-byte provenance and conservative reconstruction invariants."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .core import Store


def validate(root: Path, retrieval_date: str) -> dict:
    store = Store(root, retrieval_date); rows = [json.loads(line) for line in (store.manifests / "source_inventory.jsonl").read_text(encoding="utf-8").splitlines()]
    url_bytes: dict[str, str] = {}; errors = []
    for row in rows:
        path = Path(row["raw_path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]: errors.append(f"artifact_hash_mismatch:{row['url']}")
        prior = url_bytes.setdefault(row["url"], row["sha256"])
        if prior != row["sha256"]: errors.append(f"url_maps_to_multiple_bytes:{row['url']}")
    parse_manifest = store.manifests / "attachment_parse.jsonl"
    if parse_manifest.exists():
        attachments = {
            (row["sha256"], row["url"])
            for row in rows
            if "attachments" in Path(row["raw_path"]).parts
        }
        for parsed in (json.loads(line) for line in parse_manifest.read_text(encoding="utf-8").splitlines()):
            identity = (parsed.get("raw_artifact_sha256"), parsed.get("source_url"))
            status = parsed.get("parse_status")
            if identity not in attachments:
                errors.append("parse_record_not_in_attachment_inventory")
            if status == "PARSED" and (not isinstance(parsed.get("text"), str) or not parsed["text"].strip()):
                errors.append("parsed_record_missing_text")
            if status == "PARSED_EMPTY" and (not isinstance(parsed.get("text"), str) or parsed["text"].strip()):
                errors.append("parsed_empty_record_has_text")
            if status == "UNPARSED" and parsed.get("text") is not None:
                errors.append("non_parsed_record_has_text")
            if status not in {"PARSED", "PARSED_EMPTY", "UNPARSED"}:
                errors.append("unknown_parse_status")
    result = {"valid": not errors, "artifacts": len(rows), "errors": errors}
    if errors: raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result
