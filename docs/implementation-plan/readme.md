# Kế Hoạch Triển Khai CLARA (Bản Tổng)

Phiên bản: 3.0  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu

Bộ tài liệu này là kế hoạch triển khai chính thức cho CLARA với 3 trục bắt buộc:
- Hai nhánh sản phẩm chạy song song: `CLARA Research` và `CLARA Self-Med`.
- Nền tảng đa kênh: Web + ứng dụng di động Flutter.
- Bổ sung `System Control Tower Dashboard` để quản trị toàn bộ hệ thống vận hành AI y tế.

## 2. Quyết định kỹ thuật đã chốt

- Áp dụng ngay `LangChain/LangGraph` cho orchestration workflow AI.
- Backend runtime ưu tiên `Rust` cho gateway, policy, audit, session, API orchestration.
- Dịch vụ ML (OCR/ASR/embedding/rerank/generation/verifier) chạy Python, kết nối qua hợp đồng API chuẩn.
- Intent router 2 lớp: `B1 Role Classification -> B2 Intent Classification theo Role`.
- `Synthesis` và `Verification` tách node độc lập.
- Cache y khoa theo quy tắc `UPDATE/INVALIDATE`, không cộng dồn mù.

## 3. Danh sách file chuẩn

1. `phase-00-to-06-master-plan.md`
2. `workstream-clara-research.md`
3. `workstream-clara-self-med.md`
4. `frontend-web-mobile-flutter-plan.md`
5. `frontend-web-ux-revamp-plan.md`
6. `backend-rust-plan.md`
7. `metrics-gates-and-operating-model.md`
8. `system-control-tower-dashboard-plan.md`
9. `ui-ux-audit-report.md`
10. `content-glossary-vi.md`
11. `web-sitemap-v2.md`
12. `flutter-android-route-map.md`
13. `p1-to-p6-microtasks-detailed-plan.md`
14. `source-integration-execution-board.md`
15. `docs-gap-audit-2026-03-25.md`
16. `web-mobile-information-architecture-v3.md`
17. `architecture-plan-alignment-audit-v3.md`

## 4. KPI runtime theo role

- Normal users: < 2 phút cho câu trả lời hoàn chỉnh.
- Researchers: tiến dần theo mốc 5-10-20 phút.
- Doctors: 10-20 phút với AI Council, bắt buộc hiển thị log hội chẩn.

## 5. Cách dùng bộ kế hoạch

1. Đọc `phase-00-to-06-master-plan.md` để nắm roadmap tổng thể.
2. Đọc hai workstream để tách phạm vi Research và Self-Med.
3. Đọc `system-control-tower-dashboard-plan.md` để triển khai control-plane quản trị.
4. Triển khai giao diện theo `frontend-web-mobile-flutter-plan.md`, `frontend-web-ux-revamp-plan.md` và `flutter-android-route-map.md`.
5. Triển khai backend theo `backend-rust-plan.md`.
6. Triển khai tích hợp nguồn theo `source-integration-execution-board.md`.
7. Vận hành bằng `metrics-gates-and-operating-model.md`.

## 6. Trách nhiệm điều phối

- Product/Program Lead: kiểm soát phạm vi, tiến độ, phụ thuộc.
- Tech Lead: thống nhất kiến trúc LangGraph + Rust.
- Clinical Lead: phê duyệt rule safety và chính sách escalation.
- Security/Compliance Lead: kiểm soát dữ liệu và tuân thủ Nghị định 13/2023/NĐ-CP.

## 7. Nguyên tắc go/no-go

- Không qua phase nếu chưa đạt gate kỹ thuật + gate an toàn + gate vận hành.
- Mọi thay đổi model/prompt/policy phải có benchmark trước/sau và rollback plan.
- Dashboard quản trị phải theo dõi được đầy đủ: hiệu năng, chất lượng AI, sự cố, compliance bằng chứng.
