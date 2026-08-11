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
