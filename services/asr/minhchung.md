# Minh chứng kỹ thuật — Chức năng Ghi âm khám bệnh (Live Medical Transcription)

> Tài liệu chỉ thẳng vào code: mỗi kỹ thuật đều kèm `file:dòng` để kiểm chứng.
> Cập nhật: 2026-06-04. Tính năng thuộc trang Medical Scribe (`/scribe`), role `doctor`.

## Sơ đồ pipeline

```
[1] Micro ──► [2] Web Audio API (sóng âm FFT) 
        └───► [3] MediaRecorder webm/opus, chu kỳ 2.8s
                      │ HTTP multipart
                      ▼
[4] API Gateway FastAPI :8100 ── validate + auth ──► [5] ML Service :8010
                                                          │
                                                          ▼
                                   [6] ASR faster-whisper local :8090 (service này)
                                                          │
                                                          ▼
[7] Text về UI ──► [8] Debounce auto-save (1.2s) + auto-SOAP (2.2s)
```

## [1-2] Thu âm & sóng âm realtime — Web Audio API (trình duyệt)

| Kỹ thuật | Code |
|---|---|
| Xin quyền micro `getUserMedia({audio:true})` (WebRTC) | `apps/web/app/scribe/page.tsx:566` |
| `AudioContext` + `AnalyserNode`, `fftSize=128` → FFT phổ tần số | `apps/web/app/scribe/page.tsx:569-576` (fftSize: dòng 573) |
| Vẽ 32 cột sóng bằng `requestAnimationFrame` (60fps) | `apps/web/app/scribe/page.tsx:543-547` |

Lưu ý kiểm chứng: tầng này chạy 100% trong browser — sóng vẫn nhảy kể cả khi backend chết
(đây từng là nguồn nhầm lẫn "có sóng mà không có chữ").

## [3] Đóng gói audio — MediaRecorder + codec Opus

| Kỹ thuật | Code |
|---|---|
| Chọn MIME ưu tiên `audio/webm;codecs=opus` (fallback webm → mp4) | `apps/web/app/scribe/page.tsx:579-585` |
| **Xoay vòng recorder** (segment cycling): mỗi 2.8s `stop()` rồi tạo recorder MỚI → mỗi blob là một file webm hoàn chỉnh có header EBML | `apps/web/app/scribe/page.tsx:589-611` (interval 2800ms: dòng 605-611) |
| `recorder.start()` KHÔNG timeslice — blob duy nhất khi stop | `apps/web/app/scribe/page.tsx:600` |
| Hàng đợi chunk + upload tuần tự (mạng chậm không mất chunk) | `apps/web/app/scribe/page.tsx:268` (queue), `469-513` (processChunkQueue) |
| Dọn tài nguyên audio khi dừng (clear interval, stop tracks, close ctx) | `apps/web/app/scribe/page.tsx:326-` (teardownAudioPipeline) |

**Bài học kỹ thuật đã sửa (2026-06-04):** bản cũ dùng `recorder.start(2800)` (timeslice) —
chỉ chunk đầu có header EBML, chunk 2+ là lát cắt giữa stream nên server decode lỗi 422.
Fix = xoay vòng recorder như trên.

## [4] API Gateway — FastAPI

| Kỹ thuật | Code |
|---|---|
| Endpoint nhận multipart từ UI | `services/api/src/clara_api/api/v1/endpoints/scribe.py:254-287` |
| Client gọi từ frontend | `apps/web/lib/scribe.ts:204` |
| Giới hạn 15MB + whitelist MIME | `services/api/.../scribe.py:174-186` |
| Chuẩn hóa content-type `audio/webm;codecs=opus` → `audio/webm` | `services/api/.../scribe.py:151` (_normalize_audio_content_type) |
| Proxy sang ML kèm internal key `X-ML-Internal-Key` | `services/api/.../scribe.py:188-218` (_call_scribe_transcribe_ml) |
| Role guard chỉ bác sĩ | `require_roles("doctor")` trong cùng file |
| Nối text vào transcript phiên (append_to_session) | `services/api/.../scribe.py:274-282` |

## [5] ML Service — định tuyến đa provider (OpenAI-compatible)

| Kỹ thuật | Code |
|---|---|
| Endpoint transcribe (validate lại + đo processing_ms) | `services/ml/src/clara_ml/main.py:913-965` |
| Setting mới `DEEPSEEK_AUDIO_BASE_URL` — tách route audio khỏi chat | `services/ml/src/clara_ml/config.py:247-252` |
| Truyền audio_base_url vào client | `services/ml/src/clara_ml/main.py:112` |
| Chọn base audio (local) ↔ fallback base chat (cloud) | `services/ml/src/clara_ml/llm/deepseek_client.py:359-360`; parse: dòng 43-45 |
| URL chuẩn OpenAI `/v1/audio/transcriptions` | `services/ml/src/clara_ml/llm/deepseek_client.py:71-75` |
| Retry theo base + backoff, phân loại lỗi auth/retryable | `services/ml/src/clara_ml/llm/deepseek_client.py:334-` (transcribe_audio) |

**Lý do tồn tại của service ASR local:** key yescale nhóm `deepseek` KHÔNG có model audio
(`whisper-1` → HTTP 400 "not available in group"), đã verify bằng `GET /v1/models` (24 model,
toàn text LLM). → Audio bắt buộc self-host.

## [6] ASR engine — faster-whisper (service trong folder này)

| Kỹ thuật | Code |
|---|---|
| Adapter FastAPI, endpoint OpenAI-compatible | `services/asr/server.py:69-99` (POST /v1/audio/transcriptions) |
| Model Whisper (Transformer encoder-decoder, OpenAI, 680k giờ audio đa ngôn ngữ) qua **faster-whisper/CTranslate2** (C++, nhanh ~4× PyTorch) | `services/asr/server.py:40-52` (_get_model, lazy-load 1 lần) |
| **Lượng tử hóa int8** trên CPU (giảm 4× RAM, tăng tốc) | `services/asr/server.py:28-30` (env `WHISPER_COMPUTE=int8`) |
| **VAD filter** (Silero) cắt khoảng lặng, chống ảo giác | `services/asr/server.py:85` (`vad_filter=True`) |
| Decode webm/opus bằng PyAV (FFmpeg nhúng trong wheel, không cần cài hệ thống) | `services/asr/Dockerfile:5-6` |
| Đổi model/thiết bị qua env (`WHISPER_MODEL=small|medium|large-v3`) | `services/asr/server.py:27-30` |
| Container hóa + volume cache model HuggingFace (tải 1 lần) | `deploy/docker/docker-compose.app.yml` (service `asr`, volume `clara_asr_models`) |

**Số đo thực tế (2026-06-04, CPU WSL2):** model `small` int8 — 48-90ms cho chunk ~2-3 giây
(nhanh hơn realtime ~30×). Model 461MB tải lần đầu, cache trong volume.

## [7-8] Hậu xử lý — Debounce pattern

| Kỹ thuật | Code |
|---|---|
| Auto-save transcript 1.2s sau thay đổi cuối | `apps/web/app/scribe/page.tsx:422-425` (delayMs 1200) |
| Auto-phân tích SOAP 2.2s | `apps/web/app/scribe/page.tsx:459-464` (2200ms) |
| Lưu phiên PostgreSQL bảng `scribe_sessions` | `services/api/src/clara_api/db/models.py` (ScribeSession) |

## Luận điểm khi thuyết trình

1. **Privacy-first**: giọng bệnh nhân không rời máy — Whisper self-host, audio không lên cloud
   (chỉ text đi tiếp). Quan trọng với dữ liệu y tế VN.
2. **Chi phí 0 đồng**: ASR cloud ~$0.006/phút; local miễn phí, scale bằng phần cứng.
3. **Latency thấp**: chunk 2.8s + xử lý <100ms → trải nghiệm "live caption" khi khám.
4. **Provider-agnostic**: giao tiếp chuẩn OpenAI API — đổi sang OpenAI/Azure thật chỉ cần đổi
   1 biến env `DEEPSEEK_AUDIO_BASE_URL`, không sửa code.
5. **Chịu lỗi**: queue chunk tuần tự; ASR chết chỉ mất transcribe — ghi chú tay + SOAP vẫn chạy.

## Trạng thái & giới hạn trung thực

- ✅ Toàn pipeline ghi âm → text hoạt động end-to-end (đã test).
- ⚠️ Tầng transcript → SOAP hiện vẫn là rule-based tiếng Anh
  (`services/ml/src/clara_ml/agents/scribe_soap.py` — regex sinh hiệu + keyword), chưa phải LLM.
  Nói tiếng Việt → transcript đúng nhưng SOAP nghèo. Kế hoạch: thay bằng DeepSeek
  (tái dùng pattern `services/ml/src/clara_ml/agents/council_intake.py` đã chạy tốt).
- ⚠️ Chất lượng tiếng Việt của model `small` ở mức khá; cần hơn thì `WHISPER_MODEL=medium`.
