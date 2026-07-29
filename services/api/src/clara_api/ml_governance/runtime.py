"""Server-owned resolution for signed local artifacts and immutable provider IDs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clara_api.core.config import Settings
from clara_api.ml_governance.artifacts import (
    ArtifactVerificationError,
    DeploymentSelection,
    SignedArtifactStore,
    select_deployment,
)
from clara_api.ml_governance.provider_identity import (
    ProviderIdentityError,
    ProviderModelIdentity,
    resolve_provider_model,
)


class RuntimeGovernanceError(ValueError):
    pass


def _json_object(raw: str, code: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeGovernanceError(code) from error
    if not isinstance(value, dict):
        raise RuntimeGovernanceError(code)
    return value


def build_signed_artifact_store(settings: Settings) -> SignedArtifactStore:
    keys = _json_object(
        settings.ml_artifact_public_keys_json,
        "artifact_public_keys_invalid",
    )
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in keys.items()):
        raise RuntimeGovernanceError("artifact_public_keys_invalid")
    return SignedArtifactStore(
        root=Path(settings.ml_artifact_root),
        public_keys={str(key): str(value) for key, value in keys.items()},
    )


def load_deployment_selection(
    settings: Settings,
    *,
    use_case_id: str,
    slot: str = "champion",
    challenger_index: int = 0,
) -> DeploymentSelection:
    """Load a code/config-owned deployment and verify the selected bytes."""

    if not settings.ml_deployment_manifest_path:
        raise RuntimeGovernanceError("deployment_manifest_not_configured")
    manifest_path = Path(settings.ml_deployment_manifest_path).resolve()
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeGovernanceError("deployment_manifest_invalid") from error
    if not isinstance(document, dict) or document.get("schema_version") != "1":
        raise RuntimeGovernanceError("deployment_manifest_invalid")
    deployments = document.get("deployments")
    if not isinstance(deployments, list):
        raise RuntimeGovernanceError("deployment_manifest_invalid")
    matches = [
        item
        for item in deployments
        if isinstance(item, dict) and item.get("use_case_id") == use_case_id
    ]
    if len(matches) != 1:
        raise RuntimeGovernanceError("deployment_use_case_not_unique")
    try:
        return select_deployment(
            store=build_signed_artifact_store(settings),
            deployment=matches[0],
            slot=slot,
            challenger_index=challenger_index,
        )
    except ArtifactVerificationError as error:
        raise RuntimeGovernanceError(str(error)) from error


def resolve_immutable_provider_model(
    settings: Settings,
    *,
    provider: str,
    configured_model: str,
) -> ProviderModelIdentity:
    """Resolve aliases only through the server-owned immutable allowlist."""

    document = _json_object(
        settings.ml_provider_model_allowlist_json,
        "provider_allowlist_invalid",
    )
    allowlist: dict[str, ProviderModelIdentity] = {}
    for alias, value in document.items():
        if not isinstance(alias, str) or not isinstance(value, dict):
            raise RuntimeGovernanceError("provider_allowlist_invalid")
        try:
            allowlist[alias] = ProviderModelIdentity(
                provider=str(value["provider"]),
                alias=alias,
                immutable_id=str(value["immutable_id"]),
                endpoint_class=str(value["endpoint_class"]),
            )
        except KeyError as error:
            raise RuntimeGovernanceError("provider_allowlist_invalid") from error
    try:
        return resolve_provider_model(
            provider=provider,
            configured_model=configured_model,
            allowlist=allowlist,
        )
    except ProviderIdentityError as error:
        raise RuntimeGovernanceError(str(error)) from error
