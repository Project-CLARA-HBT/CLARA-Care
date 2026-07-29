"""Immutable provider-model resolution; aliases cannot silently change."""

from __future__ import annotations

from dataclasses import dataclass


class ProviderIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderModelIdentity:
    provider: str
    alias: str
    immutable_id: str
    endpoint_class: str

    @property
    def reference(self) -> str:
        return f"{self.provider}:{self.immutable_id}"


def resolve_provider_model(
    *,
    provider: str,
    configured_model: str,
    allowlist: dict[str, ProviderModelIdentity],
) -> ProviderModelIdentity:
    identity = allowlist.get(configured_model)
    if identity is None:
        raise ProviderIdentityError("provider_model_not_allowlisted")
    if identity.provider != provider:
        raise ProviderIdentityError("provider_identity_mismatch")
    if not identity.immutable_id or identity.immutable_id == identity.alias:
        raise ProviderIdentityError("provider_model_is_not_immutable")
    return identity


def verify_provider_response(
    identity: ProviderModelIdentity,
    response_model: str | None,
) -> None:
    """Hold/fallback when the provider reports a different immutable identity."""

    if not response_model or response_model != identity.immutable_id:
        raise ProviderIdentityError("provider_model_changed")
