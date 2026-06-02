# RAG Seed Execution Report (VN Medical Sources)

Date: 2026-03-29

## Scope

- Source catalog input:
  - `docs/research/data/vn-medical-pdf-sources-phase1-part1-2026-03-29.csv`
- Goal:
  - pull publicly reachable VN medical documents
  - build runtime seed payload for CLARA RAG

## Implementation Added

- Acquisition scripts:
  - `scripts/rag_seed.py`
  - `scripts/rag_seed/cli.py`
  - `scripts/rag_seed/acquisition.py`
  - `scripts/rag_seed/http_client.py`
  - `scripts/rag_seed/html_discovery.py`
  - `scripts/rag_seed/pdf_extract.py`
  - `scripts/rag_seed/io_utils.py`
  - `scripts/rag_seed/models.py`
- Runtime seed loader:
  - `services/ml/src/clara_ml/rag/seed_documents.py`
  - `services/ml/src/clara_ml/rag/pipeline.py` (loads seed docs on startup)

## Outputs

- Downloaded PDFs (local workspace):
  - `data/rag_seed/downloads/` (currently 16 files, around 31 MB)
- Manifest (checked into docs data):
  - `docs/research/data/vn-medical-acquired-manifest-2026-03-29.jsonl`
- Crawl report (checked into docs data):
  - `docs/research/data/vn-medical-acquired-report-2026-03-29.json`
- RAG seed payload consumed by ML service:
  - `services/ml/src/clara_ml/nlp/seed_data/vn_medical_seed.json`

## Result Snapshot

- Catalog size: 41 sources
- Sources with direct downloadable docs pulled in this run: 16
- Seed docs generated for runtime: 41
  - 16 docs from real downloaded PDF links
  - 25 fallback catalog docs to keep full source coverage

## Run Command

```bash
python3 scripts/rag_seed.py \
  --max-sources 0 \
  --max-docs-per-source 1 \
  --max-candidate-urls-per-source 6 \
  --timeout-seconds 5 \
  --sleep-seconds 0
```

## Notes

- Some sources are API/table/restricted-access/not-direct-PDF, so they are represented as catalog fallback docs in seed.
- PDF deep text extraction currently depends on optional local tools:
  - Python package `pypdf`, or
  - system binary `pdftotext`
- If extracted text looks like low-quality binary PDF artifacts, seed builder automatically falls back to metadata-rich text (owner/category/source URL) to keep retrieval stable.
