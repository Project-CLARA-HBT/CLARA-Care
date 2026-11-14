# IFIP_SEC · Threat, trust and failure model (IFIP_SEC-threat)

**Task:** `IFIP_SEC-threat` · **Phase:** `P01` · **Venue:** `ifip_sec` · **Paper:** *Re-Execution-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage*. The primary endpoint under this threat model is the **admission-time stale-re-execution acceptance rate** across purpose, delegation, and AI proposal lineage: whether each authorization architecture admits an invalid re-consumption or rejects a legitimate operation under multi-principal interleaving.
**Contract version:** `clara.venue2027.ifip_sec.threat_model.v1`
**Status:** Frozen *prospective* threat model — a design commitment and structural gate, not experimental evidence. No number in this file is a research result; every empirical claim must later derive mechanically from `artifacts/venue2027/ifip_sec/<run_id>/manifest.json`.
**Dependencies:** `IFIP_SEC-scope` (frozen novelty contract, Decision: GO), `SH-research_ethics` (synthetic-only data policy).
**Validator gate:** this document must pass `validate_threat()` from `research/venue2027/_shared/tools/threat_model.py` (`THREAT_MODEL_VERSION 1.0.0`); §6 is written so the first occurrence of each registered family token is its genuine paired matrix row.
**Scope of this document:** the authorization admission boundary of a multi-tenant, AI-mediated health platform — consent-purpose receipts, delegation chains, AI proposal lineage, policy/consent epochs, and the consume-once nonce store. Clinical content correctness, prompt-injection detection, and transport security are out of scope here (each is owned by another venue or layer).

## 1. System and adversary summary

The platform admits an operation when a **capability receipt** — a typed commitment HMAC-bound over actor, patient, tenant, purpose, task, consent epoch, policy epoch, dispatch digest, nonce, and parent reference — verifies against a frozen principal graph and the **current** governance state. Receipts may be *delegated* (a holder attenuates and re-signs a child receipt whose `parent_ref` names its parent), *refreshed* across epoch changes, and bound into **AI proposal lineage** (each AI-proposed action carries the receipt chain that motivated it). Admission is re-execution-closed only if every verification (i) checks the full delegation ancestry, (ii) revalidates both epochs online, and (iii) atomically consumes the nonce exactly once.

The adversary's single goal is to obtain an `ALLOW` admission that the independent oracle labels `DENY` — an invalid stale-re-execution admission — or to cause a legitimate operation to be falsely denied beyond the frozen non-inferiority margin. The study measures admission decisions, not detection scores; prevention, not detection.

## 2. Attacker and observer capabilities

Attacker classes (each class adds to the previous; all capabilities are structural, never cryptographic):

- **A1 — Receipt holder (semi-trusted insider).** Holds one or more valid receipts. Can re-present any held receipt byte-for-byte across purposes, tenants, dispatch adapters, or time; can reorder or withhold delegation hops; can race two consumers of the same nonce; can re-present after partial revocation (recipient revoked, chain ancestor not; or consent revoked, policy not).
- **A2 — Delegation intermediary.** Sits on a delegation path. Can splice a foreign sub-chain into its own lineage, prune or reorder ancestry hops, re-delegate outside the granted purpose, refresh a receipt into a new consent epoch without re-consent, and re-target a child receipt to a different dispatch adapter (recipient substitution).
- **A3 — AI proposal lineage forger.** Controls one AI agent's proposal assembly. Can fabricate a proposal whose parent reference names a receipt chain that never authorized it (lineage forgery), graft an unrelated valid chain as ancestry (lineage splicing), truncate a chain to shed a revoked ancestor (lineage pruning), or fan out one approved proposal into many dispatches (proposal fan-out re-dispatch).
- **A4 — Multi-tenant confused deputy.** Operates a legitimate dispatcher or delegation service across tenants. Can be tricked into exercising its own authority on behalf of another tenant or principal (confused-deputy delegation), or into consuming a nonce under a stale policy/consent epoch read.
- **A5 — Network-observer/re-presenter.** Records all admission traffic (there are no confidential channels assumed for capability bytes; confidentiality is not a control here) and can deliver recorded bytes later, including after revocation, expiry, or epoch change. Cannot forge HMACs and cannot compromise endpoints.

- **Observers.** Synthetic-audit observers see the full event sequence, persisted nonce-store state, and all admission verdicts, but are not principals and hold no valid receipt. They anchor the independent oracle; they never participate in admission.
- **Model agency and stale-re-execution power.** The AI proposal layer is modeled as *agency under stale-re-execution power*: agents can *propose* only through receipts and cannot mint authority; but any agent output may be re-presented verbatim by A1–A5 unless the admission boundary binds proposal → receipt chain → nonce consumption. An agent re-issuing an identical proposal is an A3 instance, not a new grant of authority.
- **Revocation/schedule time.** Adversary controls event *ordering* within one logical schedule: dispatch → revoke → consume interleavings, epoch-boundary crossings, and concurrent consume races are all adversary-selectable. Wall-clock time is excluded; all ordering is logical schedule time, so stale re-execution and stale-epoch semantics are well-defined without clock assumptions.

## 3. Trusted components

Trust is placed in components and their contracts, never in tokens or agents:

- **Capability token (receipt) format.** Typed commitment HMAC over the full context tuple (actor, patient, tenant, purpose, task, consent epoch, policy epoch, dispatch digest, nonce, parent reference). Trusted only for *unforgeability of the context binding* — it does not by itself prevent stale re-presentation, staleness, or lineage forgery.
- **Delegation ledger.** Append-only record of the principal graph and every delegation edge with its epoch. Trusted for the *completeness and ordering* of ancestry; the verifier must re-derive and check the full chain from the ledger, not from attacker-supplied hops.
- **Policy engine (consent/policy epochs).** Independently versioned consent epoch and policy epoch; revalidated online at verify time against the ledger's committed state. Trusted for correct epoch numbering and revocation commitment, not for liveness.
- **Consume-once nonce store.** The single atomicity point (RQ2). Trusted only under its declared backend contract: real PostgreSQL 16 with serializable transactions for any linearizability claim; SQLite observations are inadmissible for RQ2 and any such claim is recorded `BLOCKED`/`NOT_RUN`, never as a pass.
- **Independent oracle and principal graph freeze.** Allow/deny labels derived from the frozen principal graph and commit-time consent epoch, authored without importing candidate code (see §5). Trusted for adjudication independence, not shared with any arm.
- **Synthetic fixture generator.** Deterministic, seeded, versioned; trusted for reproducibility of interleavings and isolation of synthetic accounts. Never trusted for empirical outcomes.

## 4. Excluded domains

Explicitly out of scope; attacks in these domains are neither modeled nor claimed against:

- **Compromised signing keys.** If the HMAC root key or any ledger-signing key leaks, all receipt guarantees collapse; key-compromise recovery is a different paper. The verifier's threat model *ends* at unforgeability.
- **Byzantine policy engine or ledger.** The policy engine and delegation ledger follow their protocol; arbitrary Byzantine behavior by them (silent epoch renumbering, edge deletion) is excluded. Failures are fail-closed, not adversarial.
- **Byzantine nonce store / storage-level tampering.** The nonce store is not attacker-writable; torn pages, bit flips, and storage corruption belong to DSN's crash-consistency venue, not here (admission decisions, not recovery).
- **Prompt injection / clinical-content attacks.** Agent prompt manipulation, clinical reasoning quality, and content-level safety are owned by AIME (unsafe clinical action rate) and DIMVA (detection); this model treats proposal *authority*, not proposal *content*.
- **Cryptanalysis and side channels.** HMAC forgery, timing side channels on verification, and cache/audit reconstruction (PST's endpoint) are excluded.
- **Availability and denial of service.** The adversary cannot exhaust resources to force fail-open; fail-closed on any verification error is assumed reachable.
- **Real patient data.** All fixtures are synthetic (`SH-research_ethics`); no PHI exists in any schedule, oracle, or log.

## 5. Oracle and actor authority

Authority is **defined**, not assumed:

- **Defined — independent oracle authority.** The only authority for allow/deny truth is the frozen-oracle adjudicator: labels derived from the frozen principal graph and commit-time consent epoch, authored from the event sequence and policy/DB ground truth. It imports no candidate or baseline verifier code and never reads candidate reason codes; ambiguous histories are labeled `INDETERMINATE` and are never coerced to a pass. A routine `UNKNOWN`/stale/timeout outcome is counted as unknown per arm, never as a safe rejection.
- **Defined — actor authority.** An actor may act only within the intersection of: (i) a receipt chain whose ancestry verifies against the delegation ledger, (ii) the current committed consent epoch and policy epoch at verify time, (iii) the named tenant, principal, purpose, and dispatch digest, and (iv) an unconsumed nonce consumed atomically at admission. Authority outside that intersection is invalid by definition, regardless of signature validity.
- **Defined — adjudication of the falsification rule.** If a properly scoped Macaroon (B1) with consistent authorization checks (B2) is decision-equivalent to the candidate (B4) on all attack families, the manuscript states equivalence and claims no stronger security; equivalence is an acceptable outcome, not a failure to be repaired post hoc.
- **Undefined authority is a stop condition.** Any schedule whose oracle or actor authority is undefined is halted and reported, never silently adjudicated in the candidate's favor; `MEASURE`/`INDETERMINATE` outcomes stay uncoerced. This stop condition exists because an unresolvable authority is treated as a failed guard, not as an implicit safe default.
- **Exclusion of implicit defaults.** No default-deny heuristic substitutes for an explicit adjudication: a schedule halted by the undefined-authority rule stays halted until an independent reviewer resolves its authority from the frozen graph and committed epochs.

## 6. Attack family and control matrix

Paired clean/adversarial matrix. Case IDs reference `VENUES/ifip_sec/CASE_MATRIX.md` fixtures; every family carries exactly one clean control and one adversarial case, as the validator's per-row contract requires.

| Attack family | Case | Actor/observer | Capability | Control (clean) | Adversarial case | Expected oracle verdict |
|---|---|---|---|---|---|---|
| replay | paired | A1 receipt holder | Replays a valid, fully-signed receipt byte-for-byte across purpose, delegation hop, tenant, or after partial revocation | clean: IFIP_SEC-CASE-01 — legitimate same-purpose execution, current epoch, matching dispatch, first consume → `ALLOW`; IFIP_SEC-CASE-02 control half — same receipt, same purpose, second consume → `DENY` | adversarial: IFIP_SEC-CASE-02/03/04 — cross-purpose replay, tenant substitution, and replay-after-revocation of an otherwise valid signed receipt; nonce store must reject the second consume atomically (RQ2) | `DENY` for all adversarial replays; clean first-consume `ALLOW` at ≤ frozen false-denial margin |
| purpose_scope | paired | A1/A2 | Reuses a purpose-scoped receipt for an ungranted purpose or re-delegates outside purpose | clean: IFIP_SEC-CASE-01 — same-purpose accept with full context binding | adversarial: IFIP_SEC-CASE-02 — same receipt bytes presented under a different purpose; purpose must be re-checked online against the current policy epoch, not trusted from token bytes | `DENY` (cross-purpose reuse); no purpose widening by delegation |
| revocation_timing | paired | A1/A4 + schedule | Consumes between dispatch and revocation commit, or after revocation of one chain member only (partial revocation) | clean: IFIP_SEC-CASE-04 control half — receipt used before any revoke event in the schedule → `ALLOW` | adversarial: IFIP_SEC-CASE-04 — consent/policy revocation committed between dispatch and consume; also stale-epoch consumption where the policy engine read is older than the revocation commit | `DENY` (online epoch re-check at verify time); a stale epoch read that admits is a failed RQ2 claim |
| model_agency | paired | A3 proposal forger + A4 deputy | Forges/splices/prunes AI proposal lineage, or lets an agent re-issue and re-dispatch an approved proposal | clean: IFIP_SEC-CASE-01 lineage extension — agent proposes under its own valid receipt chain, ancestry verifies, nonce fresh → `ALLOW` | adversarial: lineage splicing (foreign sub-chain grafted), lineage pruning (revoked ancestor truncated), proposal fan-out re-dispatch (one approval, many dispatches); parent-reference closure must fail the splice | `DENY` (multi-hop lineage closure at admission time); forged ancestry never admits |
| insider_or_observer | paired | A2/A4 confused deputy + audit observer | Confused-deputy delegation across tenants; forwarding to a different dispatch adapter; observer passive | clean: IFIP_SEC-CASE-06 control half — delegation to the *named* recipient adapter, audience binding matches → `ALLOW` | adversarial: IFIP_SEC-CASE-03/06 — tenant substitution and recipient mismatch via the deputy's legitimate authority; deputy's own credentials must never substitute for the delegator's scope | `DENY` (audience/tenant binding); observers yield no admission and no oracle contamination |

Schedule time is logical (§2): every revocation interleave above is expressed as dispatch → revoke-commit → consume ordering on the same schedule, so `revocation_timing` is testable without wall-clock assumptions and without SQLite stand-ins for RQ2.

## 7. Failure modes and stop conditions

- **Stop and revise if** one forbidden admission (oracle `DENY`, arm `ALLOW`) survives a complete independently labeled schedule; if the oracle fixture imports candidate code; if a baseline lacks permission/data/compute parity; if a holdout opens before freeze; if a PostgreSQL condition is claimed from SQLite observations; or if an incomplete/stale/`UNKNOWN` outcome is counted as a safe rejection.
- **Fail-closed rule:** any verification error (missing ancestor, epoch mismatch, ledger unreachable, nonce-store error) yields `DENY` with a stable reason code; no error class is silently treated as success.
- **Reporting rule:** invalid replay admissions, valid control acceptance, duplicate-consumption races, token bytes, p95 verify latency, and authorization DB round trips are reported per unique independent history; timeouts and unknowns are counted per arm and never dropped.
