# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLARA (Clinical Agent for Retrieval & Analysis) is a Vietnamese Medical AI Assistant. This is currently a **documentation-only monorepo** — no source code exists yet. All files are design documents, research papers, and planning artifacts in `docs/`. Implementation will follow the planned `src/` structure.

## Repository Structure

```
docs/
├── architecture/
│   ├── clara-platform-architecture.md
│   ├── clara-runtime-and-routing.md
│   └── clara-diagrams.html
├── proposal/
│   ├── clara-master-proposal.md
│   ├── clara-research-proposal.md
│   ├── clara-self-med-proposal.md
│   └── feature-planning-and-roadmap.md
├── research/
│   ├── market-need-and-regulatory-research.md
│   ├── multimodal-rag-and-data-connectors-research.md
│   ├── medical-slm-and-safety-research.md
│   └── risk-deep-dive-and-mitigation.md
└── implementation-plan/
    ├── phase-00-to-06-master-plan.md
    ├── team-allocation-and-task-breakdown.md
    ├── frontend-web-mobile-flutter-plan.md
    ├── backend-rust-plan.md
    └── metrics-gates-and-operating-model.md
```

## Planned Development Commands

When source code is implemented, these are the expected commands (aligned with `docs/implementation-plan/phase-00-to-06-master-plan.md`):

```bash
# Setup
cp .env.example .env                          # Configure API keys
cd deploy/docker && docker-compose up -d      # PostgreSQL, Redis, Milvus, Elasticsearch, Neo4j
pip install -e ".[dev]"                        # Python 3.11+ required
alembic upgrade head                           # Database migrations
python scripts/setup/download_models.py       # BGE-M3, Qwen2.5, BioMistral

# Development
make dev-api            # FastAPI (uvicorn, port 8000)
make dev-web            # Next.js (port 3000)
make dev-worker         # Celery async worker

# Testing & Quality
make test               # All tests
make test-unit          # Unit tests only
make test-integration   # Integration tests
make lint               # Ruff linter
make format             # Ruff formatter
make type-check         # mypy

# AI-specific
make evaluate-rag       # RAG accuracy evaluation
make evaluate-router    # Intent router evaluation
make build-embeddings   # Generate vector embeddings
```

## Architecture: Critical Design Patterns

### Two-Layer Intent Router
The system uses a **cascading SLM router** — NOT a single classifier:
- **Layer 1** (Qwen2.5-0.5B, <20ms): Classifies user *role* (Normal/Researcher/Doctor)
- **Layer 2** (Phi-3-mini + LoRA adapters, <80ms): Classifies role-specific *intent* (~15 categories per role)
- Same query produces fundamentally different responses per role
- **Confidence thresholds**: <0.7 → default to Normal (safest); 0.7-0.85 → add safety disclaimers; >0.85 → full confidence
- LoRA adapters are hot-swapped per role (~5ms swap), sharing a single base model in GPU memory

### Emergency Intent Fast-Path
Certain keywords (Vietnamese + English) **bypass all normal workflows** and trigger immediate (<1s) responses:
- Keywords: "co giật", "ngừng thở", "đau ngực dữ dội", "xuất huyết", "ngộ độc", "tự tử" (and English equivalents)
- Response: Display 115 (Vietnam emergency), pre-cached first-aid, nearest hospital
- **MUST NOT engage in diagnostic reasoning** for emergency intents

### Three Workflow Tiers
Each tier has distinct latency budgets — do not mix them:
- **Tier 1 Simple** (<2 min): Normal users, single-pass RAG, lite fact-check (dosage only), simple Vietnamese language
- **Tier 2 Research** (5-20 min): Researchers, multi-source RAG with streaming (Perplexity-style), full FIDES verification
- **Tier 3 AI Council** (<20 min): Doctors only, multi-specialist agent deliberation (Hội chẩn), live processing logs via WebSocket

### FIDES Fact Checker — Tiered Verification
Verification depth varies by tier — this is intentional, not a bug:
- Tier 1: `quick_pattern_check()` — regex patterns only
- Tier 2: `standard_verification()` — pattern + retrieval-based
- Tier 3: `full_fides_verification()` — complete 5-step pipeline (Claim Decomposition → Evidence Retrieval → Cross-Reference → Citation Validation → Verdict)

### Critical Claim Severity Actions
Claims are classified with specific failure actions — these are **safety-critical**:
- `CRITICAL` (dosage, DDI, contraindication): `BLOCK_RESPONSE` on verification failure
- `HIGH` (diagnosis, treatment): `FLAG_AND_WARN`
- `MEDIUM` (statistics): `ADD_UNCERTAINTY_NOTE`
- Drug dosage/interaction claims **always** verify against structured DB (Dược thư + RxNorm), never LLM-only

### 4-Layer Cache with UPDATE-not-APPEND Semantics
Cache uses **UPDATE, not APPEND** when new evidence arrives for an existing medical entity. This is a core safety rule — blindly appending creates contradictory medical information:
- Layer 1: Redis hot cache (TTL 24h) — keyed by `clara:qr:{role}:{normalized_query_hash}`
- Layer 2: PostgreSQL JSONB knowledge entity cache (TTL 7 days)
- Layer 3: Embedding cache (TTL 30 days)
- Layer 4: Source freshness tracker (continuous)
- Evidence priority hierarchy: BYT Protocol > Clinical Guidelines > Meta-analysis > RCT > Dược thư > Observational > Expert opinion

### Drug Normalization Pipeline
Vietnamese drug names require a multi-step normalization — direct RxNorm lookup will fail:
1. Local Vietnamese drug name lookup (Dược thư mapping table) → generic name
2. RxNorm API `/rxcui?name=` → RxCUI
3. Verify via `/drugs?conceptId=`
4. Get drug class via `/rxclass/class/byDrugName`
5. Check interactions via `/interaction/list?rxcuis=`

DDI verification requires ≥2 source confirmation: Confirmed by ≥2 → VERIFIED; 1 source → PARTIALLY_VERIFIED; severity mismatch → CONTESTED; not found → UNSUPPORTED → BLOCK if CRITICAL.

### AI Council (Hội chẩn AI)
Multi-specialist deliberation system for Tier 3 (doctors only):
- Orchestrator spawns 2-5 specialist agents (e.g., Cardiology, Nephrology)
- Each analyzes independently → conflict detection → structured debate → consensus/divergence
- Uses OpenBioLLM-8B or BioMistral-7B with specialty LoRA adapters
- Full FIDES pipeline runs on ALL claims (not lite)
- Must include BYT protocol compliance check

## Vietnamese NLP: Critical Implementation Details

### Diacritics Are Semantically Critical
Vietnamese has 12 vowels × 6 tones = 72 possible vowel forms. Incorrect diacritics change medical meaning:
- "thuốc" (medicine) vs "thuộc" (belongs to)
- "gan" (liver) vs "gân" (tendon) vs "gần" (near)
- "bệnh" (disease) vs "bênh" (to defend)

Processing pipeline must:
1. Unicode NFC normalize (same char can be precomposed U+1EC7 or decomposed U+0065+U+0323+U+0302)
2. Restore missing diacritics from user input ("benh tieu duong" → "bệnh tiểu đường") using BERT-based model
3. Handle Telex/VNI input residue ("beenh" → "bệnh")

### Word Segmentation
Vietnamese compound words must be preserved as single tokens:
- "đái tháo đường" = diabetes (3-word compound, single concept)
- Custom BM25 analyzer preserves compound words, not standard tokenizers
- Medical synonym dictionary: "thuốc ≈ dược phẩm", "bệnh nhân ≈ người bệnh"
- Medical entities get 2x BM25 weight boost

### Cross-Language Entity Linking
Vietnamese medical text mixes Vietnamese and English/Latin ("viêm phổi do Streptococcus pneumoniae"):
- VN↔EN bidirectional mapping DB (~50K entries)
- 5 linking strategies: Dictionary → UMLS → ICD-11 multilingual → RxNorm brand mapping → BGE-M3 embedding similarity
- Vietnamese synonym normalization: "tiểu đường" → "đái tháo đường" (TCVN standard)

### BYT Protocol Handling
BYT (Bộ Y tế / Ministry of Health) protocols have special status:
- Highest reliability weight (0.95) in evidence hierarchy
- Not API-accessible — must be pre-indexed in local vector database
- When BYT conflicts with international guidelines (PubMed), **flag for human review** rather than auto-resolving
- Monthly automated crawler for BYT circular updates

## Key External API Rate Limits

| API | Rate Limit | Auth Required |
|-----|-----------|---------------|
| PubMed (NCBI) | 10 req/s with key, 3 req/s without | NCBI API Key |
| RxNorm (NLM) | ~20 req/s | None |
| OpenFDA | 240 req/min with key | Optional |
| ICD-11 (WHO) | Standard | Client ID + Secret |
| ClinicalTrials.gov | Standard | None |

## Model Stack Reference

| Component | Model | Size | Latency |
|-----------|-------|------|---------|
| Role classifier (L1) | Qwen2.5-0.5B-Instruct (VN fine-tuned) | 0.5B | <20ms |
| Intent router (L2) | Qwen2.5-3B / Phi-3-mini + LoRA | 3B | <80ms |
| Medical NER | ViHealthBERT + Qwen2.5-1.5B ensemble | 110M+1.5B | <100ms |
| Response synthesis | Qwen2.5-72B / GPT-4o fallback | 72B | 2-10s |
| Fact-checking | BioMistral-7B (VN fine-tuned) | 7B | 1-5s |
| ASR | Whisper Large v3 (VN fine-tuned) | 1.5B | Real-time |
| Embeddings | BGE-M3 (multilingual) | 568M | <50ms |
| Hybrid search α | 0.6 (dense-weighted) | — | — |
