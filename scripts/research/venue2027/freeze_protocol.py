"""CLARA-Care 2027 shared task SH-freeze_tool.

Purpose
-------
Prospective freeze/hash and chronology validator. Before a confirmatory
holdout is opened, ``freeze()`` bundles SHA256 digests and timestamps of the
study protocol, cohort/case manifest, oracle source, baseline source versions
and analysis code into an immutable :class:`FreezeManifest`. ``freeze_id`` is a
SHA256 over the sorted ``(path, hash)`` pairs, so any later content edit in a
bundled file is detectable. ``verify_freeze()`` re-hashes and fails closed on
any drift (``FREEZE_DRIFT``). Amendments to the pre-registration are
append-only (``amend()``); rewriting or truncating history is refused with
``AMENDMENT_REWRITE``. Holdout data may not be accessed without a verified
freeze (``HOLDOUT_UNFROZEN``), closing the "regenerate the main split after
seeing results" loophole.

Allowed input
-------------
A :class:`FreezeConfig` describing a study root (filesystem paths only; no
network, DB, or live provider) and the relative paths of the files to bundle.
I/O is real-file hashing, read-only on the study root; the amendment log is the
only file this module writes. No production secret or patient-data access.

Failure semantics
-----------------
Every failure carries a stable ``reason_code``: ``FREEZE_INPUT_MISSING`` (a
bundled path does not exist), ``FREEZE_INPUT_INVALID`` (bad config/path), or
``FREEZE_DRIFT`` (content changed after freeze). ``verify_freeze`` fails closed
and never raises for expected conditions. Holdout access is a pure check:
``assert_holdout_allowed`` returns ``HOLDOUT_UNFROZEN`` unless the supplied
manifest verifies OK. Timestamps are injected by the caller (``now_fn``) so
tests stay deterministic and there is no hidden clock.

Version
-------
``FREEZE_PROTOCOL_SCHEMA_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

FREEZE_PROTOCOL_SCHEMA_VERSION = "1.0.0"

ReasonCode = Literal[
    "OK",
    "FREEZE_INPUT_MISSING",
    "FREEZE_INPUT_INVALID",
    "FREEZE_DRIFT",
    "AMENDMENT_REWRITE",
    "HOLDOUT_UNFROZEN",
]

# Files this module is allowed to write under the study root. Everything else
# is treated as read-only evidence.
AMENDMENT_LOG_BASENAME = "amendment_log.json"
MANIFEST_BASENAME = "freeze_manifest.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _confined_path(root: Path, rel: str) -> Path | None:
    """Resolve ``rel`` inside ``root`` or return None if it escapes.

    Rejects absolute paths, ``..`` traversal and symlink escapes, mirroring the
    hashing confinement used by ``_shared/tools/agent_protocol.py``.
    """

    candidate = Path(rel)
    if candidate.is_absolute() or not str(candidate):
        return None
    try:
        resolved_root = root.resolve()
        resolved = (resolved_root / candidate).resolve()
    except (OSError, RuntimeError):
        return None
    if resolved != resolved_root and resolved_root not in resolved.parents:
        return None
    return resolved


@dataclasses.dataclass(frozen=True)
class FreezeEntry:
    """One bundled artifact: its repo-relative path, digest and mtime."""

    path: str
    sha256: str
    timestamp_utc: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "timestamp_utc": self.timestamp_utc,
            "size_bytes": self.size_bytes,
        }


@dataclasses.dataclass(frozen=True)
class FreezeManifest:
    """Immutable freeze manifest; JSON-serialisable via :meth:`to_dict`.

    ``ok`` is False for any environmental/config failure. ``freeze_id`` is
    empty until a freeze succeeds; ``verify_freeze`` recomputes it from the
    bundled entries so a mutated ``entries`` list cannot verify.
    """

    ok: bool
    reason_code: ReasonCode
    schema_version: str
    study_id: str
    stage: str
    freeze_id: str
    entries: tuple[FreezeEntry, ...]
    amendments: tuple[dict[str, Any], ...]
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "reason_code": self.reason_code,
            "study_id": self.study_id,
            "stage": self.stage,
            "freeze_id": self.freeze_id,
            "entries": [e.to_dict() for e in self.entries],
            "amendments": [dict(a) for a in self.amendments],
            "detail": self.detail,
        }


@dataclasses.dataclass(frozen=True)
class FreezeConfig:
    """Declares what gets frozen and which clock stamps it.

    ``paths`` must be relative to ``root`` and point at existing files.
    ``now_fn`` is injected so tests are deterministic (no hidden clock).
    """

    study_id: str
    stage: str
    root: str | os.PathLike[str]
    paths: Sequence[str]
    now_fn: Callable[[], str]


def compute_freeze_id(entries: Sequence[FreezeEntry]) -> str:
    """SHA256 over the sorted ``(path, hash)`` pairs (order-independent)."""

    aggregate = hashlib.sha256()
    for entry in sorted(entries, key=lambda e: e.path):
        aggregate.update(f"{entry.path}\0{entry.sha256}\n".encode())
    return aggregate.hexdigest()


def _failure(
    config: FreezeConfig | None, code: ReasonCode, detail: str
) -> FreezeManifest:
    cfg = config or FreezeConfig("", "", ".", (), lambda: "")
    return FreezeManifest(
        ok=False,
        reason_code=code,
        schema_version=FREEZE_PROTOCOL_SCHEMA_VERSION,
        study_id=cfg.study_id,
        stage=cfg.stage,
        freeze_id="",
        entries=(),
        amendments=(),
        detail=detail,
    )


def freeze(config: FreezeConfig) -> FreezeManifest:
    """Bundle SHA256 + timestamp of every configured artifact.

    Refuses to proceed when any bundled path is missing, escapes the study
    root, or duplicates another entry. Never silently drops a missing file.
    """

    if not config.study_id.strip() or not config.stage.strip():
        return _failure(config, "FREEZE_INPUT_INVALID", "study_id and stage are required")
    root = Path(config.root)
    if not root.is_dir():
        return _failure(config, "FREEZE_INPUT_INVALID", f"study root not found: {root}")

    seen: set[str] = set()
    entries: list[FreezeEntry] = []
    for rel in config.paths:
        if rel in seen:
            return _failure(config, "FREEZE_INPUT_INVALID", f"duplicate bundle path: {rel}")
        seen.add(rel)
        target = _confined_path(root, rel)
        if target is None:
            return _failure(
                config, "FREEZE_INPUT_INVALID", f"path escapes study root: {rel}"
            )
        if not target.is_file():
            return _failure(
                config, "FREEZE_INPUT_MISSING", f"bundled artifact not found: {rel}"
            )
        entries.append(
            FreezeEntry(
                path=rel,
                sha256=_sha256_file(target),
                timestamp_utc=config.now_fn(),
                size_bytes=target.stat().st_size,
            )
        )
    if not entries:
        return _failure(config, "FREEZE_INPUT_INVALID", "no artifacts configured for freeze")

    return FreezeManifest(
        ok=True,
        reason_code="OK",
        schema_version=FREEZE_PROTOCOL_SCHEMA_VERSION,
        study_id=config.study_id,
        stage=config.stage,
        freeze_id=compute_freeze_id(entries),
        entries=tuple(entries),
        amendments=(),
        detail="",
    )


def verify_freeze(manifest: FreezeManifest, root: str | os.PathLike[str]) -> FreezeManifest:
    """Re-hash every bundled entry against ``root``; fail closed on drift.

    Returns a manifest with ``ok=False`` and ``FREEZE_DRIFT`` when any bundled
    file is missing, changed content, or when the recorded ``freeze_id`` no
    longer matches the recomputed one (e.g. an in-memory entries mutation).
    """

    base = FreezeManifest(
        ok=False,
        reason_code=manifest.reason_code,
        schema_version=manifest.schema_version,
        study_id=manifest.study_id,
        stage=manifest.stage,
        freeze_id=manifest.freeze_id,
        entries=manifest.entries,
        amendments=manifest.amendments,
        detail="",
    )
    if not manifest.ok:
        return FreezeManifest(
            **{
                **dataclasses.asdict(base),
                "detail": "refusing to verify a manifest that never froze",
            }
        )
    root_p = Path(root)
    drift: list[str] = []
    for entry in manifest.entries:
        target = _confined_path(root_p, entry.path)
        if target is None:
            drift.append(f"{entry.path}: escapes study root")
            continue
        if not target.is_file():
            drift.append(f"{entry.path}: missing")
            continue
        actual = _sha256_file(target)
        if actual != entry.sha256:
            drift.append(f"{entry.path}: frozen {entry.sha256} actual {actual}")
    if not drift:
        recomputed = compute_freeze_id(manifest.entries)
        if recomputed != manifest.freeze_id:
            drift.append(f"freeze_id mismatch: recorded {manifest.freeze_id}")
    if drift:
        return dataclasses.replace(
            base, ok=False, reason_code="FREEZE_DRIFT", detail="; ".join(drift)
        )
    return dataclasses.replace(base, ok=True, reason_code="OK")


def amend(
    manifest: FreezeManifest, amendment: Mapping[str, Any], root: str | os.PathLike[str]
) -> FreezeManifest:
    """Append ``amendment`` to the APPEND-ONLY amendment log.

    The log lives at ``<root>/<AMENDMENT_LOG_BASENAME>``. Existing entries are
    never rewritten: the new entry is appended after re-reading the on-disk
    log, and the manifest's embedded history is replaced by the merged
    (historical + new) list. Any attempt to shrink or reorder prior history
    relative to the on-disk log is refused with ``AMENDMENT_REWRITE``.
    Amendments do not change ``freeze_id`` (bundled artifacts are untouched);
    they change the *pre-registration*, which is why the log is append-only.
    """

    root_p = Path(root)
    log_path = root_p / AMENDMENT_LOG_BASENAME
    on_disk: list[dict[str, Any]] = []
    if log_path.is_file():
        try:
            loaded = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return dataclasses.replace(
                manifest,
                ok=False,
                reason_code="AMENDMENT_REWRITE",
                detail=f"amendment log unreadable: {exc}",
            )
        if not isinstance(loaded, list) or not all(isinstance(e, dict) for e in loaded):
            return dataclasses.replace(
                manifest,
                ok=False,
                reason_code="AMENDMENT_REWRITE",
                detail="amendment log is not a JSON list of objects",
            )
        on_disk = loaded
    history = list(manifest.amendments)
    if history != on_disk:
        return dataclasses.replace(
            manifest,
            ok=False,
            reason_code="AMENDMENT_REWRITE",
            detail=(
                "manifest history diverges from append-only log "
                f"(log has {len(on_disk)} entries, manifest claims {len(history)})"
            ),
        )
    payload = dict(amendment)
    stamp = payload.get("timestamp_utc") if isinstance(payload, dict) else None
    entry: dict[str, Any] = {
        "index": len(on_disk),
        "amendment": payload,
        "timestamp_utc": stamp,
    }
    merged = [*on_disk, entry]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dataclasses.replace(manifest, amendments=tuple(merged))


def assert_holdout_allowed(
    manifest: FreezeManifest, root: str | os.PathLike[str]
) -> FreezeManifest:
    """Gate confirmatory holdout access on a *verified* freeze.

    Fails with ``HOLDOUT_UNFROZEN`` when the manifest never froze, fails
    verification, or has any unresolved (unverified) amendment state.
    """

    verified = verify_freeze(manifest, root)
    if not verified.ok:
        return dataclasses.replace(
            verified,
            ok=False,
            reason_code="HOLDOUT_UNFROZEN",
            detail=f"holdout blocked: {verified.reason_code}: {verified.detail}",
        )
    return verified
