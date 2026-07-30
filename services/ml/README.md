# CLARA ML/NLP (P0)

Baseline cho P0 gồm:
- LangGraph/LangChain orchestration nền
- BaseAgent + AgentRegistry
- Prompt templates YAML theo role/intent
- RAG PoC (query -> embed -> retrieve -> generate)
- WebSocket streaming handler cơ bản
- Vietnamese NLP baseline (Unicode, tokenizer, PII, seed loader)

## Chạy nhanh

```bash
cd services/ml
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn clara_ml.main:app --reload --port 8101
pytest
```

## Optional Encoder-SLM router shadow

`ENCODER_SLM_SHADOW_ENABLED=false` is the default.  When explicitly enabled,
the ML service sends a bounded, PII-redacted copy of a non-emergency chat input
to `ENCODER_SLM_SHADOW_URL`.  The external endpoint must return the closed
`clara.encoder-slm-shadow.v1` categorical schema (intent, risk category,
entity categories, negation, temporality, experiencer and language).  It never
receives an unredacted query, produces no user-facing confidence value, and
cannot change emergency, legal, consent, RBAC, DrugBank, FIDES, or LifeMap
truth-state decisions.

Suggested internal-only deployment configuration:

```bash
ENCODER_SLM_SHADOW_ENABLED=true
ENCODER_SLM_SHADOW_URL=http://encoder.internal/v1/clinical-route
ENCODER_SLM_SHADOW_TIMEOUT_MS=750
ENCODER_SLM_SHADOW_MAX_INPUT_CHARS=1200
ENCODER_SLM_SHADOW_MODEL_ID=vi-clinical-encoder-<release-id>
```

Set `ENCODER_SLM_SHADOW_ENABLED=false` to roll the shadow integration back
immediately.  A missing, invalid, slow, malformed, or unavailable endpoint is
reported only as typed shadow metadata and falls back safely without changing
chat behavior.
