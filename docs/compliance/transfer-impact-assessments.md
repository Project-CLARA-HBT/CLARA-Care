# Transfer Impact Assessments (TIA) — CLARA-Care

**Document status:** Living record · version-controlled
**Legal basis:** Decree No. 13/2023/NĐ-CP (PDPD) Arts. 25–27 — cross-border transfer of personal data
**Last reviewed:** 2026-03

> Đánh giá tác động chuyển dữ liệu xuyên biên giới. CLARA maintains a Transfer
> Impact Assessment for each third-party processor that receives personal data
> outside Vietnam (Req 4.1). The assessments below correspond one-to-one with the
> seeded `TransferRegistry`
> (`services/api/src/clara_api/compliance/transfer.py`). The heading anchors
> match the `tia_doc_ref` values recorded on each registry row.

## How transfers are controlled

- **Consent gate (Req 4.2):** When `COMPLIANCE_CROSS_BORDER_GATING_ENABLED` is on and the user has not granted `cross_border_processing` consent, no identifiable sensitive payload leaves for an offshore processor. The call uses an in-country path if configured, otherwise it degrades to the local deterministic answer (`local-synth-*`) labeled degraded (Property P2).
- **Data minimization (Req 4.3):** Outbound requests carry only the text necessary for inference; direct identifiers are excluded where feasible.
- **No-PII logging (Req 4.4):** Each outbound event records the processor identity, purpose, and an opaque no-PII reference — never the transmitted content (Property P5).
- **Disclosure (Req 4.5):** The processor list and jurisdictions are summarized in the privacy policy.

---

## yescale-deepseek

**Processor:** YEScale-hosted DeepSeek LLM endpoint
**Model:** `deepseek-v3.2` (`DEEPSEEK_BASE_URL` default `https://api.deepseek.com`, accessed via the YEScale gateway / `YESCALE_API_KEY`)
**Registry id:** `yescale-deepseek`
**Purpose:** `llm_inference` — generate the synthesized answer for a user query
**Jurisdiction:** offshore (non-VN)

### Data transferred

Minimized query/context text required for synthesis. Direct identifiers
(name, email, insurance id, phone, address) are excluded where feasible. No PHR
identifiers are appended unless strictly necessary for the inference.

### Risk assessment

| Factor | Assessment |
|---|---|
| Data sensitivity | Clinical query text — sensitive personal data |
| Onward transfer | Bounded to the inference request; no content logged on the CLARA side |
| Re-identification risk | Reduced by payload minimization and identifier exclusion |
| Availability dependency | Mitigated by the local `local-synth-*` deterministic fallback |

### Safeguards

- Transfer occurs only with `cross_border_processing` consent when gating is enabled.
- Payload minimization (Req 4.3).
- No-PII transfer event recorded per call (`processor=yescale-deepseek`, `purpose=llm_inference`).
- Graceful degradation to in-country / local fallback when consent is absent.

### Residual risk

**Acceptable**, conditional on consent gating being enabled in production and
the local fallback remaining available.

---

## yescale-embeddings

**Processor:** YEScale-hosted, OpenAI-compatible embedding endpoint
**Endpoint:** `EMBEDDING_BASE_URL` default `https://api.yescale.io/v1`
**Registry id:** `yescale-embeddings`
**Purpose:** `embedding_generation` — produce vector embeddings for retrieval
**Jurisdiction:** offshore (non-VN)

### Data transferred

Text to be embedded for retrieval (query terms / passages). The registry records
the actual offshore recipient (YEScale), which is what the cross-border TIA gates
on (Req 4.1).

### Risk assessment

| Factor | Assessment |
|---|---|
| Data sensitivity | Query/passage text — may include sensitive terms |
| Onward transfer | Bounded to the embedding request; no content logged on the CLARA side |
| Re-identification risk | Low — embeddings are not stored against direct identifiers |
| Availability dependency | Bounded retries with short per-attempt timeout (provider exhibits bimodal latency) |

### Safeguards

- Transfer occurs only with `cross_border_processing` consent when gating is enabled.
- Payload minimization (Req 4.3).
- No-PII transfer event recorded per call (`processor=yescale-embeddings`, `purpose=embedding_generation`).

### Residual risk

**Acceptable**, conditional on consent gating in production and continued
exclusion of direct identifiers from embedded text.

---

## Review schedule

These assessments are reviewed whenever a processor, endpoint, jurisdiction, or
purpose changes, and at minimum on each transparency-notice version bump. New
processors must be added to both this document and the `TransferRegistry` seeds
so the privacy policy and admin records manifest stay consistent.
