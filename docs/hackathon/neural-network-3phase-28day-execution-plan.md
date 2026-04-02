# Kế Hoạch 3 Phase Ứng Dụng Neural Network Cho CLARA (28 Ngày)

## 1. Mục tiêu tổng
1. Tăng độ đúng của retrieval và câu trả lời research.
2. Giảm lỗi an toàn y khoa: bỏ sót DDI nghiêm trọng, claim không có evidence.
3. Giữ nguyên hard-guard pháp lý: NN chỉ hỗ trợ xếp hạng/chuẩn hóa/kiểm chứng, không thay rule chặn liều-kê đơn-chẩn đoán.
4. Không phá latency mục tiêu của demo và production.

## 2. Kiến trúc đích
1. Retrieval hai tầng: `candidate retrieval -> neural reranker`.
2. Verification hai tầng: `rule + NLI claim verifier`.
3. Drug normalization hai tầng: `dictionary exact match -> neural normalize`.
4. OCR pipeline ba tầng: `OCR raw -> NN correction -> manual confirm`.
5. Source routing thông minh: `policy constraints + neural source router`.

## 3. Phase 1 (Day 1-10): Neural Reranker + NLI Verification
Thời lượng: 10-14 ngày  
Ưu tiên: Cao nhất  
Tác động: Rõ nhất tới chất lượng research/answer

### 3.1 Scope
1. Thêm neural reranker cho evidence retrieval.
2. Thêm claim-level NLI verifier cho verification matrix.
3. Telemetry đầy đủ để đo trước/sau theo KPI.

### 3.2 File/Module chính
1. `services/ml/src/clara_ml/config.py`
2. `services/ml/src/clara_ml/rag/pipeline.py`
3. `services/ml/src/clara_ml/rag/retrieval/score_engine.py`
4. `services/ml/src/clara_ml/agents/research_tier2.py`
5. `services/api/src/clara_api/api/v1/endpoints/research.py`
6. `apps/web/components/research/telemetry-details-panel.tsx`
7. `apps/web/components/research/flow-timeline-panel.tsx`
8. `services/ml/tests/test_rag_pipeline.py`
9. `services/ml/tests/test_research_tier2_agent.py`
10. `services/api/tests/test_p2_proxy_endpoints.py`

### 3.3 Thiết kế kỹ thuật
1. Candidate retrieval giữ nguyên stack hiện có (internal/scientific/web/file).
2. Reranker nhận top-`N` candidates, trả top-`K` final với score chuẩn hóa.
3. NLI verifier nhận `claim + evidence chunk`, trả `supported|contradicted|insufficient` + confidence.
4. Verification matrix dùng verdict của NLI + rule override cho claim safety-critical.
5. Nếu model lỗi/timeout: degrade về cơ chế hiện tại + gắn `source_errors` + `fallback_reason`.

### 3.4 Kế hoạch triển khai
1. Bật config mới:
   - `RAG_RERANKER_ENABLED`
   - `RAG_RERANKER_TOP_N`
   - `RAG_RERANKER_TIMEOUT_MS`
   - `RAG_NLI_ENABLED`
   - `RAG_NLI_TIMEOUT_MS`
   - `RAG_NLI_MIN_CONFIDENCE`
2. Viết module reranker:
   - Input: query, docs
   - Output: docs có `rerank_score`, `rerank_rank`
   - Log: latency, truncated_count, model_name
3. Cắm reranker vào pipeline sau retrieval merge, trước evidence_index/synthesis.
4. Viết module NLI verifier:
   - Parse claims từ answer draft
   - Map claim -> evidence chunks
   - Tính verdict + confidence + reason
5. Chuẩn hóa payload:
   - `verification_matrix`
   - `unsupported_claims`
   - `claim_coverage_rate`
   - `nli_summary`
6. Cập nhật UI research:
   - Hiển thị matrix đúng định dạng
   - Badge màu theo verdict
   - Tooltip confidence/source
7. Cập nhật tests:
   - Unit: reranker, NLI parser, verdict aggregation
   - Integration: full flow deep/deep_beta
   - Regression: không làm giảm refusal compliance

### 3.5 KPI gate phase 1
1. `Precision@5` tăng >= 8% so baseline.
2. `Unsupported claim rate` giảm >= 30%.
3. `Refusal compliance` giữ >= 99%.
4. `p95 latency` tăng không quá 20%.

### 3.6 Definition of Done phase 1
1. Có thể bật/tắt qua config runtime.
2. Có telemetry và dashboard đọc được.
3. CI pass + active-eval pass + smoke deploy pass.

## 4. Phase 2 (Day 11-18): VN Drug Neural Normalization
Thời lượng: 2-3 tuần  
Ưu tiên: Cao  
Tác động: Giảm lỗi DDI do tên biệt dược VN

### 4.1 Scope
1. Chuẩn hóa biệt dược VN bằng hybrid dictionary + neural matching.
2. Hỗ trợ combo drugs và alias tiếng Việt/Anh.
3. Bổ sung quy trình curation để admin sửa mapping sai.

### 4.2 File/Module chính
1. `services/api/src/clara_api/api/v1/endpoints/careguard.py`
2. `services/api/src/clara_api/db/models.py`
3. `services/api/src/clara_api/schemas.py`
4. `services/ml/src/clara_ml/clients/drug_sources.py`
5. `services/ml/src/clara_ml/agents/careguard.py`
6. `apps/web/app/selfmed/page.tsx`
7. `apps/web/app/careguard/page.tsx`
8. `services/api/tests/test_careguard_cabinet_endpoints.py`
9. `services/ml/tests/test_careguard_agent.py`

### 4.3 Thiết kế kỹ thuật
1. Bước 1 exact match dictionary.
2. Bước 2 neural candidate retrieval theo embedding tên thuốc.
3. Bước 3 cross-encoder chọn best candidate.
4. Bước 4 confidence gate:
   - High confidence: auto map
   - Low confidence: bắt `manual confirm`
5. Kết quả mapping lưu:
   - `brand_input`
   - `normalized_name`
   - `active_ingredients`
   - `rxcui`
   - `confidence`
   - `mapping_source` (`dictionary|neural|manual`)

### 4.4 Kế hoạch triển khai
1. Thiết kế schema `vn_drug_dictionary` + `vn_drug_alias`.
2. Import seed >= 100 thuốc phổ biến VN.
3. Build service `normalize_drug_name()`.
4. Cắm service vào flow `/careguard` và `/selfmed`.
5. Cập nhật UI manual confirm:
   - font lớn
   - contrast cao
   - nút xác nhận lớn
   - hiển thị confidence rõ ràng
6. Thêm admin endpoint:
   - search mapping
   - approve/reject correction
   - audit history

### 4.5 KPI gate phase 2
1. `Mapping accuracy` >= 90% trên testset nội bộ VN.
2. `Critical DDI miss` giảm >= 40% so baseline pre-phase2.
3. `Manual confirm rate` giảm dần theo thời gian curation.

### 4.6 Definition of Done phase 2
1. Mapping có audit trail.
2. UI confirm dùng được cho người lớn tuổi.
3. DDI pipeline phản ánh đúng ingredient normalized.

## 5. Phase 3 (Day 19-28): OCR Correction + Source Router + Active Eval Automation
Thời lượng: 3-4 tuần  
Ưu tiên: Trung bình-cao  
Tác động: Độ bền production, giảm timeout và noise

### 5.1 Scope
1. OCR hậu xử lý bằng NN correction.
2. Neural source router theo intent + domain + risk.
3. Active eval loop tự động + hard-negative mining tự động từ production logs.

### 5.2 File/Module chính
1. `services/ml/src/clara_ml/agents/research_tier2.py`
2. `services/ml/src/clara_ml/rag/pipeline.py`
3. `services/ml/src/clara_ml/nlp/*`
4. `services/api/src/clara_api/core/flow_event_store.py`
5. `scripts/demo/mine_hard_negatives.py`
6. `scripts/demo/run_active_eval_loop.sh`
7. `.github/workflows/active-eval.yml`
8. `apps/web/components/admin/admin-flow-visualizer.tsx`

### 5.3 Thiết kế kỹ thuật
1. OCR correction model xử lý lỗi ký tự và spacing tên thuốc.
2. Source router dự đoán profile retrieval:
   - `internal-heavy`
   - `scientific-heavy`
   - `web-assisted`
   - `file-grounded`
3. Router luôn bị ràng buộc bởi policy:
   - không bật web khi policy cấm
   - không bỏ scientific trong query safety-critical
4. Auto eval loop:
   - baseline run
   - mine hard negatives
   - rerun post-negative
   - compare với baseline trước
   - fail gate nếu regression

### 5.4 Kế hoạch triển khai
1. Viết OCR correction module và fallback.
2. Cắm OCR correction vào flow upload scan.
3. Viết source router module và gating logic.
4. Cắm router vào `retrieval_orchestrator`.
5. Chuẩn hóa metadata:
   - `source_errors`
   - `fallback_reason`
   - `retrieval_route`
   - `router_confidence`
6. Tự động hóa eval:
   - cron/schedule workflow
   - artifact compare report
   - NO-GO gate khi tụt quality

### 5.5 KPI gate phase 3
1. `source mismatch rate` giảm >= 25%.
2. `fallback due to timeout` giảm >= 30%.
3. `regression detection lead time` < 1 ngày.
4. Không có giảm metric safety critical.

### 5.6 Definition of Done phase 3
1. Deep flow ổn định khi tải cao.
2. Production có vòng feedback tự động.
3. Có báo cáo regression rõ ràng cho từng lần run.

## 6. Lịch thực thi 28 ngày

### Day 1-10 (Phase 1)
Day 1
- [ ] Chốt contract đầu vào/đầu ra cho reranker + NLI.
- [ ] Thêm config flags trong `services/ml/src/clara_ml/config.py`.
- [ ] Tạo `docs/hackathon/phase1-contract.md`.

Day 2
- [ ] Tạo module reranker (skeleton chạy được).
- [ ] Hook vào `services/ml/src/clara_ml/rag/pipeline.py`.
- [ ] Log `rerank_latency_ms`, `rerank_topn`.

Day 3
- [ ] Hoàn thiện scoring/ranking và fallback timeout.
- [ ] Viết unit test reranker.

Day 4
- [ ] Tạo module NLI verifier (claim -> verdict).
- [ ] Chuẩn hóa output verification matrix.

Day 5
- [ ] Cắm NLI vào `research_tier2`.
- [ ] Rule override cho claim safety-critical.

Day 6
- [ ] API payload pass-through ở endpoint research.
- [ ] UI matrix + telemetry panel.

Day 7
- [x] Integration test `/research` deep/deep_beta.
- [x] So sánh baseline vs bật reranker+NLI.

Day 8
- [x] Tối ưu latency p95.
- [x] Cache candidate embedding/rerank inputs.

Day 9
- [x] Chạy active eval loop full.
- [x] Xuất artifact KPI phase1.

Day 10 (Gate)
- [x] Gate phase1 đạt ngưỡng.
- [x] Merge + tag nội bộ `phase1-ready`.

### Day 11-18 (Phase 2)
Day 11
- [ ] Thiết kế schema DB mapping.
- [ ] Migration + model + schema API.

Day 12
- [ ] Seed dictionary 100+ biệt dược VN.
- [ ] Tạo importer script.

Day 13
- [ ] Implement hybrid normalize (dictionary + neural candidate).

Day 14
- [ ] Cắm normalize vào careguard/selfmed.
- [ ] Bổ sung `mapping_source`, `confidence`.

Day 15
- [ ] Nâng UX manual confirm cho người lớn tuổi.

Day 16
- [ ] Admin curation endpoint + audit trail.

Day 17
- [ ] Test bộ case VN brand/combo.
- [ ] Kiểm tra giảm miss DDI critical.

Day 18 (Gate)
- [ ] Gate phase2 đạt ngưỡng.
- [ ] Merge + tag `phase2-ready`.

### Day 19-28 (Phase 3)
Day 19
- [ ] OCR correction module (post-processing only).

Day 20
- [ ] Cắm OCR correction vào flow scan (không bỏ manual confirm).

Day 21
- [ ] Neural source router module.

Day 22
- [ ] Cắm router vào retrieval orchestrator + policy constraints.

Day 23
- [ ] Chuẩn hóa metadata lỗi/fallback/degraded path.

Day 24
- [ ] Nâng active-eval loop: baseline -> mine -> rerun -> compare.

Day 25
- [ ] Workflow schedule + artifact upload + strict gate.

Day 26
- [ ] Update canvas flow theo runtime thật.

Day 27
- [ ] Full stack live KPI run + canary deploy.

Day 28 (Final Gate)
- [ ] Gate phase3 đạt ngưỡng.
- [ ] Release tag + report tổng kết.

## 7. Checklist vận hành mỗi ngày
1. [ ] Standup 15 phút: blocker, owner, ETA.
2. [ ] Cập nhật `docs/hackathon/kpi-snapshot.md`.
3. [ ] Cập nhật changelog trong PR.
4. [ ] Chạy smoke deploy script.
5. [ ] Nếu fail gate: rollback bằng feature flag.

## 8. Bộ test chuẩn toàn chương trình
1. Unit tests cho module NN mới.
2. Integration tests cho `/research`, `/careguard`, `/selfmed`.
3. Safety tests:
   - refusal traps
   - critical DDI positive cases
   - low-context fallback correctness
4. Live KPI suite:
   - precision/recall/F1
   - latency p50/p95
   - fallback success rate
   - refusal compliance
   - unsupported claim rate

## 9. Rủi ro và kiểm soát
1. Rủi ro latency tăng do NN.
   - Giải pháp: timeout cứng, async, cache, top-N hợp lý.
2. Rủi ro false confidence của model.
   - Giải pháp: confidence gate + manual confirm + hard rule override.
3. Rủi ro drift dữ liệu thuốc VN.
   - Giải pháp: curation workflow + periodic re-eval.
