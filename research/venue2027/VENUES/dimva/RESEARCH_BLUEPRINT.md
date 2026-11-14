# DIMVA · independently executable study implementation book

**Paper:** GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal Agent Events

**Proposed contribution:** A *privacy-constrained sequence detector* distinguishing benign retry bursts from deliberate multi-step policy/receipt boundary reconnaissance; generalization measured on unseen attack families and tooling changes.

**Literature gap and competing explanation:** AgentDojo and ToolEmu provide realistic agent safety attacks; IDS literature warns models can memorize environments. Novelty demands detector evaluation on independently generated multi-stage traces with constrained PHI metadata and rigorous cross-family holdout, rather than training on rejection reason codes that trivially reveal labels.

**Three research questions**

**RQ1: Can a detector identify attack campaigns from PHI-minimized events at bounded benign false alarms, without using attack-specific reason-code leakage?**
**RQ2: How does cross-family/cross-tenant holdout change precision-recall and time-to-detect relative to rule-based, IsolationForest, boosted-tree and sequence models?**
**RQ3: How do adaptive attacker retries and privacy budgets affect detection and diagnostic reconstruction?**

**Falsification criterion:** If rule thresholds perform as well as sequence models on family-held-out traces, do not claim ML necessity; if detector depends on post-hoc failure labels, invalidate primary experiment.

**Method architecture:** Derive minimal log schema independent of raw patient data; split by attack family and synthetic tenant; keep rejection codes masked in leak-safe primary test, then disclose effect of allowing them in an ablation.

**Planned study population / resources:** Multi-stage synthetic sessions plus benign retries, outages, latency spikes; attacker cannot read privileged logs; frozen family-holdout groups with no shared templates across train/test.

**Independent oracle:** Campaign intent and authorized action adjudicated from simulator ground truth, never from detector score or gateway final reason code.

**Required metrics:** campaign-level AUCPR, false alarms per 1000 benign sessions, time-to-detect, unseen-family recall, bytes of retained sensitive metadata, adaptive evasion success

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | static threshold on failures per window | strong operational baseline |
| B1 | temporal rule sequence / finite-state signature | strong interpretable baseline |
| B2 | Isolation Forest on privacy-minimized counts | unsupervised comparator |
| B3 | gradient-boosted trees with controlled features | supervised comparator |
| B4 | sequence model with time-aware features | candidate; only if holdout gain |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 7 tasks; see `PHASES/P02.md`.
- `P03`: 3 tasks; see `PHASES/P03.md`.
- `P04`: 4 tasks; see `PHASES/P04.md`.
- `P05`: 4 tasks; see `PHASES/P05.md`.
- `P06`: 3 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue dimva` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/dimva/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
