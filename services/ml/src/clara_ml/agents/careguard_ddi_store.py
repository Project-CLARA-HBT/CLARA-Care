# ruff: noqa: E501
"""Memory-safe on-disk DDI store for the large DrugBank interaction layer.

The DrugBank shard set expands to ~1.43M interaction pairs. Loading all of them
into memory as ``InteractionRule`` objects costs ~1.26 GB RSS, which OOMs small
production hosts. This module keeps the big layer **on disk in SQLite** and does
per-query pair lookups instead, so resident memory stays flat (a few MB) while
CareGuard still covers the full DrugBank interaction set.

Design:

* The curated Vietnamese rules stay in memory (they are tiny and always win on a
  conflicting pair). This module ONLY backs the optional DrugBank layer.
* A SQLite database is built ONCE from the shards under ``nlp/seed_data/drugbank``
  and cached on disk (``drugbank/ddi_index.sqlite``), keyed by the manifest
  version. If the file already exists with a matching version, no rebuild runs.
* Lookups take the C(n,2) medication pairs for a single analysis and issue one
  indexed ``SELECT`` — O(pairs) with an index seek each, not a 1.43M-row scan.
* Every operation is defensive: any build/lookup failure degrades to "no DrugBank
  contribution" so CareGuard falls back to curated-only and never crashes or
  fabricates an all-clear.

The row shape mirrors the in-memory ``InteractionRule`` semantics: medications
are normalized (stripped/lowercased) and stored as a sorted ``(med_a, med_b)``
pair so lookup is order-independent, with severity clamped to CLARA's scale.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_SHA256_HEX = set("0123456789abcdef")


@dataclass(frozen=True)
class _Manifest:
    """Verified, non-sensitive identity of a DrugBank artifact set."""

    version: str
    source_version: str
    source_sha256: str
    manifest_sha256: str
    ddi_rule_count: int
    dictionary_record_count: int
    ddi_shards: tuple[dict[str, Any], ...]
    dictionary_shards: tuple[dict[str, Any], ...]


def _normalize_med(value: object) -> str:
    return str(value or "").strip().lower()


def _normalize_severity(value: object) -> str:
    severity = str(value or "").strip().lower()
    return severity if severity in _SEVERITY_RANK else "medium"


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value.lower()) <= _SHA256_HEX
    )


def _canonical_manifest_sha256(payload: dict[str, Any]) -> str:
    """Digest manifest content excluding the self-referential digest field."""

    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    encoded = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(encoded)


class DrugBankDdiStore:
    """On-disk SQLite accessor for the DrugBank DDI pair layer."""

    def __init__(
        self,
        *,
        drugbank_dir: Path,
        manifest_path: Path,
        sqlite_path: Path | None = None,
        integrity_required: bool = True,
    ) -> None:
        self._dir = drugbank_dir
        self._manifest_path = manifest_path
        self._db_path = sqlite_path or drugbank_dir / "ddi_index.sqlite"
        self._integrity_required = integrity_required
        self._version = ""

    @property
    def version(self) -> str:
        """The manifest/version label of the built index (empty until built)."""
        return self._version

    def readiness(self) -> dict[str, object]:
        """Return a content-free operational readiness projection.

        Licensed interaction text and filesystem paths are deliberately omitted.
        A positive pair count and identical manifest/index versions are required
        before the dataset may report ``ready``.
        """

        manifest = self._read_manifest()
        manifest_version = manifest.version if manifest else ""
        database_identity = self._existing_db_identity()
        database_version = database_identity.get("version", "")
        pair_count = 0
        dictionary_record_count = 0
        pair_table_readable = False
        dictionary_table_readable = False
        if self._db_path.exists():
            try:
                conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
                try:
                    row = conn.execute(
                        "SELECT value FROM meta WHERE key = 'pair_count'"
                    ).fetchone()
                    pair_count = int(row[0]) if row and str(row[0]).isdigit() else 0
                    dictionary_row = conn.execute(
                        "SELECT value FROM meta WHERE key = 'dictionary_record_count'"
                    ).fetchone()
                    dictionary_record_count = (
                        int(dictionary_row[0])
                        if dictionary_row and str(dictionary_row[0]).isdigit()
                        else 0
                    )
                    # Validate the interaction table itself, not only its
                    # self-reported metadata. ``LIMIT 1`` is constant-time on
                    # the indexed table and catches a corrupt/incomplete DB
                    # whose meta table still looks healthy.
                    conn.execute("SELECT 1 FROM ddi_pairs LIMIT 1").fetchone()
                    pair_table_readable = True
                    # DrugBank-backed Vietnamese normalization is part of the
                    # same licensed artifact boundary. A DDI index with a
                    # missing/corrupt dictionary must not advertise complete
                    # full-DrugBank readiness.
                    conn.execute("SELECT 1 FROM drug_dictionary LIMIT 1").fetchone()
                    dictionary_table_readable = True
                finally:
                    conn.close()
            except (sqlite3.Error, OSError, ValueError):
                pair_count = 0
                dictionary_record_count = 0
                pair_table_readable = False
                dictionary_table_readable = False

        integrity_verified = bool(manifest is not None and self._integrity_required)
        identity_matches = bool(
            manifest is not None
            and database_version == manifest_version
            and database_identity.get("manifest_sha256") == manifest.manifest_sha256
            and database_identity.get("source_version") == manifest.source_version
            and database_identity.get("source_sha256") == manifest.source_sha256
        )

        counts_match = bool(
            not self._integrity_required
            or (
                manifest is not None
                and pair_count == manifest.ddi_rule_count
                and dictionary_record_count == manifest.dictionary_record_count
            )
        )
        ready = bool(
            identity_matches
            and counts_match
            and pair_count > 0
            and dictionary_record_count > 0
            and pair_table_readable
            and dictionary_table_readable
        )
        if ready:
            state = "ready"
        elif manifest_version or database_version or self._db_path.exists():
            state = "degraded"
        else:
            state = "unavailable"
        return {
            "state": state,
            "version": database_version or manifest_version,
            "pair_count": pair_count,
            "dictionary_record_count": dictionary_record_count,
            "manifest_matches_index": identity_matches,
            "integrity_verified": integrity_verified,
            "source_version": manifest.source_version if manifest else "",
        }

    # -- manifest ---------------------------------------------------------

    def _read_manifest(self) -> _Manifest | None:
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        version = str(payload.get("version") or "").strip()
        if not version:
            return None
        ddi_shards = payload.get("ddi_shards")
        dictionary_shards = payload.get("dictionary_shards", [])
        if not isinstance(ddi_shards, list) or not isinstance(dictionary_shards, list):
            return None

        source = str(payload.get("source") or "").strip().lower()
        source_version = str(payload.get("source_version") or "").strip()
        source_sha256 = str(payload.get("source_sha256") or "").strip().lower()
        manifest_sha256 = str(payload.get("manifest_sha256") or "").strip().lower()
        ddi_rule_count = payload.get("ddi_rule_count")
        dictionary_record_count = payload.get("dictionary_record_count")
        if self._integrity_required:
            if (
                source != "drugbank"
                or not source_version
                or not _is_sha256(source_sha256)
                or not _is_sha256(manifest_sha256)
                or type(ddi_rule_count) is not int
                or ddi_rule_count <= 0
                or type(dictionary_record_count) is not int
                or dictionary_record_count <= 0
                or _canonical_manifest_sha256(payload) != manifest_sha256
            ):
                return None

        normalized_ddi = self._validate_shards(ddi_shards)
        normalized_dictionary = self._validate_shards(dictionary_shards)
        if normalized_ddi is None or normalized_dictionary is None:
            return None
        return _Manifest(
            version=version,
            source_version=source_version,
            source_sha256=source_sha256,
            manifest_sha256=manifest_sha256,
            ddi_rule_count=int(ddi_rule_count or 0),
            dictionary_record_count=int(dictionary_record_count or 0),
            ddi_shards=tuple(normalized_ddi),
            dictionary_shards=tuple(normalized_dictionary),
        )

    def _validate_shards(self, shards: list[object]) -> list[dict[str, Any]] | None:
        normalized: list[dict[str, Any]] = []
        base = self._dir.resolve()
        for shard in shards:
            if not isinstance(shard, dict):
                return None
            shard_file = str(shard.get("file") or "").strip()
            if not shard_file:
                return None
            path = (self._dir / shard_file).resolve()
            if path.parent != base and base not in path.parents:
                return None
            digest = str(shard.get("sha256") or "").strip().lower()
            if self._integrity_required and not _is_sha256(digest):
                return None
            normalized.append({"file": shard_file, "path": path, "sha256": digest})
        return normalized

    # -- build ------------------------------------------------------------

    def _existing_db_identity(self) -> dict[str, str]:
        if not self._db_path.exists():
            return {}
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return {}
        try:
            rows = conn.execute(
                "SELECT key, value FROM meta WHERE key IN "
                "('version', 'manifest_sha256', 'source_version', 'source_sha256')"
            ).fetchall()
            return {str(key): str(value) for key, value in rows}
        except sqlite3.Error:
            return {}
        finally:
            conn.close()

    def ensure_built(self) -> str | None:
        """Build the SQLite index if missing/stale; return the built version.

        Idempotent and cheap on the hot path: if the DB already exists and its
        stored version matches the manifest version, this returns immediately
        without touching the shards. Returns ``None`` (degrade to curated-only)
        on any failure.
        """

        manifest = self._read_manifest()
        if manifest is None:
            return None
        existing = self._existing_db_identity()
        if self._matches_manifest(existing, manifest) and self._index_is_complete(manifest):
            self._version = manifest.version
            return manifest.version

        # Build into a temp file, then atomically replace, so a partial build is
        # never observed and concurrent readers keep the old (valid) DB.
        tmp_path: Path | None = None
        conn: sqlite3.Connection | None = None
        try:
            import os

            tmp_fd, tmp_name = tempfile.mkstemp(
                prefix="ddi_index.", suffix=".sqlite.tmp", dir=str(self._db_path.parent)
            )
            tmp_path = Path(tmp_name)
            os.close(tmp_fd)
            conn = sqlite3.connect(str(tmp_path))
            conn.execute("PRAGMA journal_mode=OFF")
            conn.execute("PRAGMA synchronous=OFF")
            conn.execute(
                "CREATE TABLE ddi_pairs ("
                "med_a TEXT NOT NULL, med_b TEXT NOT NULL, "
                "severity TEXT NOT NULL, message TEXT NOT NULL, "
                "PRIMARY KEY (med_a, med_b))"
            )
            conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

            for shard in manifest.ddi_shards:
                shard_path = Path(shard["path"])
                try:
                    raw_bytes = shard_path.read_bytes()
                    if shard["sha256"] and _sha256_bytes(raw_bytes) != shard["sha256"]:
                        return None
                    shard_payload = json.loads(raw_bytes.decode("utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    return None
                if not isinstance(shard_payload, dict):
                    return None
                raw_rules = shard_payload.get("rules")
                if not isinstance(raw_rules, list):
                    return None
                batch: list[tuple[str, str, str, str]] = []
                for raw_rule in raw_rules:
                    if not isinstance(raw_rule, dict):
                        continue
                    meds_raw = raw_rule.get("medications")
                    if not isinstance(meds_raw, list):
                        continue
                    meds = sorted({_normalize_med(m) for m in meds_raw if _normalize_med(m)})
                    if len(meds) != 2:
                        continue
                    severity = _normalize_severity(raw_rule.get("severity"))
                    message = str(raw_rule.get("message", "")).strip() or "Potential DDI detected."
                    batch.append((meds[0], meds[1], severity, message))
                if batch:
                    conn.executemany(
                        "INSERT OR IGNORE INTO ddi_pairs (med_a, med_b, severity, message) "
                        "VALUES (?, ?, ?, ?)",
                        batch,
                    )
            conn.execute(
                "CREATE TABLE drug_dictionary ("
                "alias TEXT PRIMARY KEY, normalized_name TEXT NOT NULL, "
                "active_ingredients_json TEXT NOT NULL, rxcui TEXT NOT NULL, "
                "drugbank_id TEXT NOT NULL)"
            )
            for shard in manifest.dictionary_shards:
                shard_path = Path(shard["path"])
                try:
                    raw_bytes = shard_path.read_bytes()
                    if shard["sha256"] and _sha256_bytes(raw_bytes) != shard["sha256"]:
                        return None
                    shard_payload = json.loads(raw_bytes.decode("utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    return None
                if not isinstance(shard_payload, dict):
                    return None
                records = shard_payload.get("records")
                if not isinstance(records, list):
                    return None
                batch_dictionary: list[tuple[str, str, str, str, str]] = []
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    alias = _normalize_med(record.get("brand_vn"))
                    normalized_name = _normalize_med(record.get("normalized_name"))
                    if not alias or not normalized_name:
                        continue
                    active_ingredients = record.get("active_ingredients")
                    if not isinstance(active_ingredients, list):
                        active_ingredients = [normalized_name]
                    normalized_actives = [
                        _normalize_med(value) for value in active_ingredients if _normalize_med(value)
                    ] or [normalized_name]
                    batch_dictionary.append(
                        (
                            alias,
                            normalized_name,
                            json.dumps(normalized_actives, ensure_ascii=False),
                            str(record.get("rxcui") or "").strip(),
                            str(record.get("drugbank_id") or "").strip(),
                        )
                    )
                if batch_dictionary:
                    conn.executemany(
                        "INSERT OR IGNORE INTO drug_dictionary "
                        "(alias, normalized_name, active_ingredients_json, rxcui, drugbank_id) "
                        "VALUES (?, ?, ?, ?, ?)",
                        batch_dictionary,
                    )
            actual_pair_count = int(conn.execute("SELECT COUNT(*) FROM ddi_pairs").fetchone()[0])
            actual_dictionary_count = int(
                conn.execute("SELECT COUNT(*) FROM drug_dictionary").fetchone()[0]
            )
            if self._integrity_required and (
                actual_pair_count != manifest.ddi_rule_count
                or actual_dictionary_count != manifest.dictionary_record_count
            ):
                return None
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('version', ?)",
                (manifest.version,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('pair_count', ?)",
                (str(actual_pair_count),),
            )
            conn.executemany(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                [
                    ("dictionary_record_count", str(actual_dictionary_count)),
                    ("manifest_sha256", manifest.manifest_sha256),
                    ("source_version", manifest.source_version),
                    ("source_sha256", manifest.source_sha256),
                ],
            )
            conn.commit()
            conn.close()
            conn = None
            assert tmp_path is not None
            tmp_path.replace(self._db_path)
            self._version = manifest.version
            logger.info(
                "drugbank ddi sqlite index built: version=%s pairs=%d",
                manifest.version,
                actual_pair_count,
            )
            return manifest.version
        except (sqlite3.Error, OSError):
            logger.exception("drugbank ddi sqlite build failed; degrading to curated-only")
            return None
        finally:
            if conn is not None:
                conn.close()
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _matches_manifest(existing: dict[str, str], manifest: _Manifest) -> bool:
        return bool(
            existing.get("version") == manifest.version
            and existing.get("manifest_sha256") == manifest.manifest_sha256
            and existing.get("source_version") == manifest.source_version
            and existing.get("source_sha256") == manifest.source_sha256
        )

    def _index_is_complete(self, manifest: _Manifest) -> bool:
        """Confirm a matching metadata row still represents a readable full index."""

        readiness = self.readiness()
        return bool(
            readiness.get("state") == "ready"
            and readiness.get("version") == manifest.version
            and (
                not self._integrity_required
                or (
                    readiness.get("pair_count") == manifest.ddi_rule_count
                    and readiness.get("dictionary_record_count")
                    == manifest.dictionary_record_count
                )
            )
        )

    # -- lookup -----------------------------------------------------------

    def lookup_pairs(
        self, medications: list[str]
    ) -> list[tuple[frozenset[str], str, str]]:
        """Return ``(meds, severity, message)`` for DrugBank-covered pairs.

        Enumerates the distinct C(n,2) medication pairs and looks each up in the
        on-disk index. Never raises: any error yields an empty contribution.
        """

        distinct = sorted({_normalize_med(m) for m in medications if _normalize_med(m)})
        if len(distinct) < 2:
            return []
        pairs: list[tuple[str, str]] = []
        for i in range(len(distinct)):
            for j in range(i + 1, len(distinct)):
                pairs.append((distinct[i], distinct[j]))
        if not pairs:
            return []

        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return []
        try:
            out: list[tuple[frozenset[str], str, str]] = []
            # One indexed lookup per pair; pair count is tiny (a handful), so this
            # is O(pairs * log n) with a PK seek each — never a full-table scan.
            for med_a, med_b in pairs:
                cur = conn.execute(
                    "SELECT severity, message FROM ddi_pairs WHERE med_a = ? AND med_b = ?",
                    (med_a, med_b),
                )
                row = cur.fetchone()
                if row is not None:
                    out.append((frozenset({med_a, med_b}), str(row[0]), str(row[1])))
            return out
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    def resolve_medication(self, medication: str) -> dict[str, object] | None:
        """Resolve one normalized medication alias against the indexed DrugBank dictionary.

        This is a deterministic alias lookup, not an LLM inference. The return
        value contains only the minimum traceability fields required to explain
        how an input was matched; it never guesses on a miss.
        """

        alias = _normalize_med(medication)
        if not alias:
            return None
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return None
        try:
            row = conn.execute(
                "SELECT normalized_name, active_ingredients_json, rxcui, drugbank_id "
                "FROM drug_dictionary WHERE alias = ?",
                (alias,),
            ).fetchone()
            if row is None:
                return None
            try:
                active_ingredients = json.loads(str(row[1]))
            except json.JSONDecodeError:
                return None
            if not isinstance(active_ingredients, list):
                return None
            normalized_actives = [
                _normalize_med(value) for value in active_ingredients if _normalize_med(value)
            ]
            normalized_name = _normalize_med(row[0])
            if not normalized_name:
                return None
            return {
                "alias": alias,
                "normalized_name": normalized_name,
                "active_ingredients": normalized_actives or [normalized_name],
                "rxcui": str(row[2] or "").strip(),
                "drugbank_id": str(row[3] or "").strip(),
                "source_version": self._version,
            }
        except sqlite3.Error:
            return None
        finally:
            conn.close()
