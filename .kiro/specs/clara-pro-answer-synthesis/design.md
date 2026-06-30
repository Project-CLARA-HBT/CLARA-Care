# Design Document

## Overview

This design fixes CLARA Pro (`deep_beta`) answer synthesis so length scales with
query scope and evidence (reliably reaching the 8,000–15,000 word band for
full-scope queries), and so the prose reads like an expert clinical brief rather
than a filled template. It is **additive and feature-flagged** under
`SYNTHESIS_V2_ENABLED` (default off ⇒ current behavior preserved). All work is in
`services/ml/src/clara_ml/agents/research_tier2.py` and `config.py`; no router,
retrieval, or guardrail change.

### Root causes (from the current code)

| Symptom | Current cause | Fix |
|---|---|---|
| Length too short / below 8k | `_resolve_deep_beta_word_budget` clamps target via `target_ceiling = min(hard_max-900, max(min+700, min*2.0))`; with `min_words` floored at 1200 hard-min and config 7000, the realized band is ~`(7000, 9520, 10920)` and never approaches 15k | Replace ceiling math with a scope-aware band that can reach 15k |
| Length unreliable | Expansion loop `break`s immediately when a round returns empty/duplicate content | Multi-strategy expansion with fallback directives before giving up |
| Padded short reports | `_ensure_min_deep_beta_report` appends an auto "Phụ lục/log table" to hit min chars | Enrich with substantive evidence-grounded sections first; appendix only as last resort |
| Template feel | `_resolve_report_section_contract` returns one fixed dossier heading set; identical prompt every time | Query-type-aware section planning + anti-repetition directives |
| Inconsistent counts | char-based `min_chars` vs word-based target | Single markdown-aware word counter everywhere |

### Feature flag

```
SYNTHESIS_V2_ENABLED=false   # gate the scope-aware budget + de-templating + robust expansion
```

When off, `_resolve_report_word_budget`, the section contract, and the expansion
loop behave exactly as today (Requirement 6.1, 6.2).

## Architecture

```mermaid
graph TD
    IN[deep_beta synthesis entry] --> FLAG{SYNTHESIS_V2_ENABLED?}
    FLAG -- off --> OLD[Legacy budget + fixed contract + simple expansion]
    FLAG -- on --> SCOPE[Scope classifier<br/>broad / comparative / multi-part / narrow]
    SCOPE --> BUD[Scope-aware budget<br/>min..target..max within 8k-15k band]
    BUD --> PLAN[Query-type section plan]
    PLAN --> GEN[Initial synthesis pass]
    GEN --> CONV[Convergence loop]
    CONV --> CHK{words >= target?}
    CHK -- yes --> SAN[sanitize + guardrails]
    CHK -- no --> STRAT[Next expansion strategy<br/>rotate section directive]
    STRAT --> TIME{round/timeout budget left?}
    TIME -- yes --> CONV
    TIME -- no --> ENRICH[substantive enrichment<br/>then appendix last resort]
    ENRICH --> SAN
    SAN --> OUT[final report + trace(min,target,max,scope)]
```

## Components and Interfaces

### A. Scope classifier — `_classify_query_scope(topic, citation_count, deep_pass_count, reasoning_node_count) -> ScopeSignal` (Req 1.1)

Reuses existing heuristics already in the file (`_is_comparison_query`,
`_is_nutrition_diet_query`, `_is_ddi_critical_topic`) plus token/intent cues to
emit `scope ∈ {narrow, standard, broad, comparative_multi}` and a numeric
`scope_factor ∈ [0.4, 1.0]`. Pure function, unit-testable, no PII.

### B. Scope-aware budget — replace `_resolve_deep_beta_word_budget` (Req 1.2–1.5)

New band math (flag-on):

```
floor       = clamp(config.deep_beta_report_min_words, 4000, 12000)   # default raise to 8000
hard_max    = clamp(config.deep_beta_report_max_words_cap, floor+2000, 15000)  # new cap, default 15000
density     = citations + passes + reasoning_nodes
density_factor = smoothstep(density, lo=10, hi=60) -> [0,1]
combined    = max(scope_factor, density_factor*0.9)
target      = round(floor + combined * (hard_max - floor))
min_words   = floor if scope in {broad, comparative_multi} else round(floor*0.7)
max_words   = hard_max
assert min_words <= target <= max_words <= 15000
```

This lets a broad, evidence-rich query reach ~13–15k while a narrow query stays
near `floor*0.7` without padding (Req 1.3). Invariant asserted (Req 1.5) and
config-validated (Req 6.5).

### C. Query-type section plan — extend `_resolve_report_section_contract` (Req 3.1)

Instead of one fixed dossier heading list, choose a plan by scope/type:
- **comparative_multi** → options-comparison framing (efficacy / safety / adherence / feasibility / cost-access + comparison table).
- **broad** → full dossier (current headings) but with type-specific sub-sections.
- **diagnostic-workup cues** → differential/red-flags framing.
- **narrow** → compact brief (fewer required sections).
All plans keep the executive-answer-first + decision-boundary + safety sections
(Req 3.6, 5).

### D. Robust convergence loop — rewrite expansion in `_synthesize_deep_beta_long_report` (Req 2)

- Track attempted expansion **directives**; on empty/duplicate output, rotate to
  the next directive (deepen subgroup analysis → add comparative table → add
  monitoring/safety matrix → add uncertainty/evidence-gap section) before
  stopping (Req 2.2).
- Hard bounds: `expansion_rounds` and a wall-clock check against
  `deep_beta_report_timeout_seconds`; return best-so-far on timeout (Req 2.4).
- Use one markdown-aware `_markdown_word_count` everywhere (Req 2.5).

### E. Substantive enrichment — rework `_ensure_min_deep_beta_report` (Req 2.3)

If still below `min_words`, request one targeted evidence-grounded section
(largest missing analytic dimension) rather than only emitting the auto-appendix
log table; the log/appendix becomes a final fallback only when LLM enrichment is
unavailable.

### F. Anti-repetition + tag hygiene (Req 3.2, 3.3)

Add a light post-pass that flags repeated paragraph openings (reuse existing
sanitizers `_sanitize_user_facing_answer_markdown`, `_dedupe_duplicate_h2_headings`)
and strengthen the existing internal-tag stripping so planner/debug labels never
appear (already partially done via `_strip_html_from_mermaid_blocks` and the
continuation-prompt "do NOT add internal pipeline labels" line).

## Data Models / Config

New/updated settings in `config.py` (all bounded, validated — Req 6.3, 6.5):

| setting | default | bounds | note |
|---|---|---|---|
| `SYNTHESIS_V2_ENABLED` | false | bool | master flag |
| `DEEP_BETA_REPORT_MIN_WORDS` | **8000** (raise from 7000) | 4000–12000 | floor |
| `DEEP_BETA_REPORT_MAX_WORDS_CAP` | 15000 (new) | floor+2000–15000 | ceiling |
| `DEEP_BETA_REPORT_EXPANSION_ROUNDS` | 4 | 0–10 | unchanged |
| `DEEP_BETA_REPORT_TIMEOUT_SECONDS` | 90 | 10–600 | now also wall-clock bound for loop |

No DB/schema change.

## Correctness Properties

1. **Budget invariant**: for all inputs/config, `min_words <= target <= max_words <= 15000`.
2. **Scope monotonicity**: broader scope ⇒ `target` non-decreasing, all else equal.
3. **Density monotonicity**: more evidence ⇒ `target` non-decreasing, all else equal.
4. **Broad-query band**: a broad+high-density `deep_beta` query yields `target >= 8000`.
5. **No-pad floor**: a narrow+sparse query yields `target < floor` and is not appendix-padded.
6. **Convergence**: expansion stops only on target-met OR round/timeout exhaustion, never on first empty round while strategies remain.
7. **Word-count consistency**: the same counter is used in budget, expansion, and enforcement.
8. **Flags-off equivalence**: with `SYNTHESIS_V2_ENABLED=false`, resolved budget/contract/expansion equal baseline.
9. **Guardrail preservation**: output never prescribes/diagnoses; emergency fast-path unaffected; no internal tags in body.
10. **deep ≠ deep_beta**: `deep` mode budget stays the dense-briefing band.

## Error Handling

- Missing API key / client → return baseline answer (current behavior).
- LLM error mid-expansion → keep best-so-far, log no-PII telemetry, never raise to user.
- Config out of bounds → clamp + log; invariant still holds.

## Testing Strategy

- **Property tests** (hypothesis) for properties 1–10, in `services/ml/tests`.
- **Budget unit tests** asserting band reaches 8k–15k for broad/dense, scales down for narrow.
- **Expansion loop tests** with a stub LLM returning empty/duplicate to assert strategy rotation, not early break.
- **Flags-off regression** asserting baseline equivalence.
- **Guardrail tests** reusing existing safety suites under `services/ml/tests/safety`.

## Backward-Compatibility, Guardrail & Privacy Strategy

Ships dark behind `SYNTHESIS_V2_ENABLED`. Every existing guardrail and the
`deep` vs `deep_beta` distinction are preserved and re-asserted by tests. No PII
enters telemetry; only counts, the scope label, and the `(min,target,max)`
triple are traced.
