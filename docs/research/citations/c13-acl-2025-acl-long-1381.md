# Citation 13: Medical Graph RAG: Evidence-based Medical Large Language Model via Graph Retrieval-Augmented Generation

## Định danh
- ACL Anthology ID: 2025.acl-long.1381 | DOI: 10.18653/v1/2025.acl-long.1381
- Nguồn: https://aclanthology.org/2025.acl-long.1381/
- Loại nguồn: `acl`
- Ngày xác minh metadata: 2026-04-10

## Trích dẫn chuẩn (tham khảo kỹ thuật)
Wu, Junde, Zhu, Jiayuan, Qi, Yunli, Chen, Jingkun, Xu, Min, Menolascina, Filippo, Jin, Yueming, Grau, Vicente. Medical Graph RAG: Evidence-based Medical Large Language Model via Graph Retrieval-Augmented Generation. Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). 2025. DOI: 10.18653/v1/2025.acl-long.1381.

## Hàm ý khoa học rút ra cho CLARA
Đẩy GraphRAG sidecar thành blocking branch trong deep_beta.

## Điểm chạm mã nguồn dự kiến
- `services/ml/src/clara_ml/rag/graphrag.py`
- `services/ml/src/clara_ml/rag/pipeline.py`

## KPI đánh giá khi triển khai
- Graph-supported claim ratio.

## Ghi chú sử dụng trong báo cáo thuyết minh
- Citation này dùng để làm căn cứ khoa học cho lập luận thiết kế và tiêu chí đánh giá, không thay thế hướng dẫn lâm sàng.
- Khi trích trong báo cáo chính, ưu tiên trích theo cụm: `claim -> evidence -> source id`.
