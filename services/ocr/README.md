# CLARA OCR Adapter (Google Cloud Vision)

Service mỏng làm cầu nối giữa **CLARA careguard bridge** (`_scan_with_tgc_ocr`) và
**Google Cloud Vision API** để quét ảnh toa thuốc → text.

CLARA không tự chạy OCR — nó POST ảnh tới một service ngoài trả JSON có key `text`/`lines`.
Adapter này nhận ảnh (multipart hoặc JSON base64) tại `POST /ocr`, gọi Vision
`DOCUMENT_TEXT_DETECTION`, rồi trả đúng shape CLARA đọc được.

> **Nhẹ:** OCR tính toán nằm trên cloud Google → adapter không có model, không cần GPU.
> Chỉ cần Python + 1 API key.

## 1. Yêu cầu

- Google Cloud project **đã bật billing** + **Cloud Vision API enabled**.
- 1 **API key** restrict cho Cloud Vision API.
- Python 3.11+ với `fastapi`, `uvicorn`, `httpx`, `python-multipart`
  (đã có sẵn trong venv của ML service: `services/ml/.venv`).

### Tạo API key bằng gcloud (không cần bấm console)

```bash
PROJ=<project-id-có-billing>          # vd: project-d139b539-6df5-4ff1-904
gcloud services enable vision.googleapis.com --project=$PROJ
gcloud services api-keys create \
  --project=$PROJ \
  --display-name="clara-ocr-vision" \
  --api-target=service=vision.googleapis.com \
  --format="value(response.keyString)"
# → in ra key dạng AIzaSy...  (lưu vào .env, KHÔNG commit)
```

> ⚠️ Phải tạo key trên project bạn **là owner và có billing**. Tạo trên project
> không có billing → Vision trả HTTP 403 "requires billing to be enabled".

## 2. Cấu hình `.env` (ở repo root, đã gitignored)

```bash
# Trỏ CLARA bridge vào adapter này
TGC_OCR_BASE_URL=http://localhost:8080      # native local
# (chạy trong docker thì dùng http://host.docker.internal:8080)
TGC_OCR_ENDPOINTS=/ocr,/api/ocr,/api/extract

# Key Vision (KHÔNG commit)
GCP_VISION_API_KEY=AIzaSy...
```

Biến tùy chọn của adapter (có default, không bắt buộc):

| Biến | Default | Ý nghĩa |
|---|---|---|
| `GCP_VISION_API_KEY` | *(bắt buộc)* | API key Vision |
| `GCP_VISION_ENDPOINT` | `https://vision.googleapis.com/v1/images:annotate` | endpoint Vision |
| `OCR_LANG_DEFAULT` | `vi` | languageHint mặc định |
| `GCP_VISION_TIMEOUT_SECONDS` | `30` | timeout gọi Vision |

## 3. Chạy adapter

Từ **repo root** (`/home/lehuuhoang/CLARA-Care`):

```bash
set -a; . ./.env; set +a        # nạp GCP_VISION_API_KEY vào môi trường
services/ml/.venv/bin/uvicorn server:app \
  --app-dir services/ocr --host 0.0.0.0 --port 8080
```

> Chạy bền (terminal riêng) thì bỏ vào tmux/screen, hoặc dùng systemd/pm2 tùy ý.

## 4. Kiểm tra

```bash
# health
curl -sS http://127.0.0.1:8080/health
# → {"status":"ok","service":"clara-ocr-vision","key_configured":true}

# OCR trực tiếp (JSON base64)
B64=$(base64 -w0 đường-dẫn-ảnh-toa.png)
curl -sS -X POST http://127.0.0.1:8080/ocr \
  -H "Content-Type: application/json" \
  -d "{\"image\":\"$B64\",\"lang\":\"vi\"}"

# OCR qua multipart (cách CLARA bridge thử trước)
curl -sS -X POST http://127.0.0.1:8080/ocr -F "file=@đường-dẫn-ảnh-toa.png"
```

### Xuyên qua CLARA (end-to-end)

Sau khi sửa `.env`, **touch để API reload** rồi test:

```bash
touch services/api/src/clara_api/main.py     # API đọc lại TGC_OCR_* từ .env
sleep 8
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<email>","password":"<pass>","role":"normal"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -sS -X POST http://127.0.0.1:8000/api/v1/careguard/cabinet/scan-file \
  -H "Authorization: Bearer $TOKEN" -F "file=@ảnh-toa.png"
# → {"detections":[{"drug_name":"Paracetamol","normalized_name":"paracetamol",...}]}
```

Hoặc test trên UI: **Self-MED → Thêm thuốc → Upload ảnh toa** (hoặc CareGuard → Phân tích ảnh).

## 5. Endpoints

| Method | Path | Body | Trả về |
|---|---|---|---|
| GET | `/health` | — | `{status, service, key_configured}` |
| POST | `/ocr` | multipart (field bất kỳ) **hoặc** JSON `{"image"\|"image_base64"\|"content"\|"base64"\|"file": "<b64>", "lang": "vi"}` | `{text, lines, items, ocr_provider}` |

## 6. Lỗi thường gặp

| Triệu chứng | Nguyên nhân / xử lý |
|---|---|
| `500 Chưa cấu hình GCP_VISION_API_KEY` | Chưa `set -a; . ./.env` trước khi chạy uvicorn |
| `502 Vision HTTP 403 ... requires billing` | Key thuộc project chưa bật billing → tạo key trên project có billing |
| `502 Vision HTTP 400 API key not valid` | Key sai / chưa enable Vision API trên project đó |
| CLARA scan-file vẫn 502 | API chưa reload `.env` → `touch services/api/src/clara_api/main.py`; hoặc `TGC_OCR_BASE_URL` chưa trỏ đúng `localhost:8080` |
| Scan đọc đúng text nhưng liều sai | Bug heuristic trích liều của CLARA (`_detect_drugs_from_text`), KHÔNG phải lỗi OCR — Vision trả text đúng |

## 7. Deploy lên server (tham khảo)

Server `36.50.26.18` đã có sẵn engine OCR riêng:
- `tgctranshub-api` (Rust, :8080) — gọi Vision qua `GCP_VISION_API_KEY` trong
  `/opt/tgc-transhub/services/api/.env`. Đổi sang key của bạn (project có billing) là sống lại.
- `tgc-tess-ocr` (Tesseract `vie+eng`, 127.0.0.1:8002) — **free, offline**, chạy tốt.
  Trỏ CLARA `.env` server vào `:8002` với `/ocr` nếu không muốn dùng Vision.

Hai cách trên server (chọn 1):
1. **Vision:** sửa `GCP_VISION_API_KEY` trong `/opt/tgc-transhub/services/api/.env` → restart gateway.
2. **Tesseract free:** `TGC_OCR_BASE_URL=http://host.docker.internal:8002`, `TGC_OCR_ENDPOINTS=/ocr`.

> Ảnh toa là dữ liệu y tế — dùng Vision (gửi lên Google) nên ghi rõ trong consent y tế cho production.
