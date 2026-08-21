"""Stream a Synthea FHIR archive into a minimised structural Q2 cohort.

The input may be a large nested ``.tar.gz`` distribution.  The reader scans
every FHIR patient bundle in a single pass, never extracts it to disk, and
never writes patient identifiers, names, dates, clinical codes, medication
names, observations, or free text.  A deterministic hash sample bounds the
evaluation output while the manifest records the full source scan.

This script recognises the archive supplied with this repository as FHIR STU3;
it deliberately labels that cohort ``synthea_fhir_stu3`` rather than claiming
R4 interoperability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tarfile
from collections import Counter
from pathlib import Path
from typing import BinaryIO

from evaluation.glhs_q2.run import SCENARIOS


class _HashingReader:
    """File wrapper exposing a running SHA-256 of raw archive bytes."""

    def __init__(self, raw: BinaryIO) -> None:
        self.raw = raw
        self.digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        self.digest.update(data)
        return data

    def close(self) -> None:
        self.raw.close()


def _token(identifier: str, salt: bytes) -> str:
    return hashlib.sha256(salt + b":" + identifier.encode("utf-8")).hexdigest()[:32]


def _patient_summary(payload: dict[str, object]) -> tuple[str, int] | None:
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return None
    patient_id: str | None = None
    counts: Counter[str] = Counter()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        kind = resource.get("resourceType")
        if not isinstance(kind, str):
            continue
        counts[kind] += 1
        if kind == "Patient" and isinstance(resource.get("id"), str):
            patient_id = resource["id"]
    if not patient_id:
        return None
    # A bounded structural depth comes from resource counts only; no resource
    # value, timestamp, terminology or medical fact crosses this boundary.
    episodes = counts["Encounter"] + counts["MedicationOrder"] + counts["MedicationRequest"]
    return patient_id, min(250, max(1, episodes))


def _oracle(index: int) -> tuple[str, str | None, bool]:
    scenario = SCENARIOS[(index - 1) % len(SCENARIOS)]
    expected_state = "state_current"
    expected_error: str | None = None
    authorized = True
    if scenario in {"conflict", "scribe_ambiguity", "temporal_ambiguity"}:
        expected_state, expected_error = "conflict", "comparable_authority_conflict"
    elif scenario == "insufficient_provenance":
        expected_state, expected_error = "withheld", "insufficient_provenance"
    elif scenario == "family_isolation":
        expected_state, expected_error, authorized = "withheld", "subject_profile_ambiguity", False
    elif scenario == "consent_revocation":
        expected_state, expected_error, authorized = "withheld", "consent_purpose_mismatch", False
    elif scenario == "stale_state_version":
        expected_error = "stale_state_version"
    elif scenario == "direct_write_attack":
        expected_error = "insufficient_corroboration"
    return expected_state, expected_error, authorized


def prepare(
    *,
    archive_path: Path,
    token_salt_file: Path,
    output_dir: Path,
    lawful_access_attestation: str,
    selection_modulus: int = 100,
    progress_every_bundles: int = 10_000,
    resume: bool = False,
) -> dict[str, object]:
    if not lawful_access_attestation.strip():
        raise ValueError("lawful_access_attestation_required")
    if selection_modulus < 1:
        raise ValueError("selection_modulus_must_be_positive")
    if progress_every_bundles < 1:
        raise ValueError("progress_every_bundles_must_be_positive")
    salt = token_salt_file.read_bytes()
    if len(salt) < 16:
        raise ValueError("token_salt_must_be_at_least_16_bytes")

    output_dir.mkdir(parents=True, exist_ok=True)
    # A full Synthea archive can contain >1M patients.  Persist only the
    # pseudonymous token and bounded episode count in a local temporary SQLite
    # table instead of retaining every selection in RAM.  This makes
    # ``--selection-modulus 1`` a genuine supported execution mode while still
    # never materialising source identifiers or clinical payloads.
    selection_db = output_dir / ".synthea-selection.sqlite3"
    if selection_db.exists() and not resume:
        raise FileExistsError(f"selection_temp_already_exists:{selection_db}")
    connection = sqlite3.connect(selection_db)
    # WAL lets a status probe read the last durable checkpoint while the
    # long-running archive scan is still active.  More importantly, the
    # explicit commits below mean an interrupted one-million-patient scan can
    # resume from its token-only selection state rather than losing an entire
    # uncommitted transaction.  This is a temporary, local index: it is
    # removed only after the manifest and minimised perturbation file are
    # written successfully.
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS selected (token TEXT PRIMARY KEY NOT NULL, episodes INTEGER NOT NULL)"
    )
    selected_count = int(connection.execute("SELECT COUNT(*) FROM selected").fetchone()[0])
    scanned_bundles = 0
    scanned_patients = 0
    skipped_invalid_bundles = 0
    nested_archives = 0
    resource_kinds: Counter[str] = Counter()
    # The raw outer archive is hashed during its one permitted full scan.
    with archive_path.open("rb") as raw:
        hashed = _HashingReader(raw)
        with tarfile.open(fileobj=hashed, mode="r|gz") as outer:
            for outer_member in outer:
                if not outer_member.isfile() or not outer_member.name.endswith(".tar.gz"):
                    continue
                nested_archives += 1
                nested_stream = outer.extractfile(outer_member)
                if nested_stream is None:
                    continue
                with tarfile.open(fileobj=nested_stream, mode="r|gz") as inner:
                    for member in inner:
                        if (
                            not member.isfile()
                            or "/fhir/" not in member.name
                            or not member.name.endswith(".json")
                        ):
                            continue
                        source = inner.extractfile(member)
                        if source is None:
                            skipped_invalid_bundles += 1
                            continue
                        try:
                            payload = json.load(source)
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            skipped_invalid_bundles += 1
                            continue
                        if not isinstance(payload, dict):
                            skipped_invalid_bundles += 1
                            continue
                        summary = _patient_summary(payload)
                        if summary is None:
                            skipped_invalid_bundles += 1
                            continue
                        patient_id, episodes = summary
                        scanned_bundles += 1
                        scanned_patients += 1
                        if scanned_bundles % progress_every_bundles == 0:
                            connection.commit()
                            selected_count = int(
                                connection.execute("SELECT COUNT(*) FROM selected").fetchone()[0]
                            )
                            print(
                                "synthea_scan "
                                f"bundles={scanned_bundles} selected={selected_count} "
                                f"nested_archives={nested_archives}",
                                flush=True,
                            )
                        # Keep only aggregate resource-type counts in source
                        # statistics; no bundle payload survives this scope.
                        for entry in payload.get("entry", []):
                            if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
                                kind = entry["resource"].get("resourceType")
                                if isinstance(kind, str):
                                    resource_kinds[kind] += 1
                        token = _token(patient_id, salt)
                        if (
                            int(hashlib.sha256(token.encode("ascii")).hexdigest(), 16)
                            % selection_modulus
                            == 0
                        ):
                            inserted = connection.execute(
                                "INSERT OR REPLACE INTO selected (token, episodes) VALUES (?, ?)",
                                (token, episodes),
                            ).rowcount
                            # INSERT OR REPLACE returns one changed row for a
                            # duplicate too, so this counter is only a
                            # progress estimate.  The checkpoint count above
                            # and final count are canonical.
                            selected_count += int(inserted > 0)

    connection.commit()

    selected_count = int(connection.execute("SELECT COUNT(*) FROM selected").fetchone()[0])
    if selected_count < 100:
        connection.close()
        selection_db.unlink(missing_ok=True)
        raise ValueError(f"synthea_selected_cases_below_minimum:{selected_count}")
    perturbations = output_dir / "perturbations.jsonl"
    with perturbations.open("w", encoding="utf-8") as handle:
        for index, (token, episodes) in enumerate(
            connection.execute("SELECT token, episodes FROM selected ORDER BY token"), start=1
        ):
            expected_state, expected_error, authorized = _oracle(index)
            row = {
                "case_id": f"synthea-stu3-{index:06d}",
                "subject_token": token,
                "scenario": SCENARIOS[(index - 1) % len(SCENARIOS)],
                "expected_state": expected_state,
                "expected_error": expected_error,
                "critical_fact_count": 3,
                "nonessential_authorized_fact_count": 7,
                "authorized": authorized,
                "episode_count": episodes,
            }
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    connection.close()
    # Exact, scoped cleanup of the ephemeral pseudonym-only selection index.
    selection_db.unlink(missing_ok=True)
    manifest = {
        "schema_version": "glhs-q2-external-structural-v2",
        "cohort": "synthea_fhir_stu3",
        "partition": "development",
        "lawful_access_attestation": lawful_access_attestation,
        "perturbations_file": perturbations.name,
        "perturbations_sha256": hashlib.sha256(perturbations.read_bytes()).hexdigest(),
        "source_archive_sha256": hashed.digest.hexdigest(),
        "source_archive_bytes": archive_path.stat().st_size,
        "source_scan": {
            "nested_archives": nested_archives,
            "fhir_patient_bundles": scanned_bundles,
            "fhir_patient_ids_seen": scanned_patients,
            "invalid_or_nonpatient_bundles": skipped_invalid_bundles,
            "selection_modulus": selection_modulus,
            "selected_cases": selected_count,
            "resource_type_counts": dict(sorted(resource_kinds.items())),
        },
        "fhir_release": "STU3",
        "clinical_data_in_output": False,
        "tokenization": "sha256(local_secret_salt:source_patient_id)[:32]",
        "perturbation_policy": "predeclared_structural_cycle_v1",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--token-salt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lawful-access-attestation", required=True)
    parser.add_argument("--selection-modulus", type=int, default=100)
    parser.add_argument("--progress-every-bundles", type=int, default=10_000)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse an interrupted token-only selection checkpoint.",
    )
    args = parser.parse_args()
    prepare(
        archive_path=args.archive,
        token_salt_file=args.token_salt_file,
        output_dir=args.output,
        lawful_access_attestation=args.lawful_access_attestation,
        selection_modulus=args.selection_modulus,
        progress_every_bundles=args.progress_every_bundles,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
