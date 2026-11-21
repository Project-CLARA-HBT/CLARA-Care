# Changing dependency versions on disjoint targets

This additional development condition tests whether a proposal carrying a previously
valid snapshot is rejected after a committed epoch change. It uses the v4 split
relations, common SQL, ANALYZE and two-retry policy on an isolated socket-only
PostgreSQL 16.4 instance. There are four proposal workers, eight common dependency
rows, six target-order seeds (0–5), and the same six permutations of the three
arms as v4. Run each arm once per seed. Retain all arms and seeds regardless of
throughput or correctness.

Each campaign starts at dependency version zero. In each of four waves, the
coordinator advances all eight dependencies together before releasing the workers.
The 24 new target IDs per wave are consecutive, starting at 9, shuffled within
wave by the campaign RNG. Multiples of eight carry the previous version, the
other proposals carry the new version. Each ID has one proposal and at most two
retries after serialization failure. Writers and proposal transactions occupy
distinct phases. This exercises snapshot invalidation across epochs and concurrent
proposals within epochs.

Score the 84 eligible and 12 expired target IDs per campaign against installed IDs
from a separate database connection, and check actual dependency versions each wave.
Report forbidden installs, missing valid targets, terminal outcomes and retry counts.
Measure proposal throughput as committed targets divided by the sum of the four
worker intervals (barrier release to last completion). Setup, version changes and
readback occur outside those intervals. Report both lock-arm rates divided by
same-seed SSI, each seed and the median, including values below one. Analyze this
condition separately from v4 because the timing intervals and workload differ.
