# DIMVA-threat · Threat, trust and failure model — GovernanceTrace

> **Task:** `DIMVA-threat` (venue `dimva`, phase `P01`, agent `security`, resource `cpu`).
> **Dependencies:** `DIMVA-scope` PASS (`research/venue2027/proof/DIMVA-scope.json`), `SH-research_ethics` PASS (`research/venue2027/proof/SH-research_ethics.json`).
> **Machine contract:** `validate_threat() -> ThreatCoverage` from `research/venue2027/_shared/tools/threat_model.py` (`THREAT_MODEL_VERSION = "1.0.0"`).
> **Version:** 1.0.0. **Status:** design contract — this file freezes the threat, trust and failure model; it asserts no empirical result and contains no numbers.
> **Purpose:** define who can do what to the GovernanceTrace detection study, which components are trusted, which domains are excluded, and which attack families must always carry a paired clean control before any detector is built or evaluated.
> **Allowed input:** synthetic multi-stage agent-event traces conforming to `VENUES/dimva/CASE_MATRIX.md` (`clara.venue2027.scenario.v1`); no real PHI/PII, per `SH-research_ethics`.
> **Failure semantics:** any missing section, unpaired attack family, or undefined oracle/actor authority fails the shared validator with a stable reason code; nothing is silently coerced into a safe rejection or a successful completion.

## 1. Scope and system model

GovernanceTrace is a **detection** study over a synthetic multi-tenant health-AI gateway: a privacy-constrained sequence detector distinguishes deliberate multi-step authorization-boundary reconnaissance from benign retry bursts using only the minimal event schema — event kind, scoped actor/tenant/purpose, logical time, payload digest references. Raw clinical content is never logged; rejection reason codes are masked at the telemetry boundary in the primary leak-safe test and unmasked only in a labeled ablation.

This model governs detection over event streams only. Admission and prevention are the IFIP SEC sibling study's endpoints; no DIMVA artifact decides or strengthens a single request's admission, and the four-part boundary is fixed in `novelty_contract.md` §Non-overlap. Every scientific unit is an independent campaign or benign session, never a per-event pseudo-replication.

## 2. Attacker and observer capabilities

- **A1 (probing principal).** An authenticated synthetic agent principal inside one tenant can issue arbitrarily many tool/API requests, observe its own final allow/deny outcomes, and retry at will. It cannot see rejection reason codes (masked in the primary test), other tenants' events, privileged audit logs, detector internals, or oracle labels.
- **A2 (autonomous chaining).** The agent autonomously chains tool calls and selects purposes (model agency, §7). Tool allow-lists bound what it may invoke, not the order, grouping, or pacing of invocations.
- **A3 (adaptive pacing).** The attacker fully controls request timing: bursts, drips, inter-arrival shifts beyond any fixed window, and long-horizon campaigns (low-and-slow probing across days of logical time).
- **A4 (obfuscation).** The attacker can reorder probes, interleave benign-looking traffic, imitate outage backlogs and latency spikes, rename or re-bind synthetic tool handles (tooling changes), and apply adversarial drift to its access pattern — all to defeat signatures tuned to one environment.
- **A5 (no write access to trusted components).** The attacker cannot write the event collector, alter past events, read the sealed oracle, or use the detector as an oracle beyond its observable alert/deny outcomes. Telemetry poisoning is possible only by emitting legitimate-shaped events from its own principal (see the insider/observer family, §5); every other write path is excluded by collector trust (§3).
- **O1 (telemetry observer).** The detection-side observer sees only the minimal schema: no raw clinical content, no reason codes in the primary test, digests instead of payloads. The observer is honest but minimally informed; retained sensitive metadata is measured in bytes against the frozen minimal-schema cap.
- **O2 (blinded adjudicator).** Human adjudication, where invoked, is independent and blinded to the model arm; a candidate-model agent never certifies its own oracle labels (per `SH-research_ethics`).

## 3. Trusted components

- **T1 — minimal event collector.** Append-only, schema-versioned collector producing the minimal event stream with monotonic logical time and payload digest references. Trusted for the integrity, ordering and completeness of emitted events; it replaces all wall-clock assumptions. It emits stable reason codes and fails closed: a collector failure is never counted as a safe rejection, a benign verdict, or a successful completion.
- **T2 — detection model.** The candidate detector (C0) and baselines (B0–B3, per `novelty_contract.md`) are read-only consumers of T1 output. No detector decides admission, writes events, or reads oracle state. Detector versions are pinned per arm with equal data access and equal compute budget; labels used for supervised arms are leak-safe (no attack-specific reason codes in the primary test).
- **T3 — sealed oracle.** Campaign-intent and authorized-action labels derive from simulator ground truth (`truth.json` per `VENUES/dimva/CASE_MATRIX.md`, `oracle_spec_revision` frozen). The oracle implementation never imports candidate or baseline code and is inaccessible to A1–A5.
- **T4 — gateway policy engine.** Performs authorization under versioned consent/policy epochs and produces the final allow/deny observable to A1. Its reason codes are masked at the telemetry boundary in the primary test.
- **Trust assumption.** T1–T4 are uncompromised at study start. Compromising any of them is an excluded domain (§4), not an attack family; a threat argument that requires an untrusted collector is out of scope by construction.

## 4. Excluded domains

The following are explicitly out of scope for this study and are not attack families:

- **Host-level rootkit / kernel or hypervisor compromise**, including tampering with T1–T4 processes, memory, or binaries.
- **Physical, network-layer, or infrastructure attacks** below the API surface (link cutting, routing attacks, side channels).
- **Cryptanalysis of payload digests**: digest references are integrity pointers, not secrets; payloads are never logged, so inverting a digest is out of scope.
- **Content-level prompt injection as such** (AgentDojo/ToolEmu territory): in scope only insofar as an injection produces observable probing patterns on the minimal event schema.
- **Real patient data and real deployments**: all tenants, actors, and records are synthetic; no clinical-efficacy claim is derived from this study.
- **Strengthening or bypassing the authorization check itself**: prevention endpoints belong to IFIP SEC; a "detector" that merely re-implements verification would collapse this study's distinct endpoint and is refused.

## 5. Attack family and control matrix

Every family carries a paired clean and adversarial case; the clean control is exactly the benign behavior the adversary imitates, so no family is ever documented without its control. Fixture IDs reference `VENUES/dimva/CASE_MATRIX.md`; expected verdicts are oracle targets, not measured outcomes.

| Attack family | Case | Actor/observer | Capability | Control (clean) | Adversarial case | Expected oracle verdict |
|---|---|---|---|---|---|---|
| `revocation_timing` | paired | A1 + O1 | paces requests around consent/policy revocation boundaries to exploit stale-epoch scope | clean: authorized re-request after revocation that honors the new consent epoch (DIMVA-CASE-01 single legitimate retry) | adversarial: paced request burst straddling the revocation boundary to carry pre-revocation scope into a new epoch (DIMVA-CASE-03 low-and-slow drift) | clean → BENIGN; adversarial → ATTACK |
| `replay` | paired | A1 + O1 | re-presents previously granted receipts/capability tokens under a changed purpose to look authorized | clean: token reuse for the same purpose inside an unexpired schedule window (legitimate idempotent retry) | adversarial: token reuse across a purpose/epoch change presented to a fresh authorization context (DIMVA-CASE-02 purpose hopping) | clean → BENIGN; adversarial → ATTACK |
| `model_agency` | paired | A2 + O1 | autonomously chains tool calls and selects purposes beyond the declared task intent; detector sees only emitted events, never model internals | clean: agent delegates to an allowed tool within its declared purpose (authorized care-team handoff, DIMVA-CASE-04) | adversarial: self-directed multi-step permission-discovery chain across tools (DIMVA-CASE-07 unseen mutation mechanism) | clean → BENIGN; adversarial → ATTACK |
| `purpose_scope` | paired | A1 + O1 | hops between purpose labels to widen effective scope while each single request stays individually justified | clean: purpose-consistent session in which every request shares one declared purpose | adversarial: purpose-hopping sequence linking one evidence digest across ≥3 distinct purposes (DIMVA-CASE-02) | clean → BENIGN; adversarial → ATTACK |
| `insider_or_observer` | paired | A1/A5 + O1 | emits legitimate-shaped events to poison telemetry, or infers tenant structure from minimized metadata | clean: busy provider session generating benign alert bursts under load (DIMVA-CASE-08 false-positive pressure) | adversarial: insider-shaped benign-looking probing traffic blended into outage-backlog noise (DIMVA-CASE-05 adversarial pacing) | clean → BENIGN; adversarial → ATTACK_OR_EXPOSE_LIMIT |
| `adaptive_probing` (DIMVA-specific) | paired | A1+A2+A3+A4 + O1 | obfuscates probes across tool renames and interleaving, shifts pacing beyond fixed windows, and drifts access patterns to evade minimal-event detection | clean: benign feature-flag exploration by an authorized operator during a tooling change | adversarial: cross-tool obfuscated low-and-slow campaign with adversarial drift across families (DIMVA-CASE-05/06/07) | clean → BENIGN; adversarial → ATTACK or reported evasion |

## 6. Revocation and schedule-time semantics

- Consent, purpose, and policy **epochs are versioned**; revocation is an in-schema event kind, and every event carries the epoch it was evaluated under. The detector never compares events across epochs as if scope persisted.
- **Schedule time:** detection windows run in logical time, not wall clocks. A3 may schedule campaigns across arbitrarily long horizons, so all timing claims (time-to-detect, pacing robustness) are stated in logical time. The independently labeled schedule — frozen splits, holdout sealed until protocol and analysis freeze — defines when any forbidden commit or forbidden disclosure invalidates the study.
- Revocation-boundary abuse (carrying pre-revocation scope across an epoch boundary) is the `revocation_timing` family above; its clean control is the epoch-honoring re-request, and its oracle target is adjudicated from scenario construction, not from the epoch mismatch alone.

## 7. Model agency and receipt-reuse power

- **Model agency:** the LLM agent autonomously selects tools, ordering, and purpose. The detector never sees model internals, plans, or prompts — only emitted events. Agency is bounded by T4 allow-lists but otherwise unrestricted; this is what makes purpose-hopping and permission-discovery chains realistic attacks rather than hypothetical ones, and why the candidate must link events into campaigns rather than score single requests.
- **Replay power:** A1 may re-present previously granted receipts/capability tokens under a changed purpose or expired epoch. IFIP SEC prevents acceptance of such tokens at verification time; DIMVA measures whether the resulting event pattern is *detectable* from minimal telemetry at a bounded false-alarm budget. Token reuse is therefore an in-scope detection family here and a prevention family in the sibling study — the boundary fixed in `novelty_contract.md` §Non-overlap — and no DIMVA artifact claims to prevent a replayed acceptance.

## 8. DIMVA-specific threat taxonomy

| Threat (deliverable) | Family / control | Detector risk |
|---|---|---|
| Adaptive authorization-boundary probing by agents | `purpose_scope`, `model_agency` | each single request is individually justifiable; campaign intent only exists across the sequence, so per-request scoring is structurally blind |
| Slow / low-and-slow probing | `revocation_timing`, `adaptive_probing` | fixed-width windows and wall-clock assumptions miss paced campaigns (DIMVA-CASE-03/05) |
| Probe obfuscation across tools | `adaptive_probing` | signatures memorize tool handles; tooling changes must not silently defeat detection (environment memorization, sommer10) |
| Evasion of minimal-event detection | `adaptive_probing` | trade-off between the frozen minimization cap and the detection signal (RQ3 metadata budgets); evasion success is reported, never hidden |
| False-positive pressure on benign exploration | clean controls of every family; `insider_or_observer` | retry bursts, outage backlogs, busy-provider noise (DIMVA-CASE-01/04/08); the preregistered false-alarm budget is a hard constraint, not a tuned outcome |
| Poisoned telemetry | `insider_or_observer` | the attacker emits legitimate-shaped events from its own principal; collector trust (T1) bounds the damage, and detector robustness to such blending is measured, not assumed |
| Adversarial drift of access patterns | `adaptive_probing`, `revocation_timing` | non-stationary behavior across the study window; drift is reported as evasion success or exposure of a limit, never as environment failure |

## 9. Oracle and actor authority

All authorities in this model are **defined**; an undefined oracle/actor authority is a model-invalidating stop condition, not a recoverable ambiguity.

- **Oracle authority:** simulator ground truth sealed in T3 — `truth.json` per case with a frozen `oracle_spec_revision`. Campaign intent and authorized-action labels are adjudicated from scenario construction, never from detector scores or the gateway's final reason code. The oracle implementation never imports candidate or baseline code; a candidate that could repair the oracle post hoc would invalidate the study.
- **Actor authority:** A1–A5 and O1–O2 hold exactly the capabilities listed in §2 and the §5 matrix; no actor may grant itself new capabilities mid-study. Synthetic actor identities are fixed per case (`actor_id`, `tenant_id`, `purpose`), and capability sets are part of the frozen fixture.
- **Adjudication authority:** independent, blinded human review per `SH-research_ethics`, invoked when a case is `INDETERMINATE`; `INDETERMINATE` is never coerced to PASS and never counted as a safe rejection.
- **Negative control:** a model variant in which oracle or actor authority is left undefined must fail the shared validator with a stable reason code and must not be merged; incompleteness is a failure, never a pass by default.

## 10. Failure semantics and stop conditions

- Every validator and pipeline failure surfaces a stable reason code (`MISSING_SECTION`, `FAMILY_WITHOUT_PAIR`, `UNDEFINED_AUTHORITY`, ...); unhandled exceptions are never miscounted as safe rejections, and missing dependencies are never silently dropped.
- Stop and revise if: one forbidden commit or forbidden disclosure survives a complete independently labeled schedule; the oracle imports candidate code; a holdout is opened before freeze; any output is selectively dropped; an UNKNOWN/INDETERMINATE outcome is counted as a safe rejection or successful completion; or a real-PostgreSQL condition is claimed from SQLite-only observations.
- Falsification hooks from `novelty_contract.md` remain binding on this model: if reason-code unmasking alone restores detection, the primary experiment is invalidated; if rule baselines (B0/B1) match sequence models on family-held-out traces, no ML-necessity claim is made; negative outcomes are reportable results, not hidden failures.
