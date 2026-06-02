# Day 4 NLI Verifier Contract

Date: 2026-04-02  
Scope: Phase 1 Day 4 (claim-level NLI verifier + verification matrix chuẩn hóa)

## 1) Mục tiêu
- Chuẩn hóa bước verification theo claim-level.
- Trả verdict nhất quán: `supported | contradicted | insufficient`.
- Giữ tương thích ngược cho UI/API đang dùng `unsupported_claims`.

## 2) Module mới
- File: `services/ml/src/clara_ml/factcheck/nli_verifier.py`
- Public APIs:
  - `verify_claims(claims, evidence_rows, support_threshold=0.2)`
  - `summarize_verification_matrix(rows, total_claims)`
  - `build_contradiction_summary(rows)`

## 3) Row Contract (verification matrix)
Mỗi row có:
- `claim: string`
- `claim_type: dosage | interaction | contraindication | general`
- `support_status: supported | contradicted | insufficient`
- `confidence: float`
- `overlap_score: float`
- `evidence_ref: string | null`
- `evidence_snippet: string`
- `rationale: string`

## 4) Summary Contract
- `version: "claim-v2-nli"`
- `total_claims`
- `supported_claims`
- `insufficient_claims`
- `unsupported_claims` (alias = `insufficient_claims` để backward-compatible)
- `contradicted_claims`
- `support_ratio`

## 5) Contradiction Summary
- `version: "claim-v2-nli"`
- `has_contradiction`
- `contradiction_count`
- `claims[]`
- `details[]` (gồm `claim_type`, `confidence`, `rationale`, `evidence_ref`)
- `note`

## 6) Runtime flags liên quan
- `RAG_NLI_ENABLED`
- `RAG_NLI_TIMEOUT_MS`
- `RAG_NLI_MIN_CONFIDENCE`

## 7) Ghi chú tương thích
- `research_tier2` compact/summarize đã map `unsupported -> insufficient`.
- Payload vẫn duy trì `unsupported_claims` để không gãy UI cũ.
