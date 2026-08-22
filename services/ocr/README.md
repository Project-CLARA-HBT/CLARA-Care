# CLARA OCR Adapter (Multimodal Gemini Vision Bridge)

Service mỏng làm cầu nối giữa **CLARA careguard / PHR bridge** và **Router Gateway Multimodal LLM** (`gemini-3.7-flash-tiered` / `gemini-3.6-flash-high`) để nhận diện ảnh đơn thuốc, vỏ hộp thuốc, và phiếu xét nghiệm thành văn bản và thực thể dược học có cấu trúc.

## 1. Tính năng nổi bật

- Nhận diện ký tự quang học chuẩn xác tiếng Việt có dấu, đọc được cả chữ viết tay và vỏ thuốc mờ / cong.
- Trích xuất tự động danh sách hoạt chất, hàm lượng, liều dùng, tần suất và cách sử dụng.
- Tự động fallback giữa `gemini-3.7-flash-tiered` và `gemini-3.6-flash-high`.

## 2. Cấu hình

```bash
# Gateway Router configuration
ROUTER_BASE_URL=https://router.theclaracare.com/v1
ROUTER_API_KEY=[REDACTED]
OCR_MODEL=gemini-3.7-flash-tiered
OCR_FALLBACK_MODEL=gemini-3.6-flash-high
```

## 3. Endpoints

| Method | Path | Payload | Output |
|---|---|---|---|
| GET | `/health` | — | `{"status": "ok", "service": "clara-ocr-multimodal-gemini", ...}` |
| POST | `/ocr` | multipart file HOẶC JSON `{"image": "<b64>", "mime_type": "image/jpeg"}` | `{"text": "...", "lines": [...], "items": [...], "medications": [...]}` |
| POST | `/api/ocr` | alias tương thích | như trên |
| POST | `/api/extract` | alias tương thích | như trên |
