# Runbook: Scientific Claim Linkage & Clinical Incident Support (PH49)

## 1. Overview
Governs operational procedures for investigating clinical adverse events, regulatory audits, and reconstructing non-repudiable GLHS R4 attestation traces for health authorities.

## 2. Evidence Linkage Protocol
Every automated AI recommendation must maintain unambiguous cryptographic linkage to its underlying scientific sources:
1. **Source Evidence Registration:** All consulted guidelines are indexed in `knowledge_sources` with a verified SHA-256 content digest.
2. **Snapshot Ingestion:** At inference time, clinical data is bound into a Temporal Health State Snapshot (THSS) with digest $D_1$ (`H_proj`).
3. **Application Envelope:** Prompt templates and model configurations are sealed into $D_2$ (`H_sem`).
4. **Transport Receipt:** Outbound socket bytes and provider signatures are recorded in $D_3$ (`H_trans`).

## 3. Incident Investigation & Forensic Export Procedure
When a clinical incident or diagnostic discrepancy is reported:
1. **Lookup Commitment Public ID:**
   ```sql
   SELECT id, public_id, semantic_key, domain FROM glhs_clinical_commitments WHERE public_id = :commitment_id;
   ```
2. **Extract Complete Lineage Chain:**
   ```bash
   python3 -m clara_api.ops.export_glhs_trace \
     --commitment-id "com-12345" \
     --output "incident_trace_com-12345.json"
   ```
3. **Verify Cryptographic Chain Integrity:**
   ```bash
   python3 -m clara_api.ops.verify_trace_integrity --file "incident_trace_com-12345.json"
   ```
   **Verification Criteria:**
   - D1 matches stored snapshot manifest digest.
   - D3 matches network transport log.
   - Attestation level satisfies policy requirement ($L2 \ge \text{PROVIDER\_RECEIPT\_VERIFIED}$).
   - Human reviewer signature and timestamp are present.
