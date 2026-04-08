# Deepdive Dashboard + Landing CLARA (2026-03-29)

## 0) Phạm vi và cơ sở đánh giá

- Phạm vi UI web hiện tại: `/dashboard`, `/dashboard/ecosystem`, `/dashboard/control-tower`, `/admin/*`, `/research`, `/`.
- Cơ sở đánh giá: code hiện trạng trong `apps/web` tại ngày 2026-03-29.
- Mục tiêu: tối ưu IA, mật độ dữ liệu, trust cues, action hierarchy để CLARA vừa dễ dùng cho role nghiệp vụ, vừa đủ chiều sâu cho control-plane kỹ thuật.

---

## 1) Audit dashboard hiện tại CLARA

## 1.1 IA (Information Architecture)

### Quan sát chính

1. `"Dashboard"` hiện tại đang trộn 3 vai trò trong cùng màn hình:
- launcher tính năng (module links),
- monitor hệ thống cơ bản,
- thông tin role.

2. Control-plane bị phân mảnh:
- `/dashboard/control-tower` chứa điều phối RAG,
- `/admin/overview`, `/admin/rag-sources`, `/admin/answer-flow`, `/admin/observability` cũng điều phối cùng domain.

3. Quyền truy cập có lúc xử lý muộn ở tầng nội dung (ví dụ màn hình tải xong rồi báo 403), thay vì chặn từ luồng điều hướng.

### Tác động

- Người dùng khó trả lời nhanh câu hỏi: “Tôi nên làm gì đầu tiên ở màn này?”.
- Kỹ thuật viên phải nhớ nhiều entry-point cho cùng một tác vụ điều phối.
- Mental model giữa “workspace vận hành” và “workspace nghiệp vụ” chưa tách ranh rõ.

### Đánh giá

- Mức độ: **P0** cho phân ranh workspace; **P1** cho điều hướng theo role.

## 1.2 Data density

### Quan sát chính

1. `/dashboard` có mật độ thấp (ít KPI, nhiều card mô tả), phù hợp onboarding nhưng thiếu tín hiệu quyết định cho vận hành.
2. `/admin/*` có nhiều card số liệu hơn, nhưng phần lớn là snapshot tức thời hoặc số liệu suy diễn từ config; thiếu time-window và thiếu xu hướng thật theo thời gian.
3. Bảng dữ liệu chủ yếu là “đọc” (read-only), thiếu lớp thao tác phân tích như filter theo thời gian, sort đa cột, compare theo phiên.

### Tác động

- Dễ tạo cảm giác “có dashboard nhưng chưa đủ để điều tra sự cố”.
- Khi có bất thường, người dùng chưa có lộ trình drill-down rõ (metric -> source -> hành động).

### Đánh giá

- Mức độ: **P0** cho dashboard kỹ thuật (`/admin/*`), **P1** cho dashboard tổng quan (`/dashboard`).

## 1.3 Trust cues (tín hiệu tin cậy)

### Điểm tốt hiện có

- Có badge trạng thái (health, severity, enabled/disabled).
- Có Evidence panel và Workflow steps trong `/research`.
- Có Risk note theo node trong Answer Flow.

### Thiếu hụt quan trọng

1. Thiếu metadata tin cậy nhất quán ở cấp panel:
- “data source nào”,
- “cửa sổ thời gian nào”,
- “cập nhật lúc nào”,
- “độ đầy đủ dữ liệu”.

2. Thiếu audit trail hành động quản trị trực tiếp trong UI:
- ai đổi config,
- đổi khi nào,
- rollback về đâu.

3. Ngôn ngữ và trạng thái còn lẫn Anh-Việt ở vài vùng kỹ thuật, làm giảm cảm nhận sản phẩm production-grade.

### Đánh giá

- Mức độ: **P0** cho trust metadata + audit trail, **P1** cho chuẩn hóa ngôn ngữ.

## 1.4 Action hierarchy

### Quan sát chính

1. Trên nhiều màn, CTA cạnh tranh nhau (Reload, Save, Toggle, điều hướng tab), chưa có “primary next action” rõ theo ngữ cảnh.
2. Với trạng thái lỗi/cảnh báo, UI báo vấn đề nhưng chưa luôn gắn “hành động khuyến nghị ngay tại chỗ” (investigate, rollback, retry có ngữ cảnh).
3. `/dashboard` nghiêng về “thông tin + link điều hướng”, chưa đủ “action-first cockpit”.

### Tác động

- Tăng thời gian từ nhận diện vấn đề -> hành động khắc phục.
- Người dùng mới dễ đi sai luồng vì thiếu ưu tiên thị giác cho hành động chính.

### Đánh giá

- Mức độ: **P0** cho action hierarchy ở admin, **P1** ở dashboard tổng quan.

## 1.5 Kết luận audit ngắn gọn

- Vấn đề cốt lõi không nằm ở thiếu component; nằm ở **thiếu cấu trúc điều phối thống nhất**:
1. Chưa tách rõ dashboard nghiệp vụ và dashboard kỹ thuật.
2. Chưa chuẩn hóa trust metadata ở cấp panel.
3. Chưa thiết kế đường đi hành động từ tín hiệu -> điều tra -> xử lý.

---

## 2) Benchmark nguyên tắc từ technical dashboards + chat layouts

## 2.1 Nguyên tắc technical dashboard kiểu Grafana/Datadog

1. **Global query context trước, panel sau**
- Luôn có thanh điều khiển chung: time range, environment, service scope, refresh cadence.

2. **Macro -> micro**
- Hàng đầu: SLI/SLO chính.
- Hàng sau: drill-down theo service/source/incident.

3. **Panel phải “self-explaining”**
- Mỗi panel có: metric definition, query window, last updated, datasource.

4. **Correlation-first**
- Cùng time axis để đối chiếu latency/error/dependency cùng một mốc.

5. **Alert-to-action loop**
- Cảnh báo không dừng ở màu đỏ; phải có CTA điều tra hoặc runbook ngay tại chỗ.

6. **Density có kiểm soát**
- Mật độ cao nhưng scan nhanh: số lớn + sparkline + delta.

7. **Change visibility**
- Event marker cho deploy/config change để giải thích đột biến.

## 2.2 Nguyên tắc chat product layout hiện đại

1. **3 vùng rõ nhiệm vụ**
- trái: history,
- giữa: conversation/composer,
- phải: evidence/context tools.

2. **Composer luôn là trung tâm hành động**
- cố định vị trí, trạng thái gửi rõ, hỗ trợ thao tác nhanh.

3. **Provenance hiển thị gần kết quả**
- citation/snippet/source link phải liền mạch với câu trả lời.

4. **Runtime transparency**
- cho thấy mode, flow path, fallback/verification state để tăng tin cậy.

5. **Memory + context persistence**
- source/file đã chọn phải nhìn thấy và chỉnh được ngay trong phiên.

## 2.3 Gap map của CLARA so với benchmark

1. CLARA đã có nền tốt ở 3-panel chat layout và evidence side panel.
2. Khoảng trống lớn nằm ở control-plane:
- thiếu global time/environment filter,
- thiếu runbook/incident action loop,
- thiếu chuẩn metadata tin cậy cho từng panel.
3. Khoảng trống phụ ở chat:
- chưa hiển thị đủ runtime transparency ở cấp user-facing (ví dụ nhánh fallback có kích hoạt hay không, dựa trên ngưỡng nào).

---

## 3) Benchmark landing conversion kiểu KP3-inspired

## 3.1 Framework cốt lõi: Problem -> Offer -> Proof -> Flow -> CTA

### Problem
- Nêu pain cụ thể, đo được, gần bối cảnh người dùng.
- CLARA: nhiễu thông tin y tế, rủi ro sai/nhầm thuốc, thiếu một nơi hỏi + kiểm chứng + hành động.

### Offer
- 1 pain -> 1 promise rõ.
- CLARA hiện có 3 offer block (Research, SelfMed, Control Tower) là đúng hướng.

### Proof
- Tầng chứng minh cần nhiều lớp:
1. credibility proof (nguồn chuẩn, policy gate),
2. mechanism proof (pipeline verify/fallback),
3. outcome proof (KPI thực tế, case trước/sau).

### Flow
- Cho người dùng thấy “chỉ 3 bước để ra kết quả”.
- CLARA hiện đã có section How it works 3 bước, phù hợp.

### CTA
- CTA nên lặp có chiến lược, nhưng mỗi vùng chỉ một mục tiêu chính.
- Nếu nhiều CTA ngang cấp trong hero, conversion thường bị phân tán.

## 3.2 Đối chiếu landing CLARA hiện tại

### Điểm mạnh

1. Đã có cấu trúc gần đúng KP3-style: Problem, Offer, Flow, FAQ, CTA lặp.
2. Message-value khá rõ cho nhóm user mới.
3. Visual hierarchy tốt hơn baseline trước đây.

### Điểm cần tăng lực chuyển đổi

1. Proof đang thiên về tuyên bố tính năng, thiếu số liệu hiệu quả hoặc bằng chứng vận hành thực tế.
2. Hero có nhiều nút cùng cấp; thiếu “single dominant CTA” theo chiến dịch.
3. Chưa tách flow theo persona ngay trong fold đầu (người dùng cá nhân vs bác sĩ vs admin).

## 3.3 KPI conversion nên đo ngay

1. Hero CTA CTR theo từng biến thể copy.
2. Time-to-first-action từ landing -> register/login/research.
3. Scroll reach đến section proof và final CTA.
4. Conversion theo luồng persona (Research-first, SelfMed-first, Admin-first).

---

## 4) Design principles cụ thể để triển khai ngay trong CLARA

## 4.1 Bộ nguyên tắc thực thi

1. **Tách 2 lớp dashboard rõ ràng**
- `/dashboard`: cockpit nghiệp vụ theo role (task/safety/next action).
- `/admin/*`: control-plane kỹ thuật (metrics/config/incident).

2. **Một màn hình, một mục tiêu hành động chính**
- Mỗi view chỉ có 1 CTA primary; hành động phụ dùng secondary/tertiary.

3. **Panel contract bắt buộc**
- Mọi panel kỹ thuật phải có: `metric`, `window`, `datasource`, `last_updated`, `owner`.

4. **Alert phải đi kèm action**
- warning/critical luôn có nút điều tra hoặc runbook; không chỉ badge màu.

5. **Global control bar cho admin**
- Thêm filter chung: time range, environment, service/source, auto-refresh.

6. **Densify có kiểm soát**
- Hàng đầu: 6-8 KPI có delta/sparkline.
- Hàng sau: bảng anomaly/top offenders + drill-down.

7. **Trust cues nhất quán xuyên sản phẩm**
- Chuẩn severity (`critical/warning/info`), chuẩn trạng thái (`reachable/unreachable`), chuẩn ngôn ngữ tiếng Việt có thuật ngữ kỹ thuật thống nhất.

8. **Auditability mặc định**
- Mọi thao tác Save config hiển thị diff ngắn + last editor + timestamp + khả năng rollback.

9. **Chat runtime transparency cho end-user**
- Hiển thị nhánh xử lý đã dùng (tier/mode, evidence count, fallback có/không).

10. **Evidence-first response card**
- Câu trả lời luôn đi cùng trust summary ngắn: số citation, độ mới dữ liệu, note an toàn.

11. **Landing theo persona-intent**
- Trong hero hoặc ngay dưới hero, cho 3 đường vào rõ: cá nhân, nghiên cứu, bác sĩ/admin.

12. **CTA governance cho landing**
- Hero: 1 primary + 1 secondary.
- Mid-page: 1 CTA theo intent hiện tại.
- Final section: lặp lại primary CTA nhất quán.

## 4.2 Backlog triển khai nhanh (đề xuất 14 ngày)

### Wave 1 (Ngày 1-4): IA + Action hierarchy

1. Rà soát lại vai trò của `/dashboard` và `/admin/*`, bỏ trùng entry-point.
2. Chuẩn CTA primary/secondary cho từng trang admin.
3. Đưa quyền truy cập vào điều hướng sớm hơn (giảm tình trạng vào trang rồi mới báo 403).

### Wave 2 (Ngày 5-9): Trust + density

1. Thêm panel metadata contract (`window`, `source`, `updated_at`, `owner`).
2. Bổ sung KPI row có delta/sparkline thật cho admin overview/observability.
3. Chuẩn severity/status labels nhất quán toàn bộ dashboard.

### Wave 3 (Ngày 10-14): Landing conversion + chat trust

1. Tối ưu hero CTA theo single-goal campaign.
2. Nâng proof section: thêm evidence vận hành hoặc benchmark nội bộ có số liệu.
3. Hiển thị trust summary trong chat result card (mode, citations, fallback state).

## 4.3 Definition of Done (DoD) cho vòng này

1. Người dùng trả lời được trong 5 giây: “đây là màn để quan sát hay để hành động?”.
2. Mỗi panel kỹ thuật có đủ metadata tin cậy.
3. Mỗi cảnh báo critical có hành động khắc phục trực tiếp trên UI.
4. Landing có 1 CTA primary thống trị rõ trong hero và final block.
5. Dashboard không còn trùng chức năng điều phối giữa `/dashboard/control-tower` và `/admin/*`.

---

## 5) Tóm tắt quyết định thiết kế

- CLARA đã có nền UI tốt, nhưng cần chuyển từ “đủ màn hình” sang “đủ hệ điều phối”.
- Ưu tiên cao nhất: **IA tách lớp + trust metadata + action loop**.
- Với landing, tiếp tục giữ khung KP3-inspired nhưng phải tăng lớp proof và kỷ luật CTA để tối đa hóa chuyển đổi.
