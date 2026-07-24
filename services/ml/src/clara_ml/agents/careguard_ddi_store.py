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
from pathlib import Path

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _normalize_med(value: object) -> str:
    return str(value or "").strip().lower()


def _normalize_severity(value: object) -> str:
    severity = str(value or "").strip().lower()
    return severity if severity in _SEVERITY_RANK else "medium"


class DrugBankDdiStore:
    """On-disk SQLite accessor for the DrugBank DDI pair layer."""

    def __init__(self, *, drugbank_dir: Path, manifest_path: Path) -> None:
        self._dir = drugbank_dir
        self._manifest_path = manifest_path
        self._db_path = drugbank_dir / "ddi_index.sqlite"
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

        manifest_version = self._read_manifest_version() or ""
        database_version = self._existing_db_version() or ""
        pair_count = 0
        pair_table_readable = False
        if self._db_path.exists():
            try:
                conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
                try:
                    row = conn.execute(
                        "SELECT value FROM meta WHERE key = 'pair_count'"
                    ).fetchone()
                    pair_count = int(row[0]) if row and str(row[0]).isdigit() else 0
                    # Validate the interaction table itself, not only its
                    # self-reported metadata. ``LIMIT 1`` is constant-time on
                    # the indexed table and catches a corrupt/incomplete DB
                    # whose meta table still looks healthy.
                    conn.execute("SELECT 1 FROM ddi_pairs LIMIT 1").fetchone()
                    pair_table_readable = True
                finally:
                    conn.close()
            except (sqlite3.Error, OSError, ValueError):
                pair_count = 0
                pair_table_readable = False

        ready = bool(
            manifest_version
            and database_version == manifest_version
            and pair_count > 0
            and pair_table_readable
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
            "manifest_matches_index": bool(
                manifest_version and database_version == manifest_version
            ),
        }

    # -- manifest ---------------------------------------------------------

    def _read_manifest_version(self) -> str | None:
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        version = str(payload.get("version") or "").strip()
        return version or None

    def _manifest_shard_files(self) -> list[str] | None:
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        shards = payload.get("ddi_shards")
        if not isinstance(shards, list):
            return None
        files: list[str] = []
        for shard in shards:
            if not isinstance(shard, dict):
                return None
            shard_file = str(shard.get("file") or "").strip()
            if not shard_file:
                return None
            files.append(shard_file)
        return files

    # -- build ------------------------------------------------------------

    def _existing_db_version(self) -> str | None:
        if not self._db_path.exists():
            return None
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return None
        try:
            cur = conn.execute("SELECT value FROM meta WHERE key = 'version'")
            row = cur.fetchone()
            return str(row[0]) if row else None
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def ensure_built(self) -> str | None:
        """Build the SQLite index if missing/stale; return the built version.

        Idempotent and cheap on the hot path: if the DB already exists and its
        stored version matches the manifest version, this returns immediately
        without touching the shards. Returns ``None`` (degrade to curated-only)
        on any failure.
        """

        version = self._read_manifest_version()
        if not version:
            return None
        if self._existing_db_version() == version:
            self._version = version
            return version

        shard_files = self._manifest_shard_files()
        if shard_files is None:
            return None

        # Build into a temp file, then atomically replace, so a partial build is
        # never observed and concurrent readers keep the old (valid) DB.
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix="ddi_index.", suffix=".sqlite.tmp", dir=str(self._dir)
        )
        tmp_path = Path(tmp_name)
        conn: sqlite3.Connection | None = None
        try:
            import os

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

            total = 0
            for shard_file in shard_files:
                shard_path = self._dir / shard_file
                try:
                    shard_payload = json.loads(shard_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
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
                    total += len(batch)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('version', ?)",
                (version,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('pair_count', ?)",
                (str(total),),
            )
            conn.commit()
            conn.close()
            conn = None
            tmp_path.replace(self._db_path)
            self._version = version
            logger.info(
                "drugbank ddi sqlite index built: version=%s pairs=%d path=%s",
                version,
                total,
                self._db_path,
            )
            return version
        except (sqlite3.Error, OSError):
            logger.exception("drugbank ddi sqlite build failed; degrading to curated-only")
            return None
        finally:
            if conn is not None:
                conn.close()
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

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
