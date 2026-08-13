# Deviations and scope boundary

- The common synthetic longitudinal evidence is converted to neutral JSONL
  documents because GraphRAG consumes documents, not FHIR resources directly.
  The conversion is deterministic and contains only already visible evidence.
- The benchmark solver remains the same frozen model, prompt, decoding and
  schema used by all comparable arms. GraphRAG indexing/query models and
  embeddings are recorded separately because they are intrinsic upstream
  dependencies.
- Until the frozen execution ledger exists, this component must be labelled
  `NOT RUN`, not a faithful execution, and must not appear in numerical tables.
