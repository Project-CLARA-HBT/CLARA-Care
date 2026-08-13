# Microsoft GraphRAG v3.1.0 external comparator

Status: **execution-contract prepared; NOT RUN**.

This is a pinned, official upstream implementation candidate, not a local
reimplementation.  The source is Microsoft GraphRAG release `v3.1.0`, commit
`7fc6607edda3d387d23e52ededbf8a75b6730f97`, under MIT.

The GLHS adapter serializes only the evidence visible under the same temporal
cutoff supplied to every arm.  It uses GraphRAG's own `index` and `query`
commands, then gives the frozen shared solver the resulting retrieved context.
No labels, target decisions, predicates, future evidence, task-specific prompt
tuning, or substitute local retrieval are permitted.

The condition is unavailable until a manifest verifies the upstream checkout,
router completion *and embedding* probes, input/settings hashes, CLI commands,
index completion, query completion and output checksums.  The configured router
may not expose a compatible embedding endpoint.  That is an asset/runtime gate,
not permission to claim a reproduction or to silently replace it with another
retriever.

The generated upstream configuration fixes `concurrent_requests: 5`. Its index
window is exclusive with solver calls, so total router concurrency cannot exceed
the benchmark-wide cap.

Before a real run, `prepare_upstream_run_root()` invokes the upstream `init`
command to generate its release-specific prompt assets, writes a canonical,
secret-free frozen settings file and serializes visible evidence only.  Its
`dry_validate_upstream_run_root()` command runs upstream `index --dry-run
--skip-validation` with a placeholder key; that validates configuration without
making an LLM or embedding request.  Neither preparation nor dry validation is
evidence of an executed GraphRAG benchmark.
