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
    assert first_row["support_status"] == "insufficient"
    assert first_row["claim_type"] in {"interaction", "general", "dosage", "contraindication"}
    assert first_row["evidence_ref"] is None
    assert result.contradiction_summary["has_contradiction"] is False
    assert result.fide_report["verification_matrix"]["summary"]["version"] == "claim-v2-nli"


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
    assert first_row["claim_type"] in {"interaction", "general", "dosage", "contraindication"}
    assert first_row["overlap_score"] > 0
    assert first_row["confidence"] > 0
    assert first_row["evidence_ref"] == "doc-1"
    assert first_row["evidence_snippet"]
    assert first_row["rationale"]
    assert result.contradiction_summary["has_contradiction"] is False


def test_fides_lite_heuristic_polarity_mismatch_is_insufficient() -> None:
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
    assert result.verdict == "warn"
    assert result.contradiction_summary["has_contradiction"] is False
    assert result.contradiction_summary["contradiction_count"] == 0
    matrix_row = result.verification_matrix[0]
    assert matrix_row["support_status"] == "insufficient"
    assert matrix_row["evidence_ref"] == "doc-2"
    assert matrix_row["rationale"]


def test_fides_lite_preserves_hyphenated_medical_entities() -> None:
    answer = (
        "DAPA-CKD and EMPA-KIDNEY studied SGLT2 inhibitors in non-diabetic "
        "chronic kidney disease and end-stage outcomes."
    )
    result = run_fides_lite(
        answer=answer,
        retrieved_context=[{"id": "trial-1", "source": "pubmed", "text": answer}],
    )

    assert result.total_claims == 1
    assert result.verification_matrix[0]["claim"] == answer.removesuffix(".")
