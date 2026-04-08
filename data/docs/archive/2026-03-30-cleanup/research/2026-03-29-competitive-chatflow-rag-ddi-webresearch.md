# Competitive Chatflow + RAG + DDI + Web Research cho CLARA (2026-03-29)

## Mục tiêu
Tài liệu này trả lời 4 bài toán micro cho CLARA:
- (A) Benchmark chat flow: `ChatGPT`, `Gemini`, `Perplexity`, `Dify`.
- (B) Tổng hợp các hướng RAG tiên tiến: `GraphRAG`, `Self-RAG`, `CRAG`, `Adaptive-RAG`, `RAPTOR`.
- (C) Thiết kế DDI chuẩn cao với dữ liệu: `RxNorm`, `openFDA`, `DailyMed`, `DrugBank`.
- (D) Thiết kế web research mạnh kiểu Perplexity khi chưa có API thương mại: `SearXNG + self-host crawl + legal guardrails`.

---

## (A) Benchmark chat flow: ChatGPT vs Gemini vs Perplexity vs Dify

### A.1. Bảng benchmark nhanh theo luồng nghiên cứu

| Nền tảng | Điểm mạnh chat flow | Điểm yếu chat flow | Hàm ý cho CLARA |
|---|---|---|---|
| **ChatGPT** | Luồng Deep Research rõ: chọn nguồn -> duyệt/sửa research plan -> theo dõi tiến trình real-time -> report có citation; có thể giới hạn theo site/domain tin cậy | Usage limit theo plan; trải nghiệm mạnh nhưng phụ thuộc hệ sinh thái đóng | Học cơ chế `source control + plan trước khi chạy + tiến trình + report viewer + export` |
| **Gemini** | Deep Research có luồng nguồn rất rõ (Google Search mặc định, thêm Gmail/Drive/NotebookLM/files), có bước chỉnh research plan trước khi chạy, hỗ trợ Canvas/export | Ràng buộc theo gói và hệ Google; chất lượng phụ thuộc cấu hình nguồn cá nhân | Học cơ chế `multi-source selector`, đặc biệt cho file nội bộ + web trong cùng một prompt |
| **Perplexity** | Tối ưu “search-first”: Pro Search/Research có nhiều vòng search, synthesize nhanh, citation rõ, hỏi làm rõ (clarifying questions), follow-up trong khi đang chạy, mạnh ở workflow nghiên cứu liên tục | Chất lượng có thể dao động theo nguồn web; cần kiểm chứng thủ công cho lĩnh vực y tế | Học cơ chế `iterative search`, `clarifying question`, `progressive findings`, `thread continuation` |
| **Dify** | Mạnh ở điều phối flow: node-based workflow (If/Else, Knowledge Retrieval, HTTP, Tool), Run History/Tracing tốt cho debug và governance, self-host linh hoạt | UX người dùng cuối không “consumer polished” bằng ChatGPT/Perplexity; cần tự thiết kế nhiều lớp | Dùng làm `orchestration/control plane` cho CLARA: routing, observability, QA pipeline |

### A.2. Kết luận benchmark cho CLARA

**Mẫu flow nên áp dụng (lai 2 lớp):**
- **Lớp người dùng cuối (UX kiểu ChatGPT/Perplexity):**
  - `Nhập câu hỏi` -> `hỏi làm rõ ngắn` (nếu mơ hồ) -> `chốt kế hoạch nghiên cứu ngắn` -> `chạy + hiển thị tiến trình` -> `trả lời theo lớp (TL;DR / bằng chứng / hành động)`.
- **Lớp điều phối nội bộ (kiểu Dify):**
  - Router intent -> chọn nguồn (nội bộ/web) -> retrieval/verification -> safety guardrails -> synthesis -> citation formatter -> log & tracing.

**Ưu tiên triển khai ngay:**
1. `Source selector` (Web / Internal / Web+Internal / Trusted sites only).
2. `Research plan preview` trước khi chạy tác vụ dài.
3. `Progress UI` + cho phép chèn follow-up khi đang chạy.
4. `Citations bắt buộc` + điểm tin cậy nguồn.

---

## (B) RAG tiên tiến: GraphRAG, Self-RAG, CRAG, Adaptive-RAG, RAPTOR

### B.1. So sánh nhanh

| Kỹ thuật | Ý tưởng cốt lõi | Ưu điểm | Nhược điểm | Khi nào dùng cho CLARA |
|---|---|---|---|---|
| **GraphRAG** | Dựng knowledge graph từ corpus, tạo community summaries, trả lời bằng tổng hợp nhiều mức | Rất mạnh cho câu hỏi “global sensemaking”, multi-hop, liên kết thực thể | Indexing phức tạp, tốn chi phí build graph, cần governance entity | Dùng cho kho tri thức dược-y khoa lớn, câu hỏi quan hệ phức hợp (thuốc-bệnh-chống chỉ định) |
| **Self-RAG** | Model tự quyết định khi nào cần retrieve và tự phản tư (reflection tokens) để kiểm soát factuality | Giảm retrieve thừa, tăng factuality/citation trong nhiều tác vụ | Đòi hỏi tuning/mô hình phù hợp; triển khai production khó hơn RAG thường | Dùng ở tầng sinh câu trả lời cuối + tự kiểm (self-critique) trước khi trả cho user |
| **CRAG** | Có retrieval evaluator để chấm chất lượng tài liệu lấy về; nếu kém thì corrective actions (kể cả web search) | Tăng robust khi retrieval sai; plug-and-play tốt | Tăng độ trễ, thêm pipeline phức tạp | Dùng cho truy vấn rủi ro cao (DDI/khuyến nghị y tế) để giảm hallucination |
| **Adaptive-RAG** | Phân loại độ phức tạp câu hỏi rồi chọn chiến lược phù hợp (không retrieve / retrieve 1 bước / iterative) | Cân bằng quality-latency-cost tốt | Cần classifier ổn định; sai phân loại gây giảm chất lượng | Rất hợp cho CLARA để tối ưu chi phí vì workload user có nhiều mức độ |
| **RAPTOR** | Tổ chức tài liệu theo cây tóm tắt phân cấp (recursive embed-cluster-summarize) | Mạnh khi tài liệu dài, cần hiểu ngữ cảnh nhiều mức | Build/index pipeline nặng; cần tuning chunk-tree | Dùng cho guideline/label dài, hồ sơ y khoa dài cần tổng hợp nhiều tầng |

### B.2. Đề xuất kiến trúc RAG lai cho CLARA

**Khuyến nghị thực dụng theo 3 tầng:**
- **Tầng mặc định:** `Adaptive-RAG` (để route theo độ phức tạp và tối ưu chi phí).
- **Tầng an toàn cho câu hỏi y tế rủi ro cao:** `CRAG` (retrieval evaluator + corrective retrieval).
- **Tầng tri thức sâu:**
  - `GraphRAG` cho câu hỏi quan hệ toàn cục/multi-hop.
  - `RAPTOR` cho kho tài liệu dài cần tóm tắt phân cấp.
- **Tầng generate cuối:** mượn tư tưởng `Self-RAG` để bắt buộc bước tự phản biện trước khi xuất đáp án.

**Rule vận hành đề xuất:**
- Query đơn giản -> no/low retrieval.
- Query trung bình -> adaptive single-step retrieval.
- Query phức tạp/rủi ro -> CRAG + (GraphRAG hoặc RAPTOR) + self-critique + safety template.

---

## (C) DDI chuẩn cao: RxNorm + openFDA + DailyMed + DrugBank

### C.1. Vai trò từng nguồn dữ liệu

| Nguồn | Giá trị chính | Hạn chế chính | Vai trò trong stack CLARA |
|---|---|---|---|
| **RxNorm (NLM)** | Chuẩn hóa định danh thuốc (RXCUI), mapping liên hệ tên thuốc/NDC/khái niệm; cập nhật định kỳ | Không phải nguồn “đầy đủ DDI severity/management” độc lập | `Master drug identity layer` để đồng bộ mọi nguồn |
| **openFDA** | API công khai, dữ liệu nhãn thuốc/adverse events, harmonized fields | FDA nêu rõ không dùng đơn lẻ cho quyết định lâm sàng; dữ liệu adverse event có bias/under-reporting, không chứng minh nhân quả | `Signal & evidence layer` (label snippets, post-market signals) |
| **DailyMed (NLM/FDA SPL)** | Nguồn nhãn thuốc “in use” rất quan trọng, có mapping SPL-RxNorm | DailyMed cũng nêu có thể khác nhãn FDA-approved mới nhất; không phải mọi nội dung đều được FDA verify trước khi đăng | `Authoritative labeling text layer` cho contraindications/warnings/interactions |
| **DrugBank** | DDI phong phú, thường có severity + mô tả/management chi tiết | Ràng buộc license mạnh cho commercial; điều khoản nhấn mạnh không dùng thay thế tư vấn y khoa và giới hạn use-case | `Premium DDI intelligence layer` (nếu mua license phù hợp) |

### C.2. Thực tế quan trọng cần lưu ý
- `RxNav Drug-Drug Interaction API` đã bị thông báo ngừng (mốc khoảng đầu 2024), nên không nên thiết kế phụ thuộc vào endpoint này.
- Vì vậy, với DDI production-grade, nên lấy `RxNorm` làm backbone định danh, còn luật/tri thức DDI lấy từ combination `DailyMed/openFDA + nguồn thương mại (DrugBank hoặc tương đương có license rõ)`.

### C.3. Stack DDI chuẩn cao khuyến nghị cho CLARA

**1) Data normalization layer**
- Chuẩn hóa tất cả thuốc nhập vào về `RXCUI`.
- Mapping song song: tên thương mại <-> generic <-> NDC <-> RXCUI.

**2) Evidence retrieval layer**
- Lấy nhãn tương tác/chống chỉ định từ DailyMed/openFDA theo RXCUI/NDC liên quan.
- Lưu provenance theo từng câu bằng chứng (nguồn + version + timestamp).

**3) DDI inference layer**
- Rule engine severity theo ma trận:
  - Contraindicated
  - Major (tránh phối hợp / đổi phác đồ)
  - Moderate (monitor/điều chỉnh)
  - Minor (theo dõi)
- Nếu có DrugBank license: enrich severity + management recommendations.

**4) Safety UX layer**
- Luôn trả theo format cố định: `Mức độ` + `Vì sao` + `Nên làm gì ngay` + `Khi nào đi khám gấp` + `Nguồn tham chiếu`.
- Không đưa “kê đơn”; chỉ hỗ trợ quyết định và điều hướng an toàn.

**5) Governance layer**
- Phiên bản hóa tri thức DDI theo ngày phát hành.
- Regression test bộ case DDI trọng yếu trước mỗi release.
- Audit log bắt buộc cho mọi cảnh báo Major/Contraindicated.

---

## (D) Web research mạnh kiểu Perplexity khi chưa có API thương mại

### D.1. Kiến trúc đề xuất (self-host)

**Mục tiêu:** tái tạo năng lực “deep web research + citation” mà không phụ thuộc API closed của bên thứ ba.

**Kiến trúc 5 lớp:**
1. **Meta-search gateway:** `SearXNG` (self-host) làm lớp tổng hợp kết quả từ nhiều engine.
2. **Crawler worker pool:** crawler self-host (ưu tiên crawler tôn trọng robots + rate limit) để tải nội dung chi tiết từ URL đã chọn.
3. **Content pipeline:** boilerplate removal -> chunking -> dedup -> quality scoring -> lưu index.
4. **Research orchestrator:** planner -> iterative retrieval -> cross-source verification -> synthesis.
5. **Evidence renderer:** citation inline + source panel + confidence + contradictory evidence.

### D.2. Guardrails pháp lý/vận hành (bắt buộc)

**Nguyên tắc tối thiểu:**
- Tuân thủ `robots.txt` theo chuẩn REP (RFC 9309).
- Tôn trọng Terms of Service của từng website; không crawl phần yêu cầu xác thực nếu không có quyền.
- Không bypass paywall/biện pháp kỹ thuật hạn chế truy cập.
- Thiết lập rate limiting + backoff + nhận diện User-Agent minh bạch.
- Chỉ lưu excerpt cần thiết cho mục đích trích dẫn; tránh tái phân phối full text vi phạm bản quyền.
- Có cơ chế takedown/denylist domain theo yêu cầu pháp lý/chủ sở hữu nội dung.
- Ẩn danh dữ liệu người dùng nội bộ, không đẩy PII vào pipeline crawl.

**Lưu ý:** phần này là khuyến nghị kỹ thuật-vận hành, không thay thế tư vấn pháp lý.

### D.3. Luồng “Perplexity-like” cho CLARA

- B1. User prompt -> hệ thống hỏi 1-3 câu làm rõ (nếu cần).
- B2. Planner tạo `research plan` + domain ưu tiên.
- B3. SearXNG lấy candidate URLs, crawler đọc sâu các trang đạt ngưỡng trust.
- B4. Hệ thống sinh `key findings` theo thời gian thực, cho phép user chèn follow-up giữa chừng.
- B5. Xuất report có:
  - Tóm tắt ngắn
  - Kết luận chi tiết
  - Bằng chứng theo nguồn
  - Điểm chưa chắc chắn/mâu thuẫn
  - Khuyến nghị bước tiếp theo an toàn

---

## Đề xuất áp dụng cho CLARA (ưu tiên thực thi)

### 0-30 ngày (quick wins)
1. Dựng chat flow mới: `source selector + research plan preview + progress UI + citations panel`.
2. Bật tracing theo node/pipeline tương tự Dify Run History cho mọi câu trả lời nghiên cứu.
3. Chuẩn hóa thuốc nhập liệu về RXCUI ngay tại ingestion.

### 31-60 ngày (nâng độ tin cậy)
1. Tích hợp CRAG-style retrieval evaluator cho intent y tế/DDI.
2. Áp safety template bắt buộc cho output DDI (mức độ, hành động, red flags).
3. Dựng kho bằng chứng DailyMed/openFDA có provenance/versioning.

### 61-90 ngày (nâng tầm cạnh tranh)
1. Pilot GraphRAG hoặc RAPTOR cho tập dữ liệu dài/phức tạp.
2. Dựng self-host web research stack (SearXNG + crawler + legal guardrails).
3. A/B test trải nghiệm mới với KPI: answer trust, time-to-first-useful-answer, citation click-through, DDI false-alert burden.

---

## Nguồn tham chiếu chính

### A) Chat flow benchmark
- OpenAI Help: Deep research in ChatGPT: https://help.openai.com/en/articles/10500283-deep-research
- OpenAI Help: ChatGPT Search: https://help.openai.com/en/articles/9237897-chatgpt-search
- OpenAI Product update (2026-02-10 deep research update): https://openai.com/index/introducing-deep-research/
- Google Gemini Deep Research (official product update): https://blog.google/products-and-platforms/products/gemini/google-gemini-deep-research/
- Perplexity Help: Pro Search: https://www.perplexity.ai/help-center/en/articles/10352903-what-is-pro-search
- Perplexity Help: Advanced Deep Research: https://www.perplexity.ai/help-center/en/articles/13600190-what-s-new-in-advanced-deep-research
- Perplexity Help: Internal Knowledge Search: https://www.perplexity.ai/help-center/en/articles/10352914-what-is-internal-knowledge-search
- Dify Docs: Knowledge / If-Else / Run History:
  - https://docs.dify.ai/en/use-dify/knowledge/readme
  - https://docs.dify.ai/en/use-dify/nodes/ifelse
  - https://docs.dify.ai/en/use-dify/debug/history-and-logs

### B) RAG tiên tiến
- GraphRAG paper: https://arxiv.org/abs/2404.16130
- Self-RAG paper: https://arxiv.org/abs/2310.11511
- CRAG paper: https://arxiv.org/abs/2401.15884
- Adaptive-RAG paper: https://arxiv.org/abs/2403.14403
- RAPTOR paper: https://arxiv.org/abs/2401.18059

### C) DDI data stack
- RxNorm Overview: https://www.nlm.nih.gov/research/umls/rxnorm/overview.html
- RxNorm API / RxNav APIs:
  - https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
  - https://lhncbc.nlm.nih.gov/RxNav/APIs/
- DailyMed Overview & SPL resources:
  - https://dailymed.nlm.nih.gov/
  - https://dailymed.nlm.nih.gov/dailymed/spl-resources.cfm
  - https://dailymed.nlm.nih.gov/dailymed/app-support-mapping-files.cfm
- openFDA drug label/event + terms:
  - https://open.fda.gov/apis/drug/label/
  - https://open.fda.gov/apis/drug/event
  - https://open.fda.gov/apis/openfda-fields/
  - https://open.fda.gov/terms
- DrugBank Terms/License notes:
  - https://trust.drugbank.com/drugbank-trust-center/terms-of-use
  - https://trust.drugbank.com/drugbank-trust-center/drugbank-terms-of-service

### D) Web research stack và legal guardrails
- SearXNG docs (overview/private instance):
  - https://docs.searxng.org/
  - https://docs.searxng.org/own-instance.html
- Robots Exclusion Protocol (IETF RFC 9309):
  - https://www.rfc-editor.org/rfc/rfc9309
- Scrapy settings (ROBOTSTXT_OBEY, throttle liên quan crawler hygiene):
  - https://docs.scrapy.org/en/latest/topics/settings.html?highlight=ROBOTSTXT_OBEY

---

## Ghi chú phương pháp
- Một số đề xuất kiến trúc là **suy luận kỹ thuật** dựa trên tài liệu sản phẩm/paper công khai và kinh nghiệm triển khai hệ RAG production.
- Đối với các quyết định pháp lý cụ thể theo thị trường (US/EU/VN), cần review thêm cùng legal counsel trước khi vận hành ở quy mô lớn.
