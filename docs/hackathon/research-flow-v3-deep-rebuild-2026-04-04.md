# CLARA Research Flow V3 (Deep Rebuild) — 2026-04-04

## Mục tiêu
- Tăng chiều sâu nghiên cứu cho `deep` và `deep_beta`.
- Bắt buộc long-form report có cấu trúc y khoa, chi tiết hơn, có bảng/mermaid/chart-spec.
- Tăng số vòng truy xuất + reasoning để giảm trả lời nông.

## Vấn đề của flow cũ
- Chế độ `deep` có multi-pass nhưng phần hậu xử lý báo cáo dài chỉ áp dụng cho `deep_beta`.
- Budget pass/reasoning còn bảo thủ nên câu trả lời đôi khi chưa đủ dài và chưa đào sâu phản biện.
- Một số truy vấn phức tạp chưa mở rộng đủ vòng gap-fill.

## Thay đổi chính trong V3

### 1) Tăng ngân sách truy xuất
- `deep`:
  - target pass count tăng lên: DDI=11, evidence-heavy=10, query thường=9.
  - pass cap deep tăng từ `12` -> `14`.
- `deep_beta`:
  - target pass count tăng lên: DDI=16, evidence-heavy=14, query thường=12.
  - pass cap deep_beta tăng từ `20` -> `24`.

### 2) Áp dụng long-form synthesis cho cả `deep`
- Trước đây chỉ `deep_beta` gọi LLM để rewrite ra báo cáo dài.
- Nay `deep` cũng đi qua bước long-form synthesis, giữ cấu trúc y khoa đầy đủ.

### 3) Tăng chiều sâu reasoning và report defaults
- `DEEP_BETA_REASONING_LLM_NODES`: `6 -> 8`
- `DEEP_BETA_REASONING_PARALLEL_WORKERS`: `3 -> 6`
- `DEEP_BETA_REASONING_ROUNDS`: `2 -> 3`
- `DEEP_BETA_GAP_FILL_MAX_PASSES`: `2 -> 4`
- `DEEP_BETA_GAP_FILL_MAX_QUERIES`: `8 -> 12`
- `DEEP_BETA_REPORT_MIN_WORDS`: `3600 -> 4200`
- `DEEP_BETA_REPORT_TARGET_PAGES`: `8 -> 10`
- `DEEP_BETA_REPORT_EXPANSION_ROUNDS`: `3 -> 4`

### 4) Chuẩn hóa output báo cáo dài
- Cả `deep` và `deep_beta` đều đi qua:
  - sanitize markdown/mermaid,
  - bổ sung artifact bắt buộc (table, mermaid, chart-spec) nếu thiếu.

## Kỳ vọng sau thay đổi
- Báo cáo `deep`/`deep_beta` dài hơn, có chiều sâu hơn, ít “nông” hơn.
- Timeline flow hiển thị rõ quá trình nghiên cứu dài (retrieval/reasoning/synthesis).
- Tỷ lệ thiếu artifact trình bày (table/mermaid/chart-spec) giảm rõ rệt.

## File thay đổi
- `services/ml/src/clara_ml/agents/research_tier2.py`
- `services/ml/src/clara_ml/config.py`

## Gợi ý vận hành
- Nếu ưu tiên tốc độ: giảm `DEEP_BETA_REPORT_TARGET_PAGES` xuống 8 và `DEEP_BETA_REASONING_ROUNDS` xuống 2.
- Nếu ưu tiên chiều sâu: giữ mặc định V3, và tăng timeout upstream LLM phù hợp hạ tầng.
