"""Build and import blinded packets for qualified human adjudication.

The module deliberately does not create labels.  A curator supplies already
deidentified review payloads; reviewers see opaque packet IDs only.  The
case-ID map is a separate controlled artifact and is required only when labels
are imported back for agreement/adjudication analysis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.clinical_adjudication.validate_manifest import (
    validate as validate_annotation,
)
from evaluation.evidence_program.freeze import FreezeError, sha256

SCHEMA_VERSION = "clinical-adjudication.packets.v1"
_INPUT_FIELDS = frozenset({"case_id", "review_payload", "fields"})
_LABEL_FIELDS = ("packet_id", "annotator_id", "field", "label")
_ADJUDICATION_FIELDS = ("packet_id", "adjudicator_id", "field", "final_label", "rationale")
_FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "arm", "condition", "gold", "gold_label", "model", "model_id",
    "prediction", "score", "system", "system_id",
})


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("invalid_packet_input_jsonl") from exc
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise FreezeError("packet_input_must_contain_objects")
    return rows


def _has_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in _FORBIDDEN_PAYLOAD_KEYS or _has_forbidden_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_forbidden_key(item) for item in value)
    return False


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def export_packets(
    *, input_path: Path, output_dir: Path, annotation_guide: Path,
    reviewer_ids: tuple[str, str], blinding_salt: str,
) -> dict[str, object]:
    """Export packets and a distinct case map for two independent reviewers.

    ``output_dir`` is intentionally rejected when it already exists, preventing
    accidental mutation of a frozen reviewer packet set.
    """

    if output_dir.exists():
        raise FreezeError("packet_output_already_exists")
    if len(reviewer_ids) != 2 or len(set(reviewer_ids)) != 2 or any(not item.strip() for item in reviewer_ids):
        raise FreezeError("exactly_two_distinct_reviewer_ids_required")
    if len(blinding_salt) < 16:
        raise FreezeError("blinding_salt_too_short")
    if not annotation_guide.is_file():
        raise FreezeError("annotation_guide_missing")

    packet_rows: list[dict[str, object]] = []
    map_rows: list[dict[str, str]] = []
    seen_cases: set[str] = set()
    for row in _jsonl(input_path):
        if _INPUT_FIELDS - row.keys() or not isinstance(row["review_payload"], dict) or not isinstance(row["fields"], list):
            raise FreezeError("invalid_packet_input_row")
        case_id = str(row["case_id"]).strip()
        fields = [str(field).strip() for field in row["fields"]]
        if not case_id or case_id in seen_cases or not fields or any(not field for field in fields):
            raise FreezeError("invalid_or_duplicate_packet_case")
        if _has_forbidden_key(row["review_payload"]):
            raise FreezeError("system_identity_or_outcome_in_review_payload")
        seen_cases.add(case_id)
        packet_id = "pkt_" + hashlib.sha256(f"{blinding_salt}:{case_id}".encode()).hexdigest()[:24]
        payload = {"packet_id": packet_id, "review_payload": row["review_payload"], "fields": fields}
        packet_rows.append(payload)
        map_rows.append({"packet_id": packet_id, "case_id": case_id})

    output_dir.mkdir(parents=True)
    packet_path = output_dir / "blinded_packets.jsonl"
    packet_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in packet_rows), encoding="utf-8")
    map_path = output_dir / "controlled_packet_map.csv"
    _write_csv(map_path, ("packet_id", "case_id"), map_rows)
    template_rows = [
        {"packet_id": str(packet["packet_id"]), "annotator_id": reviewer, "field": field, "label": ""}
        for reviewer in reviewer_ids for packet in packet_rows for field in packet["fields"]
    ]
    _write_csv(output_dir / "reviewer_label_template.csv", _LABEL_FIELDS, template_rows)
    _write_csv(output_dir / "adjudication_template.csv", _ADJUDICATION_FIELDS, [])
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "READY_FOR_EXTERNAL_ADJUDICATION",
        "clinical_adjudication": "NOT_RUN",
        "system_blinding": "packet IDs are opaque; payload rejects system/arm/model/prediction/gold keys",
        "packet_count": len(packet_rows),
        "reviewer_ids": list(reviewer_ids),
        "annotation_guide_sha256": sha256(annotation_guide),
        "blinded_packets_sha256": sha256(packet_path),
        "controlled_packet_map_sha256": sha256(map_path),
        "label_template_sha256": sha256(output_dir / "reviewer_label_template.csv"),
        "adjudication_template_sha256": sha256(output_dir / "adjudication_template.csv"),
    }
    _write_json(output_dir / "packet_manifest.json", manifest)
    return manifest


def import_labels(
    *, labels_path: Path, packet_dir: Path, output_path: Path,
) -> dict[str, object]:
    """Resolve opaque packet labels to controlled case IDs without changing rows."""

    try:
        manifest = json.loads((packet_dir / "packet_manifest.json").read_text(encoding="utf-8"))
        mapping_reader = csv.DictReader((packet_dir / "controlled_packet_map.csv").open(encoding="utf-8", newline=""))
        mapping = {str(row["packet_id"]): str(row["case_id"]) for row in mapping_reader}
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise FreezeError("controlled_packet_map_invalid") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("controlled_packet_map_sha256") != sha256(packet_dir / "controlled_packet_map.csv"):
        raise FreezeError("packet_map_manifest_mismatch")
    try:
        reader = csv.DictReader(labels_path.open(encoding="utf-8", newline=""))
        if reader.fieldnames is None or not set(_LABEL_FIELDS).issubset(reader.fieldnames):
            raise FreezeError("invalid_blinded_label_csv_schema")
        source_rows = list(reader)
    except OSError as exc:
        raise FreezeError("blinded_label_csv_unreadable") from exc
    reviewers = {str(item) for item in manifest.get("reviewer_ids", [])}
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in source_rows:
        packet_id, reviewer, field, label = (str(row[name]).strip() for name in _LABEL_FIELDS)
        if packet_id not in mapping or reviewer not in reviewers or not field or not label:
            raise FreezeError("invalid_blinded_label_row")
        key = (packet_id, reviewer, field)
        if key in seen:
            raise FreezeError("duplicate_blinded_label_row")
        seen.add(key)
        normalized.append({"case_id": mapping[packet_id], "annotator_id": reviewer, "field": field, "label": label})
    if output_path.exists():
        raise FreezeError("import_output_already_exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, ("case_id", "annotator_id", "field", "label"), normalized)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "HUMAN_LABELS_IMPORTED_NOT_ADJUDICATED",
        "clinical_adjudication": "NOT_RUN",
        "source_labels_sha256": sha256(labels_path),
        "normalized_labels_sha256": sha256(output_path),
        "row_count": len(normalized),
    }
    _write_json(output_path.with_suffix(".import_manifest.json"), result)
    return result


def disagreement_packets(*, labels_path: Path, packet_dir: Path, output_path: Path) -> dict[str, object]:
    """Emit only true two-reviewer disagreements for the distinct adjudicator."""

    result = import_labels(labels_path=labels_path, packet_dir=packet_dir, output_path=output_path.with_suffix(".normalized.csv"))
    rows = list(csv.DictReader(output_path.with_suffix(".normalized.csv").open(encoding="utf-8", newline="")))
    map_rows = list(csv.DictReader((packet_dir / "controlled_packet_map.csv").open(encoding="utf-8", newline="")))
    packet_for_case = {str(row["case_id"]): str(row["packet_id"]) for row in map_rows}
    grouped: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        grouped.setdefault((row["case_id"], row["field"]), {})[row["annotator_id"]] = row["label"]
    reviewers = set(json.loads((packet_dir / "packet_manifest.json").read_text(encoding="utf-8"))["reviewer_ids"])
    disagreements = [
        {"packet_id": packet_for_case[case_id], "field": field, "reviewer_labels": labels}
        for (case_id, field), labels in sorted(grouped.items())
        if set(labels) == reviewers and len(set(labels.values())) > 1
    ]
    if output_path.exists():
        raise FreezeError("adjudication_packet_output_already_exists")
    _write_json(output_path, {"schema_version": SCHEMA_VERSION, "status": "READY_FOR_EXTERNAL_ADJUDICATION", "disagreements": disagreements})
    return {**result, "disagreement_count": len(disagreements), "adjudication_packets_sha256": sha256(output_path)}


def import_adjudications(
    *, adjudications_path: Path, disagreement_path: Path, packet_dir: Path,
    annotation_manifest_path: Path, output_path: Path,
) -> dict[str, object]:
    """Resolve decisions from a distinct human adjudicator into controlled IDs."""

    validate_annotation(annotation_manifest_path)
    try:
        annotation = json.loads(annotation_manifest_path.read_text(encoding="utf-8"))
        disagreements = json.loads(disagreement_path.read_text(encoding="utf-8"))
        map_rows = list(csv.DictReader((packet_dir / "controlled_packet_map.csv").open(encoding="utf-8", newline="")))
        reader = csv.DictReader(adjudications_path.open(encoding="utf-8", newline=""))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("adjudication_input_unreadable") from exc
    if reader.fieldnames is None or not set(_ADJUDICATION_FIELDS).issubset(reader.fieldnames):
        raise FreezeError("invalid_adjudication_csv_schema")
    if disagreements.get("schema_version") != SCHEMA_VERSION or not isinstance(disagreements.get("disagreements"), list):
        raise FreezeError("adjudication_packet_invalid")
    expected = {(str(row["packet_id"]), str(row["field"])) for row in disagreements["disagreements"]}
    mapping = {str(row["packet_id"]): str(row["case_id"]) for row in map_rows}
    adjudicator = str(annotation["adjudicator_id"])
    resolved: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in reader:
        packet_id, reviewer, field, label, rationale = (str(row[name]).strip() for name in _ADJUDICATION_FIELDS)
        key = (packet_id, field)
        if reviewer != adjudicator or key not in expected or packet_id not in mapping or not label or not rationale or key in seen:
            raise FreezeError("invalid_adjudication_row")
        seen.add(key)
        resolved.append({"case_id": mapping[packet_id], "adjudicator_id": reviewer, "field": field, "final_label": label, "rationale": rationale})
    if seen != expected:
        raise FreezeError("adjudication_rows_incomplete")
    if output_path.exists():
        raise FreezeError("adjudication_import_output_already_exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, ("case_id", "adjudicator_id", "field", "final_label", "rationale"), resolved)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "HUMAN_ADJUDICATION_IMPORTED_NOT_CLINICAL_CLAIM",
        "clinical_adjudication": "HUMAN_IMPORT_REQUIRES_QUALIFICATION_AUDIT",
        "adjudication_source_sha256": sha256(adjudications_path),
        "adjudication_output_sha256": sha256(output_path),
        "decision_count": len(resolved),
    }
    _write_json(output_path.with_suffix(".import_manifest.json"), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--input", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--annotation-guide", type=Path, required=True)
    export.add_argument("--reviewer", action="append", required=True)
    export.add_argument("--blinding-salt", required=True)
    imported = commands.add_parser("import-labels")
    imported.add_argument("--labels", type=Path, required=True)
    imported.add_argument("--packet-dir", type=Path, required=True)
    imported.add_argument("--output", type=Path, required=True)
    disagreements = commands.add_parser("disagreements")
    disagreements.add_argument("--labels", type=Path, required=True)
    disagreements.add_argument("--packet-dir", type=Path, required=True)
    disagreements.add_argument("--output", type=Path, required=True)
    adjudications = commands.add_parser("import-adjudications")
    adjudications.add_argument("--adjudications", type=Path, required=True)
    adjudications.add_argument("--disagreements", type=Path, required=True)
    adjudications.add_argument("--packet-dir", type=Path, required=True)
    adjudications.add_argument("--annotation-manifest", type=Path, required=True)
    adjudications.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            result = export_packets(input_path=args.input, output_dir=args.output, annotation_guide=args.annotation_guide, reviewer_ids=tuple(args.reviewer), blinding_salt=args.blinding_salt)
        elif args.command == "import-labels":
            result = import_labels(labels_path=args.labels, packet_dir=args.packet_dir, output_path=args.output)
        elif args.command == "disagreements":
            result = disagreement_packets(labels_path=args.labels, packet_dir=args.packet_dir, output_path=args.output)
        else:
            result = import_adjudications(adjudications_path=args.adjudications, disagreement_path=args.disagreements, packet_dir=args.packet_dir, annotation_manifest_path=args.annotation_manifest, output_path=args.output)
    except FreezeError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
