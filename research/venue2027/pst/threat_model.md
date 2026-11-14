# PST threat, trust and failure model — ReceiptMin

**Task:** `PST-threat` (phase `P01`, venue `pst`, priority `P0`, agent `security`)
**Version:** 1.0.0 (2026-11-15; worktree base SHA `f35af111cc04588c8c35705a53b47c4586db137d`)
**Study:** *ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization* — see `pst/novelty_contract.md` (Decision: GO) and `VENUES/pst/CASE_MATRIX.md` (case anchors PST-CASE-01…09).

This is a design-level model: it declares adversaries, trusted components, excluded domains, time semantics and paired attack/control cases. It contains no measured results; every quantitative outcome is deferred to P02+ and must derive mechanically from `artifacts/venue2027/pst/<run_id>/manifest.json`. It validates against the shared contract `research/venue2027/_shared/tools/threat_model.py` (`validate_threat()`, version 1.0.0).

## Object of protection and system view

The evaluated artifact is **B4 — the purpose-bound minimized receipt plus retention map** — measured against B0 (full plaintext append-only log), B1 (hash-only content digests), B2 (encrypted full log with role-gated decryption and managed deletion) and B3 (RFC 9162-style Merkle transparency with authorized material retrieval).

Protected assets:

| Asset | Content | Loss condition |
|---|---|---|
| S1 event commitment | HMAC-bound digest committing an AI health action to a purpose and a consent/policy epoch | forgery or unnoticed substitution breaks forensic accountability |
| S2 consent/policy epoch proof | evidence that the action was authorized under the epoch active at commit | staleness conflated with validity |
| S3 retention map | per-field schedule declaring what decays at each retention deadline | silent schedule editing erases or extends retention selectively |
| S4 residual receipt content | whatever content fields survive minimization at the reader's epoch | linkage or attribute inference beyond declared bounds |
| S5 independent oracle ledger | trusted offline complete ledger held by the evaluation role | any candidate access invalidates adjudication |

Trust boundary: everything downstream of the commit event — storage, extracts, the audit reader's workstation — is potentially compromised up to the capabilities declared below. Integrity of committed history rests on the witnessed append-only chain; confidentiality of residual content rests on minimization plus key custody, never on the chain alone.

## Attacker and observer capabilities

Privileges are declared ex ante and frozen before any arm runs; the RQ2 primary adversary is P1 extended with P2's auxiliary joins.

| ID | Actor | Privilege / capability | Boundary respected |
|---|---|---|---|
| P1 | compromised read-only audit reader | reads every retained artifact granted to the audit role (receipts, retention map, chain heads) at its epoch; cannot write, delete, or decrypt | read-only; no key custody |
| P2 | auxiliary-data joiner | P1 plus external linkage tables (public records, employer schedules, marketing data) joined on quasi-identifiers such as pseudonyms, timestamps and purpose strings | no write or delete; joins are measured, not assumed away |
| P3 | forensic-query abuser | holds a legitimate query credential; issues adjacent-window and differencing queries to compose leakage across retention epochs (PST-CASE-03) | query budget is a declared control, not a physical limit |
| P4 | malicious committer (agency abuse) | controls which evidence fields enter a receipt at commit time; may under-commit to evade future accountability | cannot alter the frozen mandatory-field set unnoticed |
| P5 | receipt forger / injector | crafts well-formed receipts and submits them into extracts or exports; lacks the chain-head witness and the purpose-binding keys | cannot retroactively append to the witnessed chain |
| P6 | post-retention reader | reads only what survives the retention schedule at epoch E+1; models the post-retention access privilege named in the study thesis | sees decayed content only |
| P7 | passive transport observer | observes collection metadata in transit only | no store access |

**Resubmission power.** P3 and P5 may resubmit captured artifacts, including after a purpose authorization has ended. Controls: every commit carries a stable logical operation ID so duplicate submission collapses idempotently, and every receipt carries the epoch identifiers against which a verifier checks freshness; a stale artifact is rejected as `STALE_EPOCH` and the rejection is counted, never treated as a silent success.

**Model agency.** The assistant commits receipts autonomously for each health action. Agency is bounded: the ex-ante frozen forensic query set defines the mandatory evidence field set per query class, so the committer can neither withhold a mandatory field (a missing field yields `INDETERMINATE`, PST-CASE-05) nor add unrestricted content (the purpose string itself is a redaction surface, PST-CASE-06). Agency never extends to adjudication: a committing arm cannot mark its own output reconstructed or private.

## Trusted components

Trust is narrow and failure behavior is declared per component; a component trusted for integrity is never treated as confidential, and a digest is never treated as authorization.

| ID | Component | Exact trust assumption | Failure behavior |
|---|---|---|---|
| T1 | append-only receipt log | hash-chained and tamper-evident; the chain head is witnessed outside the audit reader's privilege; the log is *not* confidential and *not* tamper-proof | any edit or witness mismatch yields `DETECT_TAMPER` with break location (PST-CASE-04) |
| T2 | retention policy engine + retention map | the policy version is pinned into each receipt; the engine enforces per-field decay at declared retention deadlines | schedule tampering yields `RETENTION_MAP_TAMPER`; a missing epoch yields `MISSING_EPOCH`, fail closed |
| T3 | HMAC purpose-binding key custody | purpose-binding keys are held outside the audit-read privilege (P1 holds none); verification failures never fall back to unverified reads | missing or invalid key yields `AUTH_FAILED`, fail closed (PST-CASE-07) |
| T4 | independent oracle ledger | held by the evaluation role only; labels frozen before arms run; the candidate never imports oracle code | any candidate-oracle import is a protocol violation, not a label |
| T5 | consent/policy epoch registry | append-only registry binding purpose authorization to epochs; sole authority for staleness decisions | a revoked or expired epoch yields `STALE_EPOCH`, fail closed |

Explicit non-assumptions: integrity evidence is never treated as confidentiality; a cryptographic digest is never treated as clinical reasoning proof; statistical confidence is never treated as authorization.

## Excluded domains

Declared out of scope, with the residual risk stated rather than hidden:

- **X1 — full disk / endpoint compromise.** Total compromise of the audit store host or of the reader workstation (encryption at rest defeated, memory scraping, root malware) is excluded; this model bounds a read-only audit privilege (P1/P2), not a root adversary. Residual risk: an attacker operating inside X1 exceeds every bound declared here.
- **X2 — key-custody and physical compromise.** HSM extraction, coercion of key holders, and side channels against T3 are excluded; key-governance gaps are reported as availability limitations (`INDETERMINATE`, PST-CASE-07), not solved here.
- **X3 — live-session and dispatch-path privacy.** Traffic analysis and side channels on the inference dispatch path are the PoPETs 2027 study's surface, deliberately disjoint from this post hoc audit model.
- **X4 — immutable historical disclosures and unverified backups.** No content-deletion claim is made about already-disclosed history or about backups whose deletion cannot be verified; retention decay applies to the retained audit store only. This externality is declared per the task risk note.
- **X5 — production enforcement.** B4 is an evaluation instrument; no new access-control or authorization enforcement mechanism is proposed (novelty-contract boundary), so enforcement-bypass attacks against a deployed receipt mechanism are out of scope.
- **X6 — real patient data.** All fixtures are synthetic (`synthetic-pst-2027`) per `SH-research_ethics`; no real PHI exists to attack.

## Time model: revocation and schedule

- **Commit time t_c.** Each action produces one receipt bound to the consent epoch and the policy epoch active at t_c.
- **Validity window.** A purpose authorization is valid on [v_start, v_end); the epoch registry (T5) is the sole authority for staleness decisions.
- **Revocation instant r.** Revocation at r stops *new* commits under the purpose immediately; already-committed receipts remain valid *integrity* evidence, while their *readable content* continues to decay on the retention schedule. The interval [r, retention deadline) is the primary revocation-timing attack surface: an adversary who can observe or query inside it may time events or authorizations to sub-epoch precision.
- **Retention deadline d (schedule time).** At d the retention map drops the declared content fields while the commitment and epoch proofs persist — the ReceiptMin design point. Reading after d exercises P6.
- **Epoch composition.** Adjacent-window queries across epoch boundaries (PST-CASE-03) compose; budgets are declared ex ante and leakage is reported as `MEASURE_LEAK`, never coerced into a pass.

## Attack family and control matrix

Every family pairs a clean control (behavior under the declared controls — the baseline a fair evaluation must reproduce) with an adversarial case (the strongest declared attack). Verdicts use the oracle statuses of `VENUES/pst/CASE_MATRIX.md`; `INDETERMINATE` is reported as incompleteness and is never converted into a pass or into a safe rejection.

| Attack family | Case anchor | Actor | Capability exercised | Control (clean case) | Adversarial case | Expected oracle verdict |
|---|---|---|---|---|---|---|
| revocation_timing | PST-CASE-03 | P3 | adjacent-window differencing across epoch boundaries and the [r, d) gap | clean: query budget declared ex ante; epochs declared per receipt; leakage measured and reported per window | adversarial: unbounded composition across the revocation gap to time a consent change or a clinical event to sub-epoch precision | clean: `MEASURE_LEAK` within budget; adversarial: `QUERY_BUDGET_EXCEEDED` while leakage is still reported |
| replay | PST-CASE-04 | P5 | resubmission of a captured receipt after purpose end to inflate history or revive stale authorization evidence | clean: logical operation ID collapses duplicates idempotently; epoch registry marks freshness | adversarial: resubmit a pre-revocation receipt so a verifier treats the stale commitment as current authorization | stale epoch yields `STALE_EPOCH`, fail closed and counted; never silent acceptance |
| model_agency | PST-CASE-05 | P4 | committer under- or over-commits evidence fields at receipt creation | clean: mandatory field set frozen ex ante from the forensic query set; a complete receipt is scored for answerability | adversarial: committer systematically drops the fields that would later convict it (model version, policy epoch) while keeping plausible filler | missing mandatory field yields `FORENSIC_OMISSION` / `INDETERMINATE` reported as audit incompleteness; never a false `RECONSTRUCT` |
| purpose_scope | PST-CASE-06 | P5 | purpose-bound receipt forgery or purpose-field inflation to widen read authorization | clean: purpose tags verified against the consent/policy epoch registry before any read; the purpose string itself is redacted per the threat model | adversarial: forge a receipt claiming an investigation purpose to exfiltrate linkable material, or rewrite a purpose field post-commit | missing key custody yields `AUTH_FAILED`; post-commit edit yields `DETECT_TAMPER`; fail closed either way |
| insider_or_observer | PST-CASE-02 | P1+P2 | compromised read-only reader joins receipts with auxiliary linkage tables | clean: privilege, auxiliary tables and join strategy frozen ex ante; re-identification and attribute advantage measured against declared priors | adversarial: reader combines two tenants' extracts with an auxiliary table to re-identify subjects or infer diagnoses from retained metadata | `NO_UNNECESSARY_LINK` evaluated; a bound violation is reported, never hidden |
| forensic_omission | PST-CASE-01 / PST-CASE-05 | P4 + P6 | audit minimization erases evidence a legitimate investigation later needs | clean: authorized investigator reconstructs a bounded decision from the receipt plus retention map; answerability is scored against the oracle ledger | adversarial: minimization dropped a load-bearing field, so the system must report incompleteness instead of a confident reconstruction | `RECONSTRUCT` only with exact oracle agreement; otherwise `INDETERMINATE` counted as incompleteness |
| receipt_forgery | PST-CASE-04 | P5 | minting a well-formed minimized receipt wholesale and injecting it into an extract | clean: the verifier checks chain membership and HMAC binding before trusting any receipt in an extract | adversarial: a forged receipt with valid syntax but no chain membership is submitted as forensic evidence | `DETECT_TAMPER` / `CHAIN_MEMBERSHIP_FAILED`, fail closed |
| selective_omission | PST-CASE-05 | P4 in the reporting role | the reporting pipeline drops inconvenient arm outcomes before analysis | clean: every arm outcome — including timeout, unknown and rejected — is counted per arm per the case-matrix rules; denominators reconcile against the run manifest | adversarial: selectively drop the high-leakage arm row or the B2-dominance row before reporting | denominator mismatch yields `SELECTIVE_OMISSION`, a protocol violation that blocks the run |
| record_tampering | PST-CASE-04 | P5 | post-commit modification of a minimized record or of a retention-map entry | clean: hash chain and witness validated on every read; the retention-map version is pinned per receipt | adversarial: a forensic witness or retention-map entry is edited after commit to hide an event or to extend retention selectively | `DETECT_TAMPER` with break location; `RETENTION_MAP_TAMPER` for schedule edits |
| linkability_leakage | PST-CASE-02 / PST-CASE-06 | P1+P2 | residual identifiers (pseudonyms, purpose strings, timing) enable linkage across receipts | clean: leakage evaluated with auxiliary joins under the frozen attacker model; precision reported against declared priors | adversarial: the attacker accumulates one subject's receipts across retention epochs to reconstruct a longitudinal profile | `MEASURE` plus `NO_UNNECESSARY_LINK` evaluation; exposure bounds reported with uncertainty, never asserted as zero |
| timestamp_inference | PST-CASE-03 / PST-CASE-06 | P1+P2 | timestamp-only forensic inference: timing patterns leak attributes even when all content is removed | clean: timestamp granularity and coarsening declared per retention epoch; inference advantage measured against a declared prior | adversarial: exact commit timestamps joined with auxiliary schedules (shift patterns) to infer an attribute | `MEASURE_LEAK` / `EVALUATE_DISCLOSURE`; the coarsening trade-off is recorded, not assumed away |

Mapping to the shared validator families: `forensic_omission` and `selective_omission` operationalize agency abuse; `receipt_forgery` and `record_tampering` are the integrity surfaces behind forgery and the insider reader; `linkability_leakage` and `timestamp_inference` are the insider/observer privacy surfaces; the resubmission and epoch-composition families are declared verbatim in rows two and one.

## Failure semantics and stable reason codes

All errors surface as stable reason codes; an unhandled exception is never counted as a safe rejection or as a successful completion. Oracle statuses: `RECONSTRUCT`, `NO_UNNECESSARY_LINK`, `MEASURE_LEAK`, `DETECT_TAMPER`, `EVALUATE_DISCLOSURE`, `MEASURE`, `INDETERMINATE`.

| Code | Trigger | Counted as |
|---|---|---|
| `FORENSIC_OMISSION` | mandatory evidence field absent at read time | incompleteness (utility bound), never a pass |
| `RECEIPT_FORGERY` / `CHAIN_MEMBERSHIP_FAILED` | receipt fails chain or HMAC verification | rejected read, counted |
| `SELECTIVE_OMISSION` | reported denominators do not reconcile with the run manifest | protocol violation, blocks the run |
| `RECORD_TAMPER` | post-commit edit detected | integrity failure, counted |
| `LINKABILITY_BOUND_EXCEEDED` | measured advantage exceeds the pre-registered bound | reported exposure result (RQ2), never hidden |
| `TIMESTAMP_INFERENCE_LEAK` | timing-only advantage above the declared prior | reported exposure result |
| `STALE_EPOCH` | epoch registry marks the authorization ended | fail-closed rejection, counted |
| `MISSING_EPOCH` / `AUTH_FAILED` | epoch or key verification impossible | fail-closed; availability limitation reported (PST-CASE-07) |
| `QUERY_BUDGET_EXCEEDED` | differencing composition beyond the declared budget | counted; leakage still measured |
| `UNKNOWN` | any outcome the harness cannot classify | counted per arm; never coerced |

## Oracle and actor authority

Defined, with no authority left unstated:

- **Oracle.** The trusted offline complete ledger, held by the evaluation role only, is the sole ground truth for reconstruction, exposure and recovery questions. Its labels are frozen before any arm runs; the candidate never imports oracle code; disagreements are counted and reported, never repaired post hoc.
- **Actor authority.** The evaluation role adjudicates oracle statuses and operates the blinded attacker harness with ground-truth labels from the ledger. The audit reader (P1) holds read-only privilege and no adjudication authority. Committing arms produce artifacts and hold no authority over labels. The statistician operates the frozen analysis plan and cannot change it post hoc. A candidate agent cannot approve its own ground-truth labels.
- **Ties and gaps.** Where two readings of an oracle label are plausible, the case stays `INDETERMINATE` until independently adjudicated (case-matrix rule). Routine incomplete, stale or `UNKNOWN` outcomes are counted as their own class and never as safe rejections or as successes.

## Falsification hooks and non-claims

- If B2 (encrypted full log with a well-managed retention policy) dominates B4 on privacy and reconstruction at comparable cost, the novelty-superiority claim is rejected and reported as a negative result (study-level falsification rule in the novelty contract).
- No content-deletion claim is made about immutable historical disclosures or unverified cloud backups (X4).
- B4 is an evaluation instrument; this model asserts no new access-control or enforcement mechanism (X5).
- Every adversarial row above is a declared attack to be implemented in P02+ harnesses; an attack that is not implemented is reported as `NOT_RUN`, never as demonstrated resistance.
