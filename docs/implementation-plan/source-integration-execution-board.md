# Bảng Triển Khai Tích Hợp Nguồn Dữ Liệu

Mục tiêu: triển khai toàn bộ nguồn dữ liệu cho CLARA theo thứ tự an toàn và khả thi: `nguồn công khai` -> `nguồn cần key` -> `nguồn thương mại`.

Quy ước trạng thái:
- `[ ]` chưa làm
- `[~]` đang làm
- `[x]` hoàn tất

## 1. Definition of Done cho mỗi nguồn

Mỗi nguồn chỉ được đánh dấu hoàn tất khi đủ 6 micro-task:
1. `connector_stub`: tạo connector + hợp đồng dữ liệu chuẩn.
2. `auth`: xác thực (hoặc đánh dấu public/no-auth).
3. `mapping`: map về schema chuẩn CLARA.
4. `validation`: kiểm tra chất lượng và tính hợp lệ dữ liệu.
5. `freshness_monitor`: theo dõi độ mới dữ liệu + cảnh báo stale.
6. `fallback`: định nghĩa nguồn dự phòng khi lỗi/quota.

## 2. Phase A - Nguồn công khai ưu tiên (không cần key)

| Nguồn | Nhánh dùng chính | connector_stub | auth | mapping | validation | freshness_monitor | fallback |
|---|---|---|---|---|---|---|---|
| Bộ Y tế Việt Nam (moh.gov.vn) | Research + Self-Med | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| Cục Quản lý Dược (DAV) | Self-Med | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| Trung tâm DI & ADR Quốc gia | Self-Med | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| PubMed (NCBI E-utilities, no-key mode) | Research | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| ClinicalTrials.gov API v2 | Research | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| openFDA (drug label/event, no-key mode) | Self-Med + Research | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| DailyMed Web Services | Self-Med | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| RxNav/RxNorm công khai | Self-Med | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |
| WHO disease/outbreak public feeds | Research | [ ] | [ ] no-auth | [ ] | [ ] | [ ] | [ ] |

Ghi chú:
- Giai đoạn này phải hoàn tất trước để có baseline dữ liệu và dashboard freshness.
- Với nguồn public, vẫn bắt buộc rate-limit và retry/backoff.

## 3. Phase B - Nguồn cần API key hoặc OAuth

| Nguồn | Nhánh dùng chính | connector_stub | auth | mapping | validation | freshness_monitor | fallback |
|---|---|---|---|---|---|---|---|
| NHIC/CSDL Dược (API Bộ Y tế) | Self-Med | [ ] | [ ] OAuth2 | [ ] | [ ] | [ ] | [ ] |
| WHO ICD API | Research + Self-Med | [ ] | [ ] client_credentials | [ ] | [ ] | [ ] | [ ] |
| PubMed key mode (NCBI API key) | Research | [ ] | [ ] API key | [ ] | [ ] | [ ] | [ ] |
| openFDA key mode | Self-Med + Research | [ ] | [ ] API key | [ ] | [ ] | [ ] | [ ] |
| FHIR API đối tác bệnh viện/phòng khám | Self-Med + Doctor | [ ] | [ ] OAuth2 | [ ] | [ ] | [ ] | [ ] |
| Google Cloud Vision OCR | Self-Med OCR | [ ] | [ ] service account | [ ] | [ ] | [ ] | [ ] |
| AWS Textract | Self-Med OCR | [ ] | [ ] IAM/SigV4 | [ ] | [ ] | [ ] | [ ] |
| Azure Document Intelligence | Self-Med OCR | [ ] | [ ] key/token | [ ] | [ ] | [ ] | [ ] |

Ghi chú:
- Toàn bộ secret phải đi qua secret manager.
- Bổ sung cảnh báo quota và circuit breaker theo từng nguồn.

## 4. Phase C - Nguồn thương mại và license nâng cao

| Nguồn | Nhánh dùng chính | connector_stub | auth | mapping | validation | freshness_monitor | fallback |
|---|---|---|---|---|---|---|---|
| DrugBank API | Self-Med | [ ] | [ ] commercial key | [ ] | [ ] | [ ] | [ ] |
| NICE Syndication API | Research | [ ] | [ ] account/key | [ ] | [ ] | [ ] | [ ] |
| UMC VigiBase data access | Self-Med + Research | [ ] | [ ] agreement/key | [ ] | [ ] | [ ] | [ ] |
| Scopus API | Research | [ ] | [ ] commercial key | [ ] | [ ] | [ ] | [ ] |
| Web of Science API | Research | [ ] | [ ] commercial key | [ ] | [ ] | [ ] | [ ] |
| OCR ABBYY/Nanonets/Rossum (nếu chọn) | Self-Med OCR | [ ] | [ ] commercial key | [ ] | [ ] | [ ] | [ ] |

Ghi chú:
- Chỉ bật Phase C khi đã có legal review + cost guardrails.

## 5. Checklist credential cần bạn cung cấp

### 5.1 Cần trước ngay cho Phase B
- [ ] `NHIC_CLIENT_ID`, `NHIC_CLIENT_SECRET`, `NHIC_TOKEN_URL`, `NHIC_BASE_URL`
- [ ] `WHO_ICD_CLIENT_ID`, `WHO_ICD_CLIENT_SECRET`, `WHO_ICD_TOKEN_URL`
- [ ] `NCBI_API_KEY`
- [ ] `OPENFDA_API_KEY`
- [ ] `FHIR_BASE_URL`, `FHIR_CLIENT_ID`, `FHIR_CLIENT_SECRET`, `FHIR_TOKEN_URL`
- [ ] `GCP_PROJECT_ID`, `GCP_VISION_SERVICE_ACCOUNT_JSON`
- [ ] `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- [ ] `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY`

### 5.2 Cần khi mở Phase C
- [ ] `DRUGBANK_API_KEY` + xác nhận license
- [ ] `NICE_API_KEY` (hoặc tài khoản syndication) + xác nhận điều khoản
- [ ] `VIGIBASE_ACCESS_INFO` + xác nhận data agreement
- [ ] `SCOPUS_API_KEY`, `WOS_API_KEY` (nếu dùng)
- [ ] OCR commercial credentials (nếu chọn nhà cung cấp thương mại)

## 6. Thứ tự thực thi micro-task

1. Hoàn tất toàn bộ nguồn Phase A (đủ 6 micro-task mỗi nguồn).
2. Khóa schema chuẩn và chạy báo cáo chất lượng tuần đầu.
3. Nhận credential Phase B, triển khai từng nguồn theo thứ tự: NHIC -> WHO ICD -> OCR chính.
4. Chỉ mở Phase C sau khi có legal sign-off và ngân sách.

## 7. Gate để chuyển pha

- Gate A -> B:
  - Tỷ lệ ingest thành công Phase A >= 97%.
  - Freshness monitor hoạt động ổn định 7 ngày liên tục.
- Gate B -> C:
  - Auth/key rotation vận hành ổn định.
  - Không có incident nghiêm trọng về leak secret/quota spike.
  - Đã có quyết định ngân sách và pháp lý cho nguồn thương mại.
