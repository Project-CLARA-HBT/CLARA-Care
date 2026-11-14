# SACMAT · independently executable study implementation book

**Paper:** PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines

**Proposed contribution:** A *history-sensitive conformance property* for delegated consent and purpose-bound access with trace-level metamorphic test generation and independent oracle adjudication across Cedar, OpenFGA and OPA encodings.

**Literature gap and competing explanation:** MC/DC XACML policy testing and XACBench cover static policy structures; what must be demonstrated as new is systematic conformance testing of policy *histories* with revocation/redelegation and replay, including portability failures attributable to mismatched semantics.

**Three research questions**

**RQ1: Which distinct trace-level policy errors are undetected by static rule/decision coverage but exposed by temporal metamorphic tests?**
**RQ2: How many executable mutants representing revocation, delegation, purpose and temporal precedence are killed by comparable budgets for random, MC/DC-inspired and PolicyTrace generation?**
**RQ3: Across Cedar, OpenFGA and OPA, which semantics are faithfully expressible, and where do adapters necessarily diverge?**

**Falsification criterion:** If trace generator does not outperform stateful and MC/DC-guided baselines at equal oracle-call budget, do not claim novel fault detection; publish portability limits transparently.

**Method architecture:** Define a portable three/four-valued decision oracle (PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE) and a partial mapping to each PDP; test revocation-before-replay, delegation expiration, explicit-deny precedence and temporal reorderings.

**Planned study population / resources:** Versioned synthetic policy and principal graphs + 50 independently designed mutants; reserve fresh holdout mutant families; source/seed freeze prior to scoring.

**Independent oracle:** Executable declarative reference semantics and independent human review of semantically non-equivalent mutants.

**Required metrics:** mutation score at fixed oracle budget, trace witness detection coverage, policy-engine disagreement, invalid/indeterminate parity, generation runtime, minimal failure trace length

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | uniform random authorization requests | weak reference |
| B1 | MC/DC-inspired XACML policy testing (Xu et al. SACMAT 2018) | strong coverage baseline |
| B2 | XACBench policy profile–driven synthetic tests | strong benchmark baseline |
| B3 | property-based history generator without temporal metamorphs | strong stateful testing baseline |
| B4 | PolicyTrace temporal generator plus oracle | candidate |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 5 tasks; see `PHASES/P03.md`.
- `P04`: 4 tasks; see `PHASES/P04.md`.
- `P05`: 5 tasks; see `PHASES/P05.md`.
- `P06`: 2 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue sacmat` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/sacmat/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
