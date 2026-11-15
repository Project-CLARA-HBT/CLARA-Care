# DIMVA-X05_rules_detector · B1 static cross-scope denial signatures: formalization and measured weakness

> **Task:** `DIMVA-X05_rules_detector` · **Phase:** `P03` · **Venue:** `dimva` · **RQ:** `RQ1` (primary falsification surface), `RQ2`, `RQ3`
> **Paper:** *GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal Agent Events*
> (`research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md`; task contract
> `research/venue2027/VENUES/dimva/TASKS/DIMVA-X05_rules_detector.md`).
> **Arm formalized here:** blueprint arm **B1** — *temporal rule sequence / finite-state signature*,
> realized in this worktree as the **static cross-scope denial signature** (registry entry
> `temporal-rule-sequence-signature`, arm id `B1` in
> `evaluation/venue2027/dimva/baselines.py::BASELINE_REGISTRY`, fidelity `in-project interpretable baseline`).
> **Implementation (reused, not forked):** `evaluation/venue2027/dimva/baselines.py`
> (`BASELINES_VERSION = "1.0.0"`), entry points `run_baseline("B1", case, ctx) -> Outcome` and
> `run_baseline_detection("B1", case, ctx) -> DetectionDecision`. The DIMVA-baselines task already
> delivered the B1 evaluator (`_evaluate_b1`); this task formalizes its semantics, locks its operating
> point, measures its real detection counts on a synthetic event stream, and documents — with an
> executed negative control — **why the rule family structurally misses low-and-slow campaigns**.
> **Test driver:** `research/venue2027/dimva/tests/test_x05_rules_detector.py` (imports the REAL
> baseline module; never re-implements or stubs the algorithm).
> **Status:** formalization + executable measurement on deterministic synthetic events only; no live
> workload, no PHI/PII, no network, no hidden clock or randomness. Every number quoted below under
> "Measured behavior" is asserted by the test driver.

---

## 1. Scope and role of the arm

B1 is the blueprint's *strong interpretable baseline*: a deterministic, hand-authored rule over
ordered minimal events with **no learned parameters**. Its scientific roles are fixed by the
blueprint and the literature matrix:

- **RQ1 falsification surface (with B0):** if B0/B1 match the candidate's campaign-level AUCPR on
  family-held-out traces, no sequence-modeling necessity is claimed; the negative result is reported
  instead.
- **RQ3 pacing-robustness reference:** B1 is the strongest competing explanation for any apparent
  adaptive-robustness gain, so its miss modes must be measured, not assumed.
- **Interpretability anchor:** every alarm carries the exact structural counts
  (`cross_scope_followups`, `total_denials`, `horizon_seconds`) that produced it — an operator can
  audit the rule without a model card.

The candidate arm (blueprint B4, campaign-level linkage with time-aware sequence features) is a
separate downstream task and is **not** formalized here. B1's known weakness against low-and-slow
same-scope campaigns is the *measured contrast* that motivates the candidate, not a defect to hide.

## 2. Formal model (as implemented; all objects JSON-serializable)

### 2.1 Input alphabet

One case = one session/campaign for exactly one principal. Events come from the leak-safe minimal
schema (validated fail-closed by `baselines._validate_events`):

| Field | Type | Meaning |
|---|---|---|
| `actor_id` | non-empty `str` | principal (session must be single-actor) |
| `tool` | non-empty `str` | tool identifier (no raw content) |
| `scope` | non-empty `str` | authorization scope / purpose partition |
| `allowed` | `bool` | gateway admit/deny decision for that request |
| `ts` | non-negative `int`, non-decreasing | monotonic logical time (seconds) |

Any extra key fails closed; any `reason_code`-like key (`reason_code`, `reject_reason`,
`denial_reason`, `rejection_code`, `why`) is refused as `EVENT_REASON_CODE_FIELD_FORBIDDEN` — the
RQ1 masking contract: rejection reason codes never reach the detector surface. Malformed payloads
yield first-class `INDETERMINATE` outcomes with stable reason codes, never silently counted as safe
rejections.

### 2.2 Locked rule (B1 static cross-scope denial signature)

Let `E = ⟨e_1 … e_n⟩` be the event sequence, `D = {e ∈ E : ¬e.allowed}` the denial set, and
`H = ctx.b1_horizon_seconds` the injected follow-up horizon (default `86400` s = 24 h, one
`DetectorContext` field, never environment-read). The rule counts **cross-scope follow-ups**:

```
followups(E, H) = |{ e ∈ E_allowed ∪ D :
                     ∃ d ∈ D : e.scope ≠ d.scope ∧ 0 ≤ e.ts − d.ts ≤ H }|
```

- **Allowed follow-ups** use offset `0 ≤ e.ts − d.ts ≤ H` (an allowed request in a *different*
  scope after any prior denial is evidence of purpose hopping).
- **Denied follow-ups** use strict offset `0 < e.ts − d.ts ≤ H` (a denial cannot follow itself at
  Δt = 0; only a *subsequent* denial in another scope counts — this is the finite-state notion of a
  signature transition: state "denied in scope s" → event in scope s′ ≠ s).

**Decision semantics (locked operating point):**

```
DETECT   ⟺ followups(E, H) ≥ 1      reason_code = CROSS_SCOPE_DENIAL_RULE
NO_DETECT otherwise                   reason_code = NO_ALARM
score    = min(1, followups / max(1, |D|))   (arm-local evidence magnitude, NOT a probability)
```

The operating point is `followups ≥ 1` — a single cross-scope transition alarms. This is the
rule family's inherent precision/recall trade-off (§3): the threshold cannot be raised without
losing the single-hop campaigns the rule exists to catch, and cannot be lowered (the count is
already minimal). The operating point, the horizon `H` and the score normalization are frozen in
`DetectorContext` (injectable, additive-compatible defaults) — "published rule and locked
threshold" per the task DoD.

### 2.3 Legal state transition relation (finite-state reading)

Reading `scope` as the state variable, B1 is the two-state-per-scope signature machine:

1. `IDLE(s) --denied request in s--> DENIED(s)` (any scope s).
2. `DENIED(s) --event in s′ ≠ s, 0 ≤ Δt ≤ H--> COUNT (followups + 1)`; the machine does **not**
   reset: `DENIED(s)` persists for the whole horizon, so multiple later scopes each count against
   the same denial.
3. `DENIED(s) --denied request in s′ ≠ s, 0 < Δt ≤ H--> COUNT (followups + 1)` and the machine
   enters `DENIED(s′)` as well (denial chains accumulate follow-ups).
4. Every other transition (same-scope event, allowed retry in s, event beyond the horizon) leaves
   the counters unchanged — **order within a scope, inter-arrival pacing and absolute rate are
   invisible to the signature**.

Property 4 is exactly what §4 exploits: the signature's evidence channel is
`(scope transitions after denials)`; anything orthogonal to that channel (pacing, tool identity,
per-window counts) is unobservable to B1 by construction.

### 2.4 Failure semantics

- Wiring errors (unknown arm id, non-mapping case, malformed `DetectorContext`) raise
  `BaselineError` with stable uppercase codes — never an arm outcome.
- Malformed events → `INDETERMINATE` (`CASE_EVENTS_MISSING`, `EVENT_SEQUENCE_EMPTY`,
  `EVENT_UNKNOWN_FIELD`, `EVENT_REASON_CODE_FORBIDDEN`, `EVENT_TS_NOT_MONOTONIC`,
  `SESSION_MIXED_ACTORS`, …), `counted_as_success = False`.
- A `NO_DETECT` on a real campaign is a **measured false negative**, reported as such (§4), never
  relabeled as a safe rejection.

## 3. Precision / recall behavior of the rule family

**Precision posture.** The `followups ≥ 1` point is deliberately *high-recall, precision-capped*:
any single denial followed by legitimate activity in another scope alarms. Benign sessions do
cross scopes after transient denials (a denied self-care read then an allowed care-team lookup),
so sustained FPR control would require either a higher threshold (sacrificing single-hop recall)
or benign-traffic whitelisting (sacrificing leak-safety generality). In the locked synthetic
campaign below the rule holds 0 false alarms on the 20 benign controls *because those fixtures
never combine a denial with a same-session cross-scope move* — a property of the fixture family,
not a guarantee of the rule; the burst fixture (`_benign_burst`) already shows the benign shape
(many denials, one scope) the rule tolerates, and the honest framing is that single-denial +
cross-scope benign sessions are the rule's unavoidable FPR source at this operating point.

**Recall posture.** B1 detects exactly the campaigns whose evidence lies on its signature channel:
denials (or post-denial activity) in a scope different from a prior denial's scope, within `H`.
Multi-hop purpose hopping alarms on the first hop; repeated hops accumulate follow-ups (score
stays saturated at 1.0 by the `min(1, ·)` normalization).

**Structurally invisible (recall-0 by construction):**

1. **Same-scope campaigns** — all denials inside one scope produce `followups = 0` regardless of
   count, tool diversity, span or pacing (the transition relation never leaves `DENIED(s)`'s
   counting state for same-scope events).
2. **Tool renames / re-binds inside one scope** — `tool` is not in the signature alphabet at all;
   an attacker rotating tool identifiers within one scope changes nothing B1 reads.
3. **Rate and pacing** — no window statistic enters the rule; a campaign spread over days alarms
   identically to a burst within seconds (given the same scope pattern), and conversely a
   sub-window-paced campaign is indistinguishable from its benign counterpart.

## 4. Why the rule family misses low-and-slow campaigns (measured)

A low-and-slow campaign is the *dual* evasion of B1's signature channel: the attacker keeps every
request inside one scope (never crossing the scope boundary the rule watches) and paces denials
under every window the counting baseline (B0) watches. Concretely, the canonical fixture — 9
denials across 9 distinct `probe_tool_*` identifiers in `self_care` at 1080 s inter-arrival
(≈2.7 h logical span), max 4 denials per B0 window — yields, executed against the real module:

| Arm | Decision | Real evidence (from the test run) |
|---|---|---|
| B0 (count threshold) | `NO_DETECT` | `max_window_denials = 4 < 5` (paced under the window) |
| **B1 (this rule)** | **`NO_DETECT`** | `cross_scope_followups = 0` over `total_denials = 9` (same scope) |
| B3 (campaign linkage, candidate comparator) | `DETECT` | all 5 linkage criteria met (`distinct_denied_tools = 9`, `span = 8640 s`, window-evading pace, continuity) |

The mechanism of the miss is structural, not tunable:

- **Signature channel mismatch.** B1's only evidence channel is *scope transitions after denials*
  (§2.2). A single-scope campaign has an empty channel: `∃ d, e: e.scope ≠ d.scope` is false for
  the whole stream, so `followups = 0` and `DETECT` is unreachable **for any threshold setting**.
  Raising or lowering the threshold, or the horizon `H`, cannot help; only adding a *different*
  evidence channel (tool diversity, span, pacing — i.e., B3's linkage criteria or a learned
  sequence model) can.
- **Pacing orthogonality.** Inter-arrival times enter neither the signature nor its score; the
  attacker's 18-minute spacing is chosen to defeat B0's window, and B1 never observes pacing in
  the first place — the two baselines are blind on *complementary* axes, which is why both must be
  reported (RQ1 needs B0, RQ3 needs B1).
- **Falsification consequence.** Because B1 misses the low-and-slow family at recall 0 while B3
  detects it, the rule family cannot be the whole answer to RQ1; symmetrically, if B1 *matches*
  the sequence-model candidate on the family-held-out *overt* split, the blueprint's falsification
  rule forbids claiming ML necessity. Both directions are measurable in the locked test driver.

The measured campaign-level behavior on the locked mixed set (§5: 20 benign + 6 overt + 6
low-and-slow): B1 **AUCPR ≈ 0.6599** (real `precision_recall_auc` output), overt recall 6/6,
low-and-slow recall 0/6, false alarms 0/20 benign sessions. This is the arm's honest operating
envelope: perfect on its signature channel, exactly zero on the evading family — the documented
gap the candidate arm must close.

## 5. Locked evaluation fixtures (deterministic; asserted in the test driver)

- `DIMVA-X05-OVERT-1` — overt cross-scope probing: 3 denials in `self_care`, cross-scope
  follow-ups into `billing` / `research_secondary` ⇒ `followups = 3`, `DETECT`,
  `score = 1.0` (recorded real count).
- `DIMVA-X05-LOW-SLOW-1` — low-and-slow sibling: 9 denials across 9 distinct tools in `self_care`,
  1080 s spacing ⇒ B1 `NO_DETECT` with `followups = 0`, `total_denials = 9` (recorded real
  count); B0 also `NO_DETECT`; B3 `DETECT` (contrast asserted).
- Horizon boundary pair — cross-scope follow-up at `Δt = H` alarms; `Δt = H + 1` does not (the
  locked `86400` s horizon is inclusive).
- Benign family — quiet (1 transient denial, same scope), burst (5 denials, one scope),
  exploration (multi-scope, zero denials) ⇒ all `NO_DETECT`, exercising the rule's tolerance for
  same-scope denials and denial-free scope changes.
- Adversarial controls — leak-safe `reason_code` field refused (`INDETERMINATE`), mixed actors
  refused, non-monotonic `ts` refused; determinism (byte-identical `to_dict()` on repeat runs);
  stub-refusal gate `refuse_constant_stub` admits the real B1 (`STUB_SEPARATION_OK`) because B1
  separates the paired benign/attack probes.

## 6. Provenance and evidence discipline

- **Implementation source:** `evaluation/venue2027/dimva/baselines.py` (task `DIMVA-baselines`,
  report `research/venue2027/proof/DIMVA-baselines.json`) — reused verbatim; this task adds **no**
  detector code, only the formalization document, the test driver and the proof report. The
  baseline file is unmodified, so `evaluation/venue2027/dimva/test_baselines.py` (57 tests) stays
  green by construction and is re-run as the backwards-compatibility gate.
- **No oracle repair:** the expected B1 behaviors above are derived from the rule definition
  (§2.2) *before* execution and then asserted; the miss of the low-and-slow family is reported as
  a first-class negative result, never hidden or re-labeled.
- **No label leakage:** every fixture uses the five-key minimal schema; rejection reason codes are
  absent from all event streams (and their *presence* is itself an asserted adversarial control).
- **Scientific unit:** one case = one session/campaign for one principal; the AUCPR is
  campaign-level over 32 independently-labeled cases (≥ `MIN_AUC_SAMPLE_SIZE` = 30), never
  per-event pseudo-replication.

## 7. Handoff

Next dependent work per `VENUES/dimva/PHASES/P03.md` and the blueprint: the campaign-linkage
comparator arm (B3) and the learned sequence-model candidate (blueprint B4) own the low-and-slow
family this task shows B0+B1 cannot cover; cross-family holdout scoring (RQ2) should reuse the
locked fixtures of §5 as the rule arms' frozen operating points.
