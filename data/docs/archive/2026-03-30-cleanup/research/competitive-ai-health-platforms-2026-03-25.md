# Benchmark cạnh tranh AI health platforms (25-03-2026)

## 1) Danh sách sản phẩm

| Sản phẩm | Nhóm | Giá trị chính | Claim chính (kèm nguồn) |
|---|---|---|---|
| **Perplexity** | AI research assistant | Tìm kiếm + tổng hợp có citation theo thời gian thực | - Có citation theo từng câu trả lời, giữ ngữ cảnh hội thoại, chọn model. [S1]  - Pro Search tổng hợp từ nhiều nguồn, hỗ trợ chế độ nguồn (web/academic/files), code interpreter. [S2][S3] |
| **Gemini app** | AI assistant + research | Deep Research + Gems + kiểm chứng lại câu trả lời | - Deep Research tìm và tổng hợp web; có Gems tùy biến trợ lý. [S4]  - Có nút Sources và tính năng Double-check để đối chiếu bằng Google Search. [S5] |
| **ChatGPT (core)** | AI assistant đa năng | Search + Deep Research + workspace theo project | - Search/Deep Research có nguồn trích dẫn; Deep Research cho phép chọn domain, duyệt kế hoạch trước khi chạy. [S7][S8]  - Projects hỗ trợ memory theo ngữ cảnh dự án dài hạn. [S9] |
| **ChatGPT Health / ChatGPT for Healthcare** | AI health workflows | Không gian health tách biệt + bản enterprise cho clinical workflow | - ChatGPT Health: có thể kết nối hồ sơ y tế (US-only), tách riêng dữ liệu Health; không dùng để train foundation models. [S12]  - ChatGPT for Healthcare: hỗ trợ citations lâm sàng, RBAC, audit logs, HIPAA/BAA, quyết định cuối thuộc clinician. [S13] |
| **Ada** | Symptom checker | Đánh giá triệu chứng theo luồng hỏi đáp có cấu trúc | - Flow rõ ràng: nhập triệu chứng -> trả lời câu hỏi -> báo cáo nguyên nhân khả dĩ. [S15]  - 2026 tái tập trung vào core assessment, loại bỏ nhiều tracker phụ (BMI/symptom/medication/allergy...). [S16] |
| **Medisafe** | Medication adherence & safety | Nhắc thuốc + cảnh báo tương tác + caregiver loop | - Có reminder, refill alert, interaction warnings, measurement tracker, Medfriend caregiver. [S17]  - Có bằng chứng cải thiện adherence trong nghiên cứu thực địa 2025. [S18] |
| **MyTherapy** | Medication companion | Nhắc thuốc, nhật ký dùng thuốc, báo cáo bác sĩ | - Reminder + refill + tracking triệu chứng/chỉ số + tạo health report chia sẻ cho bác sĩ. [S20] |
| **Drugs.com Interaction Checker** | Drug safety tool | Kiểm tra tương tác thuốc/đồ ăn/rượu/bệnh nền | - Cho phép kiểm tra tương tác và phân mức độ (Major/Moderate/Minor/Unknown). [S21]  - Hệ dữ liệu thuốc lớn, cập nhật nguồn dữ liệu y dược thường xuyên. [S21][S22] |
| **Dify** | AI workflow builder | Orchestration cho Chatflow/Workflow + KB pipeline | - Chatflow có memory, Answer node; Workflow mạnh về IF/ELSE, iteration, automation. [S23][S28]  - KB pipeline + retrieval + citation attribution + Human Input node. [S24][S25][S26][S27] |
| **Langflow** | Visual flow builder | Kéo-thả component, test realtime, share/API/MCP | - Visual editor kéo-thả node + Playground để quan sát logic/tool calls theo thời gian thực. [S30][S31] |
| **OpenHands (flow-style agent)** | Agentic execution platform | CLI/GUI + sandbox chạy tác vụ nhiều bước | - Có CLI/Local GUI/Cloud, hỗ trợ cộng tác và RBAC ở bản cloud/enterprise. [S32]  - Nhấn mạnh sandbox (Docker khuyến nghị) để cô lập khi agent chạy lệnh/chỉnh file. [S33][S35] |

## 2) Flow người dùng theo từng sản phẩm

| Sản phẩm | Flow người dùng điển hình | Pattern UI/UX có thể học cho CLARA |
|---|---|---|
| **Perplexity** | - Nhập câu hỏi -> chọn nguồn/model -> nhận câu trả lời có citation -> hỏi follow-up trong cùng thread. [S1][S2][S3] | - `Source-first`: đặt chọn nguồn ngay ô nhập.  - Citation inline + panel nguồn ở cuối phản hồi. |
| **Gemini** | - Nhập prompt (hoặc Deep Research) -> xem nguồn -> dùng Double-check cho claim quan trọng -> tinh chỉnh bằng Gems cá nhân hóa. [S4][S5] | - `Verify-first`: nút kiểm chứng ngay dưới câu trả lời.  - Cho phép tạo "chuyên gia mini" (Gem) theo use case. |
| **ChatGPT** | - Chọn Search/Deep Research -> duyệt/sửa research plan -> theo dõi tiến độ -> nhận report có citation -> lưu trong Project để tiếp tục. [S7][S8][S9] | - `Plan-before-run`: cho user duyệt kế hoạch trước khi agent chạy sâu.  - `Longitudinal workspace`: project memory cho case theo dõi dài ngày. |
| **ChatGPT Health/Healthcare** | - Vào không gian Health riêng -> (tùy chọn) kết nối dữ liệu health -> hỏi đáp có context sức khỏe -> với bản healthcare: dùng nguồn nội bộ + lâm sàng có citation. [S12][S13] | - `Context boundary`: tách không gian dữ liệu y tế khỏi chat thường.  - `Role-aware access`: RBAC theo vai trò clinical/ops. |
| **Ada** | - Start assessment -> nhập triệu chứng -> trả lời chuỗi câu hỏi xác suất -> nhận báo cáo nguyên nhân khả dĩ và hướng đi tiếp. [S15] | - `Guided triage`: wizard từng bước, giảm mơ hồ.  - Report cuối dạng tóm tắt có thể mang đi khám. |
| **Medisafe** | - Nhập thuốc -> nhận nhắc uống/refill -> phát hiện tương tác và cảnh báo theo mức -> (tuỳ chọn) mời Medfriend khi bỏ liều. [S17][S19] | - `Safety escalations`: cảnh báo theo severity.  - `Care circle`: caregiver loop khi người dùng bỏ liều. |
| **MyTherapy** | - Thiết lập phác đồ -> nhận nhắc thuốc/chỉ số/appointment -> ghi nhận đã uống/bỏ liều -> xuất report cho bác sĩ. [S20] | - `Adherence journaling`: timeline rõ đã uống/chưa uống.  - `Doctor-ready report`: xuất báo cáo 1 chạm. |
| **Drugs.com** | - Thêm nhiều thuốc/chất liên quan -> xem mức độ tương tác + khuyến nghị xử lý -> hỏi FAQ liên quan. [S21][S22] | - `Safety checker độc lập`: cho phép check nhanh ngoài luồng chat chính.  - Dùng nhãn mức độ dễ hiểu (Major/Moderate/Minor/Unknown). |
| **Dify** | - Chọn Chatflow/Workflow -> nối node (LLM/Retrieval/IF-ELSE/Human Input) -> test retrieval/citation -> publish. [S23][S24][S25][S27][S28] | - `Human-in-the-loop node` ở điểm rủi ro cao.  - Quan sát data flow/citation tại node level để debug nhanh. |
| **Langflow** | - Kéo-thả component -> nối Chat Input/LLM/Output -> test ở Playground -> share qua API/embed/MCP. [S29][S30][S31] | - `Visual trace`: cho user nhìn tool calls + output từng bước.  - Dễ tách proto vs production qua API/export. |
| **OpenHands** | - Chọn mode (CLI/GUI/Cloud) -> agent thực thi task trong sandbox -> theo dõi session/chia sẻ với team. [S32][S33][S34] | - `Execution transparency`: hiển thị rõ mode chạy và phạm vi quyền.  - `Sandbox-by-default` cho tác vụ có quyền ghi/chạy lệnh. |

## 3) Điểm mạnh/yếu

| Sản phẩm | Điểm mạnh | Điểm yếu / rủi ro |
|---|---|---|
| **Perplexity** | - Citation mạnh, phù hợp research nhanh. [S1][S2] | - Chất lượng phụ thuộc nguồn web; vẫn cần user thẩm định claim y khoa. [S1] |
| **Gemini** | - Double-check trực tiếp trong UI, tốt cho fact-check. [S5] | - Không phải phản hồi nào cũng có Sources; cần bước kiểm tra thủ công. [S5] |
| **ChatGPT (core)** | - Deep Research có plan-review và report có citation, hợp bài toán phức tạp. [S8] | - OpenAI nêu rõ output có thể sai, không dùng thay tư vấn chuyên môn nếu thiếu human review. [S10][S11] |
| **ChatGPT Health/Healthcare** | - Tách dữ liệu health + không train mặc định; bản Healthcare có compliance stack mạnh. [S12][S13] | - Health consumer có phạm vi cá nhân wellness; EHR consumer là US-only lúc ra mắt. [S12] |
| **Ada** | - Luồng symptom assessment tập trung, dễ hiểu, dễ hoàn tất. [S15][S16] | - Việc bỏ nhiều tracker cho thấy trade-off: depth theo dõi dài hạn có thể giảm nếu chỉ tập trung triage. [S16] |
| **Medisafe** | - Mạnh ở adherence + caregiver + medication safety alerts. [S17][S18][S19] | - Một số bằng chứng interaction feature cũ (2017); cần đánh giá độ cập nhật feature theo thị trường hiện tại. [S19] |
| **MyTherapy** | - Trải nghiệm quản lý dùng thuốc và chia sẻ bác sĩ rất thực dụng. [S20] | - Không nhấn mạnh mạnh phần interaction checker real-time như Drugs.com/Medisafe. [S20] |
| **Drugs.com** | - Checker chuyên sâu, phân mức severity rõ, phạm vi tương tác rộng. [S21][S22] | - Công cụ độc lập, không phải workflow chăm sóc end-to-end; UX thiên tra cứu hơn hội thoại. [S21] |
| **Dify** | - Builder linh hoạt: routing, HITL, retrieval/citation, trigger automation. [S23][S25][S27][S28] | - Cần năng lực thiết kế flow tốt; dễ tạo flow phức tạp khó bảo trì nếu thiếu chuẩn hóa. [S23][S24] |
| **Langflow** | - Trực quan hóa mạnh, test nhanh qua Playground, hỗ trợ share/embed/API. [S30][S31] | - Playground tiện cho thử nghiệm nhưng cần thêm lớp production governance riêng. [S30] |
| **OpenHands** | - Rõ ràng về mode vận hành và sandbox, hỗ trợ cộng tác team. [S32][S33][S35] | - Nếu cấu hình process sandbox/host exposure kém có thể tăng rủi ro bảo mật. [S33][S34] |

## 4) Những gì CLARA nên copy

| Pattern nên copy | Vì sao đáng copy | Cách áp dụng cho CLARA |
|---|---|---|
| **`Citation + nguồn bấm được` ở mọi câu trả lời y khoa** | Tăng khả năng kiểm chứng và niềm tin. [S1][S5][S7][S8][S13] | - Mặc định hiển thị source chip ngay dưới từng claim nguy cơ cao (thuốc/chẩn đoán/phác đồ). |
| **`Plan-before-run` cho nghiên cứu phức tạp** | Giảm chạy sai hướng, tăng kiểm soát người dùng. [S8] | - Cho user duyệt kế hoạch: mục tiêu, nguồn, giới hạn, output trước khi agent chạy. |
| **`Triage wizard` nhiều bước có logic xác suất** | Dễ hoàn thành, giảm cognitive load cho user không chuyên. [S15][S16] | - Luồng 4 bước: Triệu chứng chính -> câu hỏi làm rõ -> red flags -> khuyến nghị hành động. |
| **`Medication safety layer` độc lập khỏi chat chính** | Drug interaction là tác vụ safety-critical, cần UX chuyên biệt. [S21][S22][S17] | - Nút cố định "Kiểm tra tương tác" trong mọi màn hình thuốc; dùng nhãn Major/Moderate/Minor/Unknown. |
| **`Care-circle` cho adherence** | Người nhà/caregiver giúp giảm bỏ liều. [S17][S18] | - Cơ chế mời người hỗ trợ; gửi cảnh báo khi trễ liều X phút. |
| **`Human-in-the-loop` ở điểm rủi ro cao** | Cân bằng tự động hóa và an toàn quyết định y khoa. [S25][S28] | - Bắt buộc duyệt tay trước khi gửi khuyến nghị có tác động điều trị. |
| **`Context boundary` cho dữ liệu sức khỏe** | Giảm rò rỉ ngữ cảnh, tăng kiểm soát quyền riêng tư. [S12][S13] | - Tách workspace Health khỏi chat chung; RBAC theo vai trò (patient/caregiver/clinician). |
| **`Visual trace` cho team nội bộ CLARA** | Hỗ trợ debug nhanh và audit logic agent. [S31][S30][S23] | - Màn hình nội bộ hiển thị node path, sources, và quyết định rẽ nhánh theo thời gian. |

## 5) Những gì CLARA nên tránh

| Điều nên tránh | Vì sao cần tránh | Biện pháp phòng tránh |
|---|---|---|
| **Đưa khuyến nghị y khoa kiểu "chốt quyết định" không có human review** | Vi phạm nguyên tắc an toàn/tuân thủ và dễ gây hại. [S10][S11][S13] | - Luôn chèn disclaimer + escalation "liên hệ bác sĩ" cho high-risk outputs. |
| **Ẩn nguồn hoặc chỉ để nguồn ở cuối rất khó thấy** | User khó kiểm chứng, tăng nguy cơ tin nhầm. [S1][S5][S7] | - Inline citation + panel nguồn cố định, ưu tiên claim liên quan thuốc/chẩn đoán. |
| **Nhồi quá nhiều tính năng tracker không phục vụ mục tiêu chính** | Tăng độ phức tạp và làm loãng core value (bài học từ Ada refocus 2026). [S16] | - Giữ core: triage + research + medication safety; feature phụ phải chứng minh retention. |
| **Workflow builder không có chuẩn governance** | Flow dễ rối, khó bảo trì, khó audit trong môi trường y tế. [S23][S24][S30] | - Thiết lập thư viện flow chuẩn + checklist review bắt buộc trước publish. |
| **Chạy agent có quyền cao mà thiếu sandbox/permission boundary** | Rủi ro bảo mật và thao tác ngoài ý muốn. [S33][S34][S35] | - Sandbox mặc định, explicit permission cho hành động ghi/xóa/gửi dữ liệu. |
| **Đánh đồng “nhắc thuốc” với “an toàn thuốc”** | Reminder tốt cho adherence nhưng không thay thế interaction safety checker. [S20][S21][S22] | - Tách rõ 2 luồng UX: `Adherence` và `Interaction Risk`. |

---

### Ghi chú phương pháp
- Các khuyến nghị “copy/tránh” là **suy luận sản phẩm** từ flow/tính năng công khai trong nguồn.
- Mốc thời gian quan trọng để tránh nhầm lẫn: bài refocus của Ada xuất bản **22-01-2026**. [S16]

### Nguồn tham chiếu
- [S1] https://www.perplexity.ai/help-center/en/articles/10352895-how-does-perplexity-work
- [S2] https://www.perplexity.ai/help-center/en/articles/10352903-what-is-pro-search
- [S3] https://www.perplexity.ai/help-center/en/articles/10354759-why-can-t-i-see-focus-mode-on-my-search-bar
- [S4] https://blog.google/products-and-platforms/products/gemini/new-gemini-app-features-march-2025/
- [S5] https://support.google.com/gemini/answer/14143489?hl=en
- [S6] https://support.google.com/a/users/answer/14506784
- [S7] https://help.openai.com/en/articles/9237897-chatgpt-search/
- [S8] https://help.openai.com/en/articles/10500283-deep-research
- [S9] https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- [S10] https://openai.com/policies/terms-of-use/
- [S11] https://openai.com/policies/usage-policies/
- [S12] https://help.openai.com/en/articles/20001036-what-is-chatgpt-health
- [S13] https://help.openai.com/it-it/articles/20001046-chatgpt-for-healthcare
- [S14] https://ada.com/app/
- [S15] https://ada.com/help/how-do-i-start-a-symptom-assessment/
- [S16] https://ada.com/editorial/ada-introduces/
- [S17] https://www.medisafe.com/wp-content/uploads/2024/02/Medisafe_Feb-24-Medfriend_CaseStudy.pdf
- [S18] https://www.medisafe.com/education-resources/medisafe-demonstrates-significant-impact-on-medication-adherence-in-medically-underserved-populations/
- [S19] https://www.medisafe.com/medisafe-launches-feature-to-alert-users-of-potentially-harmful-drug-interactions/
- [S20] https://www.mytherapyapp.com/
- [S21] https://www.drugs.com/drug_interactions.html
- [S22] https://www.drugs.com/support/
- [S23] https://docs.dify.ai/versions/3-0-x/en/user-guide/workflow/README
- [S24] https://docs.dify.ai/en/use-dify/knowledge/knowledge-pipeline/readme
- [S25] https://docs.dify.ai/en/use-dify/nodes/human-input
- [S26] https://docs.dify.ai/en/use-dify/nodes/llm
- [S27] https://docs.dify.ai/versions/3-0-x/en/user-guide/knowledge-base/retrieval-test-and-citation
- [S28] https://docs.dify.ai/en/use-dify/nodes/ifelse
- [S29] https://docs.langflow.org/
- [S30] https://docs.langflow.org/concepts-overview
- [S31] https://docs.langflow.org/concepts-playground
- [S32] https://github.com/OpenHands/OpenHands
- [S33] https://docs.openhands.dev/openhands/usage/sandboxes/overview
- [S34] https://docs.openhands.dev/openhands/usage/cli/web-interface
- [S35] https://docs.openhands.dev/openhands/usage/sandboxes/docker
