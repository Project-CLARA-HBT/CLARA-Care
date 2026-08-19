# GLHS v7 Development Partition Clean Run

- **Run ID**: `glhs-v7-development-clean-20260820`
- **Git SHA**: `1dc4d8100853cd7528a74d70b3be5f26d5403acb`
- **Split**: `development` (192 subjects, 1,056 cases with adversarial variants)
- **Grid**: 1,056 cases × 9 conditions × 2 models = **19,008 total cells**
- **Execution Mode**: `glhs_bench_router`
- **Execution Order**: Gemini first (`gemini-3.6-flash-high`), Claude second (`claude-sonnet-4.6`)
- **Retry Backoff**: 1.5s exponential backoff

## Status & Metrics Summary

- **Total Solver Cells Attempted**: 19,008 / 19,008 (100% complete)
- **Successful Outputs**: 18,908
- **Terminal Solver Format Errors**: 100 (retained fail-closed in error ledger, no retry inflation)
- **Overall All-Axes Exact Match Accuracy**: **78.87%** (14,992 / 19,008)

### By Model & Condition Breakdown

#### Gemini 3.6 Flash High (9,504 / 9,504 complete)
- `full_authorized_history`: 100.0% (1,056 / 1,056)
- `long_context_chronological`: 100.0% (1,056 / 1,056)
- `naive_rag`: 100.0% (1,056 / 1,056)
- `lww`: 97.73% (1,032 / 1,056)
- `btsa`: 100.0% (1,056 / 1,056)
- `glhs_no_predicate_engine`: 100.0% (1,056 / 1,056)
- `glhs_no_bitemporal_knowledge_time`: 100.0% (1,056 / 1,056)
- `glhs_hybrid`: 100.0% (1,056 / 1,056)
- `glhs_hybrid_thss_strict`: 100.0% (1,056 / 1,056)

#### Claude Sonnet 4.6 (9,404 outputs + 100 format errors)
- `btsa`: 89.30% (943 / 1,056)
- `glhs_no_predicate_engine`: 67.61% (714 / 1,056)
- `glhs_no_bitemporal_knowledge_time`: 60.51% (639 / 1,056)
- `lww`: 59.19% (625 / 1,056)
- `full_authorized_history`: 53.60% (566 / 1,056)
- `glhs_hybrid`: 51.89% (548 / 1,056)
- `long_context_chronological`: 49.15% (519 / 1,056)
- `glhs_hybrid_thss_strict`: 45.36% (479 / 1,056)
- `naive_rag`: 45.36% (479 / 1,056)

All artifacts are persisted and verified with checksums.
