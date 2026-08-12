# CommitLoop v5 batch-5 router run

This is a sealed, synthetic software-evaluation artifact. Clinical adjudication
was not run, so these results are descriptive engineering evidence only.

- Implementation SHA: `2beec1ec833060a608f7cd100938e316b40ca87b`.
- Frozen cohort: 384 independent subjects, 9 conditions, 3,456 solver cells.
- Execution: Claude reviewer only; no retries or fallback; bounded execution
  with `batch_size=5` and `max_concurrency=8` (five requests submitted per
  durable batch).
- Provider calls: 3,456 benchmark calls plus 2 pre-run model-probe calls.
- Validation: `VALID`; 3,236 parsed outputs and 220 fail-closed malformed
  outputs; offline reproduction made zero provider calls and matched all
  derived files.

## Pre-specified primary contrast

Reference: `glhs_hybrid_thss_strict`; comparator:
`full_authorized_history`; unit: subject; n=384. Wins/losses/ties were
70/73/241. The mean reference-minus-comparator effect was -0.0078125, with
95% bootstrap CI [-0.0677083, 0.0520833] and exact two-sided sign-test
p=0.8672499071. The run is therefore recorded as
`DESCRIPTIVE_SYNTHETIC_ONLY`, not as a clinical or publication claim.

Aggregate exact-match accuracy across all cells was 2032/3456 (0.587963).
Axis accuracy was lifecycle 2822/3456 (0.816551), evidence 3162/3456
(0.914931), and timeliness 2396/3456 (0.693287).

The complete sealed run, checksums, raw/parsed synthetic outputs, error ledger,
and zero-call reproduction are retained outside the tracked tree at
`/tmp/clara-glhs-v5-batch5-live-run`; the pre-provider freeze is at
`/tmp/clara-glhs-v5-batch5-freeze`. The tracked summary intentionally excludes
credentials, PHI, and raw provider content.
