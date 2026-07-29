import pytest

from clara_ml.lifemap.research_boundaries import (
    FederatedThreatModel,
    ResearchBoundaryError,
    ResearchProjectAuthority,
    require_research_authority,
    validate_federated_threat_model,
)


@pytest.mark.parametrize(
    "capability",
    (
        "disease_prediction",
        "deterioration_prediction",
        "individual_treatment_effect",
        "digital_twin",
        "raw_waveform_foundation_model",
        "federated_learning",
        "split_learning",
        "continuous_online_learning",
    ),
)
def test_high_risk_capability_cannot_use_generic_product_flag(capability: str) -> None:
    with pytest.raises(ResearchBoundaryError, match="separate_research"):
        require_research_authority(capability, None)


def test_separate_authority_has_no_product_flag() -> None:
    authority = ResearchProjectAuthority(
        project_id="research-project-1",
        capability="digital_twin",
        intended_use_approval="intended-use-1",
        regulatory_review="regulatory-1",
        privacy_security_review="privacy-security-1",
        dataset_approval="dataset-1",
        prospective_protocol="protocol-1",
    )
    assert require_research_authority("digital_twin", authority) == authority
    assert authority.production_flag is None


def test_federated_research_requires_complete_threat_model() -> None:
    complete = FederatedThreatModel(True, True, True, True, True, True, True, True)
    validate_federated_threat_model(complete)
    with pytest.raises(ResearchBoundaryError, match="incomplete"):
        validate_federated_threat_model(
            FederatedThreatModel(True, True, True, False, True, True, True, True)
        )
