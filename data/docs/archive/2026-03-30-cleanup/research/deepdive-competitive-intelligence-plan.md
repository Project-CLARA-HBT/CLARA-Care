# Kế Hoạch Deepdive Nghiên Cứu Đối Thủ

## 1) Mục tiêu và phạm vi
- Mục tiêu: lập bản đồ đầy đủ các sản phẩm tương tự CLARA theo 5 cụm chức năng, phân tích mức cạnh tranh, độ tin cậy y khoa, và khoảng trống sản phẩm.
- Phạm vi deepdive bắt buộc:
  - `AI medical chat`
  - `Medication manager`
  - `DDI checker` (Drug-Drug Interaction)
  - `Symptom checker`
  - `Telehealth`
- Đơn vị phân tích: sản phẩm/app/feature-level (không chỉ công ty-level).
- Đầu ra ưu tiên: dữ liệu có thể chấm điểm được, truy xuất nguồn rõ ràng, cập nhật định kỳ.

## 2) Khung tìm kiếm “tất cả sản phẩm tương tự”
### 2.1 Danh sách nguồn bắt buộc theo kênh
- Web:
  - Website chính thức sản phẩm, trang pricing, docs/FAQ, trang compliance/regulatory.
  - Landing pages tính năng và blog release.
- App Store:
  - Apple App Store, Google Play.
  - Metadata app: mô tả, version history, rating, số lượng review, phân loại tuổi, quốc gia hỗ trợ.
- Review:
  - G2, Capterra, Trustpilot, Reddit (nếu có thảo luận sản phẩm), cộng đồng chuyên ngành.
- Changelog/Release:
  - Changelog chính thức, release notes trên website, product updates.
  - Nếu là sản phẩm dev-facing: GitHub Releases/Roadmap công khai.

### 2.2 Cụm từ khóa và truy vấn
- Cụm `AI medical chat`:
  - `"AI medical chat"`, `"AI doctor chat app"`, `"clinical chatbot"`
- Cụm `Medication manager`:
  - `"medication manager app"`, `"pill reminder"`, `"medication tracking"`
- Cụm `DDI checker`:
  - `"drug interaction checker"`, `"DDI checker app"`, `"medication interaction alert"`
- Cụm `Symptom checker`:
  - `"AI symptom checker"`, `"symptom assessment app"`, `"triage chatbot"`
- Cụm `Telehealth`:
  - `"telehealth app"`, `"virtual care platform"`, `"online doctor consultation"`
- Truy vấn kết hợp bắt buộc:
  - `(<cụm>) + ("HIPAA" OR "GDPR" OR "medical disclaimer")`
  - `(<cụm>) + ("pricing" OR "subscription" OR "free trial")`
  - `(<cụm>) + ("changelog" OR "release notes" OR "what's new")`

### 2.3 Quy tắc đưa vào / loại ra
- Đưa vào:
  - Có sản phẩm hoạt động công khai, truy cập được trên web/app store.
  - Có ít nhất 1 tính năng trùng cụm mục tiêu.
- Loại ra:
  - Sản phẩm chết/không cập nhật >18 tháng (trừ khi là đối thủ lịch sử quan trọng).
  - Nội dung mơ hồ, không chứng minh được tính năng từ nguồn chính thức.

## 3) Quy trình thu thập dữ liệu
## 3.1 Pipeline chuẩn
1. Discovery:
   - Thu candidate list theo từng cụm từ web + app store.
2. Validation:
   - Xác nhận sản phẩm còn hoạt động, đúng domain y tế/chăm sóc sức khỏe.
3. Extraction:
   - Trích xuất dữ liệu theo schema chuẩn (xem mục 4).
4. Evidence-linking:
   - Mỗi field quan trọng phải có URL nguồn + ngày truy xuất.
5. Scoring:
   - Chấm điểm theo schema 100 điểm (mục 5).
6. Synthesis:
   - Tạo artifact tổng hợp + insight + khoảng trống chiến lược.

### 3.2 Dữ liệu tối thiểu cần thu cho mỗi sản phẩm
- Thông tin định danh: tên sản phẩm, công ty, URL chính, quốc gia.
- Cụm phù hợp: 1-n cụm trong 5 cụm bắt buộc.
- Tính năng: core feature, giới hạn, edge cases.
- Tin cậy y khoa: disclaimer, clinical oversight, nguồn kiến thức.
- An toàn và pháp lý: HIPAA/GDPR/SOC2 (nếu công khai), terms/privacy.
- Giá và mô hình doanh thu: free/freemium/subscription/B2B contract.
- Tín hiệu thị trường: rating/review count/app installs (nếu có).
- Nhịp cập nhật: ngày update gần nhất, release cadence.

## 4) Data schema chuẩn hóa
- Bảng `products_master`:
  - `product_id`, `product_name`, `company`, `cluster_tags`, `platforms`, `regions`, `pricing_model`, `target_users`, `last_seen_at`.
- Bảng `features_evidence`:
  - `product_id`, `feature_name`, `feature_category`, `evidence_url`, `evidence_type` (web/appstore/review/changelog), `captured_at`.
- Bảng `trust_safety`:
  - `product_id`, `medical_disclaimer`, `human_in_loop`, `clinical_reference`, `compliance_claims`, `risk_notes`.
- Bảng `market_signals`:
  - `product_id`, `rating_avg`, `rating_count`, `review_sentiment`, `price_point`, `release_frequency`.
- Bảng `scoring`:
  - `product_id`, `feature_fit_score`, `trust_score`, `ux_score`, `go_to_market_score`, `velocity_score`, `total_score`.

## 5) Schema chấm điểm (100 điểm)
- `Feature Fit` (30):
  - Độ phủ tính năng theo cụm chính và cụm mở rộng.
- `Medical Trust & Safety` (25):
  - Disclaimer minh bạch, thông tin clinical governance, guardrails.
- `User Experience` (15):
  - Dễ onboarding, clarity của flow, chất lượng phản hồi người dùng.
- `Commercial & GTM` (15):
  - Pricing clarity, segment fit (B2C/B2B), distribution channels.
- `Product Velocity` (15):
  - Tần suất cập nhật/changelog, mức tiến hóa tính năng.

**Công thức**:  
`Total = Feature Fit + Trust & Safety + UX + Commercial & GTM + Velocity`

## 6) Output artifacts bắt buộc
- `Artifact A`: Master competitor list (CSV/Sheet) theo 5 cụm.
- `Artifact B`: Hồ sơ 1 trang cho mỗi đối thủ trọng điểm (battlecard).
- `Artifact C`: Ma trận so sánh tính năng x đối thủ.
- `Artifact D`: Bảng chấm điểm + ranking + confidence level.
- `Artifact E`: Insight memo (top patterns, khoảng trống sản phẩm, cơ hội khác biệt).
- `Artifact F`: Watchlist cập nhật (sản phẩm mới, thay đổi pricing, release lớn).

## 7) Micro-task breakdown (siêu nhỏ)
| ID | Micro-task | Effort | DoD (Definition of Done) | Nguồn dữ liệu |
|---|---|---:|---|---|
| CI-MT01 | Tạo danh sách từ khóa cho 5 cụm | 0.5h | File keyword list có >= 15 truy vấn | Web search engine |
| CI-MT02 | Chuẩn hóa tiêu chí include/exclude | 0.5h | Checklist 1 trang, có ví dụ pass/fail | Internal rubric |
| CI-MT03 | Thu 20 candidates cho cụm AI medical chat | 1.0h | Danh sách có URL + trạng thái active | Web + App Store |
| CI-MT04 | Thu 20 candidates cho cụm medication manager | 1.0h | Danh sách có URL + platform | Web + App Store |
| CI-MT05 | Thu 20 candidates cho cụm DDI checker | 1.0h | Danh sách có URL + mô tả DDI | Web + App Store |
| CI-MT06 | Thu 20 candidates cho cụm symptom checker | 1.0h | Danh sách có URL + use case | Web + App Store |
| CI-MT07 | Thu 20 candidates cho cụm telehealth | 1.0h | Danh sách có URL + loại dịch vụ | Web + App Store |
| CI-MT08 | Deduplicate toàn bộ candidate list | 0.5h | Không còn bản ghi trùng product/domain | Master sheet |
| CI-MT09 | Verify tình trạng hoạt động từng sản phẩm | 1.0h | 100% record có active/inactive flag | Website chính thức |
| CI-MT10 | Gắn tag cụm chính/phụ cho từng sản phẩm | 0.5h | Mỗi record có >=1 cluster tag hợp lệ | Master sheet |
| CI-MT11 | Thu feature evidence từ website chính thức | 2.0h | Mỗi sản phẩm có >=3 evidence links | Web |
| CI-MT12 | Thu metadata App Store/Google Play | 2.0h | Có rating, review count, update date | Apple App Store + Google Play |
| CI-MT13 | Thu review định tính (ưu/nhược) | 1.5h | Mỗi sản phẩm có >=5 điểm review tổng hợp | G2/Capterra/Trustpilot/Reddit |
| CI-MT14 | Thu changelog/release notes | 1.5h | Có mốc cập nhật gần nhất + cadence | Changelog/Release pages |
| CI-MT15 | Trích thông tin pricing và plan | 1.0h | 100% record có pricing_model | Pricing pages |
| CI-MT16 | Trích tín hiệu legal/compliance công khai | 1.0h | Có HIPAA/GDPR/SOC2 claim nếu tồn tại | Trust center/Privacy/Terms |
| CI-MT17 | Chuẩn hóa dữ liệu theo schema | 1.5h | 5 bảng schema được điền >90% | Internal dataset |
| CI-MT18 | Chấm điểm Feature Fit | 1.0h | Điểm 0-30 cho tất cả sản phẩm | Features evidence |
| CI-MT19 | Chấm điểm Trust & Safety | 1.0h | Điểm 0-25 + ghi chú rủi ro | Legal/clinical evidence |
| CI-MT20 | Chấm điểm UX từ review + flow | 1.0h | Điểm 0-15 + rationale ngắn | Review + app screenshots |
| CI-MT21 | Chấm điểm GTM/commercial | 0.5h | Điểm 0-15 + pricing logic | Pricing + distribution |
| CI-MT22 | Chấm điểm velocity sản phẩm | 0.5h | Điểm 0-15 dựa trên cadence | Changelog/update history |
| CI-MT23 | Tổng hợp ranking + confidence level | 0.5h | Bảng xếp hạng có cột confidence | Scoring table |
| CI-MT24 | Tạo battlecard top 10 đối thủ | 2.0h | 10 battlecards hoàn chỉnh | All validated sources |
| CI-MT25 | Viết insight memo + product gaps | 1.5h | Memo nêu top 5 cơ hội khác biệt | Artifacts A-D |
| CI-MT26 | Thiết lập watchlist cập nhật hàng tháng | 0.5h | Danh sách nguồn + lịch refresh | Changelog + app stores + news |
| CI-MT27 | Review legal/ethics trước khi chia sẻ | 0.5h | Checklist legal/ethics pass | Internal policy + legal docs |

## 8) Nguyên tắc pháp lý và đạo đức (bắt buộc)
- Mục tiêu của nghiên cứu là **học ý tưởng, benchmark và tìm khoảng trống**, không sao chép.
- Không sao chép:
  - Tên thương hiệu, slogan, nhận diện thương hiệu.
  - Nội dung bản quyền (copywriting, hình ảnh, tài liệu độc quyền).
  - Mã nguồn, logic độc quyền, reverse engineering trái phép.
- Chỉ dùng nguồn công khai/hợp pháp; lưu bằng chứng URL và thời điểm truy xuất.
- Không thu thập dữ liệu cá nhân nhạy cảm hoặc vượt quá điều khoản sử dụng nền tảng.
- Mọi đề xuất sản phẩm nội bộ phải được diễn giải lại theo ngữ cảnh CLARA, có cải tiến khác biệt rõ.

## 9) Tiêu chí hoàn tất toàn bộ deepdive
- Có danh sách đối thủ hợp lệ cho cả 5 cụm, đã loại trùng và xác thực hoạt động.
- Có dữ liệu nguồn đầy đủ web/app store/review/changelog cho nhóm trọng điểm.
- Có bảng chấm điểm 100 điểm + ranking + confidence level.
- Có đầy đủ artifacts A-F.
- Có biên bản legal/ethics xác nhận tuân thủ.
