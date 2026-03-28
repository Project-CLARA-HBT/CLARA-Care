from clara_ml.factcheck import run_fides_lite


def test_fides_lite_warns_when_no_evidence() -> None:
    result = run_fides_lite(
        answer="Paracetamol co the lam tang nguy co chay mau khi dung cung warfarin.",
        retrieved_context=[],
    )
    assert result.verdict == "warn"
    assert result.severity == "high"
    assert result.evidence_count == 0


def test_fides_lite_passes_when_claim_matches_evidence() -> None:
    result = run_fides_lite(
        answer="Paracetamol co the tang nguy co chay mau khi dung cung warfarin.",
        retrieved_context=[
            {
                "id": "doc-1",
                "text": "Tai lieu cho thay paracetamol co the tang nguy co chay mau khi dung cung warfarin.",
                "source": "pubmed",
            }
        ],
    )
    assert result.verdict == "pass"
    assert result.severity == "low"
    assert result.supported_claims >= 1
