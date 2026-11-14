# POPETS · Threat, trust and failure model — *Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts*

> **Task:** `POPETS-threat` (Phase `P01`, venue `popets`, priority `P0`) · **Status:** DESIGNED MODEL — structural threat specification, no empirical claims.
> **Machine contract:** `validate_threat() -> ThreatCoverage` from `research/venue2027/_shared/tools/threat_model.py` (version `1.0.0`), enforced by `research/venue2027/popets/tests/test_threat_model.py`.
> **Scope register:** `research/venue2027/popets/novelty_contract.md` (§4 truly distinct endpoint, §5 archive-reuse refusal) · **Fixtures:** `research/venue2027/VENUES/popets/CASE_MATRIX.md` (POPETS-CASE-01…09).
> **Synthetic-only:** every actor, subject, grant, and timestamp in this model is synthetic; no production data, secrets, or live provider calls are in scope (`SH-research_ethics`).

## 1. Scope and system model

The protected object is the **outbound model-dispatch stream** of a longitudinal AI assistant. A dispatch `d`, sent at logical time `t(d)`, may carry content assembled from five derivation paths:

1. **prompt segments** freshly assembled from authorized source records;
2. **cached summaries** derived from earlier authorized assemblies (transitively: summaries of summaries);
3. **embedding pointers** that resolve, at dispatch time, to vector content derived from source records;
4. **retry payloads** parked in a persistent retry queue after a failed send;
5. **fallback transports** (secondary provider endpoints, asynchronous batch channels) used when the primary transport is unavailable.

**Noninterference predicate (control target).** For consent grant `g`, purpose `p`, and dispatch `d` with `t(d) >= t_r` (revocation time recorded in the consent ledger):

```
forbidden_label(g, p) ∩ lineage(d) = ∅
```

where `lineage(d)` is the transitive closure of origin- and purpose-labels over every artifact consulted while assembling `d` (prompt segment, cached summary, embedding pointer, retry payload, fallback payload), and `forbidden_label(g, p)` is the label set withdrawn by revoking `g` for purpose `p`. **Re-disclosure after revoked consent from cached longitudinal context** — any post-`t_r` dispatch that carries revoked labels through any of the five paths — is the leak class this model exists to measure and prevent.

**Observation model.** Leakage is measured by a byte-level dispatch interceptor plus a sealed cancellation log (blueprint oracle). A dispatch blocked before send is a *cancellation*, not a leak; only bytes that leave the process boundary count as disclosure. The audit reports *preventable future* disclosures only (§5, §10).

## 2. Timing model — revocation and schedule time

- `t_r` — revocation request time, defined by the append-only consent ledger entry.
- `t_e` — effective revocation time: the point at which revocation propagation has reached every writer of the five derivation paths. The declared bound is `t_e − t_r ≤ Δ_max`; `Δ_max` is measured per deployment, never assumed zero.
- `t_d` — dispatch time assigned by the logical scheduler immediately before send; no hidden wall clock, no hidden randomness.
- **Event order:** events are totally ordered by `(logical_time, event_id)`. When the order of two events is unknown or contradictory (for example a dispatch whose assembly overlapped `t_r`), the state is `INDETERMINATE` and the dispatch fails closed (blocked or freshly reconstructed); the outcome is counted in the per-arm `indeterminate` bucket — never as a safe rejection.

**Schedule-time races in scope** (the adversary may influence scheduling, never the clock):

- R1 — dispatch in flight at `t_r`: assembled before revocation, sent after it.
- R2 — cache write in flight: a derived artifact built from a pre-revocation read lands in cache after `t_e`.
- R3 — retry-queue drain racing propagation through the `Δ` window.
- R4 — purpose/policy epoch change concurrent with revocation.
- R5 — clock skew between scheduler and ledger readers; eliminated by using only the ledger's logical clock for every `t(d) >= t_r` decision.

## 3. Attacker and observer capabilities

| id | Actor / observer | Capabilities | Boundary |
|---|---|---|---|
| A1 | Network observer | passive capture of dispatch bytes on any transport; traffic analysis and timing correlation | cannot break transport crypto; no endpoint compromise |
| A2 | Model provider (contractual) | receives and observes all dispatched bytes; retains them per stated terms; may serve cached context to its own subsystems | infrastructure compromise beyond contractual terms is excluded (§5) |
| A3 | Platform operator / insider | read access to caches, the lineage store, the retry queue, and schedule metadata; can correlate disclosures over time | cannot tamper with the sealed interceptor log or the consent ledger (§4) |
| A4 | Data subject / end user | issues revocation; observes own surfaces; may collude with an external party to probe re-disclosure | cannot forge ledger entries |
| A5 | Model agency | the model autonomously issues follow-up dispatches — regeneration, tool calls, cache-warming requests — that reuse cached longitudinal context without a fresh platform-side assembly | the model cannot sign dispatches itself; every outbound byte passes the interceptor |
| A6 | Scheduler adversary (re-issue power) | controls retry ordering and drain timing; can re-issue any historical dispatch payload — including byte-identical pre-revocation prompts — after `t_r` and out of causal order | cannot alter consent epochs or lineage labels, only reuse them |
| A7 | Cross-tenant / cross-purpose principal | issues requests under its own valid consent to probe cache-key reuse across purposes and tenants | authenticated only; no privileged cache read |
| A8 | Longitudinal observer | accumulates dispatches across visits and re-disclosures; performs linkage and re-identification from quasi-identifiers inside cached summaries | passive; no source-record access |

**Model agency and re-issue power are first-class capabilities.** A5 and A6 are what separate this threat model from record-read access control: content can leave the process boundary through a dispatch *no human explicitly requested*, and any *previously sent* payload can be *resent verbatim* by the retry machinery after consent is gone. Both capabilities act through ordinary system machinery, which is precisely why per-use reauthorization baselines can miss them.

## 4. Trusted components and trust assumptions

| Component | Trust basis | Failure semantics |
|---|---|---|
| **Consent ledger** | append-only, versioned, signed grant/revocation entries; single source of truth for `t_r`, the purpose set, and policy epochs | missing or ambiguous entry → fail closed (`INDETERMINATE`); never a default-allow |
| **Revocation propagation** | at-least-once, idempotent (keyed by revocation id) invalidation of reverse dependency edges from revoked grants to derived artifacts; bounded by `Δ_max` | edges not yet invalidated within `Δ_max` are treated as still live → dispatches touching them are blocked after `t_r` |
| **Lineage / label service** | labels derived artifacts at creation; tamper-evident edge store | missing ancestry edge → `INDETERMINATE_MISSING_LINEAGE`; fresh authorized reconstruction forced (POPETS-CASE-07) |
| **Dispatch interceptor** | byte-level, outside the candidate's code path, sealed cancellation log | any attempted interceptor bypass is counted as an environment failure per arm and invalidates the run |
| **Logical scheduler** | monotonic logical clock; the full schedule is recorded in the sealed log | hidden clocks or randomness are forbidden; a non-reproducible schedule invalidates the run |

**Trust assumptions made explicit.** (i) Ledger signature verification is correct (standard cryptographic assumption). (ii) Propagation completes within the declared `Δ_max`; the model does *not* assume instantaneous revocation. (iii) The provider honors its stated retention terms; behavior beyond terms is excluded (§5). (iv) No attacker capability includes writing to the ledger, the lineage store, or the sealed logs. (v) Every error surfaces as a stable reason code (§9); a routine incomplete, stale, or `INDETERMINATE` outcome is never counted as a safe rejection or as successful completion.

## 5. Excluded domains

1. **Compromised model-provider infrastructure beyond contractual terms.** If the provider's infrastructure is breached, or a provider insider exfiltrates retained context, the controls in this paper cannot help; that domain is governed by provider security terms and data-processing agreements, and it is explicitly excluded from this threat model and from every leakage metric.
2. **Already-delivered content (pre-`t_r` dispatches).** Bytes delivered to any external provider before `t_r` cannot be retracted. They are measured as `OUT_OF_SCOPE_PAST` (POPETS-CASE-06) and excluded from all preventable-leakage endpoints. **No claim of cryptographic retroactive erasure is made anywhere in this scope.**
3. **Post-delivery compromise of the recipient side** — provider-side downstream sharing within terms, subpoenas or other legal compulsion, and malware on recipient endpoints after receipt.
4. **Physical and side-channel attacks** on the dispatch host (EM, power, timing observable outside the interceptor's view).
5. **Statistical inference from authorized disclosures.** Utility-authorized bytes can still carry inferential risk; that residual is governed by data-minimization policy, reported as background surface — not as a revocation-gate failure.

## 6. Attack family and control matrix

Each family is paired: one clean control and one adversarial case, anchored to the venue fixture set (`CASE_MATRIX.md`). Verdict vocabulary follows the fixture contract: `ALLOW`, `DENY`, `DENY_ON_REVOKE`, `OUT_OF_SCOPE_PAST`, `INDETERMINATE`, `MEASURE`.

| Attack family | Pairing | Actor / observer | Capability exercised | Clean control | Adversarial case | Expected oracle verdict |
|---|---|---|---|---|---|---|
| revocation_timing | paired | A6 scheduler adversary + A2 provider | reorders or delays retry drain so a dispatch crosses `t_r` with stale consent state; exploits propagation lag `Δ_max` | clean: POPETS-CASE-02 — revocation is recorded before the scheduled retry fires; the interceptor cancels every dispatch with `t_d >= t_e`; zero synthetic canary bytes leave | adversarial: POPETS-CASE-08 — a retry is deliberately emitted out of causal order carrying a stale consent epoch, racing the revocation barrier inside `Δ_max` | DENY (fail closed on unknown ordering); zero forbidden bytes after `t_r` |
| replay | paired | A6 scheduler adversary (re-issue power) | drains the retry queue or fallback transport with a byte-identical pre-revocation prompt payload after `t_r` | clean: POPETS-CASE-09 — an identical re-dispatch while consent is still valid and the purpose unchanged is authorized (disclosure ALLOW; cost MEASURE) | adversarial: POPETS-CASE-02 — the cached pre-revocation context is re-issued after `t_r` through the retry queue or a fallback path | DENY via consent-epoch revalidation immediately before send, on every transport |
| model_agency | paired | A5 model agent + A2 provider (observer) | model initiates a regeneration or tool-call dispatch reusing cached longitudinal context; the provider observes and retains dispatched bytes within terms | clean: POPETS-CASE-01 — the provider receives exactly the authorized bytes for the stated purpose under valid consent | adversarial: a model-initiated dispatch after `t_r` assembled from cached summaries or embedding pointers without a fresh consent-gated assembly | DENY; every model-initiated dispatch passes the same gate as scheduler-initiated dispatch |
| purpose_scope | paired | A7 cross-purpose principal + A3 operator | cache key omits purpose or policy epoch, so context built for purpose A serves purpose B (cache-key purpose confusion) | clean: POPETS-CASE-04 — an unrelated record edit for purpose B recomputes scope-local context; no stale reuse and no false invalidation | adversarial: POPETS-CASE-05 — a purpose-B request resolves a cache entry built under purpose A's consent scope | DENY; strict `(tenant, principal, purpose, epoch)` key binding; purpose inheritance reaches derived summaries (POPETS-CASE-03) |
| insider_or_observer | paired | A3 platform insider + A8 longitudinal observer | reads the cache or lineage store, or accumulates re-disclosures across visits, to re-identify the subject via quasi-identifiers | clean: POPETS-CASE-06 — bytes already delivered before `t_r` are classified `OUT_OF_SCOPE_PAST` and excluded from preventable-leakage claims; authorized audit reads see only minimized labels | adversarial: POPETS-CASE-03 — the revoked subject's derived summary chain is re-disclosed and linked across dispatches; POPETS-CASE-07 supplies a missing-ancestry probe | DENY_ON_REVOKE with zero transitive survivors; missing lineage → `INDETERMINATE`, fail closed |

## 7. Family analyses

### 7.1 `revocation_timing` — races between revocation and the dispatch schedule

**Threat.** A dispatch whose assembly began before `t_r` is sent after it (R1); a derived artifact is written to cache after `t_e` from a pre-revocation read (R2); the retry queue drains inside the propagation window (R3); a purpose or policy epoch flips concurrently with revocation (R4).

**Leak witness.** The interceptor records forbidden-label bytes in a post-`t_r` dispatch whose schedule entry predates `t_r`.

**Controls.** Every assembled artifact carries the consent epoch it was built under; authorization is revalidated immediately before send, not at enqueue time; reverse-edge invalidation is ordered before any queue drain; unknown ordering fails closed (§2).

**Baseline behavior.** B0 (TTL-only) leaks throughout the window; B1 (coarse purge) blocks but pays false-invalidation cost; B2 (always-recompute) blocks at assembly; B3 (consistency tokens) blocks only if the token is revalidated at send and leaks if checked only at enqueue; B4 (candidate) blocks via reverse edges at drain time.

**Fixtures.** Clean: POPETS-CASE-02 → `DENY`. Adversarial: POPETS-CASE-08 → `DENY`.

### 7.2 `replay` — re-issue of pre-revocation prompts

**Threat.** A6 re-issues a byte-identical pre-revocation prompt payload after `t_r` through the retry queue or a fallback transport. The idempotency machinery that exists for crash recovery (stable logical operation IDs) becomes a leak channel precisely because it intentionally bypasses reassembly.

**Leak witness.** Two interceptor records with identical payload hashes — one before `t_r`, one after — where the latter is not a cancellation.

**Controls.** Every transport (primary, retry, fallback) revalidates the consent epoch against the ledger immediately before send; payloads carry the epoch they were assembled under, and a stale epoch produces a `DENY_EPOCH_STALE` cancellation; retries stay idempotent by logical operation ID but are never exempt from revalidation.

**Baseline behavior.** B0 leaks; B1 blocks after purge; B2 blocks; B3 blocks only if derived-cache tagging covers the retry queue; B4 blocks because the retry queue is a first-class lineage node.

**Fixtures.** Clean: POPETS-CASE-09 → disclosure `ALLOW`, cost `MEASURE`. Adversarial: POPETS-CASE-02 → `DENY`.

### 7.3 `model_agency` — provider observation of cached context and model-initiated dispatch

**Threat.** Two sub-threats. (a) *Observation*: even a fully authorized dispatch exposes cached longitudinal context to the provider, which observes and retains it within terms — the exposure surface persists beyond platform control. (b) *Agency*: A5 initiates a dispatch that reuses cached summaries or embedding pointers without a fresh platform-side assembly, potentially after `t_r` (for example an agentic regeneration or cache-warming call).

**Leak witness.** An outbound dispatch whose assembly trace contains no user-initiated request record; or provider-side re-serving of pre-revocation context via a model-initiated flow.

**Controls.** Model-initiated dispatches pass the identical gate — same `forbidden_label ∩ lineage` predicate, same epoch revalidation; cache-warming may only materialize artifacts labeled with their source grants; provider observation within terms is *declared exposure*, reported as background and never counted as a gate failure, while provider behavior beyond terms is excluded (§5.1).

**Baseline behavior.** B2 blocks model-initiated leaks by construction (nothing cached); B0, B1, B3, and B4 must explicitly cover the model-initiated path or their leak counts include it.

**Fixtures.** Clean: POPETS-CASE-01 → `ALLOW` (exact authorized bytes). Adversarial: model-initiated regeneration after `t_r` → `DENY`.

### 7.4 `purpose_scope` — cache-key purpose confusion

**Threat.** A cache key that omits purpose, principal scope, or policy epoch lets a request for purpose B resolve context assembled and consented for purpose A — consent given for self-care guidance is silently reused for a purpose the subject never consented to. Derived summaries inherit the origin purpose, so confusion propagates transitively through summary-of-summary chains.

**Leak witness.** Two dispatches with different declared purposes resolving the same cache entry ID.

**Controls.** Cache keys bind `(tenant, principal, purpose, consent epoch)`; purpose labels propagate through every derivation edge; a purpose change on a derived artifact forces re-labeling or invalidation; unrelated edits must not trigger cross-purpose invalidation (false-invalidation guard).

**Baseline behavior.** B0 confuses freely; B1 purges everything on any consent change (safe, high false-invalidation cost); B2 recomputes per purpose; B3 is safe only if derived-cache tagging includes purpose in the tag set; B4 propagates purpose labels through the closure.

**Fixtures.** Clean: POPETS-CASE-04 → `ALLOW` with no false invalidation. Adversarial: POPETS-CASE-05 → `DENY`; POPETS-CASE-03 → `DENY_ON_REVOKE`.

### 7.5 `insider_or_observer` — insider linkage and longitudinal re-identification

**Threat.** A3 or A8 accumulates re-disclosures over time: individually authorized summaries, re-issued across visits, link into a quasi-identifier trajectory that re-identifies the subject. A revoked subject is especially exposed because their historical cached summaries are exactly the high-entropy artifacts most attractive to link. Separately, an insider reading the lineage store directly obtains the subject's derivation graph.

**Leak witness.** A linkage set: at least two post-`t_r` dispatches sharing forbidden-label derived content under the same subject key, observed by A3 or A8.

**Controls.** Lineage-store access is role-gated and audit-logged; dispatch bytes are minimized per purpose; per-purpose cache partitioning limits cross-surface linkage; the audit reports only *preventable* post-`t_r` disclosures (pre-`t_r` delivery is `OUT_OF_SCOPE_PAST` — never silently dropped, never claimed as prevented); missing ancestry edges fail closed to defeat lineage-store tampering.

**Baseline behavior.** All baselines remain exposed to linkage unless byte-minimization is applied; B2 limits stale linkage by construction at full recompute cost.

**Fixtures.** Clean: POPETS-CASE-06 → `OUT_OF_SCOPE_PAST` (threat precision). Adversarial: POPETS-CASE-03 → `DENY_ON_REVOKE`; POPETS-CASE-07 → `INDETERMINATE`, fail closed.

## 8. Oracle and actor authority

- Authority is **defined and partitioned**: (a) the **consent ledger** is authoritative for `t_r`, grants, purposes, and epochs; (b) the **sealed interceptor and cancellation log** are authoritative for which bytes left the process and when; (c) the **independent oracle** — recomputation of all live-purpose permission clauses directly from source snapshots, code disjoint from the candidate (module isolation enforced here and in `POPETS-oracle`) — is authoritative for `ALLOW` / `DENY` / `DENY_ON_REVOKE` verdicts; (d) truth labels derive from the **event sequence and policy/consent ground truth**, never from candidate reason codes (`GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`, item 2); (e) a human adjudicator resolves `INDETERMINATE` cases before holdout access, and the resolution is recorded in the run manifest.
- Reviewers are blinded to the model arm; the oracle never imports candidate invalidation code.
- An actor or authority that is absent, ambiguous, or self-contradictory is a **fail-closed** condition: the case is recorded as rejected-or-indeterminate in the mutually exclusive per-arm outcome counts — never as a safe rejection, never silently dropped.

## 9. Failure semantics and stable reason codes

| Reason code | Meaning | Counted as |
|---|---|---|
| `DENY_POST_REVOCATION` | dispatch with `t_d >= t_r` carries forbidden lineage | cancellation if blocked before send; disclosure if bytes left |
| `DENY_PURPOSE_MISMATCH` | dispatch purpose is not among the purposes consented for the lineage labels | cancellation |
| `DENY_EPOCH_STALE` | payload bound to a superseded consent or policy epoch | cancellation |
| `INDETERMINATE_MISSING_LINEAGE` | ancestry edge absent or unverifiable | indeterminate bucket; fresh authorized reconstruction forced |
| `OUT_OF_SCOPE_PAST` | bytes delivered before `t_r` | excluded from preventable-leakage endpoints; reported for precision |
| `ENVIRONMENT_FAILURE` | interceptor, clock, or ledger unavailable | environment-failure bucket; run invalidated |

## 10. Prominent limitation and falsification hook

- **Nothing already delivered can be retracted.** This model governs *future* dispatches after `t_r` only (novelty contract §5.4); already-delivered bytes are excluded from every leakage claim (§5.2).
- If the always-recompute authorized projection (B2) matches the candidate (B4) with negligible overhead and zero post-revocation leakage on the frozen holdout, the mechanism claim narrows to an engineering trade-off (blueprint falsification rule; novelty contract C8). The threat model itself remains valid as the measurement contract.
- Metrics bound to this model: future unauthorized disclosure rate, attribute-exposure byte count, conditional cache hit rate, false invalidation rate, latency and rebuild cost, and re-issue-path coverage — the blueprint's replay-path coverage metric, reconciled against independently generated dispatch schedules (`RQ3`).

## 11. Cross-references

- Fixtures and verdict vocabulary: `research/venue2027/VENUES/popets/CASE_MATRIX.md`.
- Baselines B0–B4: `research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md`.
- Scope, claims C1–C8, decision: `research/venue2027/popets/novelty_contract.md`.
- Evidence gates and per-arm outcome accounting: `research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`.
