"""Server-authoritative, content-free client vocabulary for LifeMap."""

from __future__ import annotations

from typing import Any

from clara_api.core.config import Settings

CLIENT_CONTRACT_VERSION = "lifemap-client-contract-v1"

STATE_VOCABULARY: dict[str, dict[str, Any]] = {
    "draft": {
        "truth_authority": False,
        "can_mutate": True,
        "vi": "Bản nháp",
        "en": "Draft",
    },
    "awaiting_review": {
        "truth_authority": False,
        "can_mutate": True,
        "vi": "Chờ xem lại",
        "en": "Awaiting review",
    },
    "confirmed": {
        "truth_authority": True,
        "can_mutate": True,
        "vi": "Đã xác nhận",
        "en": "Confirmed",
    },
    "disputed": {
        "truth_authority": False,
        "can_mutate": True,
        "vi": "Đang có tranh chấp",
        "en": "Disputed",
    },
    "stale": {
        "truth_authority": False,
        "can_mutate": False,
        "vi": "Có thể đã cũ",
        "en": "May be stale",
    },
    "unavailable": {
        "truth_authority": False,
        "can_mutate": False,
        "vi": "Không khả dụng",
        "en": "Unavailable",
    },
    "offline": {
        "truth_authority": False,
        "can_mutate": False,
        "vi": "Ngoại tuyến",
        "en": "Offline",
    },
}


def build_client_contract(settings: Settings) -> dict[str, Any]:
    capabilities = {
        "lifemap_v2": settings.lifemap_v2_enabled,
        "capture": settings.lifemap_capture_enabled,
        "baselines": settings.lifemap_baselines_v2_enabled,
        "next_question": settings.lifemap_next_question_v2_enabled,
        "replay": settings.lifemap_replay_v2_enabled,
        "visit_extraction": settings.lifemap_visit_extraction_enabled,
        "evidence_monitor": settings.lifemap_evidence_monitor_enabled,
        "fhir_export": settings.lifemap_fhir_export_enabled,
        "fhir_import": settings.lifemap_fhir_import_enabled,
    }
    return {
        "version": CLIENT_CONTRACT_VERSION,
        "states": STATE_VOCABULARY,
        "capabilities": {
            key: {
                "enabled": enabled,
                "mutation_policy": "online_only",
            }
            for key, enabled in capabilities.items()
        },
        "offline_policy": {
            "mutations": "disabled",
            "queued_health_mutations_supported": False,
            "cached_safety_status_current": False,
            "requires_encrypted_cache": True,
            "requires_cached_at": True,
            "requires_valid_until": True,
        },
    }
