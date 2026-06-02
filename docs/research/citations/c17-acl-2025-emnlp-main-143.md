# Citation 17: MedHallu: A Comprehensive Benchmark for Detecting Medical Hallucinations in Large Language Models

## Định danh
- ACL Anthology ID: 2025.emnlp-main.143 | DOI: 10.18653/v1/2025.emnlp-main.143
- Nguồn: https://aclanthology.org/2025.emnlp-main.143/
- Loại nguồn: `acl`
- Ngày xác minh metadata: 2026-04-10

## Trích dẫn chuẩn (tham khảo kỹ thuật)
Pandit, Shrey, Xu, Jiawei, Hong, Junyuan, Wang, Zhangyang, Chen, Tianlong, Xu, Kaidi, Ding, Ying. MedHallu: A Comprehensive Benchmark for Detecting Medical Hallucinations in Large Language Models. Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing. 2025. DOI: 10.18653/v1/2025.emnlp-main.143.

## Hàm ý khoa học rút ra cho CLARA
Thêm hallucination benchmark lane trong scientific eval.

## Điểm chạm mã nguồn dự kiến
- `services/ml/tests/test_research_tier2_agent.py`
- `docs/hackathon/scientific-eval-testkit-guide-2026-04-01.md`

## KPI đánh giá khi triển khai
- Hallucination rate; groundedness score.

## Ghi chú sử dụng trong báo cáo thuyết minh
- Citation này dùng để làm căn cứ khoa học cho lập luận thiết kế và tiêu chí đánh giá, không thay thế hướng dẫn lâm sàng.
- Khi trích trong báo cáo chính, ưu tiên trích theo cụm: `claim -> evidence -> source id`.
