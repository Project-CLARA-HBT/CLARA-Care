# Development dispatch run 01

The receiver observed identical payload streams and cancellation journals from always-recompute (B2) and the provenance cache (B4). Each arm had 185 scheduled requests over 37 visits from nine synthetic development histories. The receiver recorded 116 payloads and 69 cancellations per arm. All 3,712 requested authorized bytes arrived. Three other development histories have missing ancestry and were excluded by the known-lineage protocol.

Only three histories experienced revocation. Each arm cancelled 36 of their 48 post-revocation requests and delivered the full 384 bytes authorized on the other 12. The observed subject-level disclosure count was 0/3 in both arms. The paired sample variance was zero. These observations supply neither a clustered upper variance bound nor evidence of a privacy advantage for B4.

The observed IPC round-trip p95 was 203.290 µs for B2 and 278.151 µs for B4. This is one serial run per arm in fixed order, including IPC and local scheduling. The collection command used 0.33 s elapsed time and 20,168 KiB maximum RSS as reported by GNU time. Collection used CPU, local files and anonymous pipes.

## Remaining criteria

- **Observation coverage.** The complete reconciliation applies to single-field, known-ancestry fixture requests. Verify missing/ambiguous lineage adjudication and fresh reconstruction, embedding pointers, delayed writes, interleaved policy changes and independently scheduled retry/fallback transports over the registered factorial fanout grid.
- **Prospective design.** Each represented family × tenant group has one history. Obtain repeated independent histories within groups, a development-based upper variance bound, sufficient cluster coverage and a resource estimate at the planned matrix size. Freeze the prospective sample size and analysis before opening the source-disjoint holdout. The blueprint target is 1,200 subjects.
- **RQ1.** Test paired B4 versus B2 post-revocation disclosure at the subject level with the registered 0.05 useful difference, exact McNemar test and clustered confidence intervals. B0 remains NOT_RUN_EXTERNAL, leaving the weak-control leakage witness unmeasured.
- **RQ2.** Establish paired disclosure equivalence within the 0.05 TOST margin. The false-invalidation comparison requires a verified derivation-capable B3 adapter. B3 remains NOT_RUN_EXTERNAL. Any formally narrowed comparison must also narrow the claim.
- **RQ3.** Execute the B1 coarse-purge comparator under equal conditions. Measure authorized cache hits, false invalidation, rebuild cost, bytes and p95 latency across densities. The registered benefit requires matched disclosure, the 0.05 high-density hit-rate gain over B1, lower CI above zero and an arm × density interaction. Apply the registered multiplicity and cluster procedures across the primary contrasts.

## Reproduction and checks

Run from the repository root with Python 3.12.3. The manifest records the implementation commit, source hashes, fixture hash, protocol hash, wall times and evidence digests. Collection refuses an existing destination. Verification reconstructs the schedule and metrics from the captured streams.

```sh
python -m evaluation.venue2027.popets.dispatch_pilot verify artifacts/venue2027/popets/dispatch-dev-01
python -m evaluation.venue2027.popets.dispatch_pilot run /tmp/popets-dispatch-new
ruff check evaluation/venue2027/popets/{dispatch*,test_dispatch_pilot}.py
uvx --offline mypy --follow-imports=silent evaluation/venue2027/popets/dispatch*.py
python -m pytest -q evaluation/venue2027/popets research/venue2027/popets/tests tests/venue2027/popets
python research/venue2027/scripts/taskctl.py ready --venue popets
```

Archive verification, lint and type checking exited 0. Pytest reported 521 passed. Control tests detected a 64-byte forbidden payload and loss of half the requested authorized bytes. Reconciliation tests rejected missing, duplicate, conflicting, reordered, truncated and unclassifiable evidence. The task registry reported zero runnable dependent tasks. The pilot remains BLOCKED.
