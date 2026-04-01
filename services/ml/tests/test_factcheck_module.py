from clara_ml.factcheck import run_fides_lite


def test_fides_lite_warns_when_no_evidence() -> None:
    result = run_fides_lite(
        answer="Paracetamol co the lam tang nguy co chay mau khi dung cung warfarin.",
        retrieved_context=[],
    )
    assert result.verdict == "warn"
    assert result.severity == "high"
    assert result.evidence_count == 0
    assert len(result.verification_matrix) >= 1
    first_row = result.verification_matrix[0]
    assert first_row["support_status"] == "unsupported"
    assert first_row["evidence_ref"] is None
    assert result.contradiction_summary["has_contradiction"] is False


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
    assert len(result.verification_matrix) >= 1
    first_row = result.verification_matrix[0]
    assert first_row["claim"]
    assert first_row["support_status"] == "supported"
    assert first_row["overlap_score"] > 0
    assert first_row["confidence"] > 0
    assert first_row["evidence_ref"] == "doc-1"
    assert first_row["evidence_snippet"]
    assert result.contradiction_summary["has_contradiction"] is False


def test_fides_lite_detects_contradiction_and_exports_details() -> None:
    result = run_fides_lite(
        answer="Paracetamol khong lam tang nguy co chay mau khi dung cung warfarin.",
        retrieved_context=[
            {
                "id": "doc-2",
                "text": (
                    "Tai lieu cho thay paracetamol co the tang nguy co chay mau "
                    "khi dung cung warfarin."
                ),
                "source": "pubmed",
            }
        ],
    )
    assert result.verdict == "fail"
    assert result.contradiction_summary["has_contradiction"] is True
    assert result.contradiction_summary["contradiction_count"] >= 1
    assert len(result.contradiction_summary["details"]) >= 1
    matrix_row = result.verification_matrix[0]
    assert matrix_row["support_status"] == "contradicted"
    assert matrix_row["evidence_ref"] == "doc-2"
