# Hướng dẫn triển khai bằng DeepSeek và Gemini — bản V3

## Mục tiêu

Bản V3 có **322 task** với từng ID duy nhất, chia **P00–P09** và mười luồng (phần chung + chín bài). Mỗi task là một file Markdown riêng, có đường dẫn code rõ ràng, API/hàm cần làm, cách xử lý lỗi, testcase dương/âm, chuẩn thống kê, đầu ra và điều kiện DONE.

## Dùng đúng cách

1. Download ZIP, giải nén tại thư mục riêng **ngoài** repository CLARA-Care để tránh ghi đè bản mã hiện hữu.
2. Chạy `python3 scripts/taskctl.py validate` ngay trong gói specs. Khi chưa có task nào hoàn tất, `ready --venue shared` sẽ chỉ hiển thị các task không phụ thuộc vào task khác.
3. Sao chép `AGENTS/MASTER_GOAL_DEEPSEEK.md` cho orchestrator DeepSeek. Với Gemini, dùng `AGENTS/MASTER_GOAL_GEMINI.md`.
4. Giao duy nhất 1 task cho 1 agent bằng lệnh `python3 scripts/taskctl.py prompt COMPSAC-scope`. Agent phải đọc source thực tế trước khi viết code. Nếu chưa đủ dependency, agent trả BLOCKED, không bịa API.
5. Không cho 2 agent sửa cùng `models.py`/`commit_kernel.py`/migrations. Dùng quy định lock ở `AGENTS/RESOURCE_SCHEDULING.md`.
6. Sau code, đọc diffs/logs và chỉ ghi PASS nếu có bằng chứng pytest/CI trên máy thực. `taskctl.py mark` không tự chạy code của repo và không thể chứng nhận nghiên cứu thay người.
7. Giữ 9 bộ thí nghiệm độc lập; chỉ dùng chung API, harness và công cụ phân tích, không dùng chung primary results để coi là 9 đóng góp.

## Tối ưu chi phí và tiến độ

- Ưu tiên `shared` -> `compsac` (PG16, có thể chạy offline) song song `aime` (thiết kế case, human review) và `popets` (revocation graph); giảm số tác vụ LLM trước khi xác nhận protocol.
- Dùng pilot nhỏ, 3 seed là mức dò lỗi; xác định power để quyết định sample thật. Không tự khẳng định 5 seed đủ để đạt kết quả có ý nghĩa.
- LLM/API model thiếu tiền thì ghi `BLOCKED_COST` trong unresolved, không trả kết quả mock như nghiên cứu thực.
- Để tăng khả năng được nhận, chọn baseline mạnh nhất, độc lập dữ liệu, điều kiện bác bỏ, CI thống kê và tái lập. Không đảm bảo thắng mọi baseline; không dùng ngôn ngữ tự hạ bệ bài trong bản manuscripts.

## Kiểm tra nhanh

```bash
python3 scripts/taskctl.py validate
python3 scripts/test_manifest.py
python3 scripts/taskctl.py ready --venue shared
python3 scripts/taskctl.py list --venue compsac --phase P04
python3 scripts/taskctl.py prompt COMPSAC-X07_scope_occ > compsac_scope_occ_prompt.md
```
