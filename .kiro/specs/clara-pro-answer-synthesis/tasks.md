# Implementation Plan: CLARA Pro Answer Synthesis

## Overview

Implement scope-aware length, reliable convergence, and de-templated prose for
`deep_beta` synthesis — additively and behind `SYNTHESIS_V2_ENABLED` (default
off). Every task is independently verifiable with `make lint type-check test`
and preserves existing guardrails and the `deep` vs `deep_beta` distinction.

### Testing prerequisites (set up once, in task 1.1)
- Reuse `services/ml/tests` (pytest + hypothesis).
- Add a `synthesis_v2` test package; tag property tests `P1..P10` to the design's Correctness Properties.
- A flags-off baseline fixture asserts budget/contract/expansion equal pre-feature behavior.

## Tasks

- [x] 1. Config + flag foundations
  - [x] 1.1 Add `SYNTHESIS_V2_ENABLED` (false) and `DEEP_BETA_REPORT_MAX_WORDS_CAP` (15000) to `config.py`; raise `DEEP_BETA_REPORT_MIN_WORDS` default to 8000 with validated bounds. Test harness package.
  - [x] 1.2 Add config-bounds validation so `min <= target <= max <= 15000` cannot be violated. Property P1.

- [x] 2. Scope classifier
  - [x] 2.1 `_classify_query_scope(...) -> ScopeSignal` reusing `_is_comparison_query`/`_is_nutrition_diet_query`/`_is_ddi_critical_topic` + intent cues; pure, no PII. Properties P2.
  - [x] 2.2 Unit tests for scope labels + `scope_factor` ranges.

- [x] 3. Scope-aware budget
  - [x] 3.1 Flag-gated rewrite of `_resolve_deep_beta_word_budget` / `_resolve_adaptive_report_word_budget` with the new band math; legacy path when flag off. Properties P1–P5, P8.
  - [x] 3.2 Trace the resolved `(min,target,max)` + scope label (no PII). Requirement 1.6.

- [x] 4. Query-type section planning
  - [x] 4.1 Flag-gated extension of `_resolve_report_section_contract` to choose plan by scope/type; keep exec-answer-first + decision-boundary + safety. Requirement 3.1, 3.6.
  - [x] 4.2 Style-profile variation + anti-repetition directives in `_resolve_report_style_profile`/prompt. Requirement 3.2.

- [x] 5. Robust convergence loop
  - [x] 5.1 Rewrite expansion in `_synthesize_deep_beta_long_report`: directive rotation on empty/duplicate, wall-clock + round bounds, best-so-far on timeout. Properties P6, P7.
  - [x] 5.2 Stub-LLM tests (empty/duplicate/timeouts) asserting rotation, not early break.

- [x] 6. Substantive enrichment
  - [x] 6.1 Rework `_ensure_min_deep_beta_report` to request a targeted evidence-grounded section before the appendix fallback. Requirement 2.3, P5.

- [x] 7. Tag hygiene + word-count unification
  - [x] 7.1 Single markdown-aware `_markdown_word_count` used in budget/expansion/enforcement. Property P7.
  - [x] 7.2 Strengthen internal-tag stripping in `_sanitize_user_facing_answer_markdown`. Requirement 3.3, P9.

- [x] 8. Guardrail + flags-off regression
  - [x] 8.1 Reuse `services/ml/tests/safety`; assert no prescribe/diagnose, emergency fast-path intact, FIDES CRITICAL preserved at long length. Property P9.
  - [x] 8.2 Flags-off equivalence suite. Property P8. `deep` distinct from `deep_beta`. Property P10.

- [-] 9. Final checkpoint — full suite green; runbook for staged enablement (enable in staging, sample 8k–15k outputs, then production).

## Notes

### Property → implementing test task
- P1 → 1.2/3.1 · P2 → 2.1 · P3 → 3.1 · P4 → 3.1 · P5 → 3.1/6.1 · P6 → 5.1 · P7 → 7.1 · P8 → 8.2 · P9 → 7.2/8.1 · P10 → 8.2

### Subagent assignment guidance
- Budget + scope (tasks 1–3) — one writer.
- Section/style/prompt (task 4) — disjoint writer.
- Expansion/enrichment/sanitize (tasks 5–7) — disjoint writer (same file `research_tier2.py`, so serialize 4–7 to avoid write conflicts).
