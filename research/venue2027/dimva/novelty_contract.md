# DIMVA-scope · Novelty contract (P01)

> **Purpose:** signed scope register for `DIMVA-scope` (venue `dimva`, phase `P01`), per `VENUES/dimva/TASKS/DIMVA-scope.md` and `AGENTS/EXECUTION_CONTRACT.md`.
> **Dependencies:** `SH-claim_overlap` PASS, `SH-literature_hardening` PASS (`research/venue2027/proof/`).
> **Contract version:** 1.0.0. **Failure semantics:** this file freezes questions, endpoints, oracles and falsification rules only; it claims no empirical result. Any number appearing later in DIMVA artifacts must derive mechanically from `artifacts/venue2027/dimva/<run_id>/manifest.json`.

## Title and target reader

**Title:** GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal Agent Events.

**Target reader:** the DIMVA core audience — intrusion-detection and malicious-activity researchers, plus security operators of multi-tenant clinical-AI gateways who must distinguish deliberate multi-step authorization-boundary reconnaissance from benign retry bursts while holding only privacy-minimized agent telemetry. The reader cares about detection quality at operationally bounded false-alarm budgets, generalization to unseen attack families and tooling changes, and what a detector can legitimately know when raw clinical content and label-leaking rejection reason codes are withheld.

## Scope paragraph

GovernanceTrace studies a synthetic multi-tenant health-AI deployment in which an adaptive adversary probes the authorization boundary with paced, multi-step campaigns — purpose hopping, receipt/lineage reuse, delegation abuse, permission-discovery sequences — while benign traffic contains legitimate retries, outage backlogs and latency spikes that mimic the same low-level event patterns. The detector may read only a minimal event schema (event kind, scoped actor/tenant/purpose, logical time, payload digest references); raw clinical content is never logged and rejection reason codes are masked in the primary leak-safe test, with the label-leaking effect of unmasking them disclosed only in a dedicated ablation. Evaluation uses independently generated multi-stage traces split by attack family and synthetic tenant, a campaign-intent oracle sealed against detector access, and a preregistered false-alarm budget; every scientific unit is an independent campaign or benign session, never a per-event pseudo-replication.

## Claim-to-prior-work falsification matrix

Prior-work ids below are taken verbatim from the verified ledger `research/venue2027/_shared/literature_validity_ledger.csv` (SH-literature_hardening output) and from `research/publication_registry.yaml` (archive study id `glhs-journal`). No invented ids are permitted; the structural test rejects unknown ids.

| Claim | Prior-work id | What prior work establishes | Falsification / refutation condition |
|---|---|---|---|
| C1 | agentdojo24 | Stateful prompt-injection attack/defense benchmark for tool agents; environment-level security evaluation, not an authorization-boundary campaign detector over audit telemetry | Falsified if a detector derived from agentdojo24 attack traces reaches campaign-level PR-AUC at our preregistered fixed false-positive budget on our family-held-out split; the contribution then collapses to an engineering integration and the paper is re-scoped |
| C2 | toolemu24 | LM-emulated sandbox with judge-validated risk taxonomy; simulated tool outcomes are not persisted authorization events and no false-positive-budgeted detection endpoint is defined | Falsified if toolemu24-style emulation is shown to already supply an equivalent campaign-detection metric at a fixed false-positive budget with unseen-family holdout |
| C3 | tauben25 | tau-bench scores final database state and policy following of tool agents; no probing-campaign notion and no temporal detection metric | Falsified if a tau-bench-derived evaluation yields equivalent unseen-family campaign detection at bounded false alarms; the endpoint is then not distinct and the claim is refused |
| C4 | injecagent24 | Benchmarks indirect prompt injections on tool-integrated LLMs; semantic injection families are not multi-step authorization-boundary probing campaigns | Falsified if its threat corpus plus a published detector matches our leak-safe campaign AUCPR at the fixed budget, collapsing the injection/probing boundary we rely on |
| C5 | sommer10 | Warns that ML intrusion detection memorizes environments and that unrealistic labels inflate results; motivates our cross-family holdout and reason-code masking | Premise refuted for this corpus if the masked-vs-unmasked reason-code ablation and the family holdout leave all arms statistically unchanged within the preregistered margin δ; masking must then be justified on privacy-minimization grounds alone, never on label-leak grounds |
| C6 | zanzibar19 | Consistency-aware global authorization service; a verification-time permission system with no temporal campaign-detection surface | Falsified if a published authorization platform ships a telemetry detector evaluated at a fixed false-positive budget with unseen-family holdout equal to ours |
| C7 | macaroons14 | Contextual-caveat capability tokens: enforcement happens at verification time; no detection-over-time endpoint exists in the mechanism | Falsified if caveat-style mechanisms are demonstrated to detect (not prevent) probing campaigns from minimal events at bounded false alarms |
| C8 | glhs-journal | Frozen GLHS E15–E22 dispatch-attestation and governance-integrity evidence: admission/prevention endpoints; E15–E19 attested on `sqlite:///:memory:`, E20 `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE` | Refused as new evidence in both directions: no E15–E22 number may be re-labeled as a DIMVA detection result, and no DIMVA detection result may be claimed as validating the archive's prevention claims |

## Research questions

Exactly three research questions are frozen here; operational estimands are handed to `DIMVA-rq_registry`. Margin δ and the numeric false-alarm budget are frozen before holdout unsealing, not asserted here.

### RQ1 — Detection under data minimization

- **Primary endpoint:** campaign-level PR-AUC (AUCPR) over independent attack campaigns, evaluated at a preregistered fixed false-positive budget expressed as false alarms per 1,000 benign sessions, with recall at that budget as co-primary summary. This is a detection metric computed over event streams, not a prevention or admission rate.
- **Strongest competing baseline:** B0 — static threshold on denied-request counts per sliding window; the strongest competing explanation is that benign retry bursts and outage backlogs already produce equivalent alarms by counting alone.
- **Independent oracle:** simulator ground truth (`truth.json` per `VENUES/dimva/CASE_MATRIX.md`): campaign intent and authorized-action labels adjudicated from scenario construction, never from the detector score or the gateway's final reason code; the oracle implementation must not import any candidate or baseline detector.
- **Statistical test:** paired per-campaign detection indicators at the fixed budget compared with McNemar's exact test (candidate vs B0), plus a 95% cluster bootstrap CI for the AUCPR difference, resampling independent campaigns as clusters.
- **Falsification condition:** if B0 matches the candidate's campaign AUCPR within margin δ at the fixed false-positive budget on the leak-safe split, we do not claim detection necessity for sequence modeling; and if the candidate's performance depends on attack-specific rejection reason codes — masking collapses it toward the label-shuffled control while unmasking alone restores it — the primary experiment is invalidated.

### RQ2 — Robustness to novel campaigns

- **Primary endpoint:** unseen-family recall and campaign-level PR-AUC under cross-family/cross-tenant holdout, with time-to-detect as the supporting measurement; in-distribution-to-holdout degradation is reported per held-out family.
- **Strongest competing baseline:** B3 — gradient-boosted trees on controlled leak-safe features, the strongest supervised comparator; B1 temporal rule/FSM signature is retained as the interpretable reference for the ML-necessity rule.
- **Independent oracle:** the same sealed simulator ground truth; holdout family and tenant membership is frozen before any holdout access, and labels are never derived from detector output or gateway decisions.
- **Statistical test:** stratified cluster bootstrap (clusters are independent campaigns within held-out families) for recall and AUCPR differences vs B3, with a paired family-level comparison of time-to-detect.
- **Falsification condition:** if rule-based arms (B0/B1) perform as well as sequence models on family-held-out traces within δ, we do not claim ML necessity; if unseen-family recall is statistically indistinguishable from a label-shuffled control, the generalization claim fails and the result is reported as a negative outcome.

### RQ3 — Adaptation and privacy cost

- **Primary endpoint:** adaptive evasion success — the fraction of adaptive campaigns undetected at the fixed false-positive budget — and bytes of retained sensitive metadata under escalating minimization budgets, both measured at equivalent budgets across arms.
- **Strongest competing baseline:** B1 — temporal rule sequence / finite-state signature; interpretable rules are the strongest competing explanation for any apparent pacing robustness, so the candidate must beat them, not merely survive.
- **Independent oracle:** simulator-known attack pacing and ground-truth campaign intent (adversarial fixtures in the spirit of `DIMVA-CASE-05`/`DIMVA-CASE-07`); metadata retention is measured against the frozen minimal-schema cap, never self-reported by the detector.
- **Statistical test:** paired bootstrap at matched false-positive budget for the evasion-success difference (candidate vs B1), plus a paired comparison of retained-metadata bytes across minimization budgets with family-clustered CIs.
- **Falsification condition:** if adaptive pacing reduces candidate detection to or below the strongest baseline at matched budget, the adaptive-robustness claim is refused; if detection holds only at minimization budgets that retain sensitive metadata beyond the frozen cap, the privacy-compatible detection claim fails.

## Strong baseline set

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | static threshold on denied-request counts per sliding window | strong operational baseline; strongest competing explanation for RQ1 |
| B1 | temporal rule sequence / finite-state signature | strong interpretable baseline; pacing-robustness reference for RQ3 |
| B2 | Isolation Forest on privacy-minimized counts | unsupervised anomaly-detection comparator |
| B3 | gradient-boosted trees with controlled leak-safe features | strongest supervised comparator for RQ2 |
| B4 | sequence model with time-aware features | candidate family; admitted only if it shows holdout gain over B0–B3 |

All arms must use pinned real upstream implementations where available, with fidelity vectors, equal data access and equal compute budget. `NOT_RUN_EXTERNAL` is a permitted transparent status, but it blocks any comparative claim against that arm.

## Distinct contribution and endpoint

The distinct contribution is GovernanceTrace: a privacy-constrained sequence detector that identifies adaptive authorization-boundary probing campaigns from minimal agent events — event kind, scoped actor/tenant/purpose, logical time, payload digest references — with no raw clinical content and no rejection reason codes in the primary test, and with generalization measured on unseen attack families and tooling changes. The truly distinct endpoint is campaign-level probing detection AUC (PR-AUC) at a fixed false-positive budget: a temporal detection metric over event streams. No sibling venue, prior work, or archive result in the matrix above uses this endpoint. The strongest competing explanation that the study must defeat is that trivial counting over benign retry bursts, outages and latency spikes (B0) explains the alarms, and that any apparent generalization is environmental memorization (sommer10); if the candidate does not beat that explanation on family-held-out, leak-safe data, the paper reports negative results instead of an ML-necessity claim.

## Non-overlap: IFIP SEC (prevention) vs DIMVA (detection)

The 2027 sibling study `ifip_sec` (registered in `research/venue2027/_shared/publication_overlap_registry.yaml` and `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`) is a *prevention* study: replay-closed authorization across purpose, delegation and AI proposal lineage, with primary endpoint "replay acceptance rate across purpose/delegation lineage". DIMVA is a *detection* study: it does not strengthen verification and never decides a single request's admission. The matrix fixes the boundary: "IFIP/DIMVA: One prevents invalid tokens at verification, one detects campaigns over time, measured on independent detectors and event streams." Four-part distinction: (1) research question — does verification-time replay closure prevent authorized-looking replay vs can probing campaigns be detected from telemetry; (2) unit of analysis — one authorization request/receipt vs one multi-event campaign; (3) primary endpoint — replay acceptance rate vs campaign-level PR-AUC at a fixed false-positive budget; (4) artifacts — receipt/consumed-once mechanism and replay threat corpus vs the GovernanceTrace minimal event schema, detector and synthetic campaign set. Only repository background and governance vocabulary are shared, and they are cited, not cannibalized.

## Archive refusal: frozen GLHS E15–E22 are not new evidence

The frozen GLHS E15–E22 evidence (registry study `glhs-journal`, `research/glhs_journal/q4_r4/release/`) is background only, and this study refuses to present any of it as new DIMVA evidence, per `GATES/ANTI_SALAMI_REVIEW.md` rule 5. E15–E22 measured dispatch-attestation integrity, comparator decision safety, witness and state-space checks and offline reproducibility — admission/prevention endpoints of a governance contract, not detection endpoints over event streams. Additionally, `CONTEXT/SOURCE_AUDIT_2026_11_14.md` attests that E15–E19 ran on `sqlite:///:memory:` and E20 was `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`, so those frozen numbers cannot even support PostgreSQL-specific concurrency claims, let alone campaign-detection claims. The accepted HEALTHINF work is likewise disclosed background, cited where relevant and never silently reused. No number from the archive appears in this contract, and none may appear in DIMVA results.

## Decision: GO

Decision: GO

Rationale: both dependencies (`SH-claim_overlap`, `SH-literature_hardening`) are PASS; the shared overlap registry declares a distinct dimva research question and endpoint with `reuses_archive: []`; and the five-part anti-salami distinction test passes — distinct question (detection vs prevention/replay), distinct primary endpoint (campaign PR-AUC at fixed false-positive budget), independently frozen evaluation design (`VENUES/dimva/CASE_MATRIX.md`), a material new artifact (minimal-event campaign detector plus synthetic campaign corpus), and candid citation of the closest prior work above. Conditions: this GO stands only under the preregistered falsification rules above; negative outcomes are reportable results, and any breach — holdout unsealed early, oracle importing candidate code, or reason-code leakage entering the primary test — converts this contract to NO-GO pending re-scoping.
