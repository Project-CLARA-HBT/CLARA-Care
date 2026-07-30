"""Focused regression tests for typed model-task routing and rollback."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from clara_ml.llm.model_registry import (
    FLASH_MODEL_VERSION,
    PRIMARY_MODEL_VERSION,
    ROLLBACK_MODEL_VERSION,
    TASK_CONTRACTS,
    TASK_CONTRACT_SCHEMA_VERSION,
    ModelTask,
    build_asr_task_client,
    build_task_client,
    load_task_contracts,
    resolve_encoder_shadow_selection,
    resolve_asr_model_selection,
    resolve_asr_provider_selection,
    resolve_model_selection,
)


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "deepseek_api_key": "test-key",
        "deepseek_base_url": "https://example.invalid/v1",
        "deepseek_model": "deepseek-primary",
        "deepseek_pro_model": "deepseek-v4-pro",
        "deepseek_flash_model": "deepseek-v4-flash",
        "deepseek_fallback_model": "",
        "model_registry_enabled": True,
        "model_registry_task_model_routing_enabled": True,
        "model_registry_force_rollback": False,
        "model_registry_rollback_model": "",
        "deepseek_timeout_seconds": 45.0,
        "deepseek_retries_per_base": 2,
        "deepseek_retry_backoff_seconds": 0.25,
        "llm_global_max_concurrency": 2,
        "llm_global_min_interval_seconds": 0.4,
        "llm_global_jitter_seconds": 0.15,
        "deepseek_audio_base_url": "https://audio.example.invalid/v1",
        "deepseek_audio_model": "whisper-1",
        "scribe_asr_primary": "whisper",
        "scribe_asr_fallback": "whisper",
        "scribe_phowhisper_model": "phowhisper-large",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_all_registered_tasks_have_closed_output_and_safe_fallback_contracts() -> None:
    assert TASK_CONTRACT_SCHEMA_VERSION == "clara.task-contracts.v2"
    assert set(TASK_CONTRACTS) == set(ModelTask)
    for task, contract in TASK_CONTRACTS.items():
        assert contract.task is task
        assert contract.prompt_version
        assert contract.output_contract
        assert contract.safety_fallback
        assert contract.risk_level in {"low", "medium", "high", "critical"}
        assert contract.allowed_model_tiers
        assert contract.model_profile in {"pro", "flash"}
        assert 0 <= contract.temperature <= 1
        assert contract.max_tokens >= 0
        assert 0 <= contract.human_review_below <= 1


def test_checked_in_task_contract_manifest_is_the_runtime_source_of_truth() -> None:
    schema_version, loaded = load_task_contracts()

    assert schema_version == TASK_CONTRACT_SCHEMA_VERSION
    assert loaded == TASK_CONTRACTS


def test_research_tasks_have_closed_json_contracts() -> None:
    for task in (ModelTask.RESEARCH_QUERY_PLANNING, ModelTask.RESEARCH_REASONING):
        contract = TASK_CONTRACTS[task]
        assert "json" in contract.output_contract
        assert contract.safety_fallback


def test_default_selection_routes_critical_tasks_to_deepseek_v4_pro() -> None:
    selection = resolve_model_selection(
        ModelTask.LIFEMAP_CAPTURE_TRIAGE,
        _settings(),
    )

    assert selection.provider == "deepseek"
    assert selection.model == "deepseek-v4-pro"
    assert selection.model_version == PRIMARY_MODEL_VERSION
    assert selection.prompt_version == "lifemap-capture-triage.v1"
    assert selection.contract_schema_version == "clara.task-contracts.v2"
    assert selection.risk_level == "critical"
    assert selection.rollback_applied is False
    assert selection.model_profile == "pro"
    assert selection.fallback_model == "deepseek-v4-flash"


def test_bounded_low_latency_tasks_route_to_deepseek_v4_flash() -> None:
    selection = resolve_model_selection(ModelTask.RAG_RERANKING, _settings())

    assert selection.model == "deepseek-v4-flash"
    assert selection.model_version == FLASH_MODEL_VERSION
    assert selection.model_profile == "flash"
    assert selection.fallback_model == "deepseek-v4-pro"


def test_task_routing_kill_switch_restores_configured_legacy_model() -> None:
    selection = resolve_model_selection(
        ModelTask.RAG_RERANKING,
        _settings(model_registry_task_model_routing_enabled=False),
    )

    assert selection.model == "deepseek-primary"
    assert selection.model_profile == "legacy"


def test_rollback_needs_an_explicit_prior_model_and_never_fakes_it() -> None:
    unavailable = resolve_model_selection(
        ModelTask.MEDICAL_SAFETY_ROUTER,
        _settings(model_registry_force_rollback=True),
    )
    assert unavailable.model == "deepseek-v4-pro"
    assert unavailable.rollback_applied is False
    assert unavailable.model_version == PRIMARY_MODEL_VERSION

    rolled_back = resolve_model_selection(
        ModelTask.MEDICAL_SAFETY_ROUTER,
        _settings(
            model_registry_force_rollback=True,
            model_registry_rollback_model="deepseek-previous",
        ),
    )
    assert rolled_back.model == "deepseek-previous"
    assert rolled_back.rollback_applied is True
    assert rolled_back.model_version == ROLLBACK_MODEL_VERSION


def test_kill_switch_preserves_primary_even_if_rollback_is_requested() -> None:
    selection = resolve_model_selection(
        ModelTask.SCRIBE_NOTE,
        _settings(
            model_registry_enabled=False,
            model_registry_force_rollback=True,
            model_registry_rollback_model="deepseek-previous",
        ),
    )
    assert selection.registry_enabled is False
    assert selection.model == "deepseek-primary"
    assert selection.rollback_applied is False


def test_task_client_uses_selected_rollback_and_keeps_audio_endpoint_scoped() -> None:
    client, selection = build_task_client(
        ModelTask.SCRIBE_TRANSCRIPTION,
        _settings(
            model_registry_force_rollback=True,
            model_registry_rollback_model="deepseek-previous",
        ),
        timeout_seconds=90.0,
        retries_per_base=0,
        audio=True,
    )

    assert selection.rollback_applied is True
    assert client.model == "deepseek-previous"
    assert client._timeout_seconds == 90.0
    assert client._retries_per_base == 0
    assert client._audio_base_urls == ["https://audio.example.invalid/v1"]


def test_asr_payload_model_is_registry_owned_and_not_a_v4_text_route() -> None:
    client, selection = build_asr_task_client(
        _settings(),
        timeout_seconds=90.0,
        retries_per_base=0,
    )

    assert selection.task is ModelTask.SCRIBE_TRANSCRIPTION
    assert selection.provider == "deepseek_audio"
    assert selection.model == "whisper-1"
    assert selection.model_version == "whisper-1.audio.v1"
    assert client.model == selection.model
    assert client._audio_base_urls == ["https://audio.example.invalid/v1"]


def test_asr_selection_fails_closed_when_audio_model_is_missing() -> None:
    with pytest.raises(ValueError, match="deepseek_audio_model_required"):
        resolve_asr_model_selection(_settings(deepseek_audio_model=""))


def test_asr_provider_selection_is_allowlisted_and_deduplicates_same_fallback() -> None:
    selection = resolve_asr_provider_selection(
        _settings(
            scribe_asr_primary="not-a-provider",
            scribe_asr_fallback="whisper",
        )
    )

    assert selection.primary.provider == "whisper"
    assert selection.primary.model == "whisper-1"
    assert selection.fallback is None


def test_asr_provider_selection_keeps_an_independent_phowhisper_fallback() -> None:
    selection = resolve_asr_provider_selection(
        _settings(
            scribe_asr_primary="phowhisper",
            scribe_asr_fallback="google_stt_v2",
        )
    )

    assert selection.primary.provider == "phowhisper"
    assert selection.primary.model == "phowhisper-large"
    assert selection.fallback is not None
    assert selection.fallback.provider == "google_stt_v2_chirp3"
    assert selection.fallback.model == "chirp_3"


def test_model_selection_telemetry_excludes_connection_values(
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="clara_ml.llm.model_registry")
    build_task_client(ModelTask.RAG_RERANKING, _settings())

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "model_task_selected" in rendered
    assert "task=rag_reranking" in rendered
    assert "profile=flash" in rendered
    assert "test-key" not in rendered
    assert "example.invalid" not in rendered


def test_encoder_shadow_selection_is_registry_governed_and_never_a_primary_route() -> None:
    selection = resolve_encoder_shadow_selection(
        _settings(
            encoder_slm_shadow_enabled=True,
            encoder_slm_shadow_url="http://encoder.example.invalid/v1/route",
            encoder_slm_shadow_api_key="encoder-test-key",
            encoder_slm_shadow_model_id="vi-clinical-encoder-2026-07",
        )
    )

    assert selection.task is ModelTask.ENCODER_SLM_SHADOW
    assert selection.state == "available"
    assert selection.prompt_version == "encoder-slm-shadow.v1"
    assert TASK_CONTRACTS[selection.task].shadow_only is True
    assert TASK_CONTRACTS[selection.task].allowed_model_tiers == ("encoder_slm",)
    assert selection.endpoint == "http://encoder.example.invalid/v1/route"


def test_encoder_shadow_registry_kill_switch_keeps_network_adapter_disabled() -> None:
    selection = resolve_encoder_shadow_selection(
        _settings(
            model_registry_enabled=False,
            encoder_slm_shadow_enabled=True,
            encoder_slm_shadow_url="http://encoder.example.invalid/v1/route",
        )
    )

    assert selection.state == "disabled"
    assert selection.reason == "model_registry_disabled"


def test_encoder_shadow_task_cannot_be_built_as_a_deepseek_primary_client() -> None:
    with pytest.raises(ValueError, match="encoder_shadow_requires_dedicated_registry_adapter"):
        build_task_client(ModelTask.ENCODER_SLM_SHADOW, _settings())
