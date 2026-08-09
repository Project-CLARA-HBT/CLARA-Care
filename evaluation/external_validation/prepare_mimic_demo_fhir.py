"""Prepare a privacy-minimised, subject-disjoint MIMIC-IV Demo-on-FHIR cohort.

Targets are derived only from observable FHIR timestamps/statuses. They are not
clinical judgments and must not be described as independently adjudicated truth.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

RESOURCE_FILES = {
    "medication": "MimicMedicationRequest.ndjson.gz",
    "diagnosis_problem": "MimicCondition.ndjson.gz",
    "lab_state": "MimicObservationLabevents.ndjson.gz",
}


def _sha(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token_list_sha(tokens: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(tokens)).encode()).hexdigest()


def _resources(path: Path) -> Iterable[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            if isinstance(value, dict):
                yield value


def _subject(resource: dict[str, object]) -> str | None:
    subject = resource.get("subject")
    if not isinstance(subject, dict):
        return None
    reference = str(subject.get("reference", ""))
    return reference.split("/", 1)[1] if reference.startswith("Patient/") else None


def _coding_key(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    coding = value.get("coding")
    if not isinstance(coding, list) or not coding or not isinstance(coding[0], dict):
        return None
    first = coding[0]
    code = str(first.get("code", "")).strip()
    system = str(first.get("system", "")).strip()
    return f"{system}|{code}" if code else None


def _medication_event(resource: dict[str, object]) -> tuple[str, str, str, str, str] | None:
    subject = _subject(resource)
    medication = resource.get("medicationReference")
    if not subject or not isinstance(medication, dict):
        return None
    slot = str(medication.get("reference", "")).strip()
    authored = str(resource.get("authoredOn", "")).strip()
    valid_time = authored
    dispense = resource.get("dispenseRequest")
    if not authored and isinstance(dispense, dict):
        period = dispense.get("validityPeriod")
        if isinstance(period, dict):
            valid_time = str(period.get("start", "")).strip()
    if not slot or not valid_time:
        return None
    value = {
        "status": resource.get("status"),
        "intent": resource.get("intent"),
        "dosageInstruction": resource.get("dosageInstruction"),
    }
    return subject, slot, valid_time, authored or valid_time, _sha(value)


def _condition_event(
    resource: dict[str, object], encounter_times: dict[str, str]
) -> tuple[str, str, str, str, str] | None:
    subject = _subject(resource)
    slot = _coding_key(resource.get("code"))
    encounter = resource.get("encounter")
    reference = str(encounter.get("reference", "")) if isinstance(encounter, dict) else ""
    timestamp = encounter_times.get(reference, "")
    if not subject or not slot or not timestamp:
        return None
    value = {
        "clinicalStatus": resource.get("clinicalStatus"),
        "verificationStatus": resource.get("verificationStatus"),
        "category": resource.get("category"),
    }
    return subject, slot, timestamp, timestamp, _sha(value)


def _lab_event(resource: dict[str, object]) -> tuple[str, str, str, str, str] | None:
    subject = _subject(resource)
    slot = _coding_key(resource.get("code"))
    timestamp = str(resource.get("effectiveDateTime") or resource.get("issued") or "").strip()
    knowledge_time = str(resource.get("issued") or timestamp).strip()
    if not subject or not slot or not timestamp:
        return None
    value = {
        "status": resource.get("status"),
        "valueQuantity": resource.get("valueQuantity"),
        "valueCodeableConcept": resource.get("valueCodeableConcept"),
    }
    return subject, slot, timestamp, knowledge_time, _sha(value)


def _encounter_times(fhir_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("MimicEncounter.ndjson.gz", "MimicEncounterED.ndjson.gz", "MimicEncounterICU.ndjson.gz"):
        path = fhir_root / name
        for resource in _resources(path):
            period = resource.get("period")
            start = str(period.get("start", "")) if isinstance(period, dict) else ""
            identifier = str(resource.get("id", ""))
            if start and identifier:
                result[f"Encounter/{identifier}"] = start
    return result


def prepare(
    fhir_root: Path,
    output_dir: Path,
    salt_file: Path,
    *,
    lawful_access_attestation: str,
    freeze_id: str,
) -> dict[str, object]:
    salt = salt_file.read_bytes()
    if len(salt) < 16:
        raise ValueError("token_salt_must_be_at_least_16_bytes")
    if not lawful_access_attestation.strip() or not freeze_id.strip():
        raise ValueError("attestation_and_freeze_id_required")
    patient_path = fhir_root / "MimicPatient.ndjson.gz"
    patients = sorted(str(row.get("id", "")) for row in _resources(patient_path) if row.get("id"))
    if not patients:
        raise ValueError("no_fhir_patients")
    development_raw = {subject for subject in patients if int(_sha(subject), 16) % 5 == 0}
    evaluation_raw = set(patients).difference(development_raw)
    if development_raw.intersection(evaluation_raw):
        raise AssertionError("split_not_disjoint")

    encounter_times = _encounter_times(fhir_root)
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    source_rows: dict[str, int] = {}
    for domain, name in RESOURCE_FILES.items():
        path = fhir_root / name
        count = 0
        for resource in _resources(path):
            count += 1
            parsed = (
                _medication_event(resource)
                if domain == "medication"
                else _condition_event(resource, encounter_times)
                if domain == "diagnosis_problem"
                else _lab_event(resource)
            )
            if parsed is None:
                continue
            subject, raw_slot, timestamp, knowledge_time, value_fingerprint = parsed
            if subject not in evaluation_raw:
                continue
            event_id = _sha({"domain": domain, "resource_id": resource.get("id")})[:24]
            grouped[(subject, domain, _sha(raw_slot)[:24])].append({
                "event_id": event_id,
                "valid_time": timestamp,
                "knowledge_time": knowledge_time,
                "value_fingerprint": value_fingerprint,
            })
        source_rows[name] = count

    output_dir.mkdir(parents=True, exist_ok=True)
    token = lambda subject: hashlib.sha256(salt + b":" + subject.encode()).hexdigest()[:32]
    tasks: list[dict[str, object]] = []
    represented_subjects: set[str] = set()
    domain_counts: dict[str, int] = defaultdict(int)
    for (subject, domain, slot), events in sorted(grouped.items()):
        events.sort(key=lambda item: (item["valid_time"], item["event_id"]))
        if len(events) < 2:
            continue
        subject_token = token(subject)
        represented_subjects.add(subject_token)
        domain_counts[domain] += 1
        tasks.append({
            "task_id": _sha({"subject": subject_token, "domain": domain, "slot": slot})[:24],
            "subject_token": subject_token,
            "domain": domain,
            "slot_fingerprint": slot,
            "index_time": events[-1]["valid_time"],
            "structured_events": events,
            "source_target_event_id": events[-1]["event_id"],
            "ground_truth_kind": "source_timestamp_derived_not_clinician_adjudicated",
        })
    if set(domain_counts) != set(RESOURCE_FILES):
        raise ValueError("three_domain_coverage_required")

    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks), encoding="utf-8"
    )
    development_tokens = sorted(token(subject) for subject in development_raw)
    evaluation_tokens = sorted(represented_subjects)
    (output_dir / "development_subjects.txt").write_text(
        "\n".join(development_tokens) + "\n", encoding="utf-8"
    )
    (output_dir / "evaluation_subjects.txt").write_text(
        "\n".join(evaluation_tokens) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "mimic-demo-fhir-source-derived-v1",
        "status": "frozen",
        "partition": "sealed_holdout",
        "freeze_id": freeze_id,
        "dataset": "mimic_iv_demo_on_fhir",
        "dataset_version": "2.1.0",
        "lawful_access_attestation": lawful_access_attestation,
        "curator_attestation": "developer-prepared; not independent",
        "independent_curator": False,
        "selection_method": "sha256(patient_fhir_id) mod 5; residue 0 development, others evaluation",
        "inclusion_exclusion": "FHIR subjects with >=1 longitudinal slot having >=2 timestamped events; deterministic 20/80 hash split before evaluation",
        "selection_frozen_at": freeze_id,
        "subject_count": len(evaluation_tokens),
        "development_subject_count": len(development_tokens),
        "task_count": len(tasks),
        "event_count": sum(len(task["structured_events"]) for task in tasks),
        "domain_coverage": dict(sorted(domain_counts.items())),
        "missingness": {},
        "synthetic_governance_separate": True,
        "clinical_oracle": False,
        "headline_eligible": False,
        "independent_annotation_status": "NOT RUN",
        "ground_truth_kind": "source_timestamp_derived_not_clinician_adjudicated",
        "development_subject_tokens_sha256": _token_list_sha(development_tokens),
        "test_subject_tokens_sha256": _token_list_sha(evaluation_tokens),
        "records_sha256": _file_sha(records_path),
        "source_checksum": {
            name: _file_sha(fhir_root / name)
            for name in sorted(set(RESOURCE_FILES.values()) | {
                "MimicPatient.ndjson.gz", "MimicEncounter.ndjson.gz",
                "MimicEncounterED.ndjson.gz", "MimicEncounterICU.ndjson.gz",
            })
        },
        "source_rows": source_rows,
    }
    manifest_path = output_dir / "cohort_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fhir-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-salt-file", type=Path, required=True)
    parser.add_argument("--lawful-access-attestation", required=True)
    parser.add_argument("--freeze-id", required=True)
    args = parser.parse_args()
    prepare(
        args.fhir_root,
        args.output,
        args.token_salt_file,
        lawful_access_attestation=args.lawful_access_attestation,
        freeze_id=args.freeze_id,
    )
