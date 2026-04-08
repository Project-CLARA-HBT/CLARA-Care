# Day 1 Unified Contract (30/03/2026)

## Mục tiêu
Đóng băng contract liên thông API/ML/Web cho các trường chung của Vòng 2:
- `policy_action`
- `fallback_used`
- `source_errors`
- `attributions`
- `consent_version`
- `accepted_at`
- `user_id`
- `external_ddi_enabled`

## 1) Contract metadata chung
Chuẩn thống nhất:
```json
{
  "policy_action": "allow|warn|block|escalate|null",
  "fallback_used": false,
  "source_errors": {
    "source_name": ["error_code"]
  },
  "attributions": [
    {
      "channel": "chat|careguard|research|...",
      "mode": "external_plus_local|local_only|null",
      "source_count": 0,
      "citation_count": 0,
      "sources": [
        {"id": "...", "name": "...", "category": "...", "type": "..."}
      ],
      "citations": [
        {"source": "...", "url": "..."}
      ]
    }
  ]
}
```

Quy ước tương thích ngược:
- API vẫn giữ `attribution` singular trong giai đoạn chuyển tiếp.
- `attributions` là chuẩn canonical để FE/BE/ML đồng bộ từ Day 1.

## 2) Consent schema (API/Auth)
Chuẩn response consent đã chốt:
```json
{
  "consent_type": "medical_disclaimer",
  "user_id": 123,
  "consent_version": "v1",
  "accepted_at": "2026-03-30T00:00:00Z"
}
```

`GET /api/v1/auth/consent-status` bổ sung `user_id` và giữ nguyên các trường:
- `required_version`
- `accepted`
- `accepted_version`
- `accepted_at`

## 3) Runtime flag
`external_ddi_enabled` đã là cờ runtime chuẩn:
- Control Tower (API) -> wire sang Careguard request payload -> ML
- Không cần restart service để có hiệu lực

## 4) Mapping đã đồng bộ
API:
- `services/api/src/clara_api/api/v1/endpoints/chat.py`: trả `attributions` + `attribution` (compat)
- `services/api/src/clara_api/api/v1/endpoints/careguard.py`: trả `attributions` + `attribution` (compat)
- `services/api/src/clara_api/api/v1/endpoints/auth.py`: trả `user_id` trong consent responses
- `services/api/src/clara_api/schemas.py`: bổ sung schema chuẩn unified metadata/attribution + consent `user_id`

ML:
- `services/ml/src/clara_ml/agents/careguard.py`: `fallback_used`, `source_errors`, `external_ddi_enabled`
- `services/ml/src/clara_ml/agents/research_tier2.py`: `policy_action`, `fallback_used`

Web:
- `apps/web/lib/consent.ts`: parse được `user_id` trong consent status

## 5) Kiểm tra nhanh
```bash
grep -RIn "policy_action\|fallback_used\|source_errors\|attributions\|consent_version\|accepted_at\|user_id\|external_ddi_enabled" services/api/src services/ml/src apps/web/lib
```
