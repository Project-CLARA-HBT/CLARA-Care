# POPETS · independently executable study implementation book

**Paper:** Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts

**Proposed contribution:** Define *future dispatch noninterference* under consent revocation for every derivation path (prompt segment, cached summary, embedding pointer, retry payload, and fallback transport). Provide a dependency-closure invalidation algorithm and leakage audit that explicitly excludes information already delivered to any external provider.

**Literature gap and competing explanation:** Existing access control and cache invalidation can block future reads, and machine unlearning targets a different threat. A research gap exists only if persistent indirect derived context, retry queues, and fallback paths cause measurable post-revocation leakage that strong per-use reauthorization baselines miss.

**Three research questions**

**RQ1: Can any post-revocation model dispatch contain disallowed attributes through transitive caches or retries, even when direct record access is denied?**
**RQ2: Does origin- and purpose-labeled dependency closure match a full always-recompute authorized view on disclosure traces?**
**RQ3: What are cache hit, bytes transferred, re-computation, false invalidation and authorized utility costs at increasing lineage density?**

**Falsification criterion:** If complete per-dispatch authorization + recompute matches the candidate with negligible overhead and zero leakage, narrow novelty to an engineering performance trade-off; never assert erasure of prior external disclosures.

**Method architecture:** For grant g, purpose p, and dispatch d after revocation time t_r, require forbidden_label(g,p) ∩ lineage(d)=∅ under a declared observation model. Label derived artifacts at creation; invalidate reverse edges on revocation; reauthorize at every dispatch.

**Planned study population / resources:** Synthetic 1200 unique subjects with 3-6 longitudinal contexts each; factorial lineage fanout, delayed cache writes, retries, and policy changes; source-disjoint holdout; label N by subject not number of dispatches.

**Independent oracle:** Independent recomputation of all live-purpose permission clauses from source snapshots; byte-level dispatch interceptor and sealed cancellation log.

**Required metrics:** future unauthorized disclosure rate, attribute-exposure byte count, conditional cache hit rate, false invalidation rate, latency and rebuild cost, replay-path coverage

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | TTL-only cache | weak lower bound |
| B1 | coarse cache purge on consent change | strong simple safety baseline |
| B2 | always-recompute authorized projection per dispatch | privacy reference upper bound, cost comparator |
| B3 | Zanzibar-like consistency-token authorization + derived-cache tagging | strong architecture baseline if adapter truly supports derivations |
| B4 | proposed transitive provenance-label invalidation | candidate |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 4 tasks; see `PHASES/P03.md`.
- `P04`: 5 tasks; see `PHASES/P04.md`.
- `P05`: 4 tasks; see `PHASES/P05.md`.
- `P06`: 2 tasks; see `PHASES/P06.md`.
- `P07`: 2 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue popets` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/popets/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
