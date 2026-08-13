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
