# SACMAT P01 · Publication and Evidence Isolation Audit (SACMAT-overlap)

- **Task:** `SACMAT-overlap` (Phase P01, venue `sacmat`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Paper:** *PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous
  Policy Engines*
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/sacmat/novelty_contract.md` (§3 non-overlap declaration, signed GO),
  `research/venue2027/sacmat/threat_model.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml` (`audit_ok: true`),
  `research/venue2027/_shared/study_claims.json`,
  `research/publication_registry.yaml`,
  `research/venue2027/CONTEXT/SOURCE_AUDIT_2026_11_14.md`.
- **Document gate:** this audit validates against the shared overlap-audit contract
  `research/venue2027/_shared/tools/overlap_contract.py` (`OVERLAP_AUDIT_VERSION 1.0.0`) via
  `overlap_contract.py research/venue2027/sacmat/overlap_audit.md --venue sacmat`
  (log: `research/venue2027/proof/logs/SACMAT-overlap.validator.log`).
- **Executable check:** `research/venue2027/_shared/tools/claim_overlap.py` over
  `research/venue2027/_shared/study_claims.json`: the `sacmat` entry shares no question+endpoint
  pair with any other venue and declares `reuses_archive: []`
  (report: `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).

## 1. Comparison against all eight sibling 2027 venues

The SACMAT study asks whether **heterogeneous policy engines agree once consent delegation has a
history**: two engines that return identical decisions on isolated single requests may still diverge
when grant→revoke→regrant ordering, delegation expiry, purpose narrowing, and replay are ordered in
an `(policy history, request)` unit. PolicyTrace contributes a portable four-valued reference oracle
(PERMIT / DENY / NOT_APPLICABLE / INDETERMINATE), a trace-level temporal metamorphic test generator,
and adapters that replay identical histories into Cedar, OpenFGA and OPA. Its primary endpoint is
the **delegation conformance divergence detection rate** (registry wording), on the frozen dataset
`synthetic-sacmat-2027`. No other 2027 track shares that question or endpoint:

| Sibling venue | Question focus | Primary endpoint | Shared with SACMAT? |
|---|---|---|---|
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — transactional write-admission benchmark on one database; SACMAT executes no write schedules and admits no commits, it replays policy histories into engines |
| PoPETs 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy surface for cached AI context after revocation; SACMAT measures no disclosure, cache, or model-dispatch outcome |
| AIME 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate under consent/medication history changes | No — task-level clinical appropriateness; SACMAT claims no clinical result (novelty contract §3.1) |
| IFIP SEC 2027 (`ifip_sec`) | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — admission-mechanism prevention endpoint (contrast in §4); SACMAT proposes no mechanism and measures no acceptance rate |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — literature-coding SoK with no executed system; SACMAT executes real engines and codes no corpus of papers |
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — durable-state recoverability; SACMAT injects no storage faults and journals nothing |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over agent event streams (contrast in §4); SACMAT runs no detector and sees no telemetry |
| PST 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc audit inference; SACMAT performs no forensic reconstruction and minimizes no audit trail |
| SACMAT 2027 | Temporal conformance testing of delegated consent across heterogeneous policy engines | delegation conformance divergence detection rate | (self) |

The machine-readable registry (`_shared/publication_overlap_registry.yaml`, `audit_ok: true`)
records `sacmat` with `research_question: "Does temporal conformance testing detect
delegated-consent divergence across heterogeneous policy engines?"`, the endpoint above, dataset
`synthetic-sacmat-2027`, and `reuses_archive: []`. The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns zero findings involving sacmat: no
`SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no `SHARED_RESEARCH_QUESTION`,
and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness on one store | Different question (single-system governance binding, not cross-engine conformance). R4's frozen E15–E22 protocols measure dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, and reproducibility — none measures cross-engine decision parity on delegated-consent histories. Historical E15–E19 backend attestation is `sqlite:///:memory:` (source audit 2026-11-14), so those runs validate no real-backend claim anywhere, and PolicyTrace makes no database-backend claim at all |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; unauthorized/stale commit acceptance | Different surface entirely (disclosure→mutation→commit drift across the real boundary). `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — SACMAT does not reuse that frozen evidence; GovRed measures no policy-engine conformance and contributes no history corpus case |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score on the sealed W8 45-mutant corpus | The declared anti-salami pair for this venue — full contrast in §3 |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `frozen_manifest: NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: AIME/HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work and cited as background per anti-salami rule 4, never silently cannibalized; its governance-correctness numbers are motivation only and are never SACMAT evidence |

The other potential merge/alternative pairs recorded in `ANTI_SALAMI_REVIEW.md` that do not involve
SACMAT (DSN–COMPSAC, PoPETs–PST, IFIP SEC–ACNS, IFIP SEC–DIMVA, AIME–HEALTHINF) do not touch the
SACMAT claim surface; the SACMAT-adjacent contrasts are resolved in §3 and §4.

## 3. SACMAT–GovMut contrast: authorization semantics vs mutation-testing adequacy

`ANTI_SALAMI_REVIEW.md` records **SACMAT–GovMut (authorization semantics vs mutation-testing
adequacy)** as a potential merge/alternative-route pair, and `PREVIOUS_ANTI_OVERLAP_MATRIX.md`
fixes the control: *"PolicyTrace measures authorization semantic conformance and portability.
GovMut measures testing strategies' fault-detection mutation scores. None of the W8 45-mutant
scores can be new PolicyTrace results."* This audit refuses the merge on the four separations of
`novelty_contract.md` §3.2:

1. **Different unit of analysis.** GovMut: mutant × testing strategy on a single stateful
   health-AI governed store. PolicyTrace: `(policy history, request)` × engine encoding, replayed
   across Cedar, OpenFGA and OPA. GovMut's scientific object is a sealed mutant corpus and adequacy
   scores; PolicyTrace's scientific object is a portable history corpus, a four-valued reference
   oracle, and cross-engine decision parity.
2. **Different direction of inference.** GovMut infers *test-suite adequacy*: which established
   strategies detect which sequence-sensitive governance faults. PolicyTrace infers *semantic
   conformance and portability*: where heterogeneous engines disagree on identical delegated-consent
   histories. Fault detection appears in SACMAT (RQ1/RQ2) only as the measurement mechanism against
   **new** mutants designed for this study — it is never a claim about the adequacy of established
   testing strategies.
3. **No corpus transfer.** GovMut's sealed W8 45-mutant corpus, its scores, and the GLHS R4
   E15–E22 outcomes are not inputs, baselines, or comparanda anywhere in this study. SACMAT's
   RQ2 mutation-score endpoint is computed over a **new** 50-mutant corpus designed against the
   F01–F05 temporal fault families with reserved fresh holdout families, authored by reviewers
   without access to candidate implementation outputs — the shared word "mutation score" does not
   make the corpora, the systems under test, or the questions the same.
4. **Anti-salami pair control.** If a future reviewer cannot defend the authorization-semantics vs
   mutation-testing-adequacy split, SACMAT is converted to a Dataset/Tool-track tool paper or
   merged — never repackaged as a second adequacy benchmark.

## 4. SACMAT-adjacent contrasts: IFIP SEC prevention and DIMVA detection

- **IFIP SEC 2027 (prevention) vs SACMAT (conformance measurement).** IFIP SEC proposes a
  replay-closed *admission mechanism* and scores it by the replay acceptance rate across
  purpose/delegation lineage on executed adversarial schedules. SACMAT proposes no mechanism: replay
  appears only as one ordered-event class inside synthetic histories fed identically to every
  engine, and the measured quantity is cross-engine decision non-parity, not attack admission. A
  prevention rate for a mechanism is not an engine-conformance divergence rate, and vice versa.
- **DIMVA 2027 (detection) vs SACMAT (testing).** DIMVA detects adaptive authorization-boundary
  probing campaigns from minimal agent event telemetry (probing detection AUC at a fixed
  false-positive budget, held-out attacker families). SACMAT runs no detector, consumes no event
  streams, and trains nothing; its observations are engine decisions on frozen policy histories.
  Both studies touch the authorization boundary, but one watches live traffic for attackers and the
  other replays frozen histories into engines — no detector, campaign, or telemetry artifact flows
  between them.

## 5. Artifact reuse table

`reuses_archive: []` is enforced both by the registry declaration and by the executable audit.
Every row states what SACMAT actually reuses and what is uniquely new:

| Artifact | Purpose in SACMAT | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic 64-subject cohort *concept* (medication/allergy/history/consent governance domain model) | Motivating context only (why delegated-consent conformance matters in health AI) | Context for RQ1–RQ3 | No — GLHS schedules, attack classes A01–A16, and case IDs are not executed, re-scored, or cited as SACMAT evidence | No | No | No — GLHS endpoints (governed read-to-proposal-to-write correctness) are not cross-engine conformance | New synthetic policy-delegation history corpus (`synthetic-sacmat-2027`) with grant→revoke→regrant, delegation-expiry, purpose-narrowing and replay orderings |
| Frozen parent GLHS E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No — see §6 refusal; E15–E22 outcomes are never presented as SACMAT results | — (citation only) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — unauthorized/stale commit acceptance is a different endpoint family | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work (§3); never an input, baseline, or comparandum | Background | No — no W8 mutant, score, or fault class enters any SACMAT arm | No | No | No — adequacy of established testing strategies is a different question | New 50-mutant corpus designed against the F01–F05 families, with reserved fresh holdout families |
| CareGuard-VN registry entry | Disclosed as NOT_RUN related work | Background | No | No | No | No — no frozen CareGuard evidence exists at all | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No — co-versioned governance protocol, not engine conformance | — |
| `xacml18` (B1), `xacbench20` (B2), property-based history generator (B3), uniform random requests (B0); `zanzibar19`, `cedar`, `openfga`, `opa`, `nistabac` | Baseline arms and pinned upstream engine/semantics sources | RQ1–RQ3 | No | No | No | No — comparators and execution targets, not reused results | Equal-oracle-call-budget comparison protocol; per-construct expressibility labeling (INDETERMINATE for untranslatable constructs) that no upstream suite provides |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any historical
or sibling 2027 study is reused as SACMAT evidence. All SACMAT claims must derive mechanically from
`artifacts/venue2027/sacmat/<run_id>/manifest.json` produced by this study's own frozen protocol.

## 6. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new independent
evidence in the SACMAT 2027 study, in any section, table, figure, corpus row, or statistical
test.** They are background and motivation only. Concretely, this audit refuses: (a) counting any
frozen E15–E22 outcome as a SACMAT result or as a `(policy history, request)` corpus case — per the
anti-salami gate, the same E15–E22 data, GovRed results, and GovMut results cannot count as any of
the nine independent 2027 results; (b) reusing R4's SQLite-era observations as real-engine
evidence — per `SOURCE_AUDIT_2026_11_14.md`, historical E15–E19 runs attested `sqlite:///:memory:`
backends, so they cannot support any executed-engine claim, and PolicyTrace additionally makes no
database-backend claim at all; (c) reusing GovRed (RIVF) or GovMut (SOICT) frozen studies as SACMAT
results — in particular, no W8 45-mutant score can be a new PolicyTrace result (§3); (d) citing the
accepted HEALTHINF paper's numbers as independently generated SACMAT evidence. Evidence for every
SACMAT claim must derive mechanically from this study's own frozen protocol artifacts. This refusal
is a binding condition inherited by all downstream SACMAT tasks (`novelty_contract.md` §3.3).

## 7. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut/CareGuard, per the five-part
distinction test: (1) the **portable four-valued reference oracle** (PERMIT / DENY /
NOT_APPLICABLE / INDETERMINATE) defined from a declarative semantics document maintained separately
from all candidate code — no cited prior work provides it; (2) the **trace-level temporal
metamorphic test generator** with bounded depth/delegation-hop budgets and minimal failing-witness
minimization; (3) **Cedar/OpenFGA/OPA conformance adapters** with pinned upstream versions and
per-construct expressibility labels; (4) a **new independently designed 50-mutant corpus** keyed to
the F01–F05 temporal fault families with reserved fresh holdout families, ground-truthed by
reviewers blind to candidate outputs; (5) the **equal-oracle-call-budget comparison protocol**
against B0–B3 with pre-registered falsification conditions (RQ1/RQ2 claims are surrendered if B1/B3
parity holds). Sharing the repository and background methods with prior work is acceptable;
repackaging the same primary experiment is not done here.

## 8. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over `_shared/study_claims.json`
returns ok with zero findings involving sacmat — no other 2027 venue shares SACMAT's
question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The shared `overlap_contract.py`
validator accepts this document against all eight sibling venues and the five historical
comparators. (3) The declared SACMAT–GovMut merge pair (authorization semantics vs mutation-testing
adequacy) is refused by the four separations of §3, with the W8 corpus contractually excluded; the
IFIP SEC prevention and DIMVA detection contrasts are resolved in §4. (4) The artifact reuse table
(§5) shows no reused raw case IDs, labels, figures, or endpoints; all extension evidence is new.
(5) Frozen E15–E22 outcomes are explicitly NOT reused as new independent evidence (§6), matching
the negative gate "Same E15–E22 outcome rebranded" — which does not occur. No duplicate primary
claim or data presented twice as new exists; the pass gate "PASS or explicit alternative-venue
merger" is satisfied by PASS.
