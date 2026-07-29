"""Fail-closed loading for offline-signed model artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class ArtifactVerificationError(ValueError):
    pass


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def sign_manifest_for_offline_pipeline(
    manifest: dict[str, Any],
    private_key: Ed25519PrivateKey,
) -> str:
    """Offline-training helper; private keys must never enter online config."""

    return base64.b64encode(private_key.sign(canonical_manifest_bytes(manifest))).decode()


@dataclass(frozen=True)
class VerifiedArtifact:
    path: Path
    sha256: str
    key_id: str
    manifest: dict[str, Any]


def verify_artifact(
    *,
    root: Path,
    manifest: dict[str, Any],
    signature_base64: str,
    key_id: str,
    public_keys: dict[str, str],
) -> VerifiedArtifact:
    required = {
        "use_case_id",
        "artifact_id",
        "version",
        "relative_path",
        "sha256",
        "release_state",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ArtifactVerificationError(f"manifest_missing:{missing[0]}")
    if manifest["release_state"] not in {
        "offline_passed",
        "redteam_passed",
        "shadow",
        "pilot",
        "challenger",
        "champion",
    }:
        raise ArtifactVerificationError("artifact_release_state_forbidden")
    encoded_key = public_keys.get(key_id)
    if not encoded_key or not signature_base64:
        raise ArtifactVerificationError("artifact_signature_required")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(encoded_key, validate=True)
        )
        signature = base64.b64decode(signature_base64, validate=True)
        public_key.verify(signature, canonical_manifest_bytes(manifest))
    except (ValueError, InvalidSignature) as error:
        raise ArtifactVerificationError("artifact_signature_invalid") from error

    resolved_root = root.resolve()
    relative = Path(str(manifest["relative_path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ArtifactVerificationError("artifact_path_invalid")
    path = (resolved_root / relative).resolve()
    if not path.is_relative_to(resolved_root) or not path.is_file():
        raise ArtifactVerificationError("artifact_missing")
    hasher = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    expected = str(manifest["sha256"]).lower()
    if len(expected) != 64 or digest != expected:
        raise ArtifactVerificationError("artifact_checksum_mismatch")
    return VerifiedArtifact(
        path=path,
        sha256=digest,
        key_id=key_id,
        manifest=dict(manifest),
    )
