# Runbook: CLARA Pro answer synthesis (`SYNTHESIS_V2_ENABLED`) staged rollout

Spec: `clara-pro-answer-synthesis` · Task 9 (final checkpoint / staged enablement).

This runbook covers the staged enablement of scope-aware length targeting,
reliable convergence, and de-templated clinical prose for `deep_beta` synthesis,
all gated behind `SYNTHESIS_V2_ENABLED`. It describes enabling in staging,
sampling 8k–15k generated outputs against guardrail/quality criteria, the
production flip, and rollback.

## Summary

All new synthesis behavior ships dark behind a single runtime flag,
`SYNTHESIS_V2_ENABLED`, read in `services/ml/src/clara_ml/config.py`:

| `SYNTHESIS_V2_ENABLED` value | Synthesis behavior                                              |
| ---------------------------- | --------------------------------------------------------------- |
| `false` (default)            | Legacy budget + fixed section contract + simple expansion       |
| `true`                       | Scope-aware budget + query-type section plan + robust expansion |

When the flag is off, `_resolve_deep_beta_word_budget`, the section contract,
and the expansion loop behave exactly as the pre-feature synthesis
(Requirement 6.1, 6.2; design Property P8 — flags-off equivalence). The flag is
read from config/env at service start, so flipping it means updating the
environment's config and restarting/redeploying the ML service — there is no
in-request toggle.

The change is confined to `services/ml/src/clara_ml/agents/research_tier2.py`
and `services/ml/src/clara_ml/config.py`. No router, retrieval, or guardrail
code changes. `deep` mode stays a dense briefing, distinct from the `deep_beta`
dossier (Requirement 6.4; design Property P10).

## Tunable settings

All settings are bounded and validated in `config.py`; cross-field validation
clamps-and-logs so a misconfiguration cannot violate
`min_words <= target <= max_words <= 15000` (Requirement 6.5; design Property P1).

| Env var                             | Default | Bounds        | Purpose                                  |
| ----------------------------------- | ------- | ------------- | ---------------------------------------- |
| `SYNTHESIS_V2_ENABLED`              | `false` | bool          | Master flag for all new behavior         |
| `DEEP_BETA_REPORT_MIN_WORDS`        | `8000`  | 4000–12000    | Floor for full-scope `deep_beta`         |
| `DEEP_BETA_REPORT_MAX_WORDS_CAP`    | `15000` | floor+2000–15000 | Ceiling for the target band           |
| `DEEP_BETA_REPORT_EXPANSION_ROUNDS` | `4`     | 0–10          | Max convergence expansion rounds         |
| `DEEP_BETA_REPORT_TIMEOUT_SECONDS`  | `90`    | 10–600        | Wall-clock bound; best-so-far on timeout |

## Prerequisites

- Spec tasks 1–8 complete: config + flag foundations, scope classifier,
  scope-aware budget, query-type section planning, robust convergence loop,
  substantive enrichment, tag hygiene, and the guardrail + flags-off regression
  suites.
- Property and unit suites green for the synthesis_v2 work (run targeted, not
  the full slow research path):
  - `services/ml/tests/test_synthesis_v2_config.py`
  - `services/ml/tests/test_synthesis_v2_budget_properties.py`
  - `services/ml/tests/test_synthesis_v2_scope_classifier.py`
  - `services/ml/tests/test_synthesis_v2_scope_labels.py`
  - `services/ml/tests/test_synthesis_v2_style_profile.py`
  - `services/ml/tests/test_synthesis_v2_convergence.py`
  - `services/ml/tests/test_synthesis_v2_min_report_enrichment.py`
  - `services/ml/tests/test_synthesis_v2_flags_off_equivalence.py`
- Guardrail suites green: `services/ml/tests/safety` (no prescribe/diagnose,
  emergency fast-path intact, FIDES CRITICAL preserved at long length;
  Requirement 5; design Property P9).
- Static checks clean: `ruff check services/ml/src/clara_ml/agents` and no
  diagnostics on `research_tier2.py` / `config.py`.

## Stage 1 — Enable in staging

1. In the **staging** ML service environment, set:
   ```
   SYNTHESIS_V2_ENABLED=true
   ```
   Leave the band/rounds/timeout settings at defaults unless tuning for the
   environment.
2. Restart/redeploy the ML service so the new config is read at start.
3. Confirm activation via trace/telemetry: a `deep_beta` request should emit the
   resolved `(min, target, max)` triple and the scope label (no PII;
   Requirement 1.6). If telemetry still shows the legacy fixed band, the flag did
   not take effect — recheck the env var and redeploy before continuing.

## Stage 2 — Sample 8k–15k generated outputs in staging

Generate and review a representative sample of `deep_beta` outputs before
touching production. Aim for a sample whose generated report lengths span the
8,000–15,000 word band, with narrow/sparse queries mixed in to confirm graceful
scale-down.

1. Assemble a query set that exercises each scope class:
   - **broad** full-scope clinical questions (expect target ≥ 8000;
     Requirement 1.2; design Property P4)
   - **comparative_multi** (options-comparison framing, comparison tables)
   - **diagnostic-workup** cues (differential / red-flags framing)
   - **narrow / sparse** (expect coherent scale-down below floor, no appendix
     padding; Requirement 1.3; design Property P5)
2. Run the set through staging `deep_beta` and capture each output plus its
   traced `(min, target, max)` and scope label.
3. Review every sampled output against the criteria below. Track pass/fail per
   item; investigate any failure before promoting.

### Guardrail criteria (must hold for every sampled output)

- No prescription of dosage and no definitive diagnosis, regardless of length
  (Requirement 5.1).
- FIDES CRITICAL-claim blocking and the mandatory clinician-review directive are
  present and intact (Requirement 5.2).
- Emergency / acute queries still take the emergency fast-path — no long
  synthesis (Requirement 5.3).
- No internal pipeline tags, planner labels, execution steps, or debug telemetry
  appear anywhere in the answer body (Requirement 3.3; design Property P9).
- Telemetry is PII-free: only counts, scope label, and the `(min, target, max)`
  triple are traced (Requirement 5.4, 1.6).
- Output is Vietnamese-first with bilingual handling per the existing
  `answer_language` resolution.

### Length / budget criteria

- Resolved budget always satisfies `min_words <= target <= max_words <= 15000`
  (Requirement 1.4, 1.5; design Property P1).
- Broad + high-density queries land in the 8,000–15,000 word band
  (Requirement 1.2).
- Narrow / sparse queries scale down to a coherent length without appendix
  padding (Requirement 1.3, 4.2).
- No report is truncated or thin: expansion reliably converges toward target,
  and any timeout returns the best-so-far report rather than a stub
  (Requirement 2.1, 2.4).

### Quality / de-templating criteria

- Section structure varies by query type rather than repeating one fixed heading
  set (Requirement 3.1).
- No repeated identical sentence openings across adjacent paragraphs
  (Requirement 3.2).
- A direct executive answer and explicit decision boundary precede background
  context (Requirement 3.6).
- Claim-to-evidence linkage is explicit, including contradictory evidence and
  its effect on confidence; comparative and risk/monitoring tables appear when
  clinically relevant (Requirement 3.4, 3.5).
- Depth tracks retrieved evidence; sparse evidence is stated as a limitation, not
  padded, and no citations are fabricated to hit a length target
  (Requirement 4.1, 4.2, 4.3).

### Promotion gate

Proceed to production only when the sampled outputs meet the guardrail criteria
with **zero** violations and the length/quality criteria across the sample show
no systematic regression. Any guardrail violation is a hard stop — do not
promote.

## Stage 3 — Flip on in production

1. After the staging sample passes the promotion gate, set in the **production**
   ML service environment:
   ```
   SYNTHESIS_V2_ENABLED=true
   ```
2. Restart/redeploy the production ML service.
3. Confirm via production telemetry that `deep_beta` requests emit the
   scope-aware `(min, target, max)` triple and scope label (no PII).
4. Monitor early production `deep_beta` traffic for:
   - report lengths within the band, with no truncation/timeout-stub spikes
   - no rise in guardrail blocks bypassed or internal-tag leakage
   - synthesis latency staying within `DEEP_BETA_REPORT_TIMEOUT_SECONDS`
5. Consider tuning the band per environment via the settings table if production
   evidence density warrants a different floor/ceiling. Cross-field validation
   keeps the invariant safe regardless of the values chosen.

## Rollback

Rollback is a single env change with no data/schema implications (the work is
purely additive and the legacy path is preserved):

1. In the affected environment set:
   ```
   SYNTHESIS_V2_ENABLED=false
   ```
2. Restart/redeploy the ML service.
3. With the flag off, the budget resolver, section contract, and expansion loop
   revert to exact pre-feature behavior (Requirement 6.2; design Property P8 —
   flags-off equivalence verified by
   `services/ml/tests/test_synthesis_v2_flags_off_equivalence.py`).

No migration or cleanup is required to roll back. `deep` mode is unaffected by
the flag in either state.
