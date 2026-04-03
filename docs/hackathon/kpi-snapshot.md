# CLARA Hackathon KPI Snapshot

Generated at (UTC): 2026-04-03T02:19:30+00:00
Round2 run_id: `day27-phase3-live-20260403-rerun`

## Core Metrics (Demo-Ready)
- Local DDI rules count: **62** pairs
- Internal DDI test set size: **50** cases
- VN Drug Dictionary alias coverage: **217** entries
- Refusal compliance pre-check: **10/10 (100.0%)**
- KPI dataset pack: **DDI / refusal / fallback / latency**

## Day 18 Gate (Phase 2)
- Gate verdict: **PASS**
- Mapping accuracy: **100.00%** (threshold >= 90%)
- Critical DDI miss reduction: **100.00%** (threshold >= 40%)
- Artifact JSON: `data/demo/day18-phase2-gate-20260402-185335.json`
- Artifact Markdown: `docs/hackathon/day18-phase2-gate.md`

## Day 24-26 (Phase 3 Runtime Hardening)
- Active-eval stage chain hardened: **baseline -> mine -> rerun -> compare**
- Added strict chain telemetry: `strict_stage_chain_ok`, `stage_failure_reasons`
- Workflow strict gate now surfaced with explicit failure reason
- Admin flow visualizer updated to reflect Active Eval scheduler + 4 stages + strict gate node

## Day 27 Live KPI + Canary
- KPI run ID: `day27-phase3-live-20260403-rerun`
- Execution mode: **live**
- Live executed: **true**
- Go/No-Go: **GO**
- KPI artifact: `artifacts/round2/day27-phase3-live-20260403-rerun/kpi-report/kpi-report.json`
- Go/No-Go artifact: `artifacts/round2/day27-phase3-live-20260403-rerun/go-no-go/go-no-go.json`

## Day 28 Final Gate
- Final verdict: **GO**
- Final gate artifact: `data/demo/day28-final-gate-20260403-021856.json`
- Final report: `docs/hackathon/day28-final-gate-report.md`
- Release tag allowed: **true**

## Notes
- Final gate selection now prefers latest **strict-pass** active-eval summary.
- Day27 GO parsing uses canonical `go: true|false` from `go-no-go.json`.
