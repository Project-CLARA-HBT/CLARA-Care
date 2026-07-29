# Model task registry and rollback

`services/ml/src/clara_ml/llm/model_registry.py` is the typed boundary for
model-backed tasks that can affect safety or clinical workflow. It does not let
requests choose a provider or model. Each task declares a prompt version,
closed output contract, and deterministic/unavailable fallback.

The current registry covers the medical safety router, LifeMap Capture triage
and visit extraction, Scribe note/transcription, Council shadow assessment,
LLM-assisted RAG reranking, evidence-bound NLI claim verification, Research
query planning, and Research reasoning/deep-beta reasoning. Those
callers still retain their existing emergency, legal, provenance, template,
FIDES, retrieval-order and shadow-only guards; the registry cannot bypass them.

The registry selects only the provider/model boundary. It never converts a
heuristic, embedding scorer or fixed-weight Council rule into a neural model,
and it never permits LLM output to confirm a LifeMap record, prescribe, change
a dose, authorize access or replace DrugBank authority.

The shadow router may receive deterministic Vietnamese clinical-language cues,
but publishes only bounded categories/counts (negation, experiencer,
temporality, severity cue, unit count and medication-candidate count). It does
not publish source text, a medication name, a dose, confidence or free-text
rationale in telemetry.

Configuration is intentionally operational rather than user-facing:

```text
MODEL_REGISTRY_ENABLED=true
MODEL_REGISTRY_FORCE_ROLLBACK=false
MODEL_REGISTRY_ROLLBACK_MODEL=
```

The default is the configured `DEEPSEEK_MODEL`. To roll back, configure a known
previous DeepSeek model in `MODEL_REGISTRY_ROLLBACK_MODEL`, then set
`MODEL_REGISTRY_FORCE_ROLLBACK=true` and restart the ML service. If no prior
model is configured, a rollback request keeps the primary model and reports no
rollback selection; it never labels the primary as a rollback.

For immediate restoration of the former selection behavior, set
`MODEL_REGISTRY_ENABLED=false` and restart the ML service. This switch only
changes selection; it does not disable emergency fast paths, legal hard guards,
FIDES verification, consent/RBAC, or deterministic fallbacks.
