# When does tracing improve a detached reuse decision?

Across 432 paired development cases, preparation-time tracing won 0, tied 424
and lost 8 against a maintained manual dependency template. Neither method
reused an invalid decision on this grid. The clinical revision exposes a benefit
only against delayed template maintenance. The external banking procedures
expose a precision cost even when the tracer observes the executed SQL correctly.

| Workflow | Valid / invalid | False admissions, traced / manual | False rejections, traced / manual | Tracing wins / ties / losses |
|---|---:|---:|---:|---:|
| DepositChecking | 16 / 0 | 0 / 0 | 8 / 0 | 0 / 8 / 8 |
| TransactSavings | 8 / 8 | 0 / 0 | 0 / 0 | 0 / 16 / 0 |
| WriteCheck | 10 / 6 | 0 / 0 | 6 / 6 | 0 / 16 / 0 |
| LifeMap, original | 48 / 144 | 0 / 0 | 0 / 0 | 0 / 192 / 0 |
| LifeMap, field-bound | 12 / 180 | 0 / 0 | 0 / 0 | 0 / 192 / 0 |

The table gives counts. Each error count uses the corresponding invalid or valid
column as its denominator. Deposit has no invalid case within this domain.
Changing checking from 0 to 6 leaves the deposit instruction at +1.3. SQLite
reports a balance read for the relative UPDATE, so tracing rejects it. For
WriteCheck, changing savings from 0 to 21 with checking fixed at 6 preserves
the debit of 5. Both sets still watch savings. Even accurate access sets can
overstate the state required to reuse a particular result.

In LifeMap, each proposal names two revisions. The original validator checked
their memberships. Its successor also reads the field bound to each revision.
The maintained template added one parameterized clause (watch the field of
each named revision). With the old template on the revised rule, 36 of 180
invalid edits were admitted, 0 of 12 valid edits were rejected, and tracing
won 36, tied 156 and lost 0. All 192 original-rule cases tied against the
lag control. The generic lookup recorder captured the added reads. The harness
supplied the version-appropriate argument and instrumented the field map.
This describes maintenance of dependency declarations within an instrumented
interface. The experiment did not measure engineering labor or discover new
interfaces automatically.

## Provenance and reproduction

Protocol commit `185e52bf` precedes the first executable run at `51939bbd`.
The port and schema match the local external study at `73b5c897`. All eight
upstream files matched its SHA-256 inventory on BenchBase
`33c00473807ebd49304d114a6d769d2d2b2bbb34`. The bank specification checks
both status and observed balance effects. Clinical labels compare full findings
returned by uninstrumented code and are cross-checked by an executable registry
predicate. Every cross-check agreed. The implementation and specifications
were written within one development study. Independence here means separate
executable paths, with no labels supplied by either dependency template.

From the repository root with the two LifeMap Git objects available, Python
3.12.3, SQLite 3.45.1 and psycopg 3.3.5 (imported by the existing port):

```sh
python3 -m evaluation.venue2027.compsac.reuse_derivation /tmp/compsac-reuse.jsonl
cmp /tmp/compsac-reuse.jsonl research/venue2027/compsac/derivation/paired.jsonl
python3 -m pytest -q evaluation/venue2027/compsac/test_reuse_derivation.py
```

SQLite uses one fixed, existing account. The clinical grid starts with accepted
proposals and varies a finite registry; multiple hidden field states can yield
the same visible registry. All counts weight the frozen input grid, not a
deployment distribution. The outcome is the validity of reusing an instruction
or review finding. Serializability, clinical outcomes and end-to-end commit
performance require separate evidence. [Frozen design](protocol.md) · [Every paired decision](paired.jsonl) · [Earlier PostgreSQL comparison](../smallbank/results.md)

## Relation to published transaction analysis

Jorwekar and colleagues analyzed transaction descriptions drawn from application
code or SQL traces to identify potential snapshot-isolation anomalies.
Vandevoort and colleagues explicitly model atomic relative updates and field
access in their robustness analysis. The observed deposit loss illustrates a
specific distinction already visible in those models. The execution reads a
value whose change preserves the prepared increment.
[VLDB 2007](https://www.vldb.org/conf/2007/papers/industrial/p1263-jorwekar.pdf) · [LMCS 2023](https://lmcs.episciences.org/12744/pdf)

Nguyen and colleagues investigated advance inference of access sets across 111
open-source applications. Our tracer runs at preparation time, after inputs are
available, and tests reuse after an edit. The small paired grid adds evidence
about this decision on one historical rule revision. It supplies no estimate
of how often real applications can infer their access sets.
[PACMMOD 2025](https://doi.org/10.1145/3725268)
