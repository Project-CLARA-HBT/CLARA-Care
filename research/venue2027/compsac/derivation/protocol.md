# Dependency derivation development protocol

Freeze before running either grid. The estimand is the decision to reuse a
detached proposal after an edit. Exact finite enumeration, no sampling or timing.
Keep individual predictions including every tie and loss. All state is synthetic.

## SmallBank

Use the pinned three-procedure Python SQL port and schema in the experiment
reported at 73b5c897. Run its plain SQL branch on a fresh in-memory SQLite
database with placeholder translation. Fixed existing customer, immutable name
and key. Observe SQLite's statement-authorizer balance-column reads (including
reads in incremental updates) during preparation. The manually written template
has access to the entire procedure: deposit requires no previous balance for its
fixed increment, withdrawal depends on savings, check on checking and savings.
Both reject when any watched coordinate changes. Independently compute the
business result (refusal or target and signed increment) before and after from
BenchBase semantics. Replay the actual procedure on both states and verify results
against this specification. Enumerate the full ordered product of starting and
ending balances, savings in {0,21}, checking in {0,6}, for each procedure.
The reuse target is an incremental instruction, not a replacement balance.

## LifeMap proposal registry

Use the actual validate_model_proposals functions from f7a33fd4 and 2977d152.
The newer endpoint binds each referenced revision to its authorized field.
One fixed admissible review proposal per unordered pair among three synthetic IDs,
same valid field, source and relation. Start with all three authorized and bound to
the matching field. Vary each ID's membership and field-match bit independently
across all 64 ending states. An absent member's stored field is invisible to the
validator. Treat a pair's proposal as valid iff ordinary uninstrumented replay
on the edited registry still yields the original finding. Also cross-check this
label against the independent membership/binding predicate.

Derive dependencies at preparation by recording membership probes during subset
comparison and mapping lookups in the running validator. No revision-indexed
edge list in the recorder. Both manual templates see the same code, versions,
proposal IDs and coordinate granularity. The maintained template watches each
referenced membership, adding each referenced field under the new rule. A
separate revision-lag control always uses the original template. Prepare and
validate under the same code revision within a pair: revision lag refers only
to metadata maintenance. Count newly required manual template clauses separately
from decision errors. No estimate of human effort.

## Reporting

Report false admissions / invalid edits, false rejections / valid edits and
paired correctness wins, ties and losses for derived vs maintained manual by
procedure and revision. On the second revision also compare to lagged manual.
Persist input states, observed dependencies, labels and arm decisions. Unexpected
oracle or replay disagreements are experiment failures and must be disclosed.
No live endpoint, patient, clinical action, database server or concurrent commit.
The units share code and states, so report counts without inferential intervals.
