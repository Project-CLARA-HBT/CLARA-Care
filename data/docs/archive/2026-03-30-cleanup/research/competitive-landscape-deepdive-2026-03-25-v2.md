# Competitive Deepdive 2026-03-25 (v2)

## 1) Mục tiêu
- So sánh các sản phẩm tương tự CLARA theo 4 trục: `chatbot UX`, `DDI safety`, `medication cabinet`, `admin/ops control`.
- Chốt feature ưu tiên để triển khai ngay cho bản ship.

## 2) Nhóm đối thủ chính
### 2.1 Medication management + DDI
- Medisafe
- Drugs.com Medication Guide
- MyTherapy
- Dosecast
- Hero (smart dispenser + caregiver app)
- MedAdvisor
- CareClinic

### 2.2 Symptom checker / AI health assistant
- Ada Health
- K Health
- Buoy Health

### 2.3 LLMOps / RAG control dashboard pattern
- Dify

## 3) Insight sản phẩm (tóm tắt thực dụng)
### 3.1 Pattern đã chứng minh hiệu quả
- `Single primary input`: giao diện một ô nhập trung tâm giúp onboarding nhanh (Perplexity/Gemini pattern).
- `Medication safety as separate module`: phần thuốc thường là module riêng, không nhét chung vào chatbot.
- `Caregiver loop`: app mạnh đều có luồng người chăm sóc, miss-dose alert, refill alert.
- `Tiered safety`: cảnh báo chia mức độ (`major/moderate/minor`), có giải thích hành động kế tiếp.
- `Ops visibility`: sản phẩm LLMOps tốt có panel logs/flow/source health rõ ràng (Dify).

### 3.2 Gaps có thể tạo khác biệt cho CLARA
- Kết hợp sâu `chat AI + permanent medicine cabinet + proactive DDI` trong cùng account graph.
- Bổ sung nguồn VN (BYT, Dược thư Quốc gia) + chuẩn quốc tế (RxNorm/openFDA/PubMed).
- Control Tower riêng để điều chỉnh RAG source/flow theo vai trò và policy.

## 4) Feature matrix rút gọn
| Capability | Medisafe | Drugs.com | MyTherapy | Hero | Ada/K/Buoy | Dify | CLARA target |
|---|---|---|---|---|---|---|---|
| Permanent medicine cabinet | Có | Có (My Med List) | Có | Có | Không trọng tâm | N/A | Bắt buộc |
| Proactive DDI alert | Có (US) | Có | Không nổi bật | Hạn chế | Không trọng tâm | N/A | Bắt buộc |
| OCR hóa đơn/toa thuốc | Không rõ mạnh | Không rõ | Không mạnh | Không | Không | N/A | Bắt buộc |
| Caregiver escalation | Có | Hạn chế | Hạn chế | Rất mạnh | Không | N/A | Bắt buộc |
| Chatbot clinical QA | Hạn chế | Hạn chế | Hạn chế | Không | Có (symptom) | Framework | Bắt buộc |
| Admin control tower cho flow/RAG | Không | Không | Không | Không | Không | Rất mạnh | Bắt buộc |

## 5) Yêu cầu triển khai cho CLARA (rút từ benchmark)
1. Web/App tách rõ 3 khu vực: `Chat`, `SelfMed`, `Admin`.
2. SelfMed có flow cố định:
- Add thuốc thủ công / scan OCR hóa đơn
- Chuẩn hóa tên thuốc
- Auto DDI check khi tủ thuốc đổi
- Alert + recommendation + next step
3. Chat UX kiểu 1-input trung tâm + source cards + follow-up chips.
4. Admin dashboard kiểu control-plane:
- RAG sources registry
- Flow toggles (role router, intent router, verification, fallback)
- Logs/trace/latency/safety events

## 6) Backlog đề xuất implement ngay
### Wave A (ship core)
- DDI engine dùng RxNorm + openFDA + fallback local rules.
- SelfMed permanent cabinet + OCR import + auto check.
- Chat UX mới (Perplexity/Gemini-like).
- Admin `/admin/*` riêng cho RAG + flow controls.

### Wave B (hardening)
- Family dashboard + escalation policy theo thời gian trễ liều.
- Nguồn BYT/Dược thư ingestion job + freshness board.
- Full observability + audit log explorer.

## 7) Nguồn tham chiếu
- Medisafe App Store: https://apps.apple.com/us/app/medisafe-medication-management/id573916946
- Medisafe interaction release: https://www.medisafe.com/medisafe-launches-feature-to-alert-users-of-potentially-harmful-drug-interactions/
- Drugs.com app: https://apps.apple.com/us/app/drugs-com-medication-guide/id599471042
- Drugs.com data sources: https://www.drugs.com/
- MyTherapy: https://www.mytherapyapp.com/
- Dosecast features: https://dosecast.com/features/
- Hero product: https://herohealth.com/our-product/
- Hero caregiver: https://herohealth.com/caregivers/
- MedAdvisor: https://www.mymedadvisor.com/medication-management-app
- CareClinic features: https://careclinic.io/features/
- Ada app: https://ada.com/app/
- K Health app: https://khealth.com/app
- Buoy symptom checker: https://www.buoyhealth.com/multi-symptom-checker
- Dify intro: https://docs.dify.ai/versions/legacy/en/user-guide/welcome
- Dify dashboard monitoring: https://docs.dify.ai/en/guides/monitoring/analysis
- Dify logs: https://docs.dify.ai/en/use-dify/monitor/logs
- Dify knowledge pipeline: https://docs.dify.ai/en/guides/knowledge-base/knowledge-pipeline/readme
