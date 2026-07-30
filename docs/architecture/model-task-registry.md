# Model task registry and rollback

`services/ml/src/clara_ml/llm/model_registry.py` is the typed boundary for
model-backed tasks that can affect safety or clinical workflow. It does not let
requests choose a provider or model. Each task declares a prompt version,
closed output contract, deterministic/unavailable fallback, risk level,
permitted tiers, tool prerequisites, token ceiling and human-review floor.

The source of truth is the versioned, non-secret manifest at
`services/ml/config/task_contracts/contracts.json`.  ML refuses to start its
model registry when that manifest is absent, malformed, or omits a registered
task; it deliberately does not silently fall back to a permissive in-code
map. The container copies this manifest to `/app/config/task_contracts/`.
The resolved selection carries the contract schema version, risk category and
model profile for safe operational correlation, never user text or prompt
content.

The current registry covers the medical safety router, LifeMap Capture triage
and visit extraction, Scribe note/transcription, Council shadow assessment,
LLM-assisted RAG reranking, evidence-bound NLI claim verification, Research
query planning, and Research reasoning/deep-beta reasoning. Those
callers still retain their existing emergency, legal, provenance, template,
FIDES, retrieval-order and shadow-only guards; the registry cannot bypass them.

RAG's explicit internal runtime connection seam is also registry-bound: it
passes its already-authorized DeepSeek connection values through a read-only
settings overlay to the `RAG_SYNTHESIS` contract. It therefore keeps the
legacy short override timeout while applying the same prompt version and
rollback selection as the default RAG client. It does not construct a provider
client directly.

The registry selects only the provider/model boundary. It never converts a
heuristic, embedding scorer or fixed-weight Council rule into a neural model,
and it never permits LLM output to confirm a LifeMap record, prescribe, change
a dose, authorize access or replace DrugBank authority.

The shadow router may receive deterministic Vietnamese clinical-language cues,
but publishes only bounded categories/counts (negation, experiencer,
temporality, severity cue, unit count and medication-candidate count). It does
not publish source text, a medication name, a dose, confidence or free-text
rationale in telemetry.

## Optional Encoder-SLM shadow

The separate Encoder-SLM seam is deliberately **shadow-only**, off by default,
and invoked only after deterministic emergency and legal hard guards return.
Its sole adapter is `model_router/encoder_shadow.py`; it redacts the already
redacted input again, bounds request/response size and time, rejects redirects,
and accepts only `clara.encoder-slm-shadow.v1`. That contract contains closed
categorical intent/risk/entity/negation/temporality/experiencer/language fields
and explicitly rejects free text, spans, confidence and extra fields.

The shadow signal cannot alter a route, response, retrieval, authorization,
DrugBank lookup, FIDES verdict, consent decision, LifeMap truth state or audit
event. Operations may enable it only with an internal endpoint and deployment
secret. Set `ENCODER_SLM_SHADOW_ENABLED=false` and restart ML for an immediate
rollback; an unavailable or malformed endpoint degrades to typed shadow
metadata without changing chat behaviour.

Configuration is intentionally operational rather than user-facing:

```text
MODEL_REGISTRY_ENABLED=true
MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=true
MODEL_REGISTRY_FORCE_ROLLBACK=false
MODEL_REGISTRY_ROLLBACK_MODEL=
DEEPSEEK_PRO_MODEL=deepseek-v4-pro
DEEPSEEK_FLASH_MODEL=deepseek-v4-flash
```

With task routing enabled, the manifest assigns `pro` to critical/safety and
reasoning tasks (medical safety routing, LifeMap triage, FIDES/NLI, RAG
synthesis, Council, Scribe note and research reasoning) and `flash` to bounded
latency-sensitive tasks (LifeMap visit candidates, ASR correction/transcript
handling, RAG reranking and research query planning). A Pro task may fail over
to Flash and a Flash task may fail over to Pro, but never to the same model.
Deterministic emergency/legal guards, FIDES, DrugBank, consent and truth-state
rules remain authoritative regardless of a model response.

Set `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=false` and restart ML for an
immediate restoration of the legacy single `DEEPSEEK_MODEL` selection. To
force a named model rollback, configure a known previous DeepSeek model in
`MODEL_REGISTRY_ROLLBACK_MODEL`, then set
`MODEL_REGISTRY_FORCE_ROLLBACK=true` and restart the ML service. If no prior
model is configured, a rollback request keeps the primary model and reports no
rollback selection; it never labels the primary as a rollback.

For immediate restoration of the former selection behavior, set
`MODEL_REGISTRY_ENABLED=false` and restart the ML service. This switch only
changes selection; it does not disable emergency fast paths, legal hard guards,
FIDES verification, consent/RBAC, or deterministic fallbacks.
