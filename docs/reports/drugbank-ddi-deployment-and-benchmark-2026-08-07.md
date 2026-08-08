# Báo cáo DrugBank DDI: triển khai, thực nghiệm và việc còn thiếu

Ngày thực hiện: 07/08/2026
Phạm vi: CareGuard DDI trên VPS `vm07302028.bnixvps.io.vn`
Mục đích: thay bộ DDI nội bộ khỏi nguồn kết luận/bằng chứng chính bằng artifact DrugBank có license; ghi chính xác số liệu có thể đưa vào báo cáo.

## Kết luận ngắn

DrugBank đã được ingest và đang là nguồn DDI bắt buộc trên VPS. Hệ thống không được dùng luật DDI nội bộ để đưa ra kết luận khi DrugBank mất, hỏng checksum hoặc không sẵn sàng: nó trả trạng thái `unavailable` thay vì “không có tương tác”.

Artifact hiện hành là **DrugBank 5.0, XML export 20/12/2017**. Đây là nguồn đã cũ; tuyệt đối không mô tả là “DrugBank mới nhất”. Cần có release mới hơn trước khi đưa hệ thống vào vận hành lâm sàng hoặc công bố tính cập nhật.

Kết quả thực nghiệm runtime đầu tiên cho thấy 242/250 cặp DrugBank dương tính được trả về đúng qua API (96,8%), 250/250 cặp âm tính được tạo từ DrugBank không trả alert (100%). Vì tập kiểm thử được lấy từ chính artifact mà runtime dùng, đây là **kiểm tra khớp nguồn–runtime (conformance)**, không phải benchmark lâm sàng độc lập. Quan trọng hơn, 8/250 ca dương tính bị bỏ sót: chưa được phép gọi hệ thống là đạt 100% coverage DrugBank.

## 1. Artifact được đưa vào runtime

Nguồn đầu vào do dự án cung cấp:

- XML: `drugbank.xml`
- SHA-256 XML: `36ec574eccdc2ed085b7510e166e8fa80255f4910bb1fcda5beebb4555e3bcf1`
- XML metadata: DrugBank `version="5.0"`, `exported-on="2017-12-20"`.
- File Excel `drug_info_with_approval_date.xlsx` được nhận cùng nguồn nhưng **chưa được dùng làm nhãn DDI hay để đánh giá độ đúng lâm sàng**.

Lệnh ingest đã chạy:

```bash
python3 scripts/data/drugbank_ingest.py \
  --input drugbank.xml \
  --out-dir <artifact-private> \
  --version drugbank-5.0-2017-12-20 \
  --source-version 5.0-2017-12-20
```

Kết quả artifact:

| Thành phần | Giá trị |
| --- | ---: |
| Top-level drug XML đã parse | 10.562 |
| Cặp DDI đã chuẩn hóa/deduplicate | 357.839 |
| Bản ghi dictionary/alias | 34.344 |
| DDI JSON shard | 88 |
| Dictionary JSON shard | 39 |
| SHA-256 manifest | `41ab4dcd628961a319a7f5eac0e46aaa6acb212d999463dec59f5992e5f9909b` |

Artifact đã nằm ngoài image/source tree tại `/secure/clara/drugbank` trên VPS; chỉ container ML được mount vào `/var/lib/clara/drugbank`. XML nguồn không được chuyển vào image hay commit vào Git.

## 2. Cấu hình runtime đã bật

Các biến production đã được thiết lập:

```dotenv
CAREGUARD_DRUGBANK_REQUIRED=true
CAREGUARD_DRUGBANK_SQLITE_ENABLED=true
CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=true
CAREGUARD_DRUGBANK_ARTIFACT_HOST_DIR=/secure/clara/drugbank
CAREGUARD_DRUGBANK_MANIFEST_PATH=/var/lib/clara/drugbank/manifest.json
CAREGUARD_DRUGBANK_SQLITE_PATH=/var/lib/clara/drugbank/ddi_index.sqlite
```

Sau redeploy, endpoint ML báo:

```json
{
  "state": "ready",
  "version": "drugbank-5.0-2017-12-20",
  "pair_count": 357839,
  "dictionary_record_count": 34344,
  "manifest_matches_index": true,
  "integrity_verified": true,
  "required": true
}
```

Khi test ở strict mode với index unavailable, response là `ddi_status.state=unavailable`, `conclusion_available=false`, không sinh alert DDI local/external và không trả “all clear”. Đây là hành vi an toàn cần giữ.

## 3. Bộ DDI nội bộ hiện còn vai trò gì?

`services/ml/src/clara_ml/nlp/seed_data/careguard_ddi_rules.v1.json` có 62 cặp luật curated. `data/demo/ddi-goldset.jsonl` và `data/demo/ddi_internal_test_set.json` có 50 ca; cả 50 đều dương tính, sinh từ 50 luật fallback đầu tiên.

Không dùng các file này để:

- gọi là “DrugBank dataset”;
- công bố recall/specificity/accuracy DDI;
- làm benchmark chính;
- xác nhận độ bao phủ DDI của production strict mode.

Chúng chỉ nên được giữ làm regression fixture cho nhánh fallback/dev, hoặc loại khỏi pipeline nếu nhóm không còn duy trì fallback. Khi `CAREGUARD_DRUGBANK_REQUIRED=true`, chúng không được dùng thay DrugBank để kết luận DDI.

## 4. Thực nghiệm đã chạy

Script mới: `scripts/evaluation/run_drugbank_runtime_conformance.py`.

Protocol:

1. Đọc manifest DrugBank đã checksum-verified.
2. Lấy mẫu quyết định với seed `20260807`: 250 cặp có DDI và 250 cặp không có trong index, từ canonical medication names của chính artifact.
3. Gọi `POST /v1/careguard/analyze` với `drugbank_required=true` vào ML đang chạy.
4. Chỉ ghi số tổng hợp, hash nguồn, nhóm lỗi và latency; không ghi mô tả interaction hoặc tên/cặp thuốc có license vào report.

Artifact kết quả trên VPS:

`/opt/clara-care/artifacts/drugbank-runtime-conformance/drugbank-5.0-2017-12-20-20260807.json`

| Chỉ số | Kết quả |
| --- | ---: |
| Cặp dương tính có trong index | 250 |
| Positive lookup pass | 242/250 = **96,8%** |
| Positive lookup fail | **8/250** |
| Cặp âm tính không có trong index | 250 |
| Negative lookup pass | **250/250 = 100%** |
| Positive latency p50 / p95 / max | 50,281 / 64,117 / 135,842 ms |
| Negative latency p50 / p95 / max | 50,161 / 60,468 / 163,305 ms |

### Diễn giải đúng

Được phép viết: “Trong kiểm tra conformance runtime với sample xác định từ artifact DrugBank 5.0 đã khóa checksum, CareGuard trả đúng 242/250 cặp có trong index và 250/250 cặp không có trong index; 8 false-negative source lookup cần được khắc phục.”

Không được viết:

- “CareGuard đạt 96,8% clinical accuracy.”
- “DrugBank benchmark đạt 96,8%.”
- “Hệ thống có specificity 100%.”
- “Hệ thống an toàn lâm sàng.”

Lý do: positive và negative đều được dựng từ chính release/index dùng để chạy. Đây không đo generalization sang release DrugBank khác, không có nhãn chuyên gia độc lập và không có patient outcome.

## 5. Phát hiện lỗi cần code ngay

8 ca dương tính trong sample không tạo alert dù index `ready`. Bảy ca có `matched_alert_count=0`; một ca có alert DrugBank nhưng pair sau normalize không còn khớp input sample. Đây là dấu hiệu đường chuẩn hóa medication trước lookup vẫn có thể đổi tên canonical bằng dictionary cũ của CLARA.

### Trạng thái sửa strict identity

Các mục 1–3 đã được triển khai trong source hiện tại, nhưng **chưa được phép
đổi số liệu runtime cũ thành pass**:

1. Khi `CAREGUARD_DRUGBANK_REQUIRED=true`, resolver đi qua
   `DrugBankDdiStore.medication_candidates()` và selection gắn với
   `drugbank_id` + `source_version`; nhánh đó tách khỏi local Vietnamese
   dictionary/alias-map.
2. Tên không có một candidate DrugBank duy nhất trả
   `requires_medication_clarification`; không chọn bằng local mapping, fuzzy
   matching hay LLM.
3. Test strict resolver/DrugBank ingest hiện pass trong môi trường source
   (45 pass, 2 skip cho nhóm focused test); đây là regression source-level,
   không thay thế runtime conformance trên deployment.
4. **Vẫn pending:** rerun conformance strict 250+250 (hoặc 1.000+1.000) trên
   image/deployment hiện hành. Release gate kỹ thuật phải là
   `positive_pair_lookup.failed == 0`, `negative_pair_lookup.failed == 0`,
   `drugbank.state == ready`, `manifest_matches_index == true`. Cho đến khi
   JSON aggregate mới được lưu, 242/250 và 8 failure ở trên vẫn là kết quả
   runtime duy nhất được phép trích dẫn.

Việc này là sửa source-identity/runtime, **không** phải chỉnh cho số benchmark đẹp.

## 6. Những việc cần setup hoặc chạy thêm

| Việc | Loại | Điều kiện hoàn thành |
| --- | --- | --- |
| Sửa strict medication identity ở mục 5 | Code + test | Không còn false negative source lookup trong sample và regression test pass |
| Rerun conformance 250+250 (hoặc 1.000+1.000) | Chạy | Lưu JSON aggregate, seed, source/manifest hash, revision/image digest |
| Bản DrugBank mới hơn | Data/license | Ingest release mới, thay atomic artifact, chạy lại toàn bộ conformance |
| Evaluation độc lập | Thiết lập data + review | Locked positive/negative set không sinh từ release runtime; nhãn dược sĩ/clinician, phân tầng serious/critical, review độc lập |
| VN name/brand/code-switch benchmark | Data + review | Các alias có review dược sĩ, tách development/locked test, metric top-1 và abstention/clarification correctness |
| Release gate | CI/ops | Không cho release strict nếu manifest/index không ready, hoặc conformance artifact bị thiếu/fail |

Để đo recall/sensitivity/specificity DDI có giá trị khoa học, tập test phải có positive và negative độc lập, đóng băng trước chạy, không được lấy trực tiếp từ index dùng để chấm. Nếu chưa có, manuscript phải ghi `not measured` thay vì bịa chỉ số.

## 7. Đoạn có thể dán vào manuscript

> CareGuard được triển khai với artifact DrugBank 5.0 (XML export ngày 20/12/2017) có license thương mại, được ingest thành 357.839 cặp tương tác và 34.344 bản ghi dictionary. Artifact được xác thực bằng source SHA-256, manifest SHA-256 và đối chiếu số bản ghi trong SQLite index. Khi bật strict mode, hệ thống fail closed nếu artifact không sẵn sàng hoặc integrity không khớp. Một kiểm tra conformance runtime trên 250 cặp có tương tác và 250 cặp không có trong chính artifact cho kết quả lần lượt 242/250 và 250/250. Đây là kiểm tra đúng đắn của đường ingest/index/runtime, không phải đánh giá lâm sàng độc lập; tám trường hợp positive lookup chưa khớp đang được xem là lỗi cần sửa trước khi sử dụng số liệu này làm release gate.

## 8. Lệnh vận hành tái lập

```bash
# Trên VPS; ML_INTERNAL_API_KEY phải có trong environment, không truyền qua argv.
set -a; . /opt/clara-care/.env; set +a
python3 /opt/clara-care/scripts/evaluation/run_drugbank_runtime_conformance.py \
  --artifact-dir /secure/clara/drugbank \
  --positive-sample 250 --negative-sample 250 --seed 20260807 \
  --output /opt/clara-care/artifacts/drugbank-runtime-conformance/<run-id>.json
```

Trước khi coi run là hợp lệ, kiểm tra authenticated `/health/details` có `drugbank.state=ready`, `manifest_matches_index=true`, `integrity_verified=true`, `pair_count>0` và `dictionary_record_count>0`.
