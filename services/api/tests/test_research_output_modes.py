"""Focused contracts for the post-release Research presentation switch.

These tests cover only deterministic projection boundaries. They intentionally
do not call an LLM, retrieval provider, or database worker.
"""

from types import SimpleNamespace

from clara_api.api.v1.endpoints import research as research_endpoint


def _released_result() -> dict[str, object]:
    return {
        "answer": "Released answer.",
        "answer_markdown": "Released answer.",
        "citations": [{"source_id": "pmid:1", "title": "Source"}],
        "quality_gate": {"passed": True},
        "metadata": {"output_mode": "professional"},
        "output_mode": "professional",
    }


def test_professional_presentation_is_post_release_and_citation_preserving(monkeypatch) -> None:
    monkeypatch.setattr(
        research_endpoint,
        "get_settings",
        lambda: SimpleNamespace(research_output_modes_enabled=True),
    )
    result = _released_result()

    projected = research_endpoint._attach_verified_research_presentation(
        result,
        request_payload={"output_mode": "professional", "role": "doctor"},
    )

    assert projected["answer_markdown"] == result["answer_markdown"]
    assert projected["citations"] == result["citations"]
    assert projected["presentation"] == {
        "schema_version": "research-presentation-v1",
        "mode": "professional",
        "answer_markdown": "Released answer.",
        "citation_ids": ["pmid:1"],
        "citation_visibility": "expanded",
    }


def test_failed_release_never_gets_a_presentation_even_when_requested(monkeypatch) -> None:
    monkeypatch.setattr(
        research_endpoint,
        "get_settings",
        lambda: SimpleNamespace(research_output_modes_enabled=True),
    )
    result = _released_result()
    result["quality_gate"] = {"passed": False, "reasons": ["unsupported_claims"]}

    projected = research_endpoint._attach_verified_research_presentation(
        result,
        request_payload={"output_mode": "professional", "role": "doctor"},
    )

    assert "presentation" not in projected
    assert projected["answer_markdown"] == "Released answer."
