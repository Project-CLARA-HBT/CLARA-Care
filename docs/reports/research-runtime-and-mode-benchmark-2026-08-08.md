# Báo cáo runtime nghiên cứu và benchmark mode — 2026-08-08

## Phạm vi và giới hạn

Đây là kiểm tra cấp phần mềm trên môi trường production, **không phải xác thực lâm sàng**. Sáu prompt là câu hỏi giáo dục/an toàn tổng quát, không chứa tên, hồ sơ, dữ liệu định danh hay dữ liệu bệnh nhân thật. Các chỉ số kiểm tra việc hoàn thành, tuân thủ mode, citation/verification, guardrail, degraded/error và latency; chúng không đo độ đúng lâm sàng.

## Thay đổi đã triển khai

- Bỏ payload trả lời thay thế ở cả endpoint đồng bộ và background job: lỗi upstream được trả về/ghi nhận là lỗi, không tạo câu trả lời nghiên cứu tổng quát thay thế.
- Giữ quality gate fail-closed. Khi bằng chứng hoặc verifier không đạt, hệ thống phát hành abstention an toàn; metadata `fallback_used=false` vì đây không phải fallback model/research.
- Tắt model fallback/rollback tự động; production dùng một model primary cho mỗi tier.
- Bổ sung whitelist cho câu hỏi giáo dục về diagnostic testing (`diagnostic test/evaluation`, sensitivity/specificity và tương đương tiếng Việt). Kiểm tra trực tiếp: câu giáo dục trả về `None`; “Diagnose me based on my symptoms” vẫn trả về `diagnosis_request`.
- Bổ sung giới hạn backend `DEEP_RESEARCH_PASS_CAP=4`; payload không thể tự tăng ngân sách retrieval. DeepBeta giữ pass cap deployment-owned.
- Bổ sung watchdog cho ML job: 1.5 lần `ML_SERVICE_TIMEOUT_SECONDS` (production: 180 giây), sau đó job fail-closed thay vì treo 8 phút.

Commit liên quan: `a6399f26`, `b6bb882f`, `c77c62d9`, `ea760d3e`, `ab8c0a5e`, `53c11aa0`.

## Benchmark chính: 18 ca (6 prompt × 3 mode)

Artifact gốc: `artifacts/research-benchmarks/production-2026-08-08-run1.json`.

Mode | Hoàn thành | Mode fidelity | Có citation/verification | Quality-gate pass | Fallback | Latency median | Latency mean
---|---:|---:|---:|---:|---:|---:|---:
Fast | 6/6 | 6/6 | 5/6 | 0/6 | 0/6 | 24.74 s | 22.89 s
Deep | 4/6 | 4/6 | 3/6 | 0/6 | 0/6 | 159.20 s | 137.00 s
DeepBeta | 1/6 | 1/6 | 0/6 | 0/6 | 0/6 | 181.23 s | 151.37 s

Raw counts are intentionally shown; no percentage is used without its denominator. Deep and DeepBeta were queued as a bounded four-user workload, so these are observed workload latencies, not single-user SLA measurements.

### Guardrail

- Dosage request was blocked in all three modes (`legal-hard-guard-v1`), about 0.03 s in Fast and about 2.05 s in Deep/DeepBeta.
- The original emergency prompt was educational rather than a direct synthetic emergency request, so its expected label was invalid. The runner was corrected to use a synthetic immediate chest-pain/shortness-of-breath scenario before the follow-up run.
- The follow-up instrumentation must treat `policy_action=escalate` as a successful emergency guard, not just `block`; this is an outstanding benchmark-harness correction.

### Citation and verification

All completed non-guard answers were labelled `degraded` with `unsupported_claims`; none passed the evidence-release quality gate. That is the expected fail-closed behaviour, but it means no normal research answer in this sample is releasable as a supported clinical conclusion. This must be fixed by improving claim extraction/citation alignment, not by relaxing the gate.

## Follow-up run after DeepBeta budget tuning

Artifact: `artifacts/research-benchmarks/production-2026-08-08-run2-partial.json` (17 records; intentionally stopped after DeepBeta requests were blocked at job creation/polling under concurrent load). Production tuning used `DEEP_BETA_REASONING_LLM_ENABLED=false`, report timeout 45 seconds and 2,048 max tokens.

- Fast completed 6/6; observed latency 0.03–16.55 seconds after service restart.
- Deep completed 5/6 and failed 1/6 at the 180-second upstream watchdog.
- DeepBeta completed only the immediately blocked dosage case; 4 ordinary education requests each failed around 181.6 seconds.

Therefore this tuning **did not fix DeepBeta**. It demonstrates that the bottleneck is not only the optional parallel reasoning node. No claim of DeepBeta readiness is justified.

## Required next engineering work

1. Add structured failure reason from ML to the job result (currently the benchmark receives only `RuntimeError`); distinguish API watchdog, model timeout, retrieval connector delay and verifier/report stage.
2. Run DeepBeta serially with stage timings before raising its timeout. Do not increase timeout blindly; determine the stage responsible for the 180-second failure.
3. Add an explicit per-mode scheduler/concurrency limit. ML currently has one Uvicorn worker while the benchmark can enqueue four heavy jobs, causing queueing to contaminate latency.
4. Fix citation-to-claim alignment so supported claims pass the existing verifier. The correct remediation is retrieval/synthesis/claim segmentation evaluation with a labelled non-PHI test set, not a weaker quality gate.
5. Correct the benchmark emergency success predicate to accept backend `escalate`, then run a fresh, single-user final 18-case evaluation after DeepBeta is repaired.

## Reproduction

Inside the API container, with a bootstrap admin configured:

```bash
/app/.venv/bin/python /tmp/clara-research-benchmark.py
```

The runner writes JSON incrementally to `/tmp/clara-research-benchmark.json`. It sends only the six versioned benchmark prompts in `scripts/benchmark_research_modes.py`; it does not load PHR, DrugBank user data, uploaded files or patient data.
