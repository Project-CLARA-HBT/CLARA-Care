# CUỘC THI SÁNG TẠO THANH THIẾU NIÊN, NHI ĐỒNG  
## THÀNH PHỐ HUẾ LẦN THỨ 19, NĂM 2026

# CLARA-Care

**Tác giả/đồng tác giả:** Nguyễn Ngọc Thiện, Nguyễn Hải Duy, Trịnh Minh Quang  
**Đơn vị:** THPT Hai Bà Trưng, Thành phố Huế  
**Lĩnh vực dự thi:** Các giải pháp kỹ thuật nhằm ứng phó với biến đổi khí hậu, bảo vệ môi trường và phát triển kinh tế  
**Ngày:** **Thứ Ba, ngày 31 tháng 3 năm 2026**

---

## PHẦN 1: TÓM TẮT ĐỀ TÀI

### 1. Tên đề tài
**CLARA-Care**

### 2. Lý do chọn đề tài
Hệ thống y tế Việt Nam đang chịu “gánh nặng kép”: vừa xử lý bệnh cấp tính, vừa đối mặt với sự gia tăng nhanh của bệnh mạn tính (tim mạch, tăng huyết áp, đái tháo đường). Ở cấp hộ gia đình, đa trị liệu, tự ý dùng thuốc, tuân thủ điều trị chưa tốt và tra cứu thông tin thiếu kiểm chứng làm tăng rủi ro sức khỏe.

Trong học tập và nghiên cứu y khoa, rào cản ngôn ngữ và dữ liệu phân mảnh khiến quá trình đối chiếu tài liệu tốn thời gian, dễ sai sót. Song song, phát triển AI y tế cần bám chặt yêu cầu bảo mật dữ liệu theo Nghị định 13/2023/NĐ-CP và nguyên tắc an toàn của WHO.

Từ đó, nhóm xây dựng CLARA-Care như một nền tảng hỗ trợ gồm:
- **CLARA Research**: trợ lý tổng hợp y văn có trích dẫn.
- **CLARA Self-MED**: hỗ trợ quản lý tủ thuốc tại nhà, cảnh báo tương tác thuốc.
- **CLARA Medical Scribe (baseline)**: chuyển transcript thành khung SOAP ở mức cơ bản.

### 3. Tính mới, tính sáng tạo

#### 3.1 Tính mới
- Tích hợp nhiều luồng nghiệp vụ trong cùng một nền tảng thay vì ứng dụng rời rạc.
- Áp dụng kiến trúc RAG có trích dẫn và cơ chế fallback an toàn khi thiếu ngữ cảnh hoặc lỗi dịch vụ.
- Định tuyến hai lớp `Role -> Intent` để điều chỉnh hành vi trả lời theo nhóm người dùng.
- Có lớp cấu hình runtime (Control Tower) cho phép bật/tắt một số luồng xử lý mà không cần sửa code.
- Hỗ trợ xây dựng **Sổ tay sức khỏe cá nhân (PHR)** do người dùng tự khai báo để phục vụ quản lý thuốc tại nhà.

#### 3.2 Tính sáng tạo
- Kết hợp lớp an toàn nhiều tầng: legal guard, kiểm tra tín hiệu rủi ro, lọc dữ liệu nhạy cảm, fallback.
- Mô hình cảnh báo tương tác thuốc lai: local rules + nguồn bên ngoài (khi khả dụng).
- Tích hợp ADE toa thuốc trong luồng quản lý tủ thuốc gia đình.
- Không định vị như chatbot tự do, mà là công cụ hỗ trợ tham khảo có kiểm soát rủi ro.

### 4. Khả năng áp dụng của sản phẩm

#### 4.1 Tại cơ sở y tế (mức hỗ trợ tham khảo)
- Hỗ trợ bác sĩ thực tập/sinh viên tra cứu nhanh tài liệu và tương tác thuốc.
- Giảm thời gian tra cứu thủ công trong các tình huống học tập, thảo luận ca.
- **Không thay thế quyết định lâm sàng, không thay thế quy trình chuyên môn của bệnh viện.**

#### 4.2 Tại cơ sở giáo dục y khoa
- Hỗ trợ sinh viên và nghiên cứu sinh tổng hợp tài liệu có trích dẫn.
- Tăng tốc bước tổng quan y văn và tiếp cận y học thực chứng (EBM).

#### 4.3 Tại cộng đồng và gia đình
- Quét và quản lý tủ thuốc tại nhà.
- Cảnh báo tương tác thuốc nguy cơ cao.
- Hỗ trợ người chăm sóc theo dõi việc dùng thuốc an toàn.

### 5. Hiệu quả kinh tế - xã hội (điều chỉnh theo phạm vi thực tế)
- Góp phần nâng cao nhận thức cộng đồng về sử dụng thuốc an toàn.
- Giảm một phần rủi ro dùng sai thuốc trong phạm vi hộ gia đình.
- Hỗ trợ sinh viên y khoa tra cứu tài liệu nhanh hơn, có căn cứ hơn.
- Là công cụ tham khảo phục vụ chuyển đổi số ở mức thí điểm học đường/cộng đồng.
- **Không tuyên bố chuẩn hóa quy trình khám chữa bệnh của địa phương.**

---

## PHẦN 2: THUYẾT MINH ĐỀ TÀI

### 1. Lý do chọn đề tài
Việt Nam đang bước vào giai đoạn già hóa dân số và gia tăng bệnh không lây nhiễm. Điều này làm nhu cầu quản lý sức khỏe chủ động tại gia đình trở nên cấp thiết, đặc biệt với nhóm đa bệnh nền và đa trị liệu.

Các thách thức chính:
- Nguy cơ tương tác thuốc bất lợi do dùng đồng thời nhiều thuốc.
- Tự mua và tự sử dụng thuốc khi chưa có tư vấn chuyên môn.
- Tuân thủ điều trị chưa cao ở một số nhóm bệnh mạn.
- Khó tổng hợp nguồn tài liệu y khoa đa ngôn ngữ một cách nhanh và có kiểm chứng.

Nhóm phát triển CLARA-Care để giải quyết bài toán hỗ trợ tra cứu và an toàn dùng thuốc ở mức thực dụng, có giới hạn trách nhiệm rõ ràng.

### 2. Mô tả mô hình và nguyên tắc hoạt động

#### 2.1 Lớp Client (Web + Mobile)
- Người dùng nhập câu hỏi, khai báo thuốc, hoặc gửi ảnh toa thuốc.
- Frontend gửi dữ liệu chuẩn hóa về backend và hiển thị kết quả kèm cảnh báo an toàn.

#### 2.2 Lớp Truy cập và Định danh (Access & Identity)
- Đăng ký/đăng nhập/xác thực người dùng.
- JWT access/refresh token và phân vai trò người dùng.

#### 2.3 Lớp Điều phối API (API Orchestration)
- Nhận request từ client, gọi đúng dịch vụ ML/API.
- Tổng hợp response thống nhất cho frontend.

#### 2.4 Lớp Định tuyến (Routing: Role -> Intent)
- Bước 1: xác định vai trò.
- Bước 2: xác định ý định truy vấn (chat/research/careguard/...).
- Chọn luồng xử lý phù hợp theo policy.

#### 2.5 Lớp An toàn (Safety Layer)
- Phát hiện yêu cầu vượt thẩm quyền (kê đơn/chẩn đoán/chỉ định liều) để từ chối.
- Lọc dữ liệu nhạy cảm cơ bản và xử lý fail-soft khi dịch vụ lỗi.
- Ưu tiên phản hồi an toàn trong ngữ cảnh thiếu dữ liệu.

#### 2.6 Lớp Tri thức và Suy luận (Knowledge & Reasoning)
- RAG truy xuất ngữ cảnh từ tập tài liệu và connector.
- Agent nghiệp vụ theo từng bài toán (careguard/research/scribe/council).
- LLM tổng hợp phản hồi dựa trên ngữ cảnh và policy an toàn.

#### 2.7 Lớp Dữ liệu và Hạ tầng (Data & Infra)

**Đang dùng trực tiếp trong phiên bản hiện tại:**
- PostgreSQL cho dữ liệu người dùng và nghiệp vụ.
- In-memory retrieval + external connectors cho một số luồng RAG.

**Đã chuẩn bị hạ tầng để mở rộng:**
- Redis, Milvus, Elasticsearch, Neo4j (ở mức infra readiness).

Lưu ý: ở bản hiện tại phục vụ cuộc thi, chưa tuyên bố production retrieval lõi qua toàn bộ vector/graph/search stack.

#### 2.8 Lớp Điều khiển và Giám sát (Control Tower & Observability)
- Quản trị cấu hình nguồn RAG và flow runtime.
- Theo dõi health/metrics/flow events cho vận hành.
- Một số dashboard đang ở mức mô phỏng để phục vụ demo.

### 3. Tính mới, tính sáng tạo (phiên bản bám sát triển khai)

#### 3.1 Tính mới
- Tích hợp Research + Self-MED + Scribe baseline trong một hệ thống thống nhất.
- Có consent gate và safety guard ở backend.
- Có attribution/citation/fallback metadata trong một số response trọng yếu.

#### 3.2 Tính sáng tạo
- Kết hợp rule-based safety với nguồn dữ liệu bên ngoài để tăng độ tin cậy cảnh báo.
- Thiết kế luồng legal-first để giảm rủi ro trả lời vượt phạm vi.
- Có khả năng chuyển trạng thái online/offline fallback cho một số chức năng cảnh báo.

### 4. Khả năng áp dụng

#### 4.1 Ở bệnh viện/trường y (hỗ trợ tham khảo)
- Hỗ trợ tra cứu nhanh, hỗ trợ đào tạo và thảo luận ca.
- Không dùng để thay thế chẩn đoán/kê đơn.

#### 4.2 Ở cộng đồng
- Tập trung bài toán quản lý tủ thuốc và cảnh báo tương tác thuốc tại nhà.
- Tăng hiểu biết dùng thuốc an toàn cho người dùng không chuyên.

### 5. Hiệu quả xã hội (điều chỉnh claim)

#### 5.1 Đối với người dùng cá nhân/gia đình
- Hỗ trợ nhận biết nguy cơ tương tác thuốc.
- Hỗ trợ tổ chức thông tin thuốc rõ ràng hơn.
- Góp phần giảm nhầm lẫn trong sử dụng thuốc tại nhà.

#### 5.2 Đối với sinh viên và giảng viên y khoa
- Rút ngắn thời gian tổng hợp tài liệu.
- Tăng thói quen kiểm tra nguồn và trích dẫn.

#### 5.3 Đối với hệ sinh thái số y tế
- Cung cấp một hướng tiếp cận “AI hỗ trợ tham khảo có kiểm soát”.
- Là nền tảng thí điểm để hoàn thiện kỹ thuật trước khi mở rộng.

### 6. Phạm vi triển khai: Đã làm / Đang làm / Chưa làm

#### 6.1 Đã làm (có trong bản hiện tại)
- `Legal guard` chặn nhóm yêu cầu vượt thẩm quyền (kê đơn/chẩn đoán/chỉ định liều).
- Consent gate ở backend trước khi xử lý dữ liệu nhạy cảm.
- Luồng cảnh báo tương tác thuốc theo mô hình lai: local rules + nguồn ngoài khi khả dụng.
- RAG mức cơ bản với trích dẫn/fallback metadata cho một số response trọng yếu.
- Hệ thống quản lý người dùng, phân quyền và JWT access/refresh token.
- Quản lý tủ thuốc gia đình và ADE toa thuốc ở mức phục vụ demo nghiệp vụ.

#### 6.2 Đang làm (đã có nền nhưng chưa hoàn thiện production)
- Củng cố chất lượng parser tài liệu nghiên cứu (đặc biệt PDF/image dài và cấu trúc phức tạp).
- Chuẩn hóa bộ đánh giá RAG/hallucination (test set, coverage, faithfulness, tracking theo phiên bản).
- Hoàn thiện observability/dashboard vận hành (một số thành phần hiện còn mức mô phỏng).
- Nâng độ ổn định của các connector bên ngoài khi timeout hoặc lỗi định dạng phản hồi.

#### 6.3 Chưa làm (hoặc chưa đủ điều kiện để tuyên bố)
- Chưa vận hành retrieval production lõi trên toàn bộ stack Redis/Milvus/Elasticsearch/Neo4j.
- Chưa có xác nhận lâm sàng đa trung tâm hoặc thử nghiệm triển khai diện rộng.
- Chưa định vị/chứng nhận như SaMD (Software as a Medical Device).
- Chưa tích hợp chính thức vào quy trình nghiệp vụ bắt buộc của bệnh viện/cơ quan quản lý.

### 7. Rủi ro & biện pháp giảm thiểu

#### 7.1 Rủi ro false alert (cảnh báo sai hoặc quá nhạy)
- **Rủi ro:** hệ thống cảnh báo tương tác thuốc khi mức bằng chứng thấp, gây lo lắng không cần thiết.
- **Giảm thiểu:** gắn mức độ cảnh báo (high/medium/low), hiển thị nguồn và mức chắc chắn; yêu cầu người dùng xác nhận với dược sĩ/bác sĩ ở mức cảnh báo cao.

#### 7.2 Rủi ro bỏ sót cảnh báo (false negative)
- **Rủi ro:** dữ liệu thuốc thiếu hoạt chất, tên biệt dược nhập sai hoặc thiếu liều dùng làm hệ thống không phát hiện tương tác.
- **Giảm thiểu:** chuẩn hóa tên thuốc theo từ điển thuốc, áp dụng fuzzy matching có ngưỡng, cảnh báo “thiếu dữ liệu” thay vì kết luận an toàn.

#### 7.3 Rủi ro dữ liệu người dùng nhập sai
- **Rủi ro:** người dùng nhập sai triệu chứng, sai lịch dùng thuốc, ảnh toa mờ làm ADE nhận dạng sai.
- **Giảm thiểu:** bắt buộc bước xác nhận lại dữ liệu trước khi phân tích; đánh dấu trường “độ tin cậy thấp”; ưu tiên khuyến nghị đi khám khi thông tin không nhất quán.

#### 7.4 Rủi ro outage dịch vụ ngoài hoặc hệ thống nội bộ
- **Rủi ro:** connector (ví dụ nguồn tra cứu thuốc) timeout/lỗi mạng làm suy giảm chất lượng phản hồi.
- **Giảm thiểu:** timeout ngắn + retry có kiểm soát; fallback sang local rules; trả về trạng thái “dịch vụ ngoài không khả dụng” thay vì trả lời suy đoán.

#### 7.5 Rủi ro pháp lý và hiểu nhầm phạm vi sử dụng
- **Rủi ro:** người dùng hiểu nhầm kết quả AI là chỉ định điều trị chính thức.
- **Giảm thiểu:** nhãn pháp lý bắt buộc trong UI/API, từ chối câu hỏi vượt phạm vi, luôn kèm tuyên bố “công cụ tham khảo - không thay thế bác sĩ/dược sĩ”.

### 8. Giới hạn và tuyên bố pháp lý bắt buộc
- CLARA-Care là **công cụ hỗ trợ tham khảo**, không thay thế bác sĩ/dược sĩ.
- CLARA-Care **không phải** hồ sơ bệnh án điện tử của cơ sở y tế.
- Dữ liệu người dùng nhập là **PHR (Personal Health Record)** do người dùng tự khai báo.
- PHR không có giá trị pháp lý tương đương EMR/EHR.
- Kết quả từ hệ thống không phải chỉ định điều trị.
- Dự án chưa định vị như SaMD (Software as a Medical Device).

### 9. Tình huống minh họa (điều chỉnh thực tế)

#### 9.1 CLARA Research
- Người học đặt câu hỏi nghiên cứu bằng ngôn ngữ tự nhiên.
- Hệ thống truy xuất tài liệu phù hợp, trả lời kèm trích dẫn.
- Mục tiêu: hỗ trợ bước đầu tổng quan y văn, không thay thế phản biện học thuật cuối cùng.

#### 9.2 CLARA Self-MED
- Người dùng quét/nhập thuốc vào tủ thuốc cá nhân.
- Hệ thống phân tích tương tác, đưa cảnh báo theo mức độ.
- Mục tiêu: hỗ trợ quản lý thuốc tại nhà an toàn hơn.

---

## DANH MỤC TỪ VIẾT TẮT

| STT | Từ viết tắt | Thuật ngữ tiếng Anh | Giải nghĩa tiếng Việt |
|---|---|---|---|
| 1 | AI | Artificial Intelligence | Trí tuệ nhân tạo |
| 2 | API | Application Programming Interface | Giao diện lập trình ứng dụng |
| 3 | DB | Database | Cơ sở dữ liệu |
| 4 | EBM | Evidence-Based Medicine | Y học dựa trên bằng chứng |
| 5 | EMR/EHR | Electronic Medical/Health Record | Hồ sơ bệnh án điện tử do cơ sở y tế quản lý |
| 6 | PHR | Personal Health Record | Sổ tay sức khỏe cá nhân do người dùng tự khai báo |
| 7 | LLM | Large Language Model | Mô hình ngôn ngữ lớn |
| 8 | ML | Machine Learning | Học máy |
| 9 | ADE | Agentic Document Extraction | Trích xuất tài liệu theo quy trình tác tử |
| 10 | PII | Personally Identifiable Information | Dữ liệu định danh cá nhân |
| 11 | RAG | Retrieval-Augmented Generation | Sinh văn bản tăng cường truy xuất |
| 12 | RxNorm | - | Hệ thống danh pháp chuẩn hóa thuốc |
| 13 | WHO | World Health Organization | Tổ chức Y tế Thế giới |

---

## PHỤ LỤC

### Phụ lục 1: Sơ đồ luồng hoạt động tổng thể CLARA
(Dịch vụ API, Dịch vụ ML, Ứng dụng di động)

```mermaid
sequenceDiagram
    autonumber
    participant M as Ứng dụng di động (Flutter)
    participant A as Dịch vụ API (FastAPI /api/v1)
    participant DB as Cơ sở dữ liệu PostgreSQL
    participant ML as Dịch vụ ML (FastAPI /v1)
    participant ADE as Dịch vụ CLARA Agentic Document Extraction
    participant EXT as API y khoa bên ngoài
    participant LLM as API trò chuyện DeepSeek

    M->>A: POST /api/v1/auth/login
    A->>DB: Xác thực người dùng + vai trò
    A-->>M: access_token + refresh_token + role

    M->>A: GET /api/v1/mobile/summary
    A-->>M: cờ tính năng + liên kết nhanh

    rect rgba(230,245,255,0.35)
    Note over M,ML: Luồng Nghiên cứu Tier2
    M->>A: POST /api/v1/research/tier2
    A->>DB: Nạp người dùng + nguồn tri thức/tài liệu
    A->>A: Ghép uploaded_file_ids thành uploaded_documents (bộ nhớ + CSDL)
    A->>ML: POST /v1/research/tier2
    ML->>ML: Lập kế hoạch + định tuyến Vai trò/Ý định + RagPipelineP1
    opt Bật truy xuất khoa học/web
        ML->>EXT: PubMed/EuropePMC/OpenAlex/Crossref/ClinicalTrials/openFDA/DailyMed/SemanticScholar/SearXNG
        EXT-->>ML: Bằng chứng truy xuất
    end
    ML->>LLM: Sinh/tóm tắt câu trả lời (khi khả dụng)
    LLM-->>ML: Phản hồi
    ML-->>A: câu trả lời + trích dẫn + sự kiện luồng + dữ liệu đo xa
    A-->>M: phản hồi tier2 đã chuẩn hóa (suy giảm an toàn khi cần)
    end

    rect rgba(235,255,240,0.35)
    Note over M,ML: Luồng CareGuard
    M->>A: POST /api/v1/careguard/analyze
    A->>DB: Kiểm tra đồng ý miễn trừ y khoa
    A->>DB: Nạp cấu hình control_tower.careguard_runtime
    A->>ML: POST /v1/careguard/analyze (cờ external_ddi_enabled)
    opt Khi external_ddi_enabled = true
        ML->>EXT: RxNav + openFDA
        EXT-->>ML: Ngữ cảnh/bằng chứng DDI
    end
    ML-->>A: mức rủi ro + cảnh báo DDI + khuyến nghị
    A-->>M: phản hồi + truy vết nguồn
    end

    M->>A: POST /api/v1/careguard/cabinet/scan-file
    A->>ADE: Gửi yêu cầu ADE multipart (các endpoint ADE đã cấu hình)
    ADE-->>A: văn bản ADE đã trích xuất
    A-->>M: danh sách phát hiện + nguồn ADE + endpoint ADE
``` 

## TÀI LIỆU THAM KHẢO

### A. Văn bản, tiêu chuẩn và nguồn chính thống

1. Nghị định số 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân (Chính phủ Việt Nam):  
   https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Nghi-dinh-13-2023-ND-CP-bao-ve-du-lieu-ca-nhan-567048.aspx
2. WHO Vietnam - Noncommunicable diseases:  
   https://www.who.int/vietnam/health-topics/noncommunicable-diseases
3. WHO Vietnam - Cardiovascular diseases:  
   https://www.who.int/vietnam/health-topics/cardiovascular-diseases

### B. Nguồn dữ liệu y khoa và dược học sử dụng trong hệ thống

1. PubMed (NCBI): https://pubmed.ncbi.nlm.nih.gov/
2. NCBI E-utilities API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
3. Europe PMC API: https://europepmc.org/RestfulWebService
4. OpenAlex API: https://docs.openalex.org/
5. Crossref REST API: https://api.crossref.org/
6. ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/about-api
7. DailyMed API / Web services: https://dailymed.nlm.nih.gov/dailymed/webservices-help.cfm
8. RxNav / RxNorm APIs (NLM): https://lhncbc.nlm.nih.gov/RxNav/APIs/
9. openFDA API: https://open.fda.gov/apis/
10. Semantic Scholar API: https://api.semanticscholar.org/api-docs/

### C. Tài liệu kỹ thuật nền tảng triển khai

1. FastAPI Documentation: https://fastapi.tiangolo.com/
2. Next.js Documentation: https://nextjs.org/docs
3. Flutter Documentation: https://docs.flutter.dev/
4. PostgreSQL Documentation: https://www.postgresql.org/docs/
5. Redis Documentation: https://redis.io/docs/
6. Milvus Documentation: https://milvus.io/docs
7. Elasticsearch Documentation: https://www.elastic.co/guide/
8. Neo4j Documentation: https://neo4j.com/docs/

### D. Tài liệu nội bộ dự án CLARA-Care (đính kèm trong repo)

1. Kiến trúc runtime và routing:  
   `/docs/architecture/clara-runtime-and-routing.md`
2. Đề xuất tổng thể dự án:  
   `/docs/proposal/clara-full-proposal-2026-03-29.md`
3. Mô tả hạ tầng và quy trình phát triển:  
   `/README.md`
4. Tài liệu API service:  
   `/services/api/README.md`
5. Tài liệu ML service:  
   `/services/ml/README.md`
6. Bộ chỉ số và hiện vật demo hackathon:  
   `/docs/hackathon/kpi-snapshot.md`, `/docs/hackathon/demo-artifact-pack.md`

### E. Bối cảnh y tế Việt Nam, sử dụng thuốc và tuân thủ điều trị (bổ sung)

1. WHO Vietnam news release (2025): NCDs are the leading cause of death in Viet Nam, accounting for about 80% of deaths.  
   https://www.who.int/vietnam/news/detail/15-12-2025-viet-nam-unites-to-tackle-top-causes-of-disease-and-death
2. WHO Vietnam CVD topic page: CVD burden and hypertension management context in Viet Nam.  
   https://www.who.int/vietnam/health-topics/cardiovascular-diseases
3. de Oliveira LM et al. Prevalence of drug interactions in hospitalised elderly patients: a systematic review. Eur J Hosp Pharm. 2021;28(1):4-9. PMID: 33355278 | DOI: 10.1136/ejhpharm-2019-002111  
   https://pubmed.ncbi.nlm.nih.gov/33355278/
4. Hughes JE et al. Prevalence of Drug-Drug Interactions in Older Community-Dwelling Individuals: A Systematic Review and Meta-analysis. Drugs Aging. 2023;40(2):117-134. PMID: 36692678 | DOI: 10.1007/s40266-022-01001-5  
   https://pubmed.ncbi.nlm.nih.gov/36692678/
5. Doan DA et al. Prevalence and associated factors of antibiotic self-medication and home storage among antibiotic users: a cross-sectional study in Vietnam. BMC Public Health. 2025;25(1):1940. PMID: 40420096 | DOI: 10.1186/s12889-025-23202-4  
   https://pubmed.ncbi.nlm.nih.gov/40420096/
6. Nguyen TPL et al. Adherence to hypertension medication: Quantitative and qualitative investigations in a rural Northern Vietnamese community. PLoS One. 2017;12(2):e0171203. PMID: 28146584 | DOI: 10.1371/journal.pone.0171203  
   https://pubmed.ncbi.nlm.nih.gov/28146584/
7. Hien HA et al. Factors influencing medication adherence among hypertensive patients in primary care settings in Central Vietnam: A cross-sectional study. PLoS One. 2025;20(1):e0307588. PMID: 39874240 | DOI: 10.1371/journal.pone.0307588  
   https://pubmed.ncbi.nlm.nih.gov/39874240/
8. Scotti S et al. Enhancing Medication Adherence in Older Adults: A Systematic Review of Evidence-Based Strategies. J Am Geriatr Soc. 2025. PMID: 41467772 | DOI: 10.1111/jgs.70257  
   https://pubmed.ncbi.nlm.nih.gov/41467772/
9. World Bank WDI indicator (SP.POP.65UP.TO.ZS): Population ages 65 and above (% of total population), Viet Nam, 1960-2024 series.  
   https://data.worldbank.org/indicator/SP.POP.65UP.TO.ZS?locations=VN

### F. Medical AI và RAG trong y khoa (bổ sung)

1. Singhal K et al. Large language models encode clinical knowledge. Nature. 2023;620(7972):172-180. PMID: 37438534 | DOI: 10.1038/s41586-023-06291-2  
   https://pubmed.ncbi.nlm.nih.gov/37438534/
2. Xiong G, Jin Q, Lu Z, Zhang A. Benchmarking Retrieval-Augmented Generation for Medicine. arXiv:2402.13178 (2024).  
   https://arxiv.org/abs/2402.13178
3. Xiong G, Jin Q, Wang X, Zhang M, Lu Z, Zhang A. Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions. arXiv:2408.00727 (2024).  
   https://arxiv.org/abs/2408.00727
4. Zhao X, Liu S, Yang SY, Miao C. MedRAG: Enhancing Retrieval-augmented Generation with Knowledge Graph-Elicited Reasoning for Healthcare Copilot. arXiv:2502.04413 (2025).  
   https://arxiv.org/abs/2502.04413
5. Jin Q et al. BiomedRAG: A retrieval augmented large language model for biomedicine. J Biomed Inform. 2025;162:104769. DOI: 10.1016/j.jbi.2024.104769  
   https://doi.org/10.1016/j.jbi.2024.104769
6. Peng C et al. A study of generative large language model for medical research and healthcare. npj Digit Med. 2023;6:188. DOI: 10.1038/s41746-023-00958-w  
   https://www.nature.com/articles/s41746-023-00958-w

### Phụ lục 2: Sơ đồ kiến trúc hệ thống và tích hợp ứng dụng web
(Routing qua chat/research/careguard/council/scribe và kết nối dịch vụ ngoài)

```mermaid
flowchart LR
    subgraph WEB["Ứng dụng Web (Next.js - apps/web)"]
      WAuth["Giao diện xác thực + interceptor làm mới JWT"]
      WResearch["/research\nTầng 1: POST /chat\nTầng 2: POST /research/tier2\nTải tệp: /research/upload-file"]
      WSelfMed["/selfmed + /careguard\nthêm/sửa/xóa tủ thuốc + quét + tự kiểm tra DDI"]
      WCouncil["/council\nPOST /council/run"]
      WScribe["/scribe\nPOST /scribe/soap"]
      WAdmin["/admin\n/system/control-tower/*\n/system/flow-events*"]
    end

    subgraph API["Dịch vụ API (FastAPI - services/api)"]
      AMW["Lớp trung gian:\nNgữ cảnh xác thực + giới hạn tần suất + đo lường + CORS"]
      ARouter["Bộ định tuyến /api/v1:\nauth, mobile, chat, research,\ncareguard, council, scribe, system"]
      ACT["Dịch vụ cấu hình Control Tower\n(đọc/ghi từ system_settings)"]
      AFlow["Bộ ghi sự kiện luồng chat\n-> FlowEventStore trong bộ nhớ + luồng SSE"]
    end

    subgraph ML["Dịch vụ ML (FastAPI - services/ml)"]
      MChat["/v1/chat/routed"]
      MResearch["/v1/research/tier2"]
      MCare["/v1/careguard/analyze"]
      MCouncil["/v1/council/run"]
      MScribe["/v1/scribe/soap"]
      MRoute["Bộ định tuyến Vai trò/Ý định P1"]
      MGuard["Chặn pháp lý cứng + ẩn PII + nhánh khẩn cấp"]
      MRag["RagPipelineP1 + bộ kiểm chứng Fides-lite"]
      MInMem["InMemoryRetriever\n(tài liệu khởi tạo + tài liệu tải lên + nguồn RAG)"]
      MCareAgent["Tác tử CareGuard\n(luật DDI cục bộ + chấm điểm rủi ro)"]
      MCouncilAgent["Mô phỏng hội chẩn đa chuyên khoa dựa trên luật"]
      MScribeAgent["Bộ phân tích SOAP khung sườn"]
    end

    subgraph DATA["Dữ liệu & Trạng thái"]
      PG["PostgreSQL\nusers, consents, medicine_cabinets,\nknowledge_sources/documents, system_settings"]
      Mem["Kho trong bộ nhớ\nuploaded_research_files, flow_event_store"]
      Infra["Hạ tầng sẵn sàng (docker):\nRedis, Milvus, Elasticsearch, Neo4j\n(chưa là retrieval lõi runtime)"]
    end

    subgraph EXT["Dịch vụ bên ngoài"]
      DeepSeek["DeepSeek /chat/completions"]
      ADE["Dịch vụ CLARA Agentic Document Extraction"]
      DrugAPI["RxNav + openFDA"]
      LitAPI["PubMed, EuropePMC, OpenAlex,\nCrossref, ClinicalTrials, DailyMed,\nSemantic Scholar, SearXNG"]
    end

    WAuth --> AMW
    WResearch --> AMW
    WSelfMed --> AMW
    WCouncil --> AMW
    WScribe --> AMW
    WAdmin --> AMW

    AMW --> ARouter
    ARouter --> ACT
    ARouter --> AFlow
    ARouter --> PG
    ARouter --> Mem

    ARouter -->|chuyển tiếp /v1/chat/routed| MChat
    ARouter -->|chuyển tiếp /v1/research/tier2| MResearch
    ARouter -->|chuyển tiếp /v1/careguard/analyze| MCare
    ARouter -->|chuyển tiếp /v1/council/run| MCouncil
    ARouter -->|chuyển tiếp /v1/scribe/soap| MScribe
    ARouter -->|quét tệp ADE| ADE

    MChat --> MGuard --> MRoute --> MRag
    MResearch --> MRoute --> MRag
    MCare --> MCareAgent
    MCouncil --> MCouncilAgent
    MScribe --> MScribeAgent

    MRag --> MInMem
    MRag --> DeepSeek
    MRag --> LitAPI
    MCareAgent --> DrugAPI

    ACT --> PG
    MInMem --> Mem
    ARouter -. sẵn sàng hạ tầng .-> Infra
    MChat -. sẵn sàng hạ tầng .-> Infra
```

### Phụ lục 3: Hệ thống website CLARA

### Phụ lục 4: Mã QR website CLARA

### Phụ lục 5: Sơ đồ CLARA ADE - CLARA Agentic Document Extraction (bám sát codebase ADE)

```mermaid
flowchart TD
    U["Ứng dụng gọi ADE\n(Web/Mobile/API trung gian)"] --> R{"Chọn API CLARA ADE"}

    R -->|POST /api/export| EX["Bộ xử lý xuất tài liệu"]
    R -->|POST /api/extract| XT["Bộ xử lý trích xuất cấu trúc"]
    R -->|POST /api/jobs| JQ["Tạo tác vụ nền"]
    R -->|GET /api/jobs hoặc /api/jobs/:job_id| JS["Theo dõi trạng thái tác vụ"]

    EX --> IN1["Nhận multipart:\nfile, target_lang, output_format,\nlayout_mode, instruction"]
    IN1 --> T1{"Loại đầu vào"}
    T1 -->|DOCX| D1["Luồng DOCX:\nphân tích bố cục -> dịch -> dựng DOCX"]
    T1 -->|PDF/Ảnh| P1["Tách trang thành ảnh"]

    P1 --> P2["CLARA ADE tiền xử lý:\nnhiều biến thể ảnh (khử nhiễu,\nnhị phân, tăng tương phản, upscale)"]
    P2 --> P3["Nhận dạng ADE theo biến thể"]
    P3 --> P4["Chấm điểm chất lượng ADE\n(chữ, độ tin cậy, bố cục, bảng)"]
    P4 --> P5["Chọn kết quả tốt nhất theo trang\n(bộ chọn block ADE tốt nhất)"]
    P5 --> P6{"Chiến lược tinh chỉnh"}
    P6 -->|ADEX/Agentic| A1["refine_adex_translations"]
    P6 -->|CORTEX| C1["refine_cortex_translations"]
    P6 -->|HYBRID| H1["merge_hybrid_page_translations"]
    A1 --> POST1{"Bật AGENTIC_ADE+ ?"}
    C1 --> POST1
    H1 --> POST1
    POST1 -->|Có| PPLUS["apply_agentic_ade_plus_postprocess"]
    POST1 -->|Không| B1["Dựng tài liệu đầu ra"]
    PPLUS --> B1
    D1 --> B1
    B1 --> O1["Trả tệp đầu ra:\nDOCX hoặc PDF có lớp văn bản"]

    XT --> IN2["Nhận multipart: file"]
    IN2 --> X1["Tách PDF thành ảnh trang"]
    X1 --> X2["Mỗi trang: ưu tiên text layer,\nthiếu thì dùng CLARA ADE blocks,\nkhông có blocks thì fallback văn bản ADE"]
    X2 --> X3["Tổng hợp ExtractionResult:\nchunks, fields, elements, particles,\ngraph ADE, warnings"]
    X3 --> O2["Trả JSON trích xuất"]

    JQ --> J1["Đưa yêu cầu vào hàng đợi tác vụ nền"]
    J1 --> O3["job_id"]
    JS --> O4["Danh sách/trạng thái/kết quả tác vụ"]
```
