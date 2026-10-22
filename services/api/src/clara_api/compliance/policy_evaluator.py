"""Purpose-Based Consent Policy Evaluator.

Part of Phase PH05 / Subagent A03 (Domain + GLHS Services).
Enforces:
1. Multi-purpose consent gating prior to medical data processing.
2. Delegated authority checks (patient self vs family circle / guardian proxy).
3. Fail-closed rejection of processing intents without verified active consent.
"""

from __future__ import annotations

import dataclasses
from typing import Literal

from sqlalchemy.orm import Session

from clara_api.compliance.consent import (
    PURPOSE_AI_TRANSPARENCY,
    PURPOSE_CORE_SERVICE,
    PURPOSE_CROSS_BORDER,
    PURPOSE_PERSONALIZATION,
    PURPOSE_RESEARCH,
    PURPOSE_SHARING,
    has_consent,
)
from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    get_latest_user_consent,
    required_medical_disclaimer_version,
)

PolicyDecision = Literal["allow", "deny", "require_reconsent"]


@dataclasses.dataclass(frozen=True)
class PolicyEvaluationResult:
    decision: PolicyDecision
    intent: str
    missing_purposes: list[str]
    reason: str
    authority_valid: bool = True


# Intent to required purposes mapping (PDPD Vietnam & AI Law compliance)
INTENT_PURPOSE_REQUIREMENTS: dict[str, list[str]] = {
    "CLINICAL_CHAT_INFERENCE": [PURPOSE_CORE_SERVICE, PURPOSE_AI_TRANSPARENCY],
    "MEDICINE_DDI_CHECK": [PURPOSE_CORE_SERVICE],
    "RESEARCH_TIER2_SYNTHESIS": [PURPOSE_CORE_SERVICE, PURPOSE_RESEARCH],
    "CROSS_BORDER_MODEL_DISPATCH": [PURPOSE_CORE_SERVICE, PURPOSE_CROSS_BORDER],
    "FAMILY_RECORD_SHARING": [PURPOSE_CORE_SERVICE, PURPOSE_SHARING],
}


class PurposePolicyEvaluator:
    """Evaluates data processing requests against active consent ledger and authority rules."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate_intent(
        self,
        *,
        user_id: int,
        intent: str,
        actor_relationship: str = "self",  # "self", "parent", "guardian", "proxy"
    ) -> PolicyEvaluationResult:
        # 1. Authority validation
        if actor_relationship not in {"self", "parent", "guardian", "proxy"}:
            return PolicyEvaluationResult(
                decision="deny",
                intent=intent,
                missing_purposes=[],
                reason=f"Invalid actor authority relationship: {actor_relationship}",
                authority_valid=False,
            )

        # 2. Medical disclaimer baseline check
        required_version = required_medical_disclaimer_version()
        med_consent = get_latest_user_consent(self.db, user_id=user_id, consent_type=MEDICAL_CONSENT_TYPE)
        if not med_consent or med_consent.consent_version != required_version or med_consent.revoked_at is not None:
            return PolicyEvaluationResult(
                decision="require_reconsent",
                intent=intent,
                missing_purposes=["medical_disclaimer"],
                reason=f"Medical disclaimer version {required_version} not accepted or revoked",
            )

        # 3. Purpose requirements evaluation
        required_purposes = INTENT_PURPOSE_REQUIREMENTS.get(intent, [PURPOSE_CORE_SERVICE])
        missing: list[str] = []
        for purpose in required_purposes:
            if not has_consent(self.db, user_id=user_id, purpose=purpose):
                missing.append(purpose)

        if missing:
            return PolicyEvaluationResult(
                decision="deny",
                intent=intent,
                missing_purposes=missing,
                reason=f"Missing required consent purpose(s): {', '.join(missing)}",
            )

        return PolicyEvaluationResult(
            decision="allow",
            intent=intent,
            missing_purposes=[],
            reason="All required consent purposes granted and active",
        )
