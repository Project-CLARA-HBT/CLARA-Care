# POPETS · Novelty Contract and Scope Register

> **Task:** `POPETS-scope` (P01, venue `popets`) · **Status:** signed register · **Version:** `1.0.0`
>
> **Base SHA:** `7ebdbbf0740e87ffebe3538d6893a53eaccf2216` · **Branch:** `research/venue2027/tasks/popets-scope`
>
> **Dependencies satisfied:** `SH-claim_overlap` (proof: `research/venue2027/proof/SH-claim_overlap.json`, status PASS) and `SH-literature_hardening` (proof: `research/venue2027/proof/SH-literature_hardening.json`, status PASS). No dependency was forged; both reports exist and record PASS with executed commands.

## 1. Paper title and target reader

**Paper title:** *Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts*

**Target reader:** A privacy-engineering and systems-security researcher at PoPETs who designs authorization, consent-management, or caching infrastructure for LLM-mediated health systems. Secondary readers: GDPR/consent-lifecycle engineers reasoning about data-subject rights after personal data has already been dispatched to model providers, and health-AI platform architects who must decide between coarse cache purges and finer-grained invalidation under revocation.

## 2. Claim-to-prior-work falsification matrix

Each claim states a falsifiable proposition and the prior work that would falsify it if that work
already demonstrated the proposition. Prior-work IDs use the verified ledger
`research/venue2027/_shared/literature_validity_ledger.csv` (all rows currently
`primary_source_read=false, status=UNVERIFIED` — relevance statements below are
therefore *background hypotheses to check*, not verified comparators) plus registry IDs from
`research/publication_registry.yaml` and `research/venue2027/_shared/publication_overlap_registry.yaml`.

| # | Claim (this paper) | Prior-work id(s) | What that work actually establishes | Falsification condition (claim dies if) |
|---|---|---|---|---|
| C1 | Post-revocation dispatches can leak revoked longitudinal attributes via transitive derived state (prompt-segment caches, cached summaries, embedding pointers, retry payloads, fallback transports) **even when direct record reads are correctly denied at the source boundary**. | `zanzibar19`; `openfga`; `cedar` | Consistency-aware permission evaluation and fine-grained ReBAC/ABAC at the *record-read boundary*; Zanzibar's zookies guard against stale *permission* reads, not stale *derived prompt/cache artifacts* re-dispatched to models. | Any ledger-verified system demonstrates enforcement across derivation paths for post-revocation *model dispatches* (not just record reads); or POPETS-rq_registry/POPETS-threat cannot exhibit a single reproducible transitive leak witness under a declared observation model. |
| C2 | Machine unlearning is a different threat: it aims at removing influence from trained weights, while this paper targets *future dispatches* of cached derived context after consent revocation, making no claim of retroactive erasure of already-delivered content. | `muse` | Distinguishes unlearning evaluation dimensions (knowledge, privacy, utility); its threat is influence removal from weights, not consent-lifecycle gating of downstream dispatches. | A ledger-verified work defines and enforces consent-revocation-time, dispatch-time noninterference for cached model contexts (not weight influence), collapsing C1+C2 into a known mechanism. |
| C3 | Origin- and purpose-labeled dependency-closure invalidation can match the disclosure behavior of a full always-recompute authorized projection on disclosure traces. | `zanzibar19` (newness check); `openfga`; `opa` | Rule-engine / ReBAC evaluation with consent encoded externally; no built-in temporal consent or derived-artifact lineage closure. | POPETS-prior finds a verified system that already performs transitive, purpose-labeled invalidation of derived model-context artifacts; or RQ2's independent oracle shows candidate ≢ always-recompute on the frozen confirmatory holdout. |
| C4 | Coarse cache purge on consent change is a strong simple safety baseline but pays measurable availability/latency/false-invalidation costs at increasing lineage density. | `fhir5` (FHIR Consent/AuditEvent structure only); `nistabac` (ABAC vocabulary) | Standards define consent and attribute structures but no cache-invalidation cost model; they do not claim or refute C4. | A verified cost analysis of consent-triggered cache purges for LLM context caches exists showing no meaningful trade-off; or RQ3 measurement finds the trade-off absent under the frozen protocol. |
| C5 | Scoped capability caveats alone do not provide revocation-complete dispatch gating because cached derivations outlive caveat checks at dispatch time. | `macaroons14` | Contextual caveat-bound capabilities; first-class attenuation, not longitudinal cache-lineage invalidation for model dispatches. | A verified extension of caveat-bound credentials demonstrably covers derived-artifact re-dispatch after revocation at equal lineage density. |
| C6 | Historical GLHS E15–E22 evidence **cannot** serve as evidence for any claim C1–C5 in this paper. | `glhs-journal` (`research/publication_registry.yaml`); GovRed `govred-rivf-2026`; GovMut `assurance-soict-2026` | GLHS: co-versioned disclosure-to-commit governance with `governed_read_to_proposal_to_write_correctness` endpoint. GovRed: `unauthorized_or_stale_commit_acceptance_and_prohibited_disclosure`. GovMut: `mutation_score`. None measures post-revocation future dispatch leakage through model-context caches. | Any manuscript draft of this paper cites E15–E22, GovRed, or GovMut numbers as new evidence; POPETS-overlap must then FAIL the audit. |
| C7 | The PoPETs study is disjoint from the PST study's endpoint. | `pst` (publication_overlap_registry); anti-salami matrix PoPETs–PST pair | PST measures forensic reconstructability and metadata inference from minimized audit receipts (post hoc); PoPETs measures re-disclosure of revoked longitudinal context to cached AI models (pre-dispatch, future-facing). | A merged analysis shows both papers measure the same quantity on the same trace surface; per the anti-salami matrix this would require merger into one manuscript. |
| C8 | The strongest competing explanation for any observed protection is *not* a new leak class but simply "per-dispatch authorization + recompute already suffices at negligible cost." | Blueprint falsification rule; B2 arm | The always-recompute authorized projection per dispatch is the privacy reference upper bound. | If B2 matches the candidate (B4) with negligible overhead and zero leakage on the frozen holdout, novelty narrows to an engineering performance trade-off (see §6 Decision logic). |

## 3. Research questions, endpoints, baselines, oracles, tests, falsification

Primary scientific unit throughout: **one unique synthetic subject history** (1200 unique subjects,
3–6 longitudinal contexts each; label N by subject, never by number of dispatches).

### RQ1 — Post-revocation transitive leakage

- **RQ:** Can any post-revocation model dispatch contain disallowed attributes through transitive caches or retries, even when direct record access is denied?
- **Primary endpoint:** future unauthorized disclosure rate per independent subject history (rate and attribute-exposure byte count of forbidden attributes reaching outbound dispatches after `t_r`), measured under a declared observation model.
- **Strongest competing baseline:** **B2 — always-recompute authorized projection per dispatch** (privacy reference upper bound; also cross-checked against B1 coarse cache purge on consent change and B3 Zanzibar-like consistency-token authorization + derived-cache tagging, per the blueprint baseline table).
- **Independent oracle:** independent recomputation of all live-purpose permission clauses directly from source snapshots (oracle code disjoint from candidate), plus a byte-level dispatch interceptor with a sealed cancellation log.
- **Statistical test:** McNemar's test on paired subject-level disclosure indicators (B4 vs B2) for the equivalence/screening comparison, with subject-clustered bootstrap CIs for the disclosure-rate contrast; no per-dispatch pseudo-replication.
- **Falsification condition:** if zero post-revocation leakage witnesses exist under any arm (including weak B0 TTL-only), or if B2's disclosure trace already equals the candidate's with no transitive/retry/fallback leak class the candidate removes, RQ1 has no distinct effect and C1 collapses to prior access-control capability.

### RQ2 — Semantic completeness of dependency-closure invalidation

- **RQ:** Does origin- and purpose-labeled dependency closure match a full always-recompute authorized view on disclosure traces?
- **Primary endpoint:** disclosure-trace equivalence to the always-recompute reference (B2) at the level of independent subject histories, jointly with the false invalidation rate (authorized context wrongly invalidated).
- **Strongest competing baseline:** **B3 — Zanzibar-like consistency-token authorization + derived-cache tagging** (strongest architecture baseline, conditional on the adapter genuinely supporting derivations; if the adapter cannot represent derived-artifact lineage, that fact is recorded and B3 is reported `NOT_RUN_EXTERNAL` rather than replaced by a custom toy under the same name).
- **Independent oracle:** the same source-snapshot recomputation oracle as RQ1, evaluating disclosure equivalence and false invalidation per subject history; oracle never imports candidate invalidation code (enforced by module isolation and reviewed in POPETS-threat).
- **Statistical test:** paired subject-level equivalence analysis — two one-sided tests (TOST) with pre-registered equivalence margin on the disclosure-indicator difference, and a sign test / Wilcoxon signed-rank on paired per-subject false-invalidation counts versus B3.
- **Falsification condition:** if the candidate's disclosure trace diverges from the always-recompute reference on the frozen confirmatory holdout beyond the pre-registered equivalence margin (any non-equivalence in either direction — over- or under-disclosure), or if the false-invalidation rate exceeds B3's beyond the margin, dependency closure is incomplete and C3 is falsified.

### RQ3 — Privacy–availability cost under lineage density

- **RQ:** What are cache hit, bytes transferred, re-computation, false invalidation and authorized utility costs at increasing lineage density?
- **Primary endpoint:** conditional cache hit rate (hits conditional on authorization) and p95 latency as a function of factorial lineage fanout, jointly reported with bytes transferred, rebuild cost, and authorized-context completeness.
- **Strongest competing baseline:** **B1 — coarse cache purge on consent change** (strong simple safety baseline that bounds the availability cost of the safety-first alternative; B2 supplies the pure cost comparator).
- **Independent oracle:** byte-level dispatch interceptor and sealed cancellation log (shared declared observation model with RQ1/RQ2), with replay-path coverage accounting reconciled against independently replayed dispatch schedules.
- **Statistical test:** two-way repeated-measures ANOVA (arm × lineage density) on conditional cache hit rate and p95 latency over subject histories, with subject-clustered bootstrap CIs on arm contrasts at each density level.
- **Falsification condition:** if B4 shows no measurable cost advantage over B1/B2 across the full factorial density grid (overlapping subject-clustered CIs on both conditional cache hit and p95 latency with no interaction effect), the trade-off claim dies and the contribution narrows to an engineering trade-off per the blueprint falsification rule.

## 4. One-paragraph scope and the truly distinct endpoint

This paper studies **revocation-complete future disclosure / re-disclosure of revoked longitudinal
context to cached AI models**: after a subject revokes consent at time `t_r`, every subsequent
outbound model dispatch — across prompt segments, cached summaries, embedding pointers, retry
payloads, and fallback transports — must satisfy `forbidden_label(g,p) ∩ lineage(d) = ∅` under a
declared observation model, with derived artifacts labeled at creation and reverse dependency edges
invalidated on revocation. The **truly distinct primary endpoint is the revoked-context
re-disclosure rate** — the rate and attribute-exposure byte volume of forbidden longitudinal
attributes reaching future model dispatches through transitive derived state — which is
**distinct from historical GLHS R4's** `governed_read_to_proposal_to_write_correctness` endpoint
(GLHS R4 binds reads to proposals to writes at the record boundary inside one co-versioned store;
it never measures what cached derivations re-disclose to models *after* revocation, and its
frozen E15–E22 runs are background, not evidence here). It is equally distinct from the other
eight 2027 venues: DSN (crash-consistency violation rate after fault injection), IFIP SEC
(replay acceptance rate across purpose/delegation lineage — admission of reused receipts, not
post-revocation dispatch content), ACNS (evidence-boundary coverage matrix, a SoK), COMPSAC
(forbidden commit rate under dependency-complete schedules — commit admission, not dispatch
disclosure), AIME (unsafe clinical action rate under consent/medication history changes —
clinical-content quality, not cache lineage), SACMAT (delegation conformance divergence
detection rate across policy engines), DIMVA (probing detection AUC at fixed false-positive
budget — detection, not prevention), and PST (forensic reconstructability score — post hoc
audit inference versus this paper's pre-dispatch future-facing control; the PoPETs–PST pair is
the anti-salami matrix's closest pair and is separated by the future-dispatch vs forensic-metadata
distinction). Secondary measurements shared with sibling studies (e.g., latency, bytes) are
declared shared context and never headline evidence.

## 5. Non-overlap declaration and archive-reuse refusal

**Declaration.** This study refuses to treat frozen historical evidence as new venue evidence.
Specifically:

1. **Frozen E15–E22 (parent GLHS runs) are not new evidence.** All GLHS E15–E22 results, the
   accepted HEALTHINF paper, GovRed (`govred-rivf-2026`) and GovMut (`assurance-soict-2026`)
   sealed outcomes are cited as background only. No figure, table, rate, or claim in this paper
   may derive from them. Any use of those numbers as new experimental results is an
   anti-salami violation that `POPETS-overlap` must fail.
2. **Independent inputs.** The primary evidence bundle is newly generated: `synthetic-popets-2027`
   (1200 unique synthetic subject histories, factorial lineage fanout, delayed cache writes,
   retries, policy changes, source-disjoint confirmatory holdout) frozen under a protocol that is
   finalized before holdout access. `reuses_archive: []` in
   `research/venue2027/_shared/publication_overlap_registry.yaml` is honored verbatim.
3. **Positive/adversarial control status.** Positive control: candidate mechanism compared against
   three or more strong baselines (B1, B2, B3; B0 as weak lower bound). Adversarial control:
   any attempt to present an overlapping published GLHS result as new evidence is refused and
   recorded as a blocked outcome, never silently dropped.
4. **No retroactive erasure claim.** Information already delivered to any external provider is
   explicitly excluded from every leakage audit; the paper claims post-revocation *future*
   leakage prevention only and prominently states that already-delivered content cannot be
   retracted. No claim of cryptographic retroactive erasure is made anywhere in this scope.

## 6. Decision

**Decision: GO**

**Justification.** (a) The five-part distinction test of `GATES/ANTI_SALAMI_REVIEW.md` passes:
different precise research question (post-revocation dispatch noninterference for cached model
context), different primary endpoint (`revoked-context re-disclosure rate` vs GLHS R4's
commit-binding correctness and every sibling venue's endpoint per §4), independently frozen
evaluation design (new synthetic-popets-2027 bundle, protocol-first holdout), material new
contribution (dependency-closure invalidation algorithm + byte-level dispatch leakage audit), and
candid citation duty toward `zanzibar19`, `macaroons14`, `muse`, `openfga`, `cedar`, `opa`, `fhir5`
(all currently UNVERIFIED in the ledger and therefore mandatory verification targets for
`POPETS-prior`, not pre-approved comparators). (b) The shared overlap registry records
`popets → reuses_archive: []` with a distinct RQ and endpoint, and `SH-claim_overlap` PASS
confirms salami and archive-reuse-as-new blocks are in force. (c) The GO is explicitly conditional
on the blueprint falsification rule: if B2 (always-recompute per dispatch) matches the candidate
with negligible overhead and zero leakage on the frozen holdout, novelty narrows to an engineering
performance trade-off and the paper must either reframe or the decision flips to NO-GO at
`POPETS-rq_registry` time. This conditionality is recorded here so downstream tasks inherit it.
