"""Fail-closed loading for offline-signed model artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
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


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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


@dataclass(frozen=True)
class DeploymentSelection:
    """A verified learned artifact or an explicit non-learned safe fallback."""

    slot: str
    artifact: VerifiedArtifact | None
    fallback_ref: str | None
    fallback_reason: str | None = None


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


def _safe_identifier(value: Any, field: str) -> str:
    normalized = str(value)
    if not _SAFE_ID.fullmatch(normalized):
        raise ArtifactVerificationError(f"artifact_identity_invalid:{field}")
    return normalized


class SignedArtifactStore:
    """Immutable online store populated only from offline-signed bundles."""

    _MANIFEST_FILE = "manifest.json"
    _SIGNATURE_FILE = "signature.json"

    def __init__(self, *, root: Path, public_keys: dict[str, str]) -> None:
        self.root = root.resolve()
        self.public_keys = dict(public_keys)

    def _bundle_path(self, artifact_id: str, version: str) -> Path:
        safe_id = _safe_identifier(artifact_id, "artifact_id")
        safe_version = _safe_identifier(version, "version")
        return self.root / safe_id / safe_version

    def install_from_staging(
        self,
        *,
        staging_root: Path,
        manifest: dict[str, Any],
        signature_base64: str,
        key_id: str,
    ) -> VerifiedArtifact:
        """Verify before copy, then publish atomically without overwriting."""

        verified = verify_artifact(
            root=staging_root,
            manifest=manifest,
            signature_base64=signature_base64,
            key_id=key_id,
            public_keys=self.public_keys,
        )
        artifact_id = _safe_identifier(manifest["artifact_id"], "artifact_id")
        version = _safe_identifier(manifest["version"], "version")
        destination = self._bundle_path(artifact_id, version)
        if destination.exists():
            installed = self.load(artifact_id=artifact_id, version=version)
            if (
                installed.sha256 == verified.sha256
                and installed.manifest == verified.manifest
                and installed.key_id == key_id
            ):
                return installed
            raise ArtifactVerificationError("artifact_version_already_exists")

        self.root.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".install-", dir=destination.parent))
        try:
            relative = Path(str(manifest["relative_path"]))
            if relative.parts[0] in {self._MANIFEST_FILE, self._SIGNATURE_FILE}:
                raise ArtifactVerificationError("artifact_path_reserved")
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(verified.path, target)
            (temporary / self._MANIFEST_FILE).write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            (temporary / self._SIGNATURE_FILE).write_text(
                json.dumps(
                    {"key_id": key_id, "signature_base64": signature_base64},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            try:
                os.rename(temporary, destination)
            except OSError as error:
                if destination.exists():
                    raise ArtifactVerificationError("artifact_version_already_exists") from error
                raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return self.load(artifact_id=artifact_id, version=version)

    def load(self, *, artifact_id: str, version: str) -> VerifiedArtifact:
        """Load only when stored identity, signature, path, and bytes all agree."""

        bundle = self._bundle_path(artifact_id, version)
        try:
            manifest = json.loads((bundle / self._MANIFEST_FILE).read_text(encoding="utf-8"))
            signature = json.loads((bundle / self._SIGNATURE_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError) as error:
            raise ArtifactVerificationError("artifact_bundle_invalid") from error
        if not isinstance(manifest, dict) or not isinstance(signature, dict):
            raise ArtifactVerificationError("artifact_bundle_invalid")
        if manifest.get("artifact_id") != artifact_id or str(manifest.get("version")) != version:
            raise ArtifactVerificationError("artifact_bundle_identity_mismatch")
        key_id = signature.get("key_id")
        encoded_signature = signature.get("signature_base64")
        if not isinstance(key_id, str) or not isinstance(encoded_signature, str):
            raise ArtifactVerificationError("artifact_bundle_invalid")
        return verify_artifact(
            root=bundle,
            manifest=manifest,
            signature_base64=encoded_signature,
            key_id=key_id,
            public_keys=self.public_keys,
        )


def _artifact_ref(value: Any, slot: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise ArtifactVerificationError(f"deployment_{slot}_invalid")
    artifact_id = _safe_identifier(value.get("artifact_id"), "artifact_id")
    version = _safe_identifier(value.get("version"), "version")
    return artifact_id, version


def select_deployment(
    *,
    store: SignedArtifactStore,
    deployment: dict[str, Any],
    slot: str = "champion",
    challenger_index: int = 0,
) -> DeploymentSelection:
    """Resolve an approved slot; a failed primary selects only the declared safe fallback."""

    use_case_id = str(deployment.get("use_case_id") or "")
    if not use_case_id:
        raise ArtifactVerificationError("deployment_use_case_required")
    if slot not in {"champion", "challenger", "fallback"}:
        raise ArtifactVerificationError("deployment_slot_invalid")

    requested: Any
    if slot == "challenger":
        challengers = deployment.get("challengers")
        if (
            not isinstance(challengers, list)
            or challenger_index < 0
            or challenger_index >= len(challengers)
        ):
            raise ArtifactVerificationError("deployment_challenger_invalid")
        requested = challengers[challenger_index]
    else:
        requested = deployment.get(slot)

    if slot == "fallback" and isinstance(requested, dict) and requested.get("kind") == "code":
        reference = str(requested.get("reference") or "")
        if not reference or len(reference) > 160:
            raise ArtifactVerificationError("deployment_fallback_invalid")
        return DeploymentSelection(slot="fallback", artifact=None, fallback_ref=reference)

    try:
        artifact_id, version = _artifact_ref(requested, slot)
        artifact = store.load(artifact_id=artifact_id, version=version)
        manifest = artifact.manifest
        if manifest.get("use_case_id") != use_case_id:
            raise ArtifactVerificationError("deployment_use_case_mismatch")
        allowed_states = {
            "champion": {"champion"},
            "challenger": {"shadow", "pilot", "challenger"},
            "fallback": {"pilot", "challenger", "champion"},
        }[slot]
        if manifest.get("release_state") not in allowed_states:
            raise ArtifactVerificationError("deployment_release_state_invalid")
        return DeploymentSelection(slot=slot, artifact=artifact, fallback_ref=None)
    except ArtifactVerificationError as primary_error:
        if slot == "fallback":
            raise
        fallback = deployment.get("fallback")
        if not isinstance(fallback, dict):
            raise
        selected = select_deployment(store=store, deployment=deployment, slot="fallback")
        return DeploymentSelection(
            slot=selected.slot,
            artifact=selected.artifact,
            fallback_ref=selected.fallback_ref,
            fallback_reason=str(primary_error),
        )
