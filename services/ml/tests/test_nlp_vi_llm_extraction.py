from __future__ import annotations

from types import SimpleNamespace

from clara_ml.nlp_vi import enrich_clinical_utterance_with_llm
from clara_ml.nlp_vi import llm_extraction


def _settings(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        clinical_language_llm_extraction_enabled=enabled,
        model_registry_enabled=True,
        model_registry_task_model_routing_enabled=True,
        deepseek_model="deepseek-v4-pro",
        deepseek_pro_model="deepseek-v4-pro",
        deepseek_flash_model="deepseek-v4-flash",
        deepseek_fallback_model="deepseek-v4-flash",
    )


def test_clinical_llm_packet_is_disabled_by_default() -> None:
    packet = enrich_clinical_utterance("Tôi đang uống Panadol", settings=_settings(enabled=False))

    assert packet.implementation == "deterministic_fallback_v1"
    assert packet.source_spans == []


def test_clinical_llm_packet_accepts_only_exact_source_spans(monkeypatch) -> None:
    text = "Mẹ tôi không khó thở, đang uống Panadol."
    start = text.index("Panadol")

    class Client:
        def generate(self, *_args, **_kwargs):
            import hashlib

            return SimpleNamespace(
                content=(
                    '{"source_text_checksum":"'
                    + hashlib.sha256(text.encode()).hexdigest()
                    + '","spans":[{"category":"medication","start":'
                    + str(start)
                    + ',"end":'
                    + str(start + len("Panadol"))
                    + ',"negated":false,"experiencer":"family",'
                    '"temporality":"current","severity":null}]}'
                )
            )

    selection = SimpleNamespace(
        model_version="deepseek-v4-flash.task-route.v1",
        prompt_version="clinical-language-source-spans.vi.v1",
    )
    monkeypatch.setattr(llm_extraction, "build_task_client", lambda *_args: (Client(), selection))

    packet = enrich_clinical_utterance(text, settings=_settings(enabled=True))

    assert packet.implementation == "hybrid_source_spans_v1"
    assert packet.source_spans[0].category == "medication"
    assert text[packet.source_spans[0].start : packet.source_spans[0].end] == "Panadol"
    assert packet.extractor_model_version == "deepseek-v4-flash.task-route.v1"


def test_clinical_llm_packet_fails_soft_for_hallucinated_offsets(monkeypatch) -> None:
    class Client:
        def generate(self, *_args, **_kwargs):
            return SimpleNamespace(
                content=(
                    '{"source_text_checksum":"wrong","spans":['
                    '{"category":"medication","start":0,"end":999,"negated":false,'
                    '"experiencer":"self","temporality":"current","severity":null}]}'
                )
            )

    selection = SimpleNamespace(model_version="v4", prompt_version="v1")
    monkeypatch.setattr(llm_extraction, "build_task_client", lambda *_args: (Client(), selection))

    packet = enrich_clinical_utterance("Tôi uống para", settings=_settings(enabled=True))

    assert packet.implementation == "deterministic_fallback_v1"
    assert packet.source_spans == []
