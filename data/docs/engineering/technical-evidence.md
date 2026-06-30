# CLARA-Care - Minh chứng kỹ thuật các luồng chính

Tài liệu này ghi lại cách các chức năng chính của CLARA-Care hoạt động dựa trên source code hiện tại. Mục tiêu là giải thích đơn giản, dễ demo, nhưng vẫn có đoạn code minh chứng.

## 1. Luồng Chat và RAG

### 1.1. Chat lấy dữ liệu từ đâu?

Khi người dùng hỏi ở màn Chat, frontend gửi câu hỏi về API. API không tự trả lời ngay mà tải cấu hình RAG hiện tại từ Control Tower, sau đó gọi ML service.

Các nguồn có thể tham gia vào chat/RAG:

- Câu hỏi người dùng.
- Role người dùng: `normal`, `researcher`, `doctor`, `admin`.
- Cấu hình `rag_flow` từ Control Tower: bật/tắt router, retrieval, verification, GraphRAG, reranker.
- Danh sách `rag_sources` từ Control Tower.
- Kho tài liệu nội bộ/seed documents trong ML.
- Tài liệu upload hoặc knowledge/source hub documents khi đi qua Research Tier2.
- Nguồn ngoài nếu bật: PubMed, Europe PMC, Semantic Scholar, openFDA, DailyMed, RxNorm, web/SearXNG.

Minh chứng API load cấu hình RAG trước khi gọi ML:

```python
# services/api/src/clara_api/api/v1/endpoints/chat.py
def _load_rag_runtime(db: Session) -> tuple[RagFlowConfig, list[dict[str, Any]]]:
    control_tower = get_control_tower_config_service().load(db)
    rag_flow = control_tower.rag_flow
    rag_sources = [item.model_dump() for item in control_tower.rag_sources]
    return rag_flow, rag_sources
```

API gọi ML endpoint `/v1/chat/routed`:

```python
# services/api/src/clara_api/api/v1/endpoints/chat.py
request_payload = {
    "query": message,
    "role": role,
    "rag_flow": rag_flow.model_dump(),
    "rag_sources": rag_sources,
}
data = _post_to_ml(url, request_payload, settings.ml_service_timeout_seconds)
```

### 1.2. Chat đưa dữ liệu vào RAG kiểu gì?

Ở ML service, endpoint `/v1/chat/routed` xử lý theo thứ tự:

1. Kiểm tra hard guard pháp lý: chặn kê đơn, chẩn đoán, chỉ định liều.
2. Redact PII trong câu hỏi.
3. Route theo role/intent.
4. Nếu là cấp cứu hoặc chào hỏi đơn giản thì đi fast path, không cần RAG nặng.
5. Nếu là câu hỏi y tế thật, gọi `rag_pipeline.run(...)`.
6. RAG truy xuất tài liệu, có thể mở rộng nguồn ngoài nếu ngữ cảnh yếu.
7. Sinh câu trả lời bằng LLM.
8. Chạy verification/factcheck nếu bật.
9. Trả về answer, retrieved IDs, context_debug, flow_events.

Minh chứng ML nhận payload, route và gọi RAG:

```python
# services/ml/src/clara_ml/main.py
pii = redact_pii(query)
route = router.route(pii.redacted_text, role_hint=role_hint)

rag_result = rag_pipeline.run(
    pii.redacted_text,
    low_context_threshold=low_context_threshold,
    deepseek_fallback_enabled=deepseek_fallback_enabled,
    scientific_retrieval_enabled=adjusted_scientific_retrieval_enabled,
    web_retrieval_enabled=adjusted_web_retrieval_enabled,
    file_retrieval_enabled=adjusted_file_retrieval_enabled,
    rag_sources=rag_sources,
    uploaded_documents=uploaded_documents,
    strict_deepseek_required=settings.deepseek_required,
    rag_reranker_enabled=rag_reranker_enabled_override,
    rag_graphrag_enabled=rag_graphrag_enabled_override,
    llm_runtime=llm_runtime,
)
```

### 1.3. Các bước truy xuất trong RAG

Pipeline RAG nằm ở `RagPipelineP1`. Khi khởi tạo, nó nạp tài liệu nền:

```python
# services/ml/src/clara_ml/rag/pipeline.py
seed_documents = load_seed_documents()
seed_by_id: dict[str, Document] = {doc.id: doc for doc in base_documents()}
for item in seed_documents:
    seed_by_id[item.id] = item

self.retriever = retriever or InMemoryRetriever(documents=list(seed_by_id.values()))
```

Khi chạy, RAG thực hiện:

1. Chuẩn hóa hint từ planner.
2. Tạo query plan: internal query, scientific query, web query.
3. Chọn top-k và connector theo độ phức tạp câu hỏi.
4. Truy xuất nội bộ trước.
5. Nếu ngữ cảnh yếu hoặc là câu hỏi tương tác thuốc, mở rộng ra nguồn ngoài.
6. Có thể chạy GraphRAG sidecar.
7. Tạo prompt từ tài liệu đã truy xuất.
8. Gọi LLM hoặc fallback deterministic nếu LLM lỗi.

Minh chứng truy xuất nội bộ:

```python
# services/ml/src/clara_ml/rag/pipeline.py
docs = self.retriever.retrieve_internal(
    internal_query,
    top_k=internal_top_k,
    file_retrieval_enabled=file_retrieval_enabled,
    rag_sources=rag_sources,
    uploaded_documents=uploaded_documents,
    rag_reranker_enabled=rag_reranker_enabled,
)
```

Minh chứng mở rộng ra nguồn ngoài khi thiếu ngữ cảnh:

```python
# services/ml/src/clara_ml/rag/pipeline.py
if (
    (low_context_before_external or should_force_external)
    and scientific_retrieval_enabled
    and external_connectors_runtime_enabled
):
    docs = self.retriever.retrieve(
        scientific_query,
        top_k=hybrid_top_k,
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=web_retrieval_enabled,
        file_retrieval_enabled=file_retrieval_enabled,
        rag_sources=rag_sources,
        uploaded_documents=uploaded_documents,
        provider_query_overrides=scientific_provider_query_overrides,
        web_query_override=web_query_override,
        rag_reranker_enabled=rag_reranker_enabled,
    )
```

Minh chứng GraphRAG sidecar:

```python
# services/ml/src/clara_ml/rag/pipeline.py
if graphrag_enabled_runtime:
    graph_result = self._graphrag.expand(
        query=query,
        documents=docs,
        max_neighbors=int(settings.rag_graphrag_max_neighbors),
        expansion_docs=int(settings.rag_graphrag_expansion_docs),
    )
    if graph_result.expansion_docs:
        docs = self._merge_documents_by_id([*docs, *graph_result.expansion_docs])
```

Minh chứng sinh prompt và gọi LLM:

```python
# services/ml/src/clara_ml/rag/pipeline.py
prompt = (
    self._build_prompt(query, docs, report_depth="deep" if long_form_generation else "standard")
    if has_relevant_context
    else self._build_no_rag_prompt(query)
)

response = runtime_llm_client.generate(
    prompt=prompt,
    system_prompt=system_prompt_text,
)
```

### 1.4. Chat trả minh chứng về UI như thế nào?

RAG trả về `context_debug` và `flow_events`. API gắn attribution để UI biết câu trả lời dùng nguồn nào, có fallback không, lỗi nguồn nào.

```python
# services/api/src/clara_api/api/v1/endpoints/chat.py
attribution = _build_chat_attribution(ml_response, rag_sources)
return {
    "reply": reply,
    "retrieved_ids": retrieved_ids,
    "attribution": attribution,
    "fallback": fallback_used,
}
```

Nói ngắn gọn khi demo:

> Chat không chỉ gọi model. Nó đi qua guard pháp lý, router, RAG nội bộ, nguồn ngoài nếu cần, GraphRAG nếu bật, LLM generation và verification.

## 2. Kiểm tra tương tác thuốc - CareGuard

### 2.1. CareGuard lấy dữ liệu từ đâu?

CareGuard có hai cách chạy chính:

- Chạy trực tiếp từ payload `/careguard/analyze`.
- Chạy từ tủ thuốc `/careguard/cabinet/auto-ddi-check`.

Nguồn dữ liệu:

- Thuốc trong tủ thuốc cá nhân.
- Dị ứng người dùng nhập.
- Triệu chứng.
- Xét nghiệm/labs.
- Từ điển thuốc Việt Nam để chuẩn hóa tên thuốc.
- Local DDI rules.
- Nguồn ngoài nếu bật: RxNav, openFDA.

Minh chứng auto-DDI lấy thuốc từ tủ thuốc:

```python
# services/api/src/clara_api/api/v1/endpoints/careguard.py
medication_items = (
    db.execute(
        select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)
    )
    .scalars()
    .all()
)
medication_names = [item.normalized_name for item in medication_items if item.normalized_name]

request_payload = {
    "symptoms": payload.symptoms,
    "labs": payload.labs,
    "medications": sorted(set(medication_names)),
    "medications_with_meta": medications_with_meta,
    "allergies": payload.allergies,
    "external_ddi_enabled": control_tower.careguard_runtime.external_ddi_enabled,
}
result = proxy_ml_post("/v1/careguard/analyze", request_payload)
```

### 2.2. CareGuard xử lý tương tác thế nào?

ML CareGuard làm theo pipeline:

1. Chuẩn hóa danh sách thuốc.
2. Map tên thuốc qua từ điển Việt Nam nếu có.
3. Chạy luật DDI cục bộ.
4. Nếu có ít nhất 2 thuốc và external DDI bật, gọi RxNav/openFDA.
5. Merge alert từ local rules, RxNav, openFDA.
6. Kiểm tra dị ứng.
7. Kiểm tra triệu chứng nguy hiểm và lab risk.
8. Tính risk score/risk level.
9. Trả khuyến nghị, metadata, source_used, source_errors.

Minh chứng:

```python
# services/ml/src/clara_ml/agents/careguard.py
raw_medications = _normalize_text_list(payload.get("medications"))
medications, vn_dictionary_metadata = _normalize_medications_with_vn_dictionary(raw_medications)

local_rules, local_ddi_rules_version = _load_local_ddi_rules()
local_ddi_alerts = _detect_ddi_alerts(medications, local_rules)
source_used = ["local_rules"]

if needs_external_lookup and external_ddi_enabled:
    external = DrugSourceClient(
        timeout_seconds=settings.external_ddi_timeout_seconds,
        max_retries=0,
    ).fetch_ddi_context(medications)
    external_ddi_alerts = external.rxnav_alerts
    openfda_alerts = external.openfda_alerts
```

Minh chứng merge alert và tính risk:

```python
# services/ml/src/clara_ml/agents/careguard.py
ddi_alerts = _merge_drug_alerts(
    local_ddi_alerts,
    external_ddi_alerts + openfda_alerts,
    openfda_evidence,
)
allergy_alerts = _detect_allergy_conflicts(medications, allergies)
all_alerts = ddi_alerts + allergy_alerts

critical_symptoms = _critical_symptom_hits(symptoms)
lab_flags = _lab_risk_flags(labs)
score, level = _risk_from_signals(all_alerts, critical_symptoms, lab_flags)
```

Nói ngắn gọn khi demo:

> CareGuard ưu tiên luật cục bộ để không bị chết khi mất mạng, sau đó enrich bằng RxNav/openFDA nếu bật. Kết quả luôn có risk, alert, khuyến nghị và nguồn tham khảo.

## 3. Hồ sơ sức khỏe cá nhân - PHR

### 3.1. PHR lưu gì?

PHR lưu hồ sơ sức khỏe cá nhân theo user:

- Họ tên, ngày sinh, giới tính.
- Nhóm máu, chiều cao, cân nặng.
- Liên hệ khẩn cấp.
- Dị ứng.
- Bệnh nền.
- Thuốc đang dùng.
- Ghi chú.

Endpoint:

```text
GET /api/v1/phr/record
PUT /api/v1/phr/record
```

Minh chứng lưu PHR:

```python
# services/api/src/clara_api/api/v1/endpoints/phr.py
profile.allergies_json = [item.model_dump(mode="json") for item in payload.allergies]
profile.conditions_json = [item.model_dump(mode="json") for item in payload.conditions]
profile.medications_json = [item.model_dump(mode="json") for item in payload.medications]

db.commit()
db.refresh(profile)
```

### 3.2. PHR tác động đến Chat như thế nào?

Trong source hiện tại, PHR không tự động gắn vào mọi câu Chat nhanh. Frontend ghi rõ: chế độ cá nhân chỉ có tác dụng ở Tier2, tức `Tư duy` hoặc `Pro`.

Minh chứng frontend:

```tsx
// apps/web/app/chat/page.tsx
// Personal mode (PHR + tủ thuốc) chỉ có tác dụng ở tier2 ("deep"/"deep_beta").
// Mặc định false để giữ invariant "không bao giờ (fast && personal)".
const [isPersonalMode, setIsPersonalMode] = useState(false);

const togglePersonalMode = useCallback(() => {
  setIsPersonalMode((prev) => {
    const next = !prev;
    if (next) {
      setSelectedResearchMode((mode) => (mode === "fast" ? "deep" : mode));
    }
    return next;
  });
}, []);
```

Khi bật chế độ cá nhân, frontend gửi `personal_mode` vào Research Tier2:

```ts
// apps/web/lib/research.ts
if (typeof options?.personalMode === "boolean") {
  payload.personal_mode = options.personalMode;
}
```

Backend Research Tier2 sẽ lấy PHR + tủ thuốc và tạo personal context:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
if personal_mode:
    personal_context = _build_personal_context_payload(
        db,
        user_id=user.id,
        answer_language=answer_language,
    )
    upstream_payload["personal_context"] = personal_context
    metadata["personal_context_medication_count"] = len(personal_context.get("medications", []))
```

Trong personal context, PHR và tủ thuốc được gộp:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
summary_lines = [f"- {header}"]
if allergy_names:
    summary_lines.append(f"- {allergies_label}: {', '.join(allergy_names)}.")
if condition_names:
    summary_lines.append(f"- {conditions_label}: {', '.join(condition_names)}.")
if med_names:
    summary_lines.append(f"- {meds_label}: {', '.join(med_names)}.")
```

Nói ngắn gọn khi demo:

> PHR giúp câu trả lời cá nhân hóa hơn khi bật chế độ Cá nhân trong Tư duy/Pro. Nó đưa dị ứng, bệnh nền và thuốc đang dùng vào context, nhưng không biến CLARA thành bác sĩ chẩn đoán.

## 4. Nguồn nghiên cứu - Source Hub

### 4.1. Source Hub là gì?

Source Hub là nơi đồng bộ dữ liệu từ các nguồn y khoa bên ngoài. Người dùng role `researcher`, `doctor`, `admin` có thể chọn nguồn, nhập query và số lượng bản ghi để đồng bộ.

Endpoint chính:

```text
GET  /api/v1/research/source-hub/catalog
GET  /api/v1/research/source-hub/records
POST /api/v1/research/source-hub/sync
```

Catalog nguồn:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
_SOURCE_HUB_CATALOG = (
    SourceHubCatalogEntry(
        key="pubmed",
        label="PubMed",
        description="NCBI PubMed biomedical literature via E-utilities",
        default_query="diabetes type 2 guideline",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="rxnorm",
        label="RxNorm",
        description="NLM RxNorm normalized clinical drug names via RxNav",
        default_query="metformin",
        supports_live_sync=True,
    ),
    ...
)
```

### 4.2. Đồng bộ nguồn hoạt động thế nào?

Frontend gọi sync:

```ts
// apps/web/lib/research.ts
export async function syncSourceHub(payload: {
  source: SourceHubSourceKey;
  query: string;
  limit?: number;
}): Promise<SourceHubSyncResult> {
  const response = await api.post<unknown>("/api/v1/research/source-hub/sync", payload);
  ...
}
```

Backend kiểm tra quyền, kiểm tra nguồn, fetch live records, chuẩn hóa, merge/dedupe và lưu theo user:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
selected_source = catalog_by_key.get(payload.source)
if selected_source is None:
    raise HTTPException(status_code=400, detail="Source chưa được cấu hình")
if not selected_source.supports_live_sync:
    raise HTTPException(status_code=400, detail="Source đang tắt live sync")

records, warnings = _fetch_source_hub_records(payload.source, query, safe_limit)

existing = _load_source_hub_records(db, user.id)
merged = _merge_source_hub_records(existing, normalized_records)
_save_source_hub_records(db, user.id, merged)
```

Sau khi đồng bộ, UI hiển thị bảng:

```text
Nguồn | Tiêu đề | Query | Công bố | Đồng bộ
```

### 4.3. Source Hub đi vào RAG như thế nào?

Khi chạy Research Tier2, frontend có thể gửi `source_hub_sources`.

```ts
// apps/web/lib/research.ts
if (sourceHubSources.length) {
  payload.source_hub_sources = sourceHubSources;
}
```

Backend lấy các record đã sync và biến thành tài liệu nội bộ:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
docs.append(
    {
        "file_id": f"source-hub-{record.id}",
        "filename": f"{record.source}-{index}",
        "content_type": "text/plain",
        "text": " | ".join(part for part in text_parts if part),
        "preview": (record.snippet or record.title or "")[:_PREVIEW_CHAR_LIMIT],
        "source": f"source_hub_{record.source}",
        "url": record.url,
    }
)
```

Sau đó đưa vào `uploaded_documents` để ML RAG dùng:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
source_hub_documents = _build_source_hub_documents(...)
uploaded_documents = [*transient_documents, *source_documents, *source_hub_documents]

if uploaded_documents:
    upstream_payload["uploaded_documents"] = uploaded_documents
```

Nói ngắn gọn khi demo:

> Source Hub kéo dữ liệu y khoa thật về, lưu lại theo user, rồi biến record thành tài liệu RAG để Research Tier2 dùng làm evidence.

## 5. Hội chẩn AI - Council

### 5.1. Hội chẩn nhận dữ liệu gì?

Council nhận:

- Triệu chứng.
- Labs.
- Thuốc.
- Tiền sử.
- Danh sách chuyên khoa hoặc số lượng chuyên khoa.

Endpoint:

```text
POST /api/v1/council/run
POST /api/v1/council/intake
POST /api/v1/council/cases/{case_id}/run
```

API chỉ cho role bác sĩ/admin:

```python
# services/api/src/clara_api/api/v1/endpoints/council.py
@router.post("/run")
def council_run(
    payload: CouncilRunRequest,
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return proxy_ml_post("/v1/council/run", payload.model_dump())
```

### 5.2. Council xử lý như thế nào?

ML Council không đơn giản gọi một prompt. Nó chạy rule-based council:

1. Chuẩn hóa symptoms/labs/medications/history.
2. Chạy evaluator theo từng chuyên khoa.
3. Phát hiện red flags.
4. Tạo conflict list.
5. Tính consensus triage.
6. Tính data quality và confidence.
7. Tạo câu hỏi cần bổ sung.
8. Tạo final recommendation.
9. Gắn citations, citation quality, reasoning timeline.
10. Tính neural shadow risk nếu bật.

Minh chứng:

```python
# services/ml/src/clara_ml/agents/council.py
assessments = [
    _SPECIALIST_EVALUATORS[specialist](symptoms, labs, medications, history)
    for specialist in specialists
]

red_flags, red_flag_matches, negated_red_flag_matches = _detect_red_flags(symptoms)
conflicts = _build_conflicts(assessments)
consensus_triage = _consensus_triage(assessments)
consensus_metadata = _build_consensus_metadata(assessments, consensus_triage, conflicts)
```

Minh chứng output có nhiều lớp phân tích:

```python
# services/ml/src/clara_ml/agents/council.py
return {
    "requested_specialists": specialists,
    "per_specialist_reasoning_logs": assessments_payload,
    "conflict_list": conflicts,
    "council_consensus": consensus_metadata,
    "divergence_notes": divergence_notes,
    "final_recommendation": final_recommendation,
    "emergency_escalation": {...},
    "citations": citations,
    "citation_quality": citation_quality,
    "reasoning_timeline": reasoning_timeline,
    "neural_risk": neural_risk,
}
```

Nói ngắn gọn khi demo:

> Council tạo nhiều góc nhìn chuyên khoa, tìm điểm đồng thuận và bất đồng, rồi đưa ra khuyến nghị tham khảo kèm escalation nếu có red flag.

## 6. Thư ký y khoa - Scribe

### 6.1. Scribe nhận dữ liệu gì?

Scribe nhận transcript hoặc audio. Với transcript, API gọi ML để tạo SOAP note.

Endpoint:

```text
POST /api/v1/scribe/soap
POST /api/v1/scribe/transcribe
POST /api/v1/scribe/sessions
POST /api/v1/scribe/sessions/{session_id}/regenerate
```

Minh chứng API proxy sang ML:

```python
# services/api/src/clara_api/api/v1/endpoints/scribe.py
@router.post("/soap")
def scribe_soap(
    payload: dict[str, Any],
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return proxy_ml_post("/v1/scribe/soap", payload)
```

### 6.2. Scribe tạo SOAP như thế nào?

ML Scribe xử lý transcript thành:

- Subjective.
- Objective.
- Assessment.
- Plan.
- Medical record note.

Minh chứng:

```python
# services/ml/src/clara_ml/agents/scribe_soap.py
def run_scribe_soap(transcript: str) -> dict:
    normalized = _normalize_transcript(transcript)
    sentences = _split_sentences(normalized)
    subjective = _subjective_block(sentences)
    objective = _objective_block(normalized, sentences)
    assessment = _assessment_block(normalized)
    plan = _plan_block(assessment)
    medical_record_note = _medical_record_note_node(...)

    return {
        "subjective": subjective,
        "objective": objective,
        "assessment": assessment,
        "plan": plan,
        "medical_record_note": medical_record_note,
        "metadata": {
            "pipeline": "p2-scribe-soap-v2",
            "flow_nodes": [
                {"stage": "transcript_normalization", "status": "completed"},
                {"stage": "soap_extraction", "status": "completed"},
                {"stage": "medical_record_note", "status": "completed"},
            ],
        },
    }
```

Scribe session lưu transcript và SOAP theo user:

```python
# services/api/src/clara_api/api/v1/endpoints/scribe.py
if transcript and request.auto_generate_soap:
    session_item.soap_json = _generate_soap(transcript)
    session_item.status = "ready"
    session_item.last_processed_at = now

db.add(session_item)
db.commit()
```

Nói ngắn gọn khi demo:

> Scribe biến ghi chú tự do thành SOAP có cấu trúc. Người dùng vẫn cần kiểm tra lại trước khi dùng trong hồ sơ thật.

## 7. Tóm tắt các endpoint chính

| Mục | Endpoint chính | Vai trò |
|---|---|---|
| Chat | `POST /api/v1/chat` | Chat routed qua ML + RAG |
| RAG ML | `POST /v1/chat/routed` | Guard, route, retrieve, generate, verify |
| CareGuard | `POST /api/v1/careguard/analyze` | Kiểm tra tương tác từ payload |
| Auto DDI | `POST /api/v1/careguard/cabinet/auto-ddi-check` | Lấy thuốc trong tủ và kiểm tra |
| PHR | `GET/PUT /api/v1/phr/record` | Lưu hồ sơ sức khỏe cá nhân |
| Source Hub | `POST /api/v1/research/source-hub/sync` | Đồng bộ nguồn nghiên cứu |
| Research Tier2 | `POST /api/v1/research/tier2/jobs` | Deep research async |
| Council | `POST /api/v1/council/run` | Hội chẩn nhiều chuyên khoa |
| Scribe | `POST /api/v1/scribe/soap` | Sinh SOAP note từ transcript |

## 8. Kết luận ngắn

CLARA-Care có các pipeline riêng biệt nhưng liên kết với nhau:

```text
Chat -> API -> ML routed chat -> RAG -> LLM -> verification -> attribution
Tủ thuốc -> CareGuard -> local DDI rules + RxNav/openFDA -> risk/recommendation
PHR -> personal context -> Research Tier2 cá nhân hóa
Source Hub -> sync nguồn ngoài -> records -> uploaded_documents -> RAG evidence
Council -> multi-specialist evaluators -> consensus/conflict/escalation
Scribe -> transcript -> SOAP -> session lưu theo user
```

Điểm quan trọng nhất: CLARA-Care không chỉ là một chatbot. Hệ thống có guard an toàn, truy xuất bằng chứng, nguồn nghiên cứu, kiểm tra tương tác thuốc, hồ sơ cá nhân, hội chẩn và ghi chú lâm sàng theo từng pipeline rõ ràng.

## 9. Code lấy dữ liệu từ các nguồn như thế nào

Trong CLARA-Care có 2 kiểu lấy dữ liệu nguồn:

1. **Đồng bộ Source Hub**: người dùng chọn nguồn, nhập query, backend gọi API/HTML nguồn ngoài, chuẩn hóa thành `SourceHubRecord`, rồi lưu vào database.
2. **Truy xuất trực tiếp khi RAG chạy**: khi chat hoặc nghiên cứu cần thêm bằng chứng, ML service gọi các connector như PubMed, Europe PMC, openFDA, DailyMed, RxNorm, ClinicalTrials, SearXNG.

### 9.1. Từ giao diện, người dùng bấm đồng bộ nguồn

Ở màn hình Source Hub, frontend chỉ lấy input rồi gọi hàm `syncSourceHub`.

```tsx
// apps/web/app/research/source-hub/page.tsx
const onSync = async (event: FormEvent<HTMLFormElement>) => {
  event.preventDefault();
  const query = syncQuery.trim();
  if (!query) {
    setError("Vui lòng nhập chủ đề cần đồng bộ.");
    return;
  }

  const parsedLimit = Number(syncLimit);
  const safeLimit = Number.isFinite(parsedLimit)
    ? Math.max(3, Math.min(100, Math.trunc(parsedLimit)))
    : 12;

  const result = await syncSourceHub({
    source: activeSource,
    query,
    limit: safeLimit,
  });

  await loadRecords(filterText);
  setMessage(
    `Đã đồng bộ ${SOURCE_LABELS[result.source]}: lấy ${result.fetched}, lưu ${result.stored} bản ghi.`
  );
};
```

Hàm gọi API:

```ts
// apps/web/lib/research.ts
export async function syncSourceHub(payload: {
  source: SourceHubSourceKey;
  query: string;
  limit?: number;
}): Promise<SourceHubSyncResult> {
  const response = await api.post<unknown>(
    "/api/v1/research/source-hub/sync",
    payload
  );

  const data = asRecord(response.data);
  const source = parseSourceHubKey(data?.source);
  const query = asText(data?.query) ?? payload.query;
  if (!source) throw new Error("Không thể đồng bộ nguồn dữ liệu.");

  return {
    source,
    query,
    fetched: Math.trunc(asNumber(data?.fetched) ?? 0),
    stored: Math.trunc(asNumber(data?.stored) ?? 0),
    records: parseList(data?.records, parseSourceHubRecord),
    warnings: parseList(data?.warnings, (item) => {
      const text = asText(item);
      return text ? text : null;
    }),
  };
}
```

Nói ngắn gọn khi demo:

> Frontend không tự scrape dữ liệu. Frontend chỉ gửi `source`, `query`, `limit` xuống backend. Backend mới là nơi gọi PubMed, RxNorm, openFDA, DailyMed và các nguồn khác.

### 9.2. Backend nhận yêu cầu sync và chọn nguồn cần gọi

Endpoint chính:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
@router.post("/source-hub/sync")
def source_hub_sync(
    payload: SourceHubSyncRequest,
    token: TokenPayload = Depends(require_roles("researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> SourceHubSyncResponse:
    user = _get_user_by_token(db, token)
    query = payload.query.strip()

    safe_limit = max(3, min(500, int(payload.limit)))
    records, warnings = _fetch_source_hub_records(
        payload.source,
        query,
        safe_limit,
    )

    existing = _load_source_hub_records(db, user.id)
    merged = _merge_source_hub_records(existing, normalized_records)
    _save_source_hub_records(db, user.id, merged)

    return SourceHubSyncResponse(
        source=payload.source,
        query=query,
        fetched=len(normalized_records),
        stored=len(merged),
        records=normalized_records,
        warnings=warnings,
    )
```

Điểm quan trọng:

- Có kiểm tra quyền: chỉ `researcher`, `doctor`, `admin` được sync.
- Có kiểm tra query rỗng.
- Có giới hạn số bản ghi.
- Có bắt lỗi timeout/lỗi HTTP từ nguồn ngoài.
- Dữ liệu mới được merge với dữ liệu cũ, tránh mất lịch sử ngay lập tức.

### 9.3. Hàm dispatch chọn connector theo source

Backend dùng `source` để quyết định gọi hàm fetch nào.

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
def _fetch_source_hub_records(
    source: SourceHubSourceKey, query: str, limit: int
) -> tuple[list[SourceHubRecord], list[str]]:
    synced_at = datetime.now(tz=UTC).isoformat()
    if source == "pubmed":
        return _fetch_pubmed_records(query, limit, synced_at)
    if source == "rxnorm":
        return _fetch_rxnorm_records(query, limit, synced_at)
    if source == "openfda":
        return _fetch_openfda_records(query, limit, synced_at)
    if source == "dailymed":
        return _fetch_dailymed_records(query, limit, synced_at)
    if source == "europepmc":
        return _fetch_europepmc_records(query, limit, synced_at)
    if source == "semantic_scholar":
        return _fetch_semantic_scholar_records(query, limit, synced_at)
    if source == "clinicaltrials":
        return _fetch_clinicaltrials_records(query, limit, synced_at)
    if source in {"vn_moh", "vn_kcb", "vn_canhgiacduoc", "vn_vbpl_byt", "vn_dav"}:
        return _fetch_vn_html_source_records(source, query, limit, synced_at)
    if source == "davidrug":
        return _fetch_davidrug_records(query, limit, synced_at)
    return [], [f"Nguồn không được hỗ trợ: {source}"]
```

Nói ngắn gọn:

> `source` giống như tên cổng kết nối. Nếu chọn PubMed thì gọi PubMed API. Nếu chọn RxNorm thì gọi RxNav API. Nếu chọn nguồn Việt Nam thì backend lấy HTML/trang công khai rồi trích link và nội dung phù hợp.

### 9.4. Hàm HTTP dùng để gọi nguồn ngoài

Backend dùng `httpx` để GET JSON hoặc HTML.

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
def _http_get_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=_SOURCE_HUB_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _http_get_text(url: str, *, params: dict[str, Any] | None = None) -> str:
    with httpx.Client(timeout=_SOURCE_HUB_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    return response.text
```

Ý nghĩa:

- Nguồn trả JSON thì dùng `_http_get_json`.
- Nguồn là website/HTML thì dùng `_http_get_text`.
- `raise_for_status()` giúp phát hiện lỗi HTTP như 404, 500.
- Timeout giúp không để hệ thống treo khi nguồn ngoài chậm.

### 9.5. Ví dụ lấy dữ liệu PubMed

PubMed được lấy qua 2 bước:

1. Gọi `esearch` để lấy danh sách PMID.
2. Gọi `esummary` để lấy tiêu đề, journal, ngày xuất bản, DOI, tác giả.

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
def _fetch_pubmed_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    search = _http_get_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"},
    )

    id_list = search.get("esearchresult", {}).get("idlist", [])

    summary = _http_get_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(id_list[:limit]), "retmode": "json"},
    )

    records: list[SourceHubRecord] = []
    for uid in summary.get("result", {}).get("uids", [])[:limit]:
        item = summary["result"].get(uid)
        records.append(
            SourceHubRecord(
                id=f"pubmed:{uid}",
                source="pubmed",
                title=item.get("title"),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                snippet=" | ".join([journal, pubdate]),
                external_id=uid,
                query=query,
                synced_at=synced_at,
                metadata={
                    "authors": item.get("authors"),
                    "pubtype": item.get("pubtype"),
                    "doi": item.get("elocationid"),
                },
            )
        )
```

### 9.6. Ví dụ lấy dữ liệu thuốc từ RxNorm, openFDA, DailyMed

RxNorm/RxNav dùng để chuẩn hóa tên thuốc và mã RxCUI:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
payload = _http_get_json(
    "https://rxnav.nlm.nih.gov/REST/approximateTerm.json",
    params={"term": query, "maxEntries": limit},
)

for item in payload.get("approximateGroup", {}).get("candidate", [])[:limit]:
    records.append(
        SourceHubRecord(
            id=f"rxnorm:{item.get('rxcui')}",
            source="rxnorm",
            title=item.get("name"),
            external_id=item.get("rxcui"),
            metadata=item,
        )
    )
```

openFDA lấy nhãn thuốc theo brand name:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
payload = _http_get_json(
    "https://api.fda.gov/drug/label.json",
    params={"search": f'openfda.brand_name:"{escaped}"', "limit": limit},
)

for item in payload.get("results", [])[:limit]:
    openfda = item.get("openfda") if isinstance(item.get("openfda"), dict) else {}
    records.append(
        SourceHubRecord(
            id=f"openfda:{set_id}",
            source="openfda",
            title=brand_name,
            snippet=purpose_or_warning[:280],
            metadata={"openfda": openfda},
        )
    )
```

DailyMed lấy SPL label theo tên thuốc:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
payload = _http_get_json(
    f"https://dailymed.nlm.nih.gov/dailymed/services/v1/drugname/{escaped_query}/spls.json"
)

for item in payload.get("data", [])[:limit]:
    set_id = item[0]
    title = item[1]
    records.append(
        SourceHubRecord(
            id=f"dailymed:{set_id}",
            source="dailymed",
            title=title,
            url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}",
        )
    )
```

### 9.7. Nguồn Việt Nam lấy kiểu gì

Các nguồn Việt Nam như Bộ Y tế, Cục Quản lý Dược, văn bản pháp luật không phải lúc nào cũng có API JSON giống PubMed. Vì vậy code có nhánh lấy HTML:

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
html = _http_get_text(page_url)
anchors = _extract_anchor_candidates(html, page_url)

for candidate in anchors:
    if query_terms and not any(term in candidate.title.lower() for term in query_terms):
        continue

    records.append(
        SourceHubRecord(
            id=f"{source}:{candidate.url}",
            source=source,
            title=candidate.title,
            url=candidate.url,
            snippet=candidate.snippet,
            query=query,
            synced_at=synced_at,
        )
    )
```

Nói ngắn gọn:

> Với nguồn có API thì hệ thống gọi API JSON. Với nguồn chỉ có website, hệ thống tải HTML, trích các link/tựa đề, lọc theo query, rồi biến thành record.

### 9.8. Dữ liệu sau khi lấy về được lưu ở đâu

Dữ liệu sau khi chuẩn hóa sẽ được lưu vào bảng `FederatedSourceRecord` theo user.

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
def _save_source_hub_records(
    db: Session,
    owner_user_id: int,
    records: list[SourceHubRecord],
) -> None:
    pruned = records[:_SOURCE_HUB_MAX_RECORDS]
    db.query(FederatedSourceRecord).filter(
        FederatedSourceRecord.owner_user_id == owner_user_id
    ).delete(synchronize_session=False)

    for record in pruned:
        db.add(
            FederatedSourceRecord(
                owner_user_id=owner_user_id,
                record_id=record.id,
                source=record.source,
                title=record.title,
                url=record.url or "",
                snippet=record.snippet or "",
                external_id=record.external_id or "",
                query=record.query or "",
                published_at=record.published_at or "",
                synced_at=parsed_synced_at,
                metadata_json=record.metadata,
            )
        )
    db.commit()
```

Ý nghĩa:

- Mỗi user có bộ record nguồn riêng.
- Record gồm: `source`, `title`, `url`, `snippet`, `external_id`, `query`, `published_at`, `synced_at`, `metadata`.
- Khi sync lại, dữ liệu mới được merge/deduplicate trước khi lưu.

### 9.9. Source Hub đưa vào RAG như thế nào

Khi chạy nghiên cứu hoặc chat có dùng nguồn đã sync, backend biến `SourceHubRecord` thành `uploaded_documents` để ML RAG có thể đọc giống như tài liệu nội bộ.

```python
# services/api/src/clara_api/api/v1/endpoints/research.py
def _build_source_hub_documents(
    db: Session,
    *,
    owner_user_id: int,
    query: str,
    source_filters: set[str],
    limit: int = 40,
) -> list[dict[str, Any]]:
    records = _load_source_hub_records(db, owner_user_id)

    matched: list[SourceHubRecord] = []
    for record in records:
        if source_filters and record.source not in source_filters:
            continue
        haystack = " ".join([record.title or "", record.snippet or "", record.query or ""]).lower()
        if query_terms and not any(term in haystack for term in query_terms):
            continue
        matched.append(record)

    docs.append(
        {
            "file_id": f"source-hub-{record.id}",
            "filename": f"{record.source}-{index}",
            "content_type": "text/plain",
            "text": " | ".join(part for part in text_parts if part),
            "preview": (record.snippet or record.title or "")[:_PREVIEW_CHAR_LIMIT],
            "source": f"source_hub_{record.source}",
            "url": record.url,
        }
    )
```

Nói ngắn gọn:

> Source Hub không đưa nguyên database vào prompt. Nó lọc theo query, lấy title/snippet/metadata liên quan, đóng gói thành document, rồi đưa vào RAG để chấm điểm và chọn bằng chứng.

### 9.10. Khi chat cần nguồn ngoài, ML service tự gọi connector

Ngoài dữ liệu Source Hub đã sync, ML RAG còn có thể gọi trực tiếp nguồn ngoài thông qua `ExternalSourceGateway`.

```python
# services/ml/src/clara_ml/rag/retrieval/external_gateway.py
class ExternalSourceGateway:
    PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    OPENALEX_WORKS_URL = "https://api.openalex.org/works"
    CROSSREF_WORKS_URL = "https://api.crossref.org/works"
    CLINICALTRIALS_V2_URL = "https://clinicaltrials.gov/api/v2/studies"
    OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
    DAILYMED_DRUGNAME_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v1/drugname"
    RXNAV_APPROXIMATE_TERM_URL = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
    SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
```

Hàm gọi JSON ở ML service:

```python
# services/ml/src/clara_ml/rag/retrieval/external_gateway.py
@staticmethod
def _fetch_json(
    url: str,
    timeout_seconds: float,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | list[Any] | None:
    ExternalSourceGateway._throttle_before_request(url)
    merged_headers = {"User-Agent": "CLARA-ML/0.1"}
    if headers:
        merged_headers.update(headers)
    request = Request(url, headers=merged_headers)
    with urlopen(request, timeout=max(timeout_seconds, 0.1)) as response:
        payload = response.read().decode("utf-8", errors="ignore")
    return json.loads(payload)
```

Điểm đáng chú ý:

- ML service có `User-Agent`.
- Có throttle theo host để tránh gọi quá nhanh.
- Có timeout.
- Có telemetry để biết nguồn nào gọi thành công/lỗi.

### 9.11. RAG chọn provider nào để gọi

Nếu là câu hỏi tương tác thuốc, hệ thống ưu tiên nguồn thuốc trước: openFDA, DailyMed, RxNorm, PubMed.

```python
# services/ml/src/clara_ml/rag/retrieval/external_gateway.py
base_order = (
    [
        "openfda",
        "dailymed",
        "rxnorm",
        "pubmed",
        "europepmc",
        "clinicaltrials",
        "semantic_scholar",
    ]
    if is_ddi_query
    else [
        "pubmed",
        "europepmc",
        "semantic_scholar",
        "rxnorm",
        "openalex",
        "crossref",
        "clinicaltrials",
    ]
)
```

Sau đó map provider sang hàm retrieve tương ứng:

```python
# services/ml/src/clara_ml/rag/retrieval/external_gateway.py
provider_map: dict[str, Any] = {
    "pubmed": lambda: self.retrieve_pubmed(...),
    "europepmc": lambda: self.retrieve_europe_pmc(...),
    "semantic_scholar": lambda: self.retrieve_semantic_scholar(...),
    "openalex": lambda: self.retrieve_openalex(...),
    "crossref": lambda: self.retrieve_crossref(...),
    "clinicaltrials": lambda: self.retrieve_clinicaltrials(...),
    "openfda": lambda: self.retrieve_openfda(...),
    "dailymed": lambda: self.retrieve_dailymed(...),
    "rxnorm": lambda: self.retrieve_rxnorm(...),
}
```

Nói ngắn gọn khi demo:

> Nếu người dùng hỏi về tương tác thuốc, RAG không tìm lan man trước. Nó ưu tiên nguồn thuốc/nhãn thuốc như openFDA, DailyMed, RxNorm rồi mới tới paper như PubMed.

### 9.12. Các document lấy về được chấm điểm và chọn vào context

Retriever lấy dữ liệu từ nhiều nguồn rồi gom lại:

```python
# services/ml/src/clara_ml/rag/retrieval/in_memory.py
def retrieve(
    self,
    query: str,
    top_k: int = 3,
    *,
    scientific_retrieval_enabled: bool = False,
    web_retrieval_enabled: bool = False,
    file_retrieval_enabled: bool = True,
    rag_sources: object = None,
    uploaded_documents: object = None,
    ...
) -> list[Document]:
    staged_docs, internal_counts = self._collect_internal_candidates(
        file_retrieval_enabled=file_retrieval_enabled,
        rag_sources=rag_sources,
        uploaded_documents=uploaded_documents,
    )
```

Sau đó dedupe, score và rerank:

```python
# services/ml/src/clara_ml/rag/retrieval/in_memory.py
deduped = dedupe_documents(candidates)
ranked = self.scorer.score_documents(
    query,
    deduped,
    top_k=top_k,
    source_policies=self.builder.parse_source_policies(rag_sources),
    score_trace=score_trace,
)
rerank_result = neural_reranker.rerank(query, ranked, top_k=top_k)
```

Nói ngắn gọn:

> Nguồn lấy về chưa được đưa thẳng cho AI trả lời. Nó phải qua bước loại trùng, chấm điểm theo query, rerank, rồi mới chọn top document làm context.

### 9.13. Tóm tắt luồng lấy dữ liệu nguồn

```text
Người dùng chọn nguồn + nhập query
-> Frontend POST /api/v1/research/source-hub/sync
-> Backend kiểm tra quyền, query, limit
-> Backend dispatch theo source
-> Gọi API JSON hoặc tải HTML nguồn ngoài
-> Parse thành SourceHubRecord
-> Merge/deduplicate
-> Lưu FederatedSourceRecord theo user
-> Khi RAG chạy: lọc record theo query
-> Đóng gói thành document
-> Dedupe, score, rerank
-> Đưa document phù hợp vào context cho câu trả lời
```

Với truy xuất trực tiếp khi chat:

```text
User hỏi
-> ML phân tích query
-> Nếu cần nguồn ngoài, chọn provider
-> Gọi PubMed / Europe PMC / openFDA / DailyMed / RxNorm / ClinicalTrials ...
-> Chuẩn hóa mỗi kết quả thành Document(id, text, metadata.source, metadata.url)
-> Dedupe, score, rerank
-> Đưa bằng chứng vào RAG prompt
-> Sinh câu trả lời có nguồn tham khảo
```

Một câu demo dễ hiểu:

> CLARA-Care lấy dữ liệu nguồn theo kiểu connector. Mỗi nguồn có một hàm riêng để gọi API hoặc đọc HTML. Kết quả được chuẩn hóa về cùng một dạng record/document, sau đó mới lưu, lọc, chấm điểm và đưa vào RAG. Nhờ vậy chat, nghiên cứu và kiểm tra tương tác thuốc có thể dùng nhiều nguồn khác nhau nhưng vẫn đi qua một pipeline chung.
