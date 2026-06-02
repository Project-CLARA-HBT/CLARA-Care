# Deep/Deep-Beta Natural Reasoning Refactor Plan (2026-04-11)

## Goal
Improve Deep/Deep-Beta output quality so responses:
1. sound more natural (less template/filler tone),
2. expose a concrete evidence-grounded reasoning process,
3. stay clinically safe and auditable.

## Architecture Findings (Current)
- Report generation is strongly template-driven and can become rigid when long-length targets are enforced.
- Deep Beta reasoning nodes return flat lists (`insights/actions/watchouts`) without a structured claim->evidence->inference->action chain.
- Final report artifacts do not guarantee a dedicated reasoning-chain section in all degraded/fallback paths.
- Report length budget is static for `deep_beta`; sparse-evidence runs may be over-expanded and sound unnatural.

## Phase Plan

### Phase 1: Reasoning Contract Hardening
Status: `completed`

Deliverables:
- Extend deep-beta reasoning-node JSON contract with `reasoning_chain` objects.
- Parse/normalize `reasoning_chain` into stable structured telemetry.
- Feed reasoning-chain context into downstream verification and follow-up query collection.

Acceptance criteria:
- Each reasoning node can emit structured claim-level reasoning cards.
- Parser degrades safely when the field is missing/invalid.

### Phase 2: Synthesis Naturalness + Adaptive Budget
Status: `completed`

Deliverables:
- Add adaptive deep-beta word budget resolver based on evidence density.
- Strengthen synthesis prompt contract for natural transitions and explicit claim->evidence->inference->action writing.
- Include reasoning-chain cards in synthesis and expansion prompts.

Acceptance criteria:
- Deep-beta runs with sparse evidence no longer force maximum dossier-style expansion.
- Final synthesis prompt receives explicit structured reasoning cards.

### Phase 3: Artifact Enforcement + Regression Tests
Status: `completed`

Deliverables:
- Ensure deep/deep-beta output always includes `## Chuỗi lập luận bằng chứng` in artifact fallback path.
- Extend tests for reasoning-chain extraction and adaptive word-budget behavior.
- Re-run targeted deep/deep-beta regressions.

Acceptance criteria:
- Missing reasoning-chain section is auto-injected.
- New and touched tests pass.

## Execution Log
Implemented in:
- `services/ml/src/clara_ml/agents/research_tier2.py`
  - Added structured `reasoning_chain` support in deep-beta reasoning nodes.
  - Added `_build_reasoning_chain_cards(...)` and `_resolve_adaptive_report_word_budget(...)`.
  - Updated report section contracts to include `## Chuỗi lập luận bằng chứng`.
  - Enhanced long-report synthesis prompt with explicit naturalness + reasoning-chain constraints.
  - Ensured report artifact fallback injects reasoning-chain section/table.
  - Propagated reasoning-chain richness into digest/evidence-verification context.
- `services/ml/tests/test_research_tier2_agent.py`
  - Added tests for reasoning-chain artifact injection.
  - Added tests for reasoning-node JSON parsing of `reasoning_chain`.
  - Added tests for adaptive deep-beta report budget reduction on sparse evidence.

Validation executed:
- `python3 -m compileall -q services/ml/src/clara_ml/agents/research_tier2.py services/ml/tests/test_research_tier2_agent.py`
  - Result: pass
- `cd services/ml && PYTHONPATH=src /tmp/clara-ml-venv/bin/pytest -q tests/test_research_tier2_agent.py -k "ensure_deep_beta_report_artifacts or sanitize_user_facing_answer_markdown or resolve_report_word_budget or run_deep_beta_llm_reasoning_node_extracts_reasoning_chain or resolve_adaptive_report_word_budget"`
  - Result: pass (`8 passed`)
- `cd services/ml && PYTHONPATH=src /tmp/clara-ml-venv/bin/pytest -q tests/test_research_tier2_agent.py -k "run_research_tier2_deep_beta_emits_beta_stages_and_metadata or run_research_tier2_deep_mode_does_not_emit_beta_stages"`
  - Result: pass (`2 passed`)
