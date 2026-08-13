# Comparator studies

This directory contains mechanism-mapped comparator contracts, never fabricated
benchmark results. Zhao-style bi-temporal state arbitration and Vital Trace are
kept as the primary temporal-state comparators; each has a method card, source
mapping, deviations, capability boundary, and fidelity tests.

VISTA and LongMedBench are reference points only until their public, runnable
assets and task/licensing conditions are independently verified. No faithful
implementation, score, or superiority claim is permitted from a citation alone;
the corresponding workstream remains **NOT RUN / asset-gated**.

`standards_composed_baseline/` is the strong novelty-isolation comparator. It
combines version-aware writes, current authorization, provenance and audit, but
intentionally omits exact THSS disclosure-context binding. It is a semantic
mechanism baseline and is never labelled as a faithful FHIR server.

`official_graphrag/` pins Microsoft GraphRAG `v3.1.0` and verifies use of its
upstream CLI. It is deliberately **NOT RUN** until a router-compatible embedding
probe and source/index/query ledger are frozen. Its adapter may not be replaced
with project-local graph or retrieval code, and it cannot appear in numerical
comparisons until that gate passes.

`published_systems.yaml` inventories published-system candidates and their
eligibility.  It intentionally records task mismatch and missing assets rather
than turning citations into fabricated reproductions. The registry is a freeze
gate for future validation/final comparisons.
