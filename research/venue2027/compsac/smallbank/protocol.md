# SmallBank procedure development comparison

Use BenchBase commit `33c00473807ebd49304d114a6d769d2d2b2bbb34`.
Verify the inventory with `sha256sum -c /path/to/upstream.sha256` from that checkout.
The PostgreSQL DDL is copied verbatim. The Python implementation adapts three Java methods.
The directory contains the repository license, full Apache license and the procedure-level H-Store notice.
[Upstream implementation and notices](https://github.com/cmu-db/benchbase/tree/33c00473807ebd49304d114a6d769d2d2b2bbb34/src/main/java/com/oltpbenchmark/benchmarks/smallbank)

All three methods resolve a zero-padded customer name to a customer ID.
DepositChecking adds 1.3 to checking. TransactSavings reads savings, rejects if
subtracting 20.2 would make it negative, and otherwise subtracts 20.2.
WriteCheck reads savings, then checking. It subtracts 4 from checking if their
sum is strictly below 5, otherwise 5. The unusual smaller debit follows the
pinned Java expression. The fixtures contain every referenced row. The
account mapping stays immutable. PostgreSQL float balances preserve upstream
double arithmetic, including threshold behavior.

Use one socket-only PG 16.4 cluster. The native arm runs the upstream statement sequence,
including all reads, in a single SERIALIZABLE transaction with native conflict detection.
The second arm executes the same procedure at READ COMMITTED. It takes FOR SHARE on
the savings read in WriteCheck, FOR UPDATE on the checking read there and on the
savings read in TransactSavings. DepositChecking's incremental UPDATE takes its normal
write lock. Keys are fixed and present. This tests the manually scoped locking
component on concurrent writes, with no detached proposal, semantic inference,
policy epoch, or full B4 implementation.

The development grid crosses 1 and 4 sessions with 4 and 32 uniformly sampled accounts,
six seeds (0–5), and both arms. Alternate which arm goes first by seed.
Each paired stream shuffles exactly 120 checks, 84 deposits, and 36 withdrawals
over 60 waves of four operations, initially 0 checking and 40.4 savings per account.
The reduced scale, low initial balances, procedure mix, scheduled waves, Python driver
and retry limit replace BenchBase's loader, timing and workload driver.
Restart the whole transaction up to twice on 40001 or 40P01, with no backoff.
Keep business rejections, final aborts and every paired rate including losses.
Time from worker release until last completion in each wave, summed across waves,
including retries, excluding setup and all coordinator readbacks. Numerator counts
committed money-changing operations. This bounded-wave design allows exhaustive
checking and does not estimate steady-state saturation throughput.

Retain inputs, observed balances, terminal outcomes, attempt failures, invocation and
response times and independent database balance readback after every wave. Offline,
enumerate all real-time-compatible orders of completed operations, checking both
branches and exact balances against the pinned semantics. Exhausted DB aborts have
no procedure result or effect. Require a witness for the entire wave including all
money movements and business rejections. A mismatch stays in the evidence.
