# Bi-temporal state arbitration comparator: mechanism mapping

## Status

**Mechanism-mapped comparator; not a claimed faithful Zhao implementation.**
The public source is Jianing Zhao et al., “Beyond Retrieval: Bi-Temporal State
Arbitration for Longitudinal Healthcare Agents,” KnowFM 2026, pp. 129–137,
[ACL Anthology PDF](https://aclanthology.org/2026.knowfm-1.10.pdf). The paper's
Algorithm 1 and four-operator table are sufficiently clear for a bounded
mechanism mapping, but not for a faithful end-to-end reproduction: the paper
does not provide the extraction model, semantic-equivalence implementation,
refinement merger, calibrated validation split, constraint code, or complete
state-graph schema. Direct empirical BTSA superiority/equivalence claims remain
prohibited.

## Code mapping

| Required mechanism | Code mapping | Explicit boundary |
| --- | --- | --- |
| Bi-temporal state unit (paper §3.1, Eq. 1, p. 131) | `valid_from/to` and `known_at`; `valid_at`/`known_at` query cutoffs | State graph and candidate object are represented by immutable event inputs; interval endpoint semantics are an implementation choice. |
| Event / valid time | `valid_from`, `valid_to`; `valid_at` query cutoff | The paper calls these `tevent`, `tvalid_start/end`; inclusive intervals are an implementation choice. |
| Ingestion / knowledge time | `known_at` on event and query | The paper's ingestion axis is mapped to `known_at`; events order by `(known_at, event_id)`. |
| SUPPORT (paper §4.1, pp. 132–133) | `relation="SUPPORT"` retains the matching candidate and history | Semantic equivalence threshold and confidence equation (2) are not claimed; no calibrated α/β/γ score is used. |
| REFINE (paper §4.1, p. 133) | `relation="REFINE"` requires an explicit target and preserves both event IDs | Qualifier merge and representative-value update are unspecified by pseudocode, so this comparator uses target replacement as a conservative mechanism mapping. |
| SUPERSEDE (paper §4.1, Algorithm 1, p. 133) | `relation="SUPERSEDE"` closes target and retains it in history | A successor is not implicitly inferred; caller supplies the new event and valid-time anchor. |
| BRANCH-CONFLICT (paper §4.1, pp. 133–134) | `relation="BRANCH-CONFLICT"` retains competing IDs and an explicit conflict set | Candidate confidence recomputation and domain constraints (§4.2) are not implemented. |
| Non-destructive history | `historical_ids` contains all known events | This is an in-memory mechanism, not a durable ledger. |

The paper's confidence formula (Eq. 2, p. 132) uses authority, normalized
recency, corroboration count and calibrated α=.5, β=.3, γ=.2. It is recorded
here as a **not implemented** deviation because the source does not define the
authority classifier, normalization horizon, independence test, or calibration
data. The paper's escalation tiers and θlow=.65/θvec=.72 (§5, pp. 133–134) are
also outside this comparator; they are retrieval/query policy, not arbitration.

## Excluded by design

No GST base-version mutation guard, consent, actor/purpose policy, THSS,
profile scope, source revocation, GLHS data model, API, or cache behavior is
implemented here. Those mechanisms must be evaluated separately and must not
be attributed to this comparator.

## Validation condition

`test_engine.py` validates each named operator and bitemporal cutoff. Before a
direct comparison is reported, record the source citation/version, reviewer,
paper-to-code section mapping, and a comparator version hash in a frozen
`comparator_manifest.json`.
