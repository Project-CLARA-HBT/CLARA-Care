# SACMAT-threat · Threat, trust and failure model — PolicyTrace

> **Task:** `SACMAT-threat` · **Phase:** `P01` · **Venue:** `sacmat` · **Status:** signed threat model (design-time, PROSPECTIVE / NOT RUN)
> **Paper:** PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines
> **Contract signature:** `validate_threat() -> ThreatCoverage` (shared validator `research/venue2027/_shared/tools/threat_model.py`, `THREAT_MODEL_VERSION = 1.0.0`)
> **Input dependencies (verified PASS in `research/venue2027/STATE/completion.json` at base SHA `f35af111cc04588c8c35705a53b47c4586db137d`):** `SACMAT-scope` (novelty contract, signed GO), `SH-research_ethics` (synthetic-only ethics constraints).
> **Evidence status:** This document is a *design-time threat and trust model* for the PolicyTrace study protocol. It declares no experimental results and no measured numbers; every case below is a designed fixture to be implemented and adjudicated by the frozen protocol (`SACMAT-rq_registry`, downstream).

## 1. Scope of the model

PolicyTrace re-executes one ordered `(policy history, request)` unit into several heterogeneous
policy decision points (Cedar, OpenFGA, OPA; XACML encodings as the static-comparison encoding) and
adjudicates decision parity with a portable four-valued oracle (PERMIT / DENY / NOT_APPLICABLE /
INDETERMINATE). The unit of analysis is the ordered history-plus-request pair — never per-request
pseudo-replication. This model defines **who can do what to the measurement**, which components are
trusted, what is explicitly out of scope, and how every attack family is paired with a clean control
so that no claimed capability is documented without a baseline case.

The five canonical families of the shared validator are all covered, and the SACMAT-specific
delegated-consent divergence families are registered as extended families in the same paired matrix
(§2), keyed to the F01–F05 temporal fault taxonomy of the novelty contract.

## 2. Attack family and control matrix

Every family has **at least one clean control case and one adversarial case**, and both cells are
adjudicated by the independent oracle. Family identifiers use the shared validator's canonical
tokens; extended SACMAT-specific families are registered below them in the same paired format.
Expected verdicts are oracle targets for *designed fixtures*, not observed results.

| Attack family | Case | Actor / observer | Capability exercised | Clean control (expected oracle verdict) | Adversarial case (expected oracle verdict) | paired |
|---|---|---|---|---|---|---|
| revocation_timing | `SACMAT-THR-01` | A1 malicious delegate + A2 history injector | Reorders revoke/request at a zero-width tick; races delegation expiry against decision time | clean: grant→revoke→request ordering; oracle says DENY, stale grant must not authorize (baseline revocation correctness, cf. SACMAT-CASE-03) | adversarial: request declared at the same logical tick as revoke; oracle says INDETERMINATE where schedule-time semantics are underspecified, and engines that silently return PERMIT are recorded as disagreement | yes |
| replay | `SACMAT-THR-02` | A1 malicious delegate | Re-invokes an archived request after revocation or expiry | clean: first presentation of a valid delegation within its window; oracle says PERMIT | adversarial: re-invocation of the same request after revoke/expiry; oracle says DENY and any engine returning PERMIT is a witness divergence | yes |
| model_agency | `SACMAT-THR-03` | A3 adapter author + insider reviewer | Tries to make the oracle inherit engine output or coerce INDETERMINATE to a safe-looking verdict | clean: oracle decides from `(history, request)` under declarative semantics only; four-valued verdict recorded with reason code | adversarial: adapter under-translates a temporal construct and engine output is offered as ground truth; oracle must return INDETERMINATE (pre-labeled untranslatable), never inherit the engine's PERMIT/DENY; coercion attempt is an audit failure | yes |
| purpose_scope | `SACMAT-THR-04` | A1 malicious delegate | Claims purpose broader than the delegation grant (purpose narrowing mid-chain) | clean: request purpose equals granted purpose; oracle says PERMIT | adversarial: granted `self_care`, requested `research`; oracle says DENY, and a mutant that drops the purpose predicate is killed by this trace (cf. SACMAT-CASE-02/06) | yes |
| insider_or_observer | `SACMAT-THR-05` | A5 insider + A4 observer | Selectively drops failing traces or relabels INDETERMINATE as safe DENY in the report path | clean: complete per-arm record with timeout/unknown/rejected counts for all arms; report matches raw logs | adversarial: report omits failing traces for one arm; audit recomputes counts from content-hashed per-arm records and the omission is detected as an integrity failure | yes |
| delegated_consent_divergence | `SACMAT-THR-06` | A3 adapter author + A1 delegate | Same delegated-consent history fed to Cedar vs OpenFGA vs OPA encodings exposes non-parity invisible to single-request tests | clean: single-request ABAC permit/deny parity across engines on non-temporal cases (cf. SACMAT-CASE-01/02/08); engines agree with oracle | adversarial: grant→revoke→regrant history with purpose narrowing fed identically into each engine; oracle says DENY at the final request, and any engine returning PERMIT constitutes a recorded conformance-divergence witness (the study's distinct endpoint) | yes |
| delegation_subchain_forgery | `SACMAT-THR-07` | A1 malicious delegate | Forges sub-chain depth/order claims: declares a delegation path longer, shorter, or reordered than the stored history | clean: request context carries the exact stored delegation chain (A delegates to B, B to C); oracle says PERMIT for C within scope | adversarial: C claims a direct A→C chain or reordered intermediate hops; oracle says DENY (chain not derivable from history); engines that reconstruct chains from relations may return PERMIT — a recorded divergence class | yes |
| policy_version_skew | `SACMAT-THR-08` | A2 history injector + A3 adapter author | Pins different policy-document versions across arms so grant and revoke resolve under different policy revisions | clean: all arms pin the same content-hashed policy version for one history; decisions are parity-checked at one version | adversarial: grant evaluated under policy v1, revoke/request under v2 (skewed pin); oracle labels the unit INDETERMINATE at mixed versions and engines accepting the skew return divergent decisions — version pinning is asserted per arm and mismatch is a detected fault, not silently normalized | yes |
| obligation_purpose_mismatch | `SACMAT-THR-09` | A1 delegate + A3 adapter author | Grant carries an approval obligation (e.g., clinician counter-sign) that the engine encoding drops, or request purpose diverges from the obligated purpose | clean: obligation satisfied within the same purpose scope; oracle says PERMIT with obligation recorded | adversarial: emergency override requested without the approval obligation, or obligation satisfied under a different purpose; oracle says DENY (F05 fault class), engines silently dropping obligations return PERMIT — recorded divergence | yes |
| conformance_test_evasion | `SACMAT-THR-10` | A3 adapter author | Crafts encodings so every conformance test passes while an untranslatable temporal construct is silently dropped from all engines | clean: corpus declares each temporal construct with its per-engine expressibility label; untranslatable ones are pre-labeled INDETERMINATE and excluded from parity denominators | adversarial: encoding silently omits a temporal metamorph construct so engines cannot disagree; audit cross-checks corpus manifests against encoding coverage — any tested-for construct missing from an encoding is an evasion failure, never scored as engine parity | yes |
| temporal_delegation_expiry_race | `SACMAT-THR-11` | A1 delegate + A2 history injector | Places expiry exactly at the request tick; varies expiry declaration (policy-relative vs decision-time) across engines | clean: request strictly before expiry under every declared schedule semantics; oracle says PERMIT uniformly | adversarial: request at exactly the expiry tick; oracle says INDETERMINATE where schedule-time semantics are underspecified; engines splitting differently (before-on-tick vs after-on-tick) are recorded as a divergence class (F01 expired-delegate family) | yes |

**Family coverage note.** The five canonical validator families each carry a paired clean/adversarial
case above; the six extended SACMAT families (delegated-consent divergence, sub-chain forgery,
policy-version skew, obligation/purpose mismatch, conformance-test evasion, expiry race) are
registered in the same paired format and keyed to the F01–F05 temporal fault taxonomy. Extended
families are additional required pairs; they do not replace the canonical five.

## 3. Attacker and observer capabilities

Attackers and observers act only through **inputs the study protocol already admits**: synthetic
policy histories, delegation grants/revocations, request attributes, purpose claims, clock/epoch
declarations, and engine adapters. No attacker in this model executes code inside a policy engine,
modifies study source after freeze, or touches real clinical systems. Capabilities are graded:

| Grade | Actor | Capabilities | Hard limits |
|---|---|---|---|
| A1 | Malicious delegate (synthetic principal) | Presents stale or re-scoped delegation tokens; re-invokes an access request after revocation or expiry; claims a broader purpose than granted; forges delegation sub-chain depth/order claims in its request context | Cannot modify stored policy history; cannot write oracle labels; cannot alter engine encodings after freeze |
| A2 | History-injecting adversary (corpus author role gone rogue, design-time only) | Constructs adversarial histories: revoke-before-request orderings, expiry racing decision time, purpose narrowing mid-chain, sub-chain reordering | Bounded by the frozen generator protocol; every injected history is versioned and hashed; cannot open the holdout split before freeze |
| A3 | Engine-semantics adversary (adapter author) | Chooses encodings that under-translate temporal constructs so that an engine *looks* conformant; drops NOT_APPLICABLE/INDETERMINATE mapping to force a decision | Encodings are frozen with source hashes before scoring; untranslatable constructs must be pre-labeled INDETERMINATE by the oracle, never coerced to PERMIT/DENY |
| A4 | Noise/observer adversary | Re-invokes benign request streams to saturate the fixed oracle-call budget; issues malformed histories to provoke crash-or-default behavior | Observed only via sanitized telemetry (attempt id, arm id, durations, error class, input/output SHA256); no PII and no policy content in logs |
| A5 | Insider with report access (post-run) | Selectively drops failing traces, relabels INDETERMINATE as safe DENY, cherry-picks engine pairs | Every run emits a complete per-arm record including timeout/unknown/rejected counts; selective drop is an audit failure, not an option |

**Observer model.** Observers see published artifacts only: sanitized per-arm records, aggregate
mutation scores, disagreement rates, and minimal failure traces with policy-content redaction.
Observers cannot distinguish individual synthetic principals, and telemetry excludes names, emails,
queries and drug or policy-content lists (no-PII telemetry invariant).

**Timing and re-invocation (replay) power.** The adversary fully controls the logical ordering of
history events (grant, revoke, regrant, delegate, expire, request) within the frozen generator
grammar, including zero-width orderings (revoke and request declared at the same logical tick) that
force engines to reveal their revocation/schedule-time semantics. The adversary can re-invoke any
prefix of any archived history an unbounded number of times against the same engine encodings —
replay power is unlimited against engines and nonexistent against oracle labels (labels are frozen
and hashed).

**Model agency.** The "model" in PolicyTrace is the declarative reference-semantics model encoded in
the independent oracle. Model agency is deliberately narrow: the oracle model decides
PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE from `(history, request)` alone, never from engine output,
never from candidate-generator internals, and never from aggregate statistics. A statistical
confidence value or a cryptographic digest of evidence is never accepted as a clinical or
authorization judgment. If the model's authority is contested for a case, the case is escalated to
independent human review with the case labeled INDETERMINATE until adjudicated — an undecided case
is never silently coerced to a safe-looking verdict.

## 4. Trusted components

Trust is assigned per component with a named failure semantics; a trusted component failing its
declared semantics is a stop-and-revise condition, not a finding.

| Component | Trust basis | Trusted for | Not trusted for | Failure semantics |
|---|---|---|---|---|
| Declarative reference-semantics model (independent oracle) | Written from the semantics document; never imports generator or engine code; source-frozen with SHA | Ground-truth four-valued decisions on `(history, request)` units; INDETERMINATE labeling of untranslatable constructs | Measuring engine behavior; scoring candidates; post-hoc repair to match any engine | Fail closed: unknown input shape → INDETERMINATE + stable reason code, never a default PERMIT/DENY |
| Independent human adjudication | Separate reviewers; no access to candidate outputs; blind to arm identity | Resolving semantically non-equivalent mutant ground truth and contested INDETERMINATE cases | Bulk decision generation; overriding oracle for scored units without recording | Disagreement recorded in `oracle_disagreement_count`; unresolved → INDETERMINATE retained |
| Conformance adapters (Cedar/OpenFGA/OPA/XACML encoders) | Frozen encodings with content hashes; faithful to each engine's documented best practice | Faithful translation of the shared history corpus into engine-native encodings | Deciding correctness (they never produce truth); masking untranslatable constructs as corpus errors | Untranslatable construct → pre-labeled INDETERMINATE unit; adapter crash → arm counted as failed, not as DENY |
| Frozen history corpus + versioned policy graphs | Deterministic generator under fixed seed + generator version; content-hashed | Providing identical `(history, request)` bytes to every arm | Containing any real patient data (synthetic-only, per SH-research_ethics) | Missing dependency → task BLOCKED with stable reason code; never silently skipped |
| External engine binaries (Cedar, OpenFGA, OPA) | Pinned upstream versions, integrity-hashed at pin time | Executing their own policy semantics during replay | Declaring conformance truth; being trusted for security guarantees | Engine crash/timeout counted per arm as timeout/unknown; never mapped to a safe decision |
| Content-hash evidence chain (SHA256 over case/truth/observed) | SHA256 over frozen inputs and outputs | Binding a published number to the exact inputs that produced it | Proving clinical or authorization correctness (a hash is provenance, not semantics) | Hash mismatch → artifact refused, run invalid |

Trusted-component trust is **fail-closed**: any trusted component that cannot produce a defined
verdict contributes INDETERMINATE plus a stable reason code, and an INDETERMINATE outcome is never
counted as a safe rejection or a successful completion in any denominator.

## 5. Excluded domains

The following are explicitly **out of scope** and no claim, metric, or fault family in this study
depends on them:

1. **Engine implementation compromise.** Compromise of Cedar/OpenFGA/OPA/XACML implementation
   internals (memory corruption, supply-chain backdoors, malicious engine releases) is excluded. The
   study measures documented-semantics divergence between pinned engines; a compromised engine is a
   threat to every authorization system, not a conformance-testing research variable. Pinned
   binaries are integrity-hashed to *detect* substitution, not to *defend* against a malicious
   upstream.
2. **Cryptographic defense strength.** Proof-of-possession schemes, signature schemes, token
   encryption, and key management behind delegation tokens are excluded; delegation credentials in
   the corpus are abstract unforgeable references.
3. **Network and transport security.** TLS, transport-layer anti-replay tokens, DoS resistance of
   engine endpoints, and side channels (timing, cache) are excluded; replay in this study is a
   *logical* history-ordering phenomenon.
4. **Production clinical systems and real patient data.** No production secret, credential, or
   patient record is accessed; the corpus is synthetic-only by SH-research_ethics. Clinical workflow
   safety is the AIME 2027 study's endpoint, not this one.
5. **Database and concurrency semantics.** Zanzibar-style consistency (zookies, stale reads) is
   cited as background; no PostgreSQL/SQLite claim is made, no storage backend is measured.
6. **Performance and scalability of policy engines.** Generation runtime is recorded as an
   operational metric, but engine throughput, latency, and memory are not study endpoints.
7. **Physical and organizational security.** Badge access, HR processes, and administrative
   overrides outside the policy corpus are excluded.

## 6. Oracle and actor authority

Authority is **defined**, exhaustively, as follows:

- **Oracle authority.** The declarative reference-semantics model is the sole authority for
  four-valued verdicts on `(history, request)` units. It is authored from the semantics document,
  versioned and frozen, and it never imports generator, engine, or candidate code (oracle
  independence invariant from SACMAT-scope §5). Its failure mode is fail-closed: an input it cannot
  interpret yields `INDETERMINATE` plus a stable reason code, never a default decision.
- **Human adjudication authority.** Independent reviewers are the sole authority for (a) mutant
  equivalence classification (equivalent / non-equivalent / indeterminate) and (b) contested
  INDETERMINATE escalation. Reviewers have no access to candidate outputs and no power to change a
  frozen oracle label on a scored unit; their disagreement with the oracle is recorded in
  `oracle_disagreement_count`, never silently resolved.
- **Actor authority (who may act on the system under test).** Synthetic principals may act only
  within the scope of the stored, versioned policy history: a delegate may act only where a valid,
  unexpired, correctly-ordered delegation chain exists for the claimed purpose. Any authority claim
  not derivable from the stored history is undefined authority and the oracle verdict is DENY or
  INDETERMINATE — undefined authority is never treated as safe, and an INDETERMINATE outcome is
  never counted as a safe rejection or a successful completion in any denominator.
- **Engine authority.** Engines execute their own semantics during replay but hold **no authority
  over ground truth**; engine–oracle mismatches are findings (divergence witnesses), not labels.
- **Report authority.** Published numbers derive mechanically from
  `artifacts/venue2027/sacmat/<run_id>/manifest.json` with the content-hash evidence chain; no agent
  may hand-enter a result. Selective dropping of outputs is an integrity failure (see A5).

**Negative control (undefined oracle/actor authority).** If a fixture cannot name which component
holds verdict authority for a case — e.g., an encoding-under-specified temporal construct with no
pre-registered INDETERMINATE label, or a request whose claimed delegation chain is not derivable
from any stored history — the case is **blocked from scoring** with reason code
`UNDEFINED_AUTHORITY`. It is never scored, never mapped to a safe decision, and never silently
dropped; the unit is recorded as blocked with the reason code and excluded from denominators
transparently.

## 7. Attack-family to RQ and fault-taxonomy mapping

| Family | RQ | Fault class (novelty contract F01–F05) | Mechanism of harm if untested |
|---|---|---|---|
| revocation_timing | RQ1, RQ2 | F03 revoke-then-regrant ordering | Stale grant authorizes after revocation |
| replay | RQ1, RQ2 | F03 (replay witness) | Revoked/expired delegation silently re-authorizes |
| model_agency | RQ1, RQ3 | cross-cutting (oracle integrity) | Engine output laundered into ground truth; INDETERMINATE coerced |
| purpose_scope | RQ1, RQ2 | F04 nested-purpose mismatch | Purpose-bounded consent broadened by delegation |
| insider_or_observer | RQ2 (report integrity) | cross-cutting (evidence chain) | Cherry-picked traces inflate mutation score |
| delegated_consent_divergence | RQ3 | F01–F05 (endpoint family) | Engines disagree only on ordered histories; single-request tests see parity |
| delegation_subchain_forgery | RQ1, RQ3 | F02 inheritance conflict | Fabricated or reordered delegation chains authorize |
| policy_version_skew | RQ1, RQ3 | F01/F03 (version-sensitive ordering) | Mixed policy versions normalize divergent decisions |
| obligation_purpose_mismatch | RQ1, RQ2 | F05 emergency override without approval obligation | Obligations silently dropped in encoding |
| conformance_test_evasion | RQ3 (method integrity) | cross-cutting (corpus coverage) | Silent construct omission manufactures false parity |
| temporal_delegation_expiry_race | RQ1, RQ2 | F01 expired-delegate role | Expiry boundary semantics differ per engine |

## 8. Stop-and-revise triggers (binding)

- A forbidden commit (frozen E15–E22/GovMut evidence as new SACMAT evidence) or a forbidden
  disclosure survives a complete independently labeled schedule — per SACMAT-scope §3.3.
- The oracle or a test fixture imports candidate implementation and thereby ceases to be
  independent.
- A baseline (B0–B4) is not faithful to its declared semantics or lacks permission/compute parity;
  `NOT_RUN_EXTERNAL` must be declared transparently rather than silently substituted.
- The holdout mutant families are opened before protocol freeze, or any output is selectively
  dropped.
- A real-engine claim is made without executing the real engine; naming Cedar/OpenFGA/OPA is not
  executing them.
- A routine incomplete/stale/UNKNOWN/INDETERMINATE outcome is counted as a safe rejection or
  successful completion in any denominator.
- A trusted component fails its declared failure semantics in §4.

## 9. Ethical and evidence constraints

Synthetic-only identities, timestamps, and stable source hashes (SH-research_ethics); no real
patient records, no production secrets. Telemetry records attempt id, independent unit id, arm id,
source SHA, backend, duration, error class and input/output SHA256 — with sensitive content
sanitized and failures never silently filtered. All numbers in downstream reports must derive
mechanically from frozen manifests; this document asserts none.

---

*Signed as the SACMAT P01 threat, trust and failure model by the SACMAT-threat agent, 2026-11-15,
at base SHA `f35af111cc04588c8c35705a53b47c4586db137d`. Downstream consumers: `SACMAT-prior`,
`SACMAT-overlap`, `SACMAT-rq_registry` (estimands), corpus generator and oracle implementation
tasks.*
