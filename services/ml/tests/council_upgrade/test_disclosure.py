"""Model & fallback disclosure for the CLARA Council upgrade (ML side).

Covers design §E "Disclosure" and Correctness Property **P10** (Requirements
6.1, 6.2, 6.3, 6.5, 9.2):

* ``run_council`` attaches an ``ai_disclosure`` block naming the deterministic
  rule engine (``rule_based_council_v2``) with ``is_fallback = False`` when
  ``COUNCIL_MODEL_DISCLOSURE_ENABLED`` is on, and omits it entirely when off.
* intake disclosure sets ``is_fallback`` true IFF the heuristic/degraded path
  (``heuristic-fallback-v1``) produced the extraction, mirroring the compliance
  model-disclosure family/version split (Requirement 6.6).

Everything here is deterministic and network-free.
"""

from __future__ import annotations

from clara_ml.agents.council import run_council
from clara_ml.agents.council_intake import _build_intake_disclosure

from .harness import council_flags

# A deterministic, non-emergency payload that exercises the full run pipeline
# without any network or red-flag escalation.
_PAYLOAD: dict[str, object] = {
    "symptoms": ["mild fatigue"],
    "labs": {"glucose": 110.0},
    "medications": ["metformin"],
    "history": ["type 2 diabetes"],
    "specialists": ["endocrinology", "cardiology"],
}


class TestRunCouncilDisclosure:
    def test_flag_off_omits_disclosure(self) -> None:
        """Flag OFF (default) ⇒ no ai_disclosure key (byte-equivalent to today)."""
        result = run_council(dict(_PAYLOAD))
        assert "ai_disclosure" not in result

    def test_flag_off_via_payload_override(self) -> None:
        """An explicit payload override of False also omits the block."""
        payload = dict(_PAYLOAD, council_model_disclosure_enabled=False)
        assert "ai_disclosure" not in run_council(payload)

    def test_payload_override_enables_disclosure(self) -> None:
        """Payload override ON ⇒ rule-engine disclosure, never a fallback."""
        payload = dict(_PAYLOAD, council_model_disclosure_enabled=True)
        result = run_council(payload)
        assert result["ai_disclosure"] == {
            "model_family": "council_rule_engine",
            "model_version": "rule_based_council_v2",
            "is_fallback": False,
        }

    def test_settings_flag_enables_disclosure(self) -> None:
        """Settings flag ON ⇒ disclosure attached even with no payload override."""
        with council_flags(council_model_disclosure_enabled=True):
            result = run_council(dict(_PAYLOAD))
        assert result["ai_disclosure"]["model_version"] == "rule_based_council_v2"
        assert result["ai_disclosure"]["is_fallback"] is False

    def test_enabling_disclosure_does_not_mutate_other_keys(self) -> None:
        """Disclosure is purely additive: the rest of the envelope is unchanged."""
        baseline = run_council(dict(_PAYLOAD))
        with council_flags(council_model_disclosure_enabled=True):
            decorated = run_council(dict(_PAYLOAD))
        decorated_without_disclosure = {
            k: v for k, v in decorated.items() if k != "ai_disclosure"
        }
        assert decorated_without_disclosure == baseline


class TestIntakeDisclosure:
    def test_heuristic_fallback_is_flagged(self) -> None:
        """Degraded heuristic extraction ⇒ is_fallback true (Property P10)."""
        disclosure = _build_intake_disclosure("heuristic-fallback-v1")
        assert disclosure == {
            "model_family": "heuristic",
            "model_version": "fallback-v1",
            "is_fallback": True,
        }

    def test_primary_model_is_not_fallback(self) -> None:
        """A real model id ⇒ is_fallback false, family/version split on hyphen."""
        disclosure = _build_intake_disclosure("deepseek-v3.2")
        assert disclosure == {
            "model_family": "deepseek",
            "model_version": "v3.2",
            "is_fallback": False,
        }

    def test_no_hyphen_model_id(self) -> None:
        """A hyphen-free id keeps the whole string as the family."""
        disclosure = _build_intake_disclosure("deepseek")
        assert disclosure["model_family"] == "deepseek"
        assert disclosure["model_version"] == "unknown"
        assert disclosure["is_fallback"] is False

    def test_blank_model_id_is_unknown(self) -> None:
        """A blank/missing id degrades to unknown without claiming fallback."""
        disclosure = _build_intake_disclosure("")
        assert disclosure == {
            "model_family": "unknown",
            "model_version": "unknown",
            "is_fallback": False,
        }
