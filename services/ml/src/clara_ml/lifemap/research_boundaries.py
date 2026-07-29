"""Fail-closed boundary between product LifeMap and high-risk AI research."""

from __future__ import annotations

from dataclasses import dataclass

HIGH_RISK_RESEARCH_CAPABILITIES = frozenset(
    {
        "disease_prediction",
        "deterioration_prediction",
        "individual_treatment_effect",
        "digital_twin",
        "raw_waveform_foundation_model",
        "federated_learning",
        "split_learning",
        "continuous_online_learning",
    }
)


class ResearchBoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class ResearchProjectAuthority:
    project_id: str
    capability: str
    intended_use_approval: str
    regulatory_review: str
    privacy_security_review: str
    dataset_approval: str
    prospective_protocol: str
    production_flag: None = None


def require_research_authority(
    capability: str,
    authority: ResearchProjectAuthority | None,
) -> ResearchProjectAuthority:
    if capability not in HIGH_RISK_RESEARCH_CAPABILITIES:
        raise ResearchBoundaryError("research_capability_unknown")
    if authority is None:
        raise ResearchBoundaryError("separate_research_project_required")
    if authority.capability != capability:
        raise ResearchBoundaryError("research_authority_capability_mismatch")
    required = (
        authority.project_id,
        authority.intended_use_approval,
        authority.regulatory_review,
        authority.privacy_security_review,
        authority.dataset_approval,
        authority.prospective_protocol,
    )
    if any(not value for value in required) or authority.production_flag is not None:
        raise ResearchBoundaryError("research_authority_incomplete_or_product_linked")
    return authority


@dataclass(frozen=True)
class FederatedThreatModel:
    gradient_leakage: bool
    non_iid_bias: bool
    poisoning: bool
    secure_aggregation: bool
    differential_privacy: bool
    withdrawal_deletion: bool
    device_energy: bool
    reproducibility: bool


def validate_federated_threat_model(model: FederatedThreatModel) -> None:
    if not all(model.__dict__.values()):
        raise ResearchBoundaryError("federated_threat_model_incomplete")
