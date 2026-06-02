# Trusted Sources Và Kế Hoạch API Access Cho CLARA (Research + Self-Med)

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-25

## 1. Mục tiêu

Thiết lập danh sách nguồn dữ liệu y khoa uy tín (Việt Nam + quốc tế) và kế hoạch truy cập API phục vụ:
- `CLARA Research`: truy xuất bằng chứng, guideline, trial, dữ liệu an toàn thuốc.
- `CLARA Self-Med`: tra cứu thông tin thuốc chuẩn hóa, cảnh báo tương tác, cảnh báo an toàn, giải thích cho người dùng phổ thông.

## 2. Danh sách nguồn ưu tiên (VN + quốc tế)

### 2.1 Việt Nam (ưu tiên pháp lý nội địa)

1. Cục Quản lý Dược (DAV) - tra cứu giấy đăng ký thuốc, thuốc không kê đơn, thuốc vi phạm chất lượng, giá thuốc công khai.
2. Trung tâm Thông tin Y tế Quốc gia (Bộ Y tế) - API Hệ thống CSDL Dược (v2, production + sandbox).
3. Trung tâm DI & ADR Quốc gia (canhgiacduoc.org.vn) - cảnh báo an toàn thuốc, thông tin cảnh giác dược, cổng báo cáo ADR trực tuyến.
4. Cổng thông tin Bộ Y tế (moh.gov.vn) - quyết định/hướng dẫn chẩn đoán và điều trị (guideline cấp Bộ).

### 2.2 Quốc tế (evidence và interoperability)

1. ClinicalTrials.gov API v2 - trial registry chuẩn cho nghiên cứu lâm sàng.
2. WHO ICTRP Search Portal Web Service - dữ liệu trial toàn cầu (mô hình truy cập theo điều kiện WHO).
3. NCBI E-utilities (PubMed/Entrez) - literature + guideline evidence mining.
4. WHO ICD API - chuẩn hóa mã bệnh ICD-11/ICD-10 (ontology/code system).
5. openFDA (drug/label, drug/event) - nhãn thuốc và dữ liệu báo cáo biến cố bất lợi.
6. DailyMed REST API - nhãn SPL mới nhất do FDA công bố.
7. RxNorm/RxNav API + RxClass API - chuẩn hóa tên thuốc/mã thuốc và quan hệ lớp thuốc.
8. DrugBank API (commercial) - dữ liệu tương tác thuốc (DDI) và tri thức dược chuyên sâu.
9. UMC VigiBase/VigiAccess API - nguồn pharmacovigilance toàn cầu từ WHO PIDM.
10. EMA EudraVigilance + adrreports.eu - dữ liệu ADR tại EU/EEA.
11. NICE Syndication API - nội dung guideline có thỏa thuận tái sử dụng.
12. OCR cho tài liệu scan: Google Cloud Vision, AWS Textract, Azure Document Intelligence.

## 3. Bảng chi tiết nguồn dữ liệu và truy cập

| Nguồn | Phạm vi chính | Mục đích dùng trong CLARA | Endpoint/loại truy cập | API key? | Cần bạn cung cấp gì | Rate-limit/Lưu ý pháp lý ngắn |
|---|---|---|---|---|---|---|
| DAV - Cổng DVC Cục Quản lý Dược | VN; thuốc lưu hành/thu hồi/OTC/giá | Kiểm tra hợp pháp thuốc tại VN, ưu tiên Self-Med | Web tra cứu + export (ví dụ: `/congbothuoc/`, `/congbothuockhongkedon`, `/congbothuocvipham/index`) | Không (public web) | Danh sách trường cần crawl hợp lệ, tần suất đồng bộ | Dữ liệu hiển thị có ghi chú chỉ là dữ liệu cấp số đăng ký gốc; cần tuân thủ điều khoản website, không crawl quá tải |
| NHIC/TTYQG - API CSDL Dược (Bộ Y tế) | VN; dữ liệu dược vận hành thời gian thực | Nguồn chuẩn để tích hợp chính thức pharmacy workflow tại VN | REST v2: `https://api.csdlduoc.com.vn/v2`, sandbox: `https://api-sandbox.csdlduoc.com.vn/v2` | Có (OAuth2 + Bearer) | Tài khoản kết nối, công văn/đăng ký tích hợp, thông tin môi trường test/prod | Bắt buộc HTTPS, OAuth2; API dành cho kết nối hệ thống nghiệp vụ, không phải API public cho end-user app |
| Trung tâm DI & ADR Quốc gia (canhgiacduoc.org.vn) | VN; cảnh giác dược | Pharmacovigilance nội địa, cảnh báo an toàn thuốc cho Self-Med | Chủ yếu web portal + bản tin + biểu mẫu ADR online | Không (public web) | Danh mục chuyên mục cần theo dõi (alert, bản tin, văn bản) | Nguồn tham khảo cảnh báo chính thống; cần kiểm duyệt lâm sàng trước khi suy diễn khuyến cáo cá nhân hóa |
| Cổng thông tin Bộ Y tế (moh.gov.vn) | VN; guideline/quyết định chuyên môn | Nguồn guideline nội địa cho Research | Web/PDF văn bản pháp quy và hướng dẫn chuyên môn | Không | Danh sách chuyên khoa ưu tiên để index | Không có API chuẩn công khai; cần quy trình ingest PDF + metadata + versioning quyết định |
| ClinicalTrials.gov API v2 | Quốc tế; trial | Trial discovery, evidence landscape, recruitment intelligence | REST + OpenAPI (`/api/v2/studies`, `/api/v2/version`) | Không | Bộ lọc nghiên cứu (disease, phase, country, status) | Dữ liệu refresh hàng ngày (Mon-Fri); ingest modernization từ 2025-08-26 có thay đổi một số field |
| WHO ICTRP Search Portal Web Service | Quốc tế; trial đa registry | Bổ sung trial ngoài ClinicalTrials.gov | XML Web Service theo điều kiện WHO | Thường có thỏa thuận truy cập | Mục đích sử dụng (research), tổ chức pháp nhân, ngân sách dịch vụ | WHO nêu rõ điều kiện sử dụng và chi phí dịch vụ web service/crawling |
| NCBI E-utilities (PubMed/Entrez) | Quốc tế; bài báo/guideline evidence | Truy xuất chứng cứ y văn và citation pipeline | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (`esearch`, `efetch`, `esummary`) | Tùy chọn (khuyến nghị có) | NCBI account + API key (nếu cần throughput cao), email/tool tag | Không key: 3 rps; có key: 10 rps (cao hơn cần xin thêm) |
| WHO ICD API | Quốc tế; coding chuẩn | Chuẩn hóa thuật ngữ bệnh/chẩn đoán cho RAG và interoperability | `https://id.who.int/icd/...` + token endpoint WHO | Có (client id/secret) | Tài khoản ICD API, client credentials, ngôn ngữ cần dùng | OAuth2 client credentials; license ICD-11 theo CC BY-ND 3.0 IGO, cần tuân thủ điều kiện license |
| openFDA - drug/label | Quốc tế; nhãn thuốc | Hỗ trợ DDI text evidence, cảnh báo thành phần chống chỉ định | `https://api.fda.gov/drug/label.json` | Tùy chọn | API key openFDA (nếu dùng thường xuyên) | 240 req/phút; không key: 1,000 req/ngày; có key: 120,000 req/ngày; dữ liệu không mặc định là “validated for clinical use” |
| openFDA - drug/event (FAERS qua API) | Quốc tế; pharmacovigilance | Signal screening ADR, trend adverse event | `https://api.fda.gov/drug/event.json` | Tùy chọn | Cấu hình query fields (reaction/drug/seriousness) | Cùng chính sách rate-limit openFDA; dữ liệu báo cáo tự nguyện, không chứng minh quan hệ nhân quả |
| DailyMed REST API | Quốc tế; SPL nhãn thuốc | Bổ sung nhãn cấu trúc chuẩn (SPL) và mapping drug labels | `https://dailymed.nlm.nih.gov/dailymed/services/v2/...` (vd `/spls.json`) | Không | Danh sách endpoint cần ingest, chu kỳ sync | Public API; cần trích dẫn nguồn NLM/FDA và lưu dấu phiên bản |
| RxNorm/RxNav + RxClass API (NLM) | Quốc tế; chuẩn hóa thuốc/lớp thuốc | Chuẩn hóa tên hoạt chất/biệt dược, mapping mã thuốc, lớp dược lý | `https://rxnav.nlm.nih.gov/REST/...`, `.../rxclass/...` | Không | Quy ước mapping nội bộ (VN brand -> RxCUI), bảng đồng bộ mã | Không cần license cho đa số API công khai; cần gắn attribution theo yêu cầu NLM |
| DrugBank API | Quốc tế; DDI/chuyên sâu dược | DDI engine chất lượng cao cho Self-Med (tầng premium) | REST API (developer hub/docs DrugBank) | Có (commercial key/password) | Gói license, phạm vi sử dụng (prod/research), pháp nhân ký hợp đồng | Trả phí; ràng buộc license rõ về mục đích sử dụng dữ liệu và phân phối lại |
| UMC VigiBase / VigiAccess API | Quốc tế; pharmacovigilance toàn cầu | Tăng coverage ADR đa quốc gia, comparative signal | Dịch vụ truy cập VigiBase + VigiAccess API | Có/Thỏa thuận | Tổ chức, use-case, hợp đồng dữ liệu | Member WHO PIDM có cơ chế riêng; tổ chức khác thường trả phí, phải chấp thuận caveat/data-use terms |
| EMA EudraVigilance + adrreports.eu | EU/EEA; pharmacovigilance | Đối chiếu tín hiệu an toàn từ thị trường EU | Portal công khai + cơ chế truy cập phân tầng EudraVigilance | Không cho portal public; có đăng ký cho mức sâu | Xác định nhu cầu: public portal hay dataset nâng cao/academic access | Truy cập dữ liệu phân tầng theo chính sách EMA; phải tuân thủ bảo mật dữ liệu và confidentiality undertaking khi cần dữ liệu mở rộng |
| NICE Syndication API | UK; guideline | Ingest guideline machine-readable có license rõ ràng | API syndication của NICE (theo account/thoả thuận) | Có (theo tài khoản thỏa thuận) | Mục đích dùng, phạm vi AI use, hợp đồng reuse content | Dùng nội dung NICE cho AI cần xin phép/phù hợp điều khoản tái sử dụng nội dung |
| Google Cloud Vision API | OCR/scan | OCR thuốc toa đơn/HDSD/PDF scan cho pipeline nhập liệu | Vision API + IAM/service account | Có (GCP auth) | GCP project, billing, service account, vùng dữ liệu | Quota mặc định theo project (ví dụ request quota), có thể xin tăng; chú ý dữ liệu sức khỏe và chính sách lưu trữ |
| AWS Textract | OCR/scan | OCR biểu mẫu, hóa đơn, chứng từ dược/phòng khám | Textract API (IAM + SigV4) | Có (AWS creds) | AWS account, IAM role/user, region, KMS/policy | Quota theo TPS + concurrent jobs theo region; cần cấu hình quyền và bảo mật dữ liệu y tế |
| Azure Document Intelligence | OCR/scan | OCR tài liệu y khoa phức tạp, form extraction | Azure AI Document Intelligence REST | Có (resource key/Entra ID) | Azure subscription, resource key, region | Quota theo tier/region; vượt ngưỡng nhận 429, cần cơ chế retry/backoff và tuân thủ data governance |

## 4. Cần bạn cung cấp ngay (Checklist)

- [ ] Xác nhận ưu tiên triển khai giai đoạn 1: chỉ nguồn `public/free` hay bao gồm luôn nguồn `commercial` (DrugBank, NICE API, VigiBase nâng cao).
- [ ] Cung cấp tài khoản/kênh đăng ký cho API VN chính thức: `NHIC CSDL Dược` (đầu mối pháp lý + kỹ thuật).
- [ ] Cung cấp API keys/tài khoản hiện có (nếu đã có): openFDA, NCBI, WHO ICD, GCP/AWS/Azure.
- [ ] Chọn 1 nhà cung cấp OCR chính cho production (Google/AWS/Azure) và 1 nhà cung cấp dự phòng.
- [ ] Chốt phạm vi pháp lý sử dụng dữ liệu: chỉ research nội bộ hay hiển thị trực tiếp cho người dùng cuối Self-Med.
- [ ] Chốt danh sách chuyên khoa/nhóm bệnh ưu tiên để ingest guideline (ví dụ: tim mạch, nội tiết, hô hấp, nhi, sản).
- [ ] Chốt thị trường ưu tiên cho trial/pharmacovigilance: VN-only, VN+US, hay global.
- [ ] Cung cấp email pháp lý/compliance để gửi yêu cầu data-use agreement (NICE, WHO ICTRP, UMC VigiBase nếu dùng).
- [ ] Chốt chính sách lưu dữ liệu nhạy cảm (PII/PHI): lưu hay không lưu ảnh scan gốc, thời gian retention, mã hóa bắt buộc.
- [ ] Chốt ngưỡng SLA/throughput mong muốn (QPS, số người dùng đồng thời) để xin quota tăng ngay từ đầu.

## 5. Khuyến nghị triển khai theo pha (ngắn)

1. Pha 1 (nhanh, ít rào cản): DAV, MOH guideline web ingest, openFDA, NCBI, ClinicalTrials.gov, DailyMed, RxNorm, 1 OCR cloud.
2. Pha 2 (chính thức VN + nâng chất lượng): NHIC CSDL Dược API, canhgiacduoc ingestion chuẩn hóa.
3. Pha 3 (premium/compliance-heavy): DrugBank, NICE API, WHO ICTRP web service nâng cao, UMC VigiBase data services.

## 6. Nguồn tham chiếu chính (official)

- DAV DVC: https://dichvucong.dav.gov.vn/congbothuoc/  
- NHIC API CSDL Dược (QĐ 522): https://nhic.vn/cong-bo-tai-lieu-ky-thuat-dac-ta-api-he-thong-co-so-du-lieu-ve-duoc/  
- canhgiacduoc: https://canhgiacduoc.org.vn/  
- Bộ Y tế: https://moh.gov.vn/  
- ClinicalTrials.gov API: https://clinicaltrials.gov/data-api/api  
- WHO ICTRP: https://www.who.int/clinical-trials-registry-platform/the-ictrp-search-portal/ictrp-search-portal-web-service  
- NCBI E-utilities usage/key: https://eutilities.github.io/site/API_Key/usageandkey/  
- WHO ICD API: https://icd.who.int/docs/icd-api/  
- openFDA auth + APIs: https://open.fda.gov/apis/authentication/  
- openFDA drug label/event: https://open.fda.gov/apis/drug/label/ , https://open.fda.gov/apis/drug/event/how-to-use-the-endpoint/  
- DailyMed Web Services: https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm  
- RxNav APIs + Terms: https://lhncbc.nlm.nih.gov/RxNav/APIs/ , https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html  
- DrugBank API docs: https://docs.drugbank.com/discovery/v1/  
- UMC VigiBase data access: https://who-umc.org/vigibase-data-access/  
- EMA EudraVigilance access policy: https://www.ema.europa.eu/en/human-regulatory-overview/research-development/pharmacovigilance-research-development/eudravigilance/access-eudravigilance-data  
- NICE syndication API: https://www.nice.org.uk/about/what-we-do/nice-syndication-api/content  
- Google Vision quotas/auth: https://docs.cloud.google.com/vision/quotas , https://cloud.google.com/vision/docs/authentication  
- AWS Textract quotas/IAM: https://docs.aws.amazon.com/textract/latest/dg/limits-quotas-explained.html , https://docs.aws.amazon.com/textract/latest/dg/security-iam.html  
- Azure Document Intelligence limits: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits

