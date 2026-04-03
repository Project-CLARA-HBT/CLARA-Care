# Council Neural Network Plan + Execution (2026-04-03)

## Mục tiêu
- Bổ sung tầng neural network cho luồng hội chẩn CLARA theo hướng **decision support**.
- Không thay thế rule-engine hiện tại; chạy shadow trước để giảm rủi ro lâm sàng.

## Phạm vi đã triển khai trong đợt này
- Thêm neural scorer sidecar tại `services/ml/src/clara_ml/agents/council_neural.py`.
- Tích hợp vào council response dưới key `neural_risk` trong `services/ml/src/clara_ml/agents/council.py`.
- Thêm config flags trong `services/ml/src/clara_ml/config.py`:
  - `COUNCIL_NEURAL_ENABLED`
  - `COUNCIL_NEURAL_SHADOW_MODE`
  - `COUNCIL_NEURAL_MEDIUM_THRESHOLD`
  - `COUNCIL_NEURAL_HIGH_THRESHOLD`
- Bổ sung test schema neural trong `services/ml/tests/test_main_api.py`.

## Contract output `neural_risk`
```json
{
  "enabled": true,
  "shadow_mode": true,
  "model_version": "council-neural-shadow-v1",
  "risk_probability": 0.67,
  "risk_band": "medium",
  "recommended_triage": "same_day_review",
  "feature_map": {
    "red_flag_rate": 0.33,
    "conflict_rate": 0.5
  },
  "top_contributors": [
    {"feature": "red_flag_rate", "impact": 0.21, "direction": "increase_risk"}
  ]
}
```

## Roadmap tiếp theo

## Phase N1 - Data & Calibration
- Thu thập dataset hội chẩn nội bộ có label triage chuẩn hóa.
- Hiệu chỉnh thresholds theo confusion matrix thực tế.
- Thêm calibration report theo từng chuyên khoa.

## Phase N2 - Hybrid Decisioning
- Áp dụng ensemble rule + neural score cho ranking triage.
- Thêm hard constraints để không bỏ sót red-flag rule.
- Ghi audit trail đầy đủ khi neural và rule mâu thuẫn.

## Phase N3 - Production Quality
- Drift monitor theo tuần (distribution shift của feature_map).
- Auto regression gate trước deploy.
- Dashboard admin theo dõi:
  - risk_band distribution
  - false negative candidates
  - override frequency

## Guardrails bắt buộc
- Neural output chỉ là recommendation, không tự phát sinh kê đơn/chẩn đoán.
- Hard legal guard luôn chạy độc lập trước pipeline hội chẩn mở rộng.
- Khi thiếu dữ liệu hoặc confidence thấp, hệ thống ưu tiên escalation/human handoff.
