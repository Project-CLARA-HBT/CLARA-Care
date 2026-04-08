from clara_ml.factcheck.nli_verifier import (
    build_contradiction_summary,
    infer_claim_type,
    summarize_verification_matrix,
    verify_claims,
)


def test_infer_claim_type_detects_interaction_and_dosage() -> None:
    assert infer_claim_type("Tuong tac warfarin voi ibuprofen") == "interaction"
    assert infer_claim_type("Nen uong lieu 500 mg moi lan") == "dosage"


def test_verify_claims_returns_verdict_objects_with_required_fields() -> None:
    rows = verify_claims(
        claims=["Paracetamol co the tang nguy co chay mau khi dung cung warfarin."],
        evidence_rows=[
            {
                "ref": "doc-1",
                "text": (
                    "Tai lieu cho thay paracetamol co the tang nguy co chay mau "
                    "khi dung cung warfarin."
                ),
            }
        ],
    )
    assert len(rows) == 1
    row = rows[0].as_dict()
    assert row["support_status"] == "supported"
    assert row["claim_type"] in {"interaction", "general"}
    assert row["nli_label"] == "supported"
    assert row["evidence_ref"] == "doc-1"
    assert row["confidence"] > 0


def test_summarize_and_contradiction_summary_contract() -> None:
    matrix_rows = [
        {
            "claim": "A",
            "claim_type": "general",
            "support_status": "supported",
            "nli_label": "supported",
            "confidence": 0.9,
            "overlap_score": 0.5,
            "evidence_ref": "doc-a",
            "evidence_snippet": "snippet a",
        },
        {
            "claim": "B",
            "claim_type": "interaction",
            "support_status": "contradicted",
            "nli_label": "contradicted",
            "confidence": 0.45,
            "overlap_score": 0.33,
            "evidence_ref": "doc-b",
            "evidence_snippet": "snippet b",
        },
    ]
    summary = summarize_verification_matrix(rows=matrix_rows, total_claims=2)
    contradiction = build_contradiction_summary(matrix_rows)

    assert summary["version"] == "claim-v2-nli"
    assert summary["total_claims"] == 2
    assert summary["supported_claims"] == 1
    assert summary["contradicted_claims"] == 1
    assert summary["unsupported_claims"] >= 0
    assert "support_ratio" in summary

    assert contradiction["version"] == "claim-v2-nli"
    assert contradiction["has_contradiction"] is True
    assert contradiction["contradiction_count"] == 1
    assert isinstance(contradiction["details"], list)


def test_verify_claims_llm_override_can_change_verdict() -> None:
    class _FakeLlmClient:
        def generate(self, prompt: str, system_prompt: str | None = None):  # noqa: ARG002
            class _Response:
                content = (
                    '{"rows":[{"claim_index":0,"support_status":"contradicted",'
                    '"confidence":0.77,"evidence_ref":"doc-1","rationale":"Conflict detected"}]}'
                )
                model = "fake-llm"

            return _Response()

    rows = verify_claims(
        claims=["Paracetamol co the tang nguy co chay mau khi dung cung warfarin."],
        evidence_rows=[
            {
                "ref": "doc-1",
                "text": (
                    "Tai lieu cho thay paracetamol co the tang nguy co chay mau "
                    "khi dung cung warfarin."
                ),
            }
        ],
        llm_enabled=True,
        llm_client=_FakeLlmClient(),
    )
    assert len(rows) == 1
    row = rows[0].as_dict()
    assert row["support_status"] == "contradicted"
    assert row["nli_label"] == "contradicted"
    assert row["evidence_ref"] == "doc-1"
    assert row["confidence"] >= 0.7


def test_verify_claims_llm_failure_falls_back_to_heuristic() -> None:
    class _BrokenLlmClient:
        def generate(self, prompt: str, system_prompt: str | None = None):  # noqa: ARG002
            raise RuntimeError("upstream_error")

    rows = verify_claims(
        claims=["Paracetamol co the tang nguy co chay mau khi dung cung warfarin."],
        evidence_rows=[
            {
                "ref": "doc-1",
                "text": (
                    "Tai lieu cho thay paracetamol co the tang nguy co chay mau "
                    "khi dung cung warfarin."
                ),
            }
        ],
        llm_enabled=True,
        llm_client=_BrokenLlmClient(),
    )
    assert len(rows) == 1
    row = rows[0].as_dict()
    assert row["support_status"] == "supported"
