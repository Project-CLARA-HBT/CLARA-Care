# AIME-X05_strict_refresh · implementation spec: strict per-step refresh comparator

**Task:** `AIME-X05_strict_refresh` · **Phase:** `P03` · **Venue:** `aime` · **RQ:** `RQ2`
**Paper:** *Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories*
**Arm formalized here:** blueprint arm **B1 in its strongest form** —
`B1-full-per-step-refresh-current-policy-filter` (registry entry in
`evaluation/venue2027/aime/baselines.py::BASELINE_REGISTRY`, fidelity status `UNAVAILABLE_NOT_RUN`
for provider-dependent full execution; the in-process structural adapter is the executable
comparator used here).
**Real baseline adapter (reused — never re-implemented):**
`evaluation/venue2027/aime/baselines.py`, module version `BASELINES_VERSION = "1.0.0"`,
entry point `run_baseline("B1-full-per-step-refresh-current-policy-filter", case, ctx) -> Outcome`.
**Test driver:** `research/venue2027/aime/tests/test_x05_strict_refresh.py`.
**Status:** formalization + executable structural measurement on deterministic synthetic
vignettes only; no live workload, no PHI, no network, no hidden clock, and no live-model call.
No claim in this document is evidence of a real-system or clinical result.

---

## 1. What the X05 arm is

X05 is the **strongest correctness/privacy comparator** for RQ2: at **every step** of a
longitudinal clinical workflow it **re-derives the entire authorized context from the live
record** — fetching the exact current consent epoch and medication list, discarding every
previously fetched segment (prompt segments, cached summaries, prior recommendation text),
reconstructing the prompt from scratch under the *current* policy epoch, regenerating the
response (same model, temperature, budget — out-of-process for the live arm), and validating
persistent intent before any completion is counted.

- **Staleness-impossible by construction.** Because no fetched context ever survives a step
  boundary, there is no cache, no epoch key and no TTL under which a stale segment could be
  re-served. A step at logical time `t` decides *only* from state as of `t`. Any
  consent revocation or medication withdrawal that occurred at any `t' < t` is visible at
  `t` with certainty — the strongest possible context-freshness guarantee among all arms
  (B0 single snapshot, B3 static + post-filter, and the X06/B4 selective candidate each
  trade some freshness for cost).
- **It is the safety ceiling of context-management designs**, but it pays for safety with
  cost: every step re-reads and re-encodes the full record (token cost linear in steps ×
  record size) and re-runs generation even when nothing changed (blueprint §Strong baselines:
  "strong correctness/privacy control"; RQ2/RQ3 cost axis).

## 2. Formal model

Fix a vignette `V = (S_0, E, T, task, purpose)` where `S_0` is the task-start snapshot
(medications + consent), `E = (e_1, …, e_m)` is the ordered timeline with logical times
`t(e_j)` (event kinds `MEDICATION_ADDED`, `MEDICATION_WITHDRAWN`, `CONSENT_GRANTED`,
`CONSENT_REVOKED`, `UNRELATED_NOTE_EDIT`), `T = (t_1 < … < t_n)` is the step schedule with
`t_j ≥ t(e_{j-1})`, and `task` names the drug under discussion for `purpose`.

**State derivation (the refresh operator).** For step `j` at logical time `t_j`, the arm
computes the **current state** `S_j = derive(S_0, {e ∈ E : t(e) ≤ t_j})` — the full record
re-read at `t_j`, never a cached projection of an earlier state. `derive` folds every
event at or before `t_j` into the snapshot (medication additions/withdrawals update the
medication set; consent grants/revocations update `granted_purposes`).

**Step decision relation** (evaluated per step, in schedule order; one full context
reconstruction per step):

1. `refresh(j) := S_j is recomputed from source` — always true by construction; counted
   once per step (the cost the arm exists to pay).
2. **Authorize against the current epoch (never the snapshot):**
   `auth(j) = REJECT/CONSENT_REVOKED_MID_TASK` if `purpose ∉ granted_purposes(S_j)`.
3. **Eligibility check on refreshed medication state:**
   `HAZARD_WITHDRAWN` if any medication withdrawn by `t_j` is still referenced by the
   task under discussion; `HAZARD_ADDED` if any medication added by `t_j` requires
   interaction re-review. Either hazard ⇒ the step's prior recommendation is **not
   countable** (`INDETERMINATE`, review/regeneration required) — never silently `SAFE`.
4. **Stable step:** no consent delta and no medication delta between `S_0` and `S_j`
   ⇒ `SAFE/NO_DETECTED_HAZARD` (the refresh confirmed the snapshot is still current).

**Guarantee (strict no-stale-context bound).** For every step `j` and every change event
`e` with `t(e) < t_j`: the effect of `e` is reflected in `S_j` and therefore evaluated by
the relation above at step `j`. Hence **no step can decide from evidence that a mid-episode
consent revocation or medication change has invalidated** — the axis-A stale-context hazard
class (RQ1) is structurally impossible for this arm, at the price of one full context
re-derivation and re-generation per step (RQ3 token-cost axis). Scope: decision-time
freshness only; no claim of retroactive erasure of content already sent to an external
provider in earlier steps' generations.

**Cost model (RQ3 quantities, all recorded per Outcome).**

| Metric | Meaning | Expected regime |
|---|---|---|
| `refresh_count` | full context re-derivations performed | exactly 1 per step |
| `per-step decisions` | `SAFE` / `UNSAFE` / `INDETERMINATE` per the relation above | hazards surface at the first step at/after the change |
| `input_sha256` | content hash of the vignette (identical across arms) | parity anchor vs B0 |

Against the single-snapshot arm (B0), X05's `refresh_count` is `n` (one per step) versus B0's
`1` (one fetch at task start, never again) — the measured cost gap RQ3 reports; against the
X06/B4 selective candidate, X05 bounds the *availability/cost ceiling* the candidate must
beat while preserving the same no-stale-context guarantee on changed state. If X05's
advantage over selective regeneration is nil on the vignette grid, the blueprint
falsification rule narrows the paper to a descriptive workflow evaluation.

## 3. Execution contract in this repository

- The comparator is **executed through the real adapter**
  `evaluation/venue2027/aime/baselines.py::run_baseline(B.BASELINE_B1, case, ctx) -> Outcome`
  over the `clara.venue2027.scenario.v1`-shaped synthetic vignette mapping; X05 does **not**
  fork a second implementation.
- Deterministic: no hidden clock/randomness/network; the vignette's `timeline` and
  `current` sections fully determine the run. Live-model execution of the full arm remains
  `PROVIDER_DEPENDENT_NOT_RUN` (transparent status; no comparative LLM claim).
- Fails closed with stable reason codes (`CONSENT_REVOKED_MID_TASK`,
  `WITHDRAWN_MEDICATION_IN_OUTPUT`, `ADDITIONAL_MEDICATION_INTERACTION_HAZARD`,
  `VIGNETTE_MALFORMED`, `VIGNETTE_MISSING_FIELD`, `VIGNETTE_BAD_TIMELINE`,
  `ARM_CONTEXT_MISMATCH`, `CONTEXT_MALFORMED`); malformed inputs are never counted as safe
  rejections and `INDETERMINATE` is first-class.
- Tests: `research/venue2027/aime/tests/test_x05_strict_refresh.py` imports the real
  baseline, drives a multi-step schedule over a vignette where consent **and** medication
  change mid-episode, asserts no step ever emits a stale-context hazard (`SAFE` on state
  that a mid-episode change invalidated), and records the real per-step refresh count
  (`n`) against the single-snapshot arm's one-shot fetch as the cost contrast.

## 4. Version

`X05_STRICT_REFRESH_SPEC_VERSION = "1.0.0"`; formalized on top of
`evaluation/venue2027/aime/baselines.py::BASELINES_VERSION = "1.0.0"` with no change to the
adapter (backwards-compatible consumers only).
