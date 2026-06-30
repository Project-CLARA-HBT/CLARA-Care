# Requirements Document

## Introduction

This feature overhauls **final answer synthesis for CLARA Pro** (the `deep_beta`
research mode, and to a lesser extent `deep`), which today produces answers that
feel **templated/robotic** and whose **length is unreliable** — sometimes too
short, sometimes padded — instead of scaling smoothly with the scope of the
question. Operators expect a Pro answer to land in the **8,000–15,000 word**
band for a full-scope query, scaling down gracefully for narrow questions, while
reading like a senior clinician's evidence brief rather than a filled-in
template.

The work targets the synthesis path in
`services/ml/src/clara_ml/agents/research_tier2.py` — specifically the word-budget
resolver (`_resolve_deep_beta_word_budget`, `_resolve_adaptive_report_word_budget`),
the section contract (`_resolve_report_section_contract`), the style profile
(`_resolve_report_style_profile`), the long-report synthesizer
(`_synthesize_deep_beta_long_report`) and its expansion loop, and the
minimum-report enforcement (`_ensure_min_deep_beta_report`). It also touches the
related config defaults in `services/ml/src/clara_ml/config.py`.

It is **additive and feature-flagged**: new synthesis behavior is gated and the
flag default preserves current behavior, so it ships dark and is enabled per
environment. Every existing safety guardrail is preserved: no prescribing, no
diagnosis, FIDES CRITICAL blocking, mandatory clinician-review directive,
emergency fast-path, and no exposure of internal pipeline/debug tags in the
answer body. Output stays Vietnamese-first with bilingual handling per the
existing `answer_language` resolution.

## Glossary

- **CLARA Pro**: The `deep_beta` research tier — the longest, most rigorous synthesis mode, surfaced in Chat as deep/deep-beta.
- **Synthesis**: The final stage that rewrites the baseline retrieved/answered content into the polished long-form report.
- **Word budget**: The `(min_words, target_words, max_words)` envelope that bounds report length.
- **Adaptive budget**: A word budget that scales with evidence density (citations + retrieval passes + reasoning nodes) and query scope.
- **Section contract**: The ordered set of required H2 sections the synthesized report must contain.
- **Expansion loop**: The iterative append-only generation that grows a report toward its target length.
- **Evidence density**: A proxy for how much material the pipeline gathered; higher density justifies a longer answer.
- **Query scope**: How broad/comparative/multi-part a question is; broad scope justifies a longer answer.
- **Template feel / robotic**: Answers that read as mechanically filled section headers with repetitive sentence openings and filler.
- **Synthesis_System**: The ML synthesis path under `research_tier2.py` plus its config.
- **Feature flag**: A configuration switch enabling new synthesis behavior while defaulting to current behavior.

## Requirements

### Requirement 1: Scope-Aware Length Targeting

**User Story:** As a clinician using CLARA Pro, I want the answer length to match the scope of my question, so that broad questions get full coverage and narrow questions are not padded.

#### Acceptance Criteria

1. THE Synthesis_System SHALL compute a length target from both evidence density and an explicit query-scope signal, not from a fixed page count alone.
2. WHERE a `deep_beta` query is full-scope (broad, comparative, or multi-part) AND evidence density is high, THE Synthesis_System SHALL target a report in the 8,000–15,000 word band.
3. WHERE a `deep_beta` query is narrow or evidence is sparse, THE Synthesis_System SHALL scale the target down to a coherent length without padding, with a documented floor.
4. THE Synthesis_System SHALL never set `min_words` below the configured floor for `deep_beta`, and SHALL never set `max_words` above 15,000 unless explicitly configured higher.
5. THE Synthesis_System SHALL keep `min_words <= target_words <= max_words` as an invariant for every resolved budget.
6. THE Synthesis_System SHALL expose the resolved `(min, target, max)` and the scope signal in trace/telemetry (no PII) for observability.

### Requirement 2: Reliable Length Convergence

**User Story:** As an operator, I want Pro answers to reliably reach their target length, so that users do not receive truncated or thin reports.

#### Acceptance Criteria

1. WHEN the first synthesis pass is below `target_words`, THE Synthesis_System SHALL run expansion rounds until the target is met or a bounded round/timeout limit is reached.
2. WHEN an expansion round returns empty or duplicate content, THE Synthesis_System SHALL attempt a different expansion strategy (e.g. a different section directive) before giving up, rather than breaking immediately.
3. WHERE the report remains below `min_words` after expansion, THE Synthesis_System SHALL enrich it with substantive, evidence-grounded content rather than only appending an auto-generated appendix/log table.
4. THE Synthesis_System SHALL bound total synthesis time by the configured report timeout and SHALL return the best available report if the timeout is hit.
5. THE Synthesis_System SHALL count words consistently (markdown-aware) across budgeting, expansion, and enforcement.

### Requirement 3: De-Templating and Natural Clinical Prose

**User Story:** As a reader, I want the report to read like an expert wrote it, so that it is engaging and trustworthy rather than a mechanical template.

#### Acceptance Criteria

1. THE Synthesis_System SHALL vary section structure based on query type (e.g. comparison vs single-intervention vs diagnostic-workup framing) rather than always emitting an identical fixed heading set.
2. THE Synthesis_System SHALL avoid repeated identical sentence openings across adjacent paragraphs.
3. THE Synthesis_System SHALL not expose internal pipeline tags, planner labels, execution steps, or debug telemetry in the answer body.
4. THE Synthesis_System SHALL keep claim-to-evidence linkage explicit, including contradictory evidence and how it changes confidence.
5. THE Synthesis_System SHALL include comparative and risk/monitoring tables when clinically relevant to the query.
6. THE Synthesis_System SHALL preserve a direct executive answer and explicit decision boundary before background context.

### Requirement 4: Evidence-Proportional Depth

**User Story:** As a clinician, I want depth to track the evidence actually retrieved, so that the report neither overclaims on thin evidence nor underuses rich evidence.

#### Acceptance Criteria

1. THE Synthesis_System SHALL increase target depth as citation count, retrieval-pass count, and reasoning-node count increase.
2. WHERE evidence is sparse, THE Synthesis_System SHALL explicitly state evidence limitations instead of padding length.
3. THE Synthesis_System SHALL ground each major claim in retrieved evidence and SHALL not fabricate citations to reach a length target.

### Requirement 5: Safety and Guardrail Preservation

**User Story:** As a safety owner, I want synthesis changes to preserve every clinical guardrail, so that longer answers are not less safe.

#### Acceptance Criteria

1. THE Synthesis_System SHALL not prescribe dosage or provide definitive diagnosis regardless of length.
2. THE Synthesis_System SHALL preserve FIDES CRITICAL-claim blocking and the mandatory clinician-review directive.
3. THE Synthesis_System SHALL preserve the emergency fast-path (no long synthesis for acute-emergency queries).
4. THE Synthesis_System SHALL keep all output PII-free in telemetry and SHALL not leak internal system structure.

### Requirement 6: Configurability, Back-Compatibility, and Flags

**User Story:** As a platform operator, I want the new synthesis gated and tunable, so that I can adopt it safely and tune length per environment.

#### Acceptance Criteria

1. THE Synthesis_System SHALL gate the new length/de-templating behavior behind a feature flag whose default preserves current behavior.
2. WHERE the flag is off, THE Synthesis_System SHALL behave equivalently to the pre-feature synthesis.
3. THE Synthesis_System SHALL expose tunable settings for the `deep_beta` floor, target band, ceiling, expansion rounds, and timeout via config/env.
4. THE Synthesis_System SHALL keep `deep` mode behavior distinct from `deep_beta` (deep stays a dense briefing, not a dossier).
5. THE Synthesis_System SHALL validate config bounds so a misconfiguration cannot violate the `min <= target <= max <= 15000` invariant.
