# Research provenance-only evidence signals

## Purpose

CLARA Research can expose auditable source metadata for verified claims when
`RESEARCH_EVIDENCE_SIGNALS_ENABLED=true`. The capability is additive and default
off. It replaces a prior heuristic which incorrectly turned retrieval metadata
into `GRADE` certainty and recommendation-strength labels.

## Output contract

Each `evidence_signals` item uses `research-evidence-signal-v1` and contains:

- `claim` and its verifier-derived `verification_status`;
- `source_binding`: `direct` only when the claim's own evidence reference
  resolves to a retrieved row, otherwise `unresolved`;
- `source_metadata`: bounded `source_id`, source type, configured trust tier,
  and publication/effective date from those directly resolved rows;
- `display_mode: professional_metadata_only` and an explicit non-GRADE notice.

The schema never contains a certainty percentage, `certainty`,
`recommendation_strength`, treatment recommendation, or an inferred quality
grade. An unresolved reference has an empty source list; it must not borrow the
best row from the broader corpus.

## Safety and rollout

The authoritative safety gate remains FIDES claim verification. This signal is
not a verifier, clinical recommendation, or policy override. End-user surfaces
ignore legacy GRADE/certainty fields as well as this professional metadata.

Enable first in a staging environment with the normal Research verification and
claim-trace flags. To roll back, set `RESEARCH_EVIDENCE_SIGNALS_ENABLED=false`
and restart the ML service. No stored state or migration is involved. The older
`RESEARCH_GRADE_ENABLED` setting is configuration-compatible only and cannot
re-enable the deprecated output.
