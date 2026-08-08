# Báo cáo thực thi GLHS Q2 — 2026-08-09

## Kết luận ngắn

Đã chạy lại Q2 theo revision `c406c813d6f53caa10f87e3189da1c622a2cd223` với
contract model arm v2 có code revision, hash runner, runtime selection, ba seed
và chặn fallback/rollback. Đây là structural conformance; **final benchmark
score vẫn không được phát hành** vì chưa có sealed independent external holdout.

Chi tiết số liệu, CSV gốc, artifact và các pending được tổng hợp tại
[`ieee-v10-all-pending-data-2026-08-09.md`](ieee-v10-all-pending-data-2026-08-09.md).

## Run cuối

| Run | Kết quả |
|---|---|
| Synthetic Q2 | 400 case, artifacts `2026-08-09-q2-frozen-c406c813-synthetic/` |
| MIMIC-IV Demo-derived | 100 case, artifacts `2026-08-09-q2-frozen-c406c813-mimic-iv-demo/` |
| MIMIC-IV-ED Demo-derived | 64 case, artifacts `2026-08-09-q2-frozen-c406c813-mimic-iv-ed-demo/` |
| Synthea STU3-derived | 15,877 case, artifacts `2026-08-09-q2-frozen-c406c813-synthea-stu3/` |
| Model arm | 360/360 completed; 249/360 structural matches; no fallback/degraded indication |

Mọi artifact ghi `git_worktree_dirty=true`; vì thế phải clean-commit rồi rerun
trước khi đưa bất kỳ bảng nào vào bản submission cuối.
