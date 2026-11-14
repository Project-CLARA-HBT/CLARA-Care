# ACNS · independently executable study implementation book

**Paper:** SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems

**Proposed contribution:** An evidence-to-claim lattice for assembly, egress, transport acknowledgment, provider-attested receipt, execution trace and semantic consumption, with mechanized *counterexample witnesses* showing which implications fail absent explicit trust assumptions.

**Literature gap and competing explanation:** Existing cryptographic attestation terminology (IETF RATS) and agent safety benchmarks address related but nonidentical assurance claims. A SoK contributes only if its systematic taxonomy is reproducible, independently double-coded and resolves real disagreements, not if it rebrands provenance as new.

**Three research questions**

**RQ1: Which attestation claims are actually supported by which observable evidence and trusted parties in published agent systems?**
**RQ2: Which claimed implication pairs are invalid under explicit adversarial and provider models, and can small executable witnesses demonstrate this?**
**RQ3: How consistently can independent reviewers classify claims and reproduce counterexamples across a pre-registered corpus?**

**Falsification criterion:** If taxonomy fails coder agreement or merely restates RFC 9334 / existing provenance literature without new cases and insights, do not claim SoK contribution.

**Method architecture:** Define observation/trust axes, mechanically enumerate implication candidates, construct counterexamples for false implications, and publish extraction rules and independently adjudicated study selection ledger.

**Planned study population / resources:** Search ACM/IEEE/USENIX/NDSS/ICLR/NeurIPS publications from pre-registered 2019-2026 window; freeze duplicate resolution, screening decisions and extraction workbook.

**Independent oracle:** Independent dual human coders; no internal LLM agents represented as independent reviewers.

**Required metrics:** inter-rater Cohen kappa, ambiguous claim fraction, counterexample reproduction rate, coverage of evidence-strength lattice, disagreement resolution rate

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | RFC 9334/RATS attestation evidence framework | normative taxonomy baseline |
| B1 | W3C PROV provenance and audit events | retrospective lineage baseline |
| B2 | AgentDojo/ToolEmu evidence and attack observability categories | empirical study taxonomy |
| B3 | two independent human-coded new taxonomy | candidate SoK; needs actual reviewers |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 6 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 2 tasks; see `PHASES/P03.md`.
- `P04`: 5 tasks; see `PHASES/P04.md`.
- `P05`: 5 tasks; see `PHASES/P05.md`.
- `P06`: 2 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 5 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue acns` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/acns/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
