# Dual-Model Non-Equivalence Review

Status: review packet frozen; model calls `NOT RUN`. The 45-case packet is
`dual_model_review_manifest.json`. Its associated byte-bound corpus input is
`corpus_freeze_input.json`; it remains unpromoted until both model dispositions,
the installed Hypothesis version, ordered seeds, and positive execution limits
are frozen.

Each candidate receives blinded invariant/fault definition, one-change diff, affected enforcement context, and test/reference-model semantics. Each model labels `NON_EQUIVALENT`, `EQUIVALENT`, `INVALID`, or `UNCERTAIN`. Only initially mutually `NON_EQUIVALENT`, or mutually `NON_EQUIVALENT` after one anonymous reconciliation round, may enter a locked mutation-score denominator. Remaining disagreement is `UNRESOLVED` and excluded transparently. This is dual-model non-equivalence review, not independent human review.

After promotion to `final_freeze.json`, execute only the fixed SOICT M0--M3
matrix with `python -m evaluation.property_assurance.soict_final_runner`.
