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

The current registry covers the medical safety router, LifeMap Ask semantic
routing, LifeMap Capture triage, free-text draft extraction and visit extraction, Scribe note/transcription, Council shadow assessment,
LLM-assisted RAG reranking, evidence-bound NLI claim verification, Research
query planning, and Research reasoning/deep-beta reasoning. Those
callers still retain their existing emergency, legal, provenance, template,
FIDES, retrieval-order and shadow-only guards; the registry cannot bypass them.

RAG always reuses its registry-built `RAG_SYNTHESIS` client. Request payloads,
queued jobs and Control Tower configuration cannot provide a provider, endpoint,
model or API key. Historical `llm_runtime` and Control Tower `llm_*` JSON keys
are ignored on read and omitted on write; this is a backward-compatible JSON
configuration cleanup with no database migration or credential transfer.
`DeepSeekClient` intentionally has no public
``from_runtime`` helper: every production construction must enter through
`build_task_client`, so a future caller cannot select a model or provider
outside a typed task contract.

The registry selects only the provider/model boundary. It never converts a
heuristic, embedding scorer or fixed-weight Council rule into a neural model,
and it never permits LLM output to confirm a LifeMap record, prescribe, change
a dose, authorize access or replace DrugBank authority.

## Deliberate non-text-model exceptions

The registry covers generative DeepSeek text tasks. It does not claim to
govern deterministic code, embeddings, encoder-SLM shadow inference, or ASR
provider selection. In particular, Scribe's `SCRIBE_TRANSCRIPTION` contract
selects the text-client transport and request budget, while
`DEEPSEEK_AUDIO_MODEL` remains a separately configured audio model sent only
to the transcription endpoint. Local Whisper, PhoWhisper, and Google STT stay
behind the typed ASR provider seam; none can be selected by end-user request
data. These exceptions must not be repurposed for text generation.

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

The production env guard requires `DEEPSEEK_MODEL` to equal
`DEEPSEEK_PRO_MODEL`, requires the Pro and Flash identifiers to be distinct,
and requires both registry switches to be explicitly `true`. This prevents a
stale deploy secret from silently reverting to a legacy single-model path.

## Semantic intent routing

Chat invokes `MEDICAL_SAFETY_ROUTER` before normal retrieval. Its closed task
proposal can select only an existing non-emergency chat intent after the
deterministic emergency and prohibited-action guards have allowed the request.
`SEMANTIC_INTENT_ROUTING_ENABLED=false` immediately restores the legacy
keyword intent selection; it cannot disable emergency escalation, legal
refusal, FIDES, consent, RBAC, DrugBank or LifeMap invariants. The router
receives a PII-redacted bounded message and records only model/task state, not
the message or generated analysis.

`POST /api/v1/lifemap/v2/ask` uses a distinct `LIFEMAP_ASK_ROUTER` task after
its deterministic emergency and legal fast paths and after API consent/profile
scope checks, but before LifeMap retrieval. The API sends only the bounded
question and locale to `/v1/lifemap/ask/route`; profile ids, grants, events,
revisions, retrieved text and source citations never cross that route. The
router may return only five closed intents, a legal block, or emergency
escalation. It cannot return an answer or mutate a record. API still retrieves
only current authorized revisions and builds/verifies exact-revision claims
deterministically. Provider errors, malformed output, or confidence below 0.7
restore the existing deterministic route. The response intentionally reports
only enabled/used/degraded state, never a model confidence. Set
`LIFEMAP_ASK_SEMANTIC_ROUTING_ENABLED=false` and restart API for an immediate
rollback; deterministic emergency/legal guards remain active either way.

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
