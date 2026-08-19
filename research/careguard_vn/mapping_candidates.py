"""Deterministic normalization and mapping-candidate generation (G-003/G-006).

Design-only module for the CareGuard-VN pipeline. It consumes a specified CSV
schema (the DAV-normalized mapping-input shape) and produces deterministic
mapping candidates to a frozen RxNorm terminology table, then joins resolved
identities to a frozen DDInter positive table when supplied.

It never executes a benchmark, never applies blinded review/adjudication, and
never needs DAV data: with an empty or synthetic input it still runs and
emits no candidates. Review, dispositions (accepted/ambiguous/unresolved/
source_conflict), and Mode A/Mode B runs are out of scope for this module.

CSV schema (mapping-input v1), one product identity row:
    source_record_id, source_record_hash, product_name, registration_number,
    active_ingredient_text, strength, dosage_form, manufacturer, registrant,
    release_label

RxNorm terminology table (CSV), from the frozen release:
    rxcui, name, synonym, tty
DDInter positive table (CSV), from the frozen archive:
    interaction_id, drug_name_a, drug_name_b, interaction_type, risk_level,
    rxcui_a, rxcui_b
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

INPUT_COLUMNS = (
    "source_record_id",
    "source_record_hash",
    "product_name",
    "registration_number",
    "active_ingredient_text",
    "strength",
    "dosage_form",
    "manufacturer",
    "registrant",
    "release_label",
)
REQUIRED_INPUT_COLUMNS = ("source_record_id", "source_record_hash", "product_name", "release_label")

_NON_TOKEN = re.compile(r"[^\w]+", re.UNICODE)
_TRAILING_STRENGTH = re.compile(r"^(.*?)\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z%/µmg]+)$")


@dataclass(frozen=True)
class NormalizedRecord:
    source_record_id: str
    source_record_hash: str
    product_name: str
    product_name_norm: str
    product_name_folded: str
    product_tokens: frozenset[str]
    active_ingredient_text: str
    active_ingredient_norm: str
    strength: str
    strength_parsed: tuple[str, str] | None
    dosage_form: str
    dosage_form_norm: str
    registration_number: str
    manufacturer: str
    registrant: str
    release_label: str
    status: str = "NORMALIZED"


@dataclass(frozen=True)
class Candidate:
    rxcui: str
    name: str
    tty: str
    method: str
    score: float


@dataclass
class RecordOutcome:
    source_record_id: str
    normalized: dict[str, Any]
    candidates: list[Candidate] = field(default_factory=list)
    status: str = "CANDIDATES"
    reason: str | None = None
    ddinter_links: list[dict[str, Any]] = field(default_factory=list)


def _fold_diacritics(value: str) -> str:
    """NFKC + casefold + strip combining diacritics (Vietnamese-safe, lossy)."""
    decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value).casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def normalize_text(value: str) -> str:
    """Deterministic normalization: NFKC, casefold, collapse runs of non-word chars."""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()
    return normalized


def tokenize(value: str) -> frozenset[str]:
    return frozenset(_NON_TOKEN.split(value.casefold()))


def parse_strength(value: str) -> tuple[str, str] | None:
    """Return (amount, unit) from a strength string like '500mg' or '500 mg'."""
    match = _TRAILING_STRENGTH.match(value.strip().lower().replace(" ", ""))
    if not match:
        return None
    amount = match.group(2).replace(",", ".")
    try:
        float(amount)
    except ValueError:
        return None
    return (amount, match.group(3))


def normalize_record(row: dict[str, Any]) -> NormalizedRecord:
    missing = [column for column in REQUIRED_INPUT_COLUMNS if not row.get(column)]
    if missing:
        raise ValueError("careguard_mapping_input_missing:" + ",".join(missing))
    product_name = str(row["product_name"])
    active_ingredient = str(row.get("active_ingredient_text") or "")
    strength = str(row.get("strength") or "")
    dosage_form = str(row.get("dosage_form") or "")
    return NormalizedRecord(
        source_record_id=str(row["source_record_id"]),
        source_record_hash=str(row["source_record_hash"]),
        product_name=product_name,
        product_name_norm=normalize_text(product_name),
        product_name_folded=_fold_diacritics(product_name),
        product_tokens=tokenize(product_name),
        active_ingredient_text=active_ingredient,
        active_ingredient_norm=normalize_text(active_ingredient),
        strength=strength,
        strength_parsed=parse_strength(strength) if strength else None,
        dosage_form=dosage_form,
        dosage_form_norm=normalize_text(dosage_form),
        registration_number=str(row.get("registration_number") or ""),
        manufacturer=str(row.get("manufacturer") or ""),
        registrant=str(row.get("registrant") or ""),
        release_label=str(row["release_label"]),
    )


class TerminologyIndex:
    """In-memory index over a frozen RxNorm release (name/synonym -> rxcuis)."""

    def __init__(self, rows: Iterable[dict[str, Any]]) -> None:
        self._by_norm: dict[str, list[dict[str, str]]] = {}
        self._by_folded: dict[str, list[dict[str, str]]] = {}
        self._names: list[tuple[str, str, str]] = []
        for row in rows:
            rxcui = str(row.get("rxcui") or "")
            name = str(row.get("name") or "")
            synonym = str(row.get("synonym") or "")
            tty = str(row.get("tty") or "")
            if not rxcui or not name:
                continue
            entry = {"rxcui": rxcui, "name": name, "synonym": synonym, "tty": tty}
            self._by_norm.setdefault(normalize_text(name), []).append(entry)
            if synonym:
                self._by_norm.setdefault(normalize_text(synonym), []).append(entry)
            self._by_folded.setdefault(_fold_diacritics(name), []).append(entry)
            if synonym:
                self._by_folded.setdefault(_fold_diacritics(synonym), []).append(entry)
            self._names.append((normalize_text(name), rxcui, tty))

    def lookup_norm(self, key: str) -> list[dict[str, str]]:
        return list(self._by_norm.get(key, []))

    def lookup_folded(self, key: str) -> list[dict[str, str]]:
        return list(self._by_folded.get(key, []))

    def fuzzy(self, tokens: frozenset[str], threshold: float, cap: int) -> list[dict[str, str]]:
        hits: list[tuple[float, dict[str, str]]] = []
        for norm_name, rxcui, tty in self._names:
            name_tokens = frozenset(norm_name.split())
            if not name_tokens:
                continue
            overlap = len(tokens & name_tokens)
            score = overlap / max(len(tokens | name_tokens), 1)
            if score >= threshold:
                hits.append((score, {"rxcui": rxcui, "name": norm_name, "tty": tty}))
        hits.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _score, entry in hits[:cap]]


def generate_candidates(
    record: NormalizedRecord,
    index: TerminologyIndex | None,
    *,
    fuzzy_threshold: float = 0.8,
    cap: int = 10,
) -> RecordOutcome:
    outcome = RecordOutcome(
        source_record_id=record.source_record_id,
        normalized={
            "product_name": record.product_name,
            "product_name_norm": record.product_name_norm,
            "product_name_folded": record.product_name_folded,
            "active_ingredient_text": record.active_ingredient_text,
            "active_ingredient_norm": record.active_ingredient_norm,
            "strength": record.strength,
            "strength_parsed": list(record.strength_parsed) if record.strength_parsed else None,
            "dosage_form": record.dosage_form,
            "dosage_form_norm": record.dosage_form_norm,
            "registration_number": record.registration_number,
            "manufacturer": record.manufacturer,
            "registrant": record.registrant,
            "release_label": record.release_label,
        },
    )
    if index is None:
        outcome.status = "NO_TERMINOLOGY"
        outcome.reason = "frozen RxNorm terminology table not supplied; candidates not generated"
        return outcome

    seen: dict[str, Candidate] = {}
    add = lambda entry, method, score: _insert(seen, entry, method, score)
    for entry in index.lookup_norm(record.product_name_norm):
        add(entry, "exact_name", 1.0)
    for entry in index.lookup_norm(record.active_ingredient_norm):
        add(entry, "ingredient_level", 0.85)
    for entry in index.lookup_folded(record.product_name_folded):
        add(entry, "diacritic_fold", 0.9)
    for entry in index.fuzzy(record.product_tokens, fuzzy_threshold, cap):
        add(entry, "token_jaccard", _token_score(record.product_tokens, entry["name"]))

    outcome.candidates = sorted(seen.values(), key=lambda item: item.score, reverse=True)[:cap]
    if not outcome.candidates:
        outcome.status = "UNRESOLVED"
        outcome.reason = "no candidate above deterministic threshold"
    return outcome


def _token_score(tokens: frozenset[str], name: str) -> float:
    name_tokens = frozenset(normalize_text(name).split())
    overlap = len(tokens & name_tokens)
    return overlap / max(len(tokens | name_tokens), 1)


def _insert(seen: dict[str, Candidate], entry: dict[str, str], method: str, score: float) -> None:
    rxcui = entry["rxcui"]
    current = seen.get(rxcui)
    if current is None or score > current.score:
        seen[rxcui] = Candidate(
            rxcui=rxcui,
            name=entry["name"],
            tty=entry["tty"],
            method=method,
            score=score,
        )


def link_ddinter(
    outcomes: Iterable[RecordOutcome],
    ddinter_rows: Iterable[dict[str, Any]] | None,
) -> None:
    """Attach eligible DDInter positive links to accepted candidate identities."""
    if ddinter_rows is None:
        return
    name_to_links: dict[str, list[dict[str, Any]]] = {}
    for row in ddinter_rows:
        for drug_name in (row.get("drug_name_a"), row.get("drug_name_b")):
            if not drug_name:
                continue
            link = {
                "interaction_id": str(row.get("interaction_id") or ""),
                "drug_name": str(drug_name),
                "role": "a" if drug_name == row.get("drug_name_a") else "b",
                "interaction_type": str(row.get("interaction_type") or ""),
                "risk_level": str(row.get("risk_level") or ""),
            }
            name_to_links.setdefault(normalize_text(str(drug_name)), []).append(link)
    for outcome in outcomes:
        if not outcome.candidates:
            continue
        links: list[dict[str, Any]] = []
        for candidate in outcome.candidates:
            matched = name_to_links.get(normalize_text(candidate.name))
            if matched:
                for link in matched:
                    links.append({**link, "rxcui": candidate.rxcui, "method": candidate.method})
        outcome.ddinter_links = links


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return [row for row in csv.DictReader(source)]


def _require_columns(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    if not rows:
        return
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        raise ValueError(f"{path}: missing columns {','.join(missing)}")


def run(
    input_path: Path,
    rxnorm_path: Path | None,
    ddinter_path: Path | None,
    output_path: Path,
    *,
    fuzzy_threshold: float = 0.8,
    cap: int = 10,
) -> dict[str, Any]:
    rows = read_csv(input_path)
    _require_columns(input_path, rows, INPUT_COLUMNS)

    index: TerminologyIndex | None = None
    if rxnorm_path is not None:
        index = TerminologyIndex(read_csv(rxnorm_path))

    ddinter_rows: list[dict[str, Any]] | None = None
    if ddinter_path is not None:
        ddinter_rows = read_csv(ddinter_path)

    outcomes: list[RecordOutcome] = []
    for row in rows:
        try:
            record = normalize_record(row)
        except ValueError as exc:
            outcomes.append(
                RecordOutcome(
                    source_record_id=str(row.get("source_record_id") or ""),
                    normalized={},
                    status="REJECTED_INPUT",
                    reason=str(exc),
                )
            )
            continue
        outcomes.append(generate_candidates(record, index, fuzzy_threshold=fuzzy_threshold, cap=cap))
    link_ddinter(outcomes, ddinter_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for outcome in outcomes:
            stream.write(
                json.dumps(
                    {
                        "source_record_id": outcome.source_record_id,
                        "status": outcome.status,
                        "reason": outcome.reason,
                        "normalized": outcome.normalized,
                        "candidates": [candidate.__dict__ for candidate in outcome.candidates],
                        "ddinter_positive_links": outcome.ddinter_links,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    candidate_count = sum(1 for outcome in outcomes if outcome.status == "CANDIDATES")
    linked_count = sum(1 for outcome in outcomes if outcome.ddinter_links)
    return {
        "input_rows": len(rows),
        "candidate_rows": candidate_count,
        "unresolved_rows": sum(1 for outcome in outcomes if outcome.status == "UNRESOLVED"),
        "rejected_rows": sum(1 for outcome in outcomes if outcome.status == "REJECTED_INPUT"),
        "ddinter_linked_rows": linked_count,
        "output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--rxnorm-table", type=Path, default=None)
    parser.add_argument("--ddinter-table", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.8)
    parser.add_argument("--cap", type=int, default=10)
    args = parser.parse_args()
    summary = run(
        args.input,
        args.rxnorm_table,
        args.ddinter_table,
        args.output,
        fuzzy_threshold=args.fuzzy_threshold,
        cap=args.cap,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def record_digest(record: NormalizedRecord) -> str:
    """SHA-256 over the normalized identity fields (deterministic provenance key)."""

    def _default(value: Any) -> Any:
        if isinstance(value, frozenset):
            return sorted(value)
        if isinstance(value, tuple):
            return list(value)
        raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")

    payload = json.dumps(asdict(record), sort_keys=True, ensure_ascii=False, default=_default)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
