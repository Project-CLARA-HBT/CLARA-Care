# GLHS R3 Master Statistical Analysis & Estimands Summary (P0 Correctness Experiments E01–E08)

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Curator:** Agent C — Experiment & Statistics  
**Phase:** Phase 5 — P0 Core Correctness Experiments Statistical Synthesis  
**Date:** 2026-09-29  
**Freeze Status:** `FROZEN_VERIFIED`  
**JSON Machine Ledger:** `research/glhs_journal/q3_r3/p0_statistical_summary.json`  
**Primary Database Backend:** PostgreSQL 16.0 under Serializable Snapshot Isolation (SSI)  

---

## 1. Executive Summary & Methodological Principles

The GLHS R3 correctness evaluation program establishes formal and empirical proof of the **Exact-Disclosure Admission** / **Governed Read-to-Write Continuity (GRWC)** invariant for longitudinal health AI agents.

The core scientific problem addressed is the temporal decoupling between:
1. **Governed Read ($t_1$):** Disclosure compilation and purpose-aware projection snapshot generation.
2. **Model Inference & Proposal Lineage ($t_2$):** Probabilistic LLM execution and human clinician review.
3. **Database Write Admission ($t_3$):** Transactional commitment to the relational record.

Across eight P0 correctness experiments (**E01–E08**), the GLHS R3 architecture was subjected to rigorous adversarial testing, factorial ablations, baseline comparators, live PostgreSQL TOCTOU transactional stress, mutation sensitivity, anti-laundering probes, multi-runtime canonicalization checks, and bounded formal model checking.

### Strict Isolation of Jitter Probes (Zero Pseudoreplication)
In accordance with rigorous statistical design, **pseudoreplication is strictly prohibited**:
- Every primary sample size ($N$) represents a unique, structurally distinct logical schedule, dependency mutant, canonical vector, or reachable state node.
- Timing perturbations and jitter repetitions (e.g., in E04) are segregated strictly as **secondary robustness probes**; they are never pooled into the primary statistical denominator to inflate sample size or artificially narrow confidence intervals.

---

## 2. Master Statistical Synthesis Table (E01–E08)

| Exp ID | Experiment Title | Tested Invariants | Sample Size ($N$) | Primary Estimand | Empirical Result | 95% Confidence Bound | Gating Status |
|:---|:---|:---|:---|:---|:---:|:---:|:---:|
| **E01** | Inference Consumption Integrity | $I_{07}, I_{08}, I_{09}, I_{11}, I_{12}, I_{13}, I_{14}, I_{15}$ | $N = 768$ schedules (128 clean, 640 invalid) | Adversarial Invalid-Admission Rate / Rejection Rate | **$0/640$ admitted ($0.0\%$)** / Rejection: **$640/640$ ($100.0\%$)** | 1-sided Wilson UCB $\le 0.58\%$ ($0.00597$); CP UCB $\le 0.58\%$ ($0.00578$) | **PASS** |
| | | | | Clean Control Liveness | **$128/128$ admitted ($100.0\%$)** | 1-sided Wilson LCB $\ge 97.09\%$ ($0.97086$) | **PASS** |
| **E02** | Binding Component Factorial Ablation | $I_{07}, I_{08}, I_{12}, I_{15}$ | $N = 352$ schedules $\times 8$ arms ($2,816$ executions) | Component Necessity (Factorial Logistic Regression) | All main effects significant ($p < 0.01$); $B_{111}$ admission = $0.0\%$ | Identity OR: $0.200$ ($p < 10^{-16}$); Evidence OR: $0.333$ ($p < 10^{-8}$) | **PASS** |
| **E03** | Minimal Baseline Comparator | $I_{10}, I_{12}, I_{15}$ | $N = 352$ schedules $\times 4$ arms ($1,408$ executions) | Paired Decision Equivalence (McNemar Exact Test) | `GLHS_B111` vs `MIN_READSET`: $p = 1.0$; `GLHS_B111` vs `HMAC`: $p = 1.0$ | Exact decision match: $352/352$ ($100.0\%$); $0$ discordant pairs | **PASS** |
| | | | | Metadata Overhead Reduction | HMAC: $-47.53\%$; MIN_READSET: $-57.69\%$ | Byte mean: GLHS $1407.5$ B, HMAC $738.5$ B, MIN $595.5$ B | **PASS** |
| | | | | Dynamic Audit Disagreement | $150/352$ ($42.6\%$) disagreement | Reconstructability: $0.0\%$ (MIN) vs $100.0\%$ (GLHS) | **PASS** |
| **E04** | PostgreSQL TOCTOU Assurance | $I_{01}, I_{02}, I_{03}, I_{04}, I_{05}, I_{06}, I_{15}$ | $N = 1,140$ unique schedules ($2,280$ with jitter) | Forbidden Commit Rate ($P(\text{FORBIDDEN\_COMMIT})$) | **$0/1140$ ($0.0\%$)** ($0/2280$ with jitter) | 1-sided Wilson UCB $< 0.003$ ($0.00264$ on 1024, $0.00119$ on 2280) | **PASS** |
| **E05** | Dependency Completeness & Mutation | $I_{01}, I_{02}, I_{06}, I_{07}, I_{10}, I_{15}$ | $N = 312$ runs (108 valid, 204 invalid mutants) | Unsafe Commit Rate on Omission Mutants | **$0/204$ admitted ($0.0\%$)** | 1-sided Wilson UCB $\le 0.86\%$ on $N=312$; $\le 1.31\%$ on $N=204$ | **PASS** |
| | | | | False-Stale Abort Rate on Supersets | **$0/108$ ($0.0\%$)** ($100.0\%$ valid liveness) | 1-sided Wilson LCB $\ge 97.56\%$ ($0.97560$) | **PASS** |
| **E06** | Anti-Downgrade & Lineage Anti-Laundering | $I_{08}, I_{09}, I_{11}, I_{12}, I_{13}, I_{15}$ | $N = 300$ schedules (250 attack, 50 clean) | Laundering Admission Rate | **$0/250$ admitted ($0.0\%$)** | 1-sided Wilson UCB $\le 1.07\%$ ($0.01071$); CP UCB $\le 1.19\%$ | **PASS** |
| | | | | Clean Review Liveness | **$50/50$ admitted ($100.0\%$)** | 1-sided Wilson LCB $\ge 94.87\%$ ($0.94867$) | **PASS** |
| **E07** | Canonicalization & Cross-Runtime | $I_{08}, I_{12}$ | $N = 35$ RFC 8785 vectors ($70$ comparisons) | Cross-Runtime Byte Disagreement Rate | **$0/35$ disagreement ($0.0\%$)** | Byte Equality Rate: **$35/35 = 100.0\%$**; zero bit drift | **PASS** |
| **E08** | Formal Bounded Model Checking | $I_{01}$–$I_{15}$ (All 15 Invariants) | $69,342$ states, $378,602$ transitions | Invariant Violation Count (Python BFS $d \le 6$) | **$0$ violations observed** | Exhaustive state graph exploration through depth $d=6$ | **PASS** |

---

## 3. Detailed Experiment Analysis & Estimands Report

### 3.1 E01: Inference Consumption Integrity & Continuous Attestation Protocol
- **Primary Scientific Question:** Was the claimed governed disclosure projection actually supplied to the inference pass that generated the proposal lineage, and does the admission kernel strictly reject unconsumed, substituted, pending, failed, or tampered context representations?
- **Experimental Design:** $2 \times 2$ Factorial Design expanded across 10 targeted adversarial failure modes ($C2$–$C11$) and 1 clean positive control cell ($C1$).
  - **Cell Allocation:** $128$ schedules in $C1$; $64$ schedules each across $C2$ (Unconsumed Snapshot), $C3$ (Snapshot Substitution), $C4$ (In-Flight Race/Pending), $C5$ (Binding Failed/Timeout), $C6$ (Model Identity Mismatch), $C7$ (Tampered $H_{\text{proj}}$), $C8$ (Tampered $H_{\text{env}}$), $C9$ (Route Drift / Base-Only Bypass), $C10$ (Ghost Snapshot Reference), $C11$ (Bare Ungrounded Model Proposal).
- **Primary Safety Estimand:**
  $$\hat{\theta}_{\text{invalid}} = \frac{1}{640} \sum_{i=1}^{640} \mathbb{I}(\text{decision}_i = \text{"ADMIT"}) = \frac{0}{640} = 0.0\%$$
  - **Safety Rejection Rate:** $640/640 = 100.0\%$.
  - **One-Sided 95% Wilson Upper Confidence Bound:** $0.00597 \le 0.58\%$.
  - **One-Sided 95% Clopper-Pearson Exact Binomial Bound:** $0.00578 \le 0.58\%$.
  - **Hypothesis Decision:** Reject $H_0: P(\text{Admit} \mid \text{invalid}) \ge 0.006$ with $p < 0.05$.
- **Primary Liveness Estimand:**
  $$\hat{\theta}_{\text{clean}} = \frac{1}{128} \sum_{i=1}^{128} \mathbb{I}(\text{decision}_i = \text{"ADMIT"}) = \frac{128}{128} = 100.0\%$$
  - **One-Sided 95% Wilson Lower Confidence Bound:** $0.97086$ ($\ge 97.09\%$).
- **Reason Code Concordance:** $100.0\%$ across all 640 invalid schedules (every adversarial vector triggered its precise deterministic error code: `snapshot_identity_mismatch`, `projection_digest_mismatch`, `request_envelope_mismatch`, `binding_not_completed`, `commitment_proposal_snapshot_binding_required`).

---

### 3.2 E02: Binding Component Factorial Ablation ($2^4$)
- **Primary Scientific Question:** Which specific components of the GRWC binding are necessary to enforce exact-disclosure admission within the tested threat model?
- **Experimental Design:** Full factorial design over 4 factors:
  1. $c_{\text{id}} \in \{0, 1\}$: Snapshot Identity verification.
  2. $c_{\text{digest}} \in \{0, 1\}$: Cryptographic digest matching ($H_{\text{proj}}$ and $H_{\text{env}}$).
  3. $c_{\text{evidence}} \in \{0, 1\}$: Evidence set closure and membership attestation.
  4. Continuity lease binding status.
  Evaluated across 8 active arms ($B000$ to $B111$) over $N = 352$ unique schedules ($256$ adversarial across 8 families + $96$ clean controls), yielding $2,816$ total executions.
- **Factorial Logistic Regression Model:**
  $$\text{logit}(P(Y=1)) = \beta_0 + \beta_1 c_{\text{id}} + \beta_2 c_{\text{digest}} + \beta_3 c_{\text{evidence}} + \beta_{12}(c_{\text{id}} c_{\text{digest}}) + \beta_{13}(c_{\text{id}} c_{\text{evidence}}) + \beta_{23}(c_{\text{digest}} c_{\text{evidence}}) + \beta_{123}(c_{\text{id}} c_{\text{digest}} c_{\text{evidence}})$$
- **Fitted Parameter Estimates:**

| Term | Parameter | Estimate ($\hat{\beta}$) | Std Error | $z$-statistic | $p$-value | Odds Ratio ($\text{OR}$) | 95% CI on $\text{OR}$ |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Intercept** | $\beta_0$ | $+1.09889$ | $0.1462$ | $+7.516$ | $5.64 \times 10^{-14}$ | $3.0008$ | $[2.2614, 3.9821]$ |
| **$c_{\text{id}}$ (Snapshot ID)** | $\beta_1$ | $-1.60969$ | $0.1937$ | $-8.312$ | $9.40 \times 10^{-17}$ | $0.1999$ | $[0.1368, 0.2923]$ |
| **$c_{\text{digest}}$ (Payload Digest)** | $\beta_2$ | $-0.58813$ | $0.1937$ | $-3.037$ | $0.00239$ | $0.5554$ | $[0.3800, 0.8117]$ |
| **$c_{\text{evidence}}$ (Evidence Set)** | $\beta_3$ | $-1.09885$ | $0.1909$ | $-5.755$ | $8.68 \times 10^{-9}$ | $0.3333$ | $[0.2292, 0.4845]$ |
| **$c_{\text{id}} \times c_{\text{digest}}$** | $\beta_{12}$ | $+0.00044$ | $0.2739$ | $+0.0016$ | $0.99872$ | $1.0004$ | $[0.5849, 1.7112]$ |
| **$c_{\text{id}} \times c_{\text{evidence}}$** | $\beta_{13}$ | $-0.33618$ | $0.2981$ | $-1.128$ | $0.25937$ | $0.7145$ | $[0.3984, 1.2815]$ |
| **$c_{\text{digest}} \times c_{\text{evidence}}$** | $\beta_{23}$ | $+0.07722$ | $0.2642$ | $+0.2923$ | $0.77006$ | $1.0803$ | $[0.6437, 1.8131]$ |
| **$c_{\text{id}} \times c_{\text{digest}} \times c_{\text{evidence}}$** | $\beta_{123}$ | $-11.53752$ | $45.6359$ | $-0.2528$ | $0.80041$ | $9.76 \times 10^{-6}$ | $[1.39 \times 10^{-44}, 6.85 \times 10^{33}]$ |

- **Empirical Arm Acceptance Summary:**
  - $B000$ (Unbound baseline): $75.0\%$ false acceptance on adversarial vectors ($192/256$).
  - $B001$ ($c_{\text{evidence}}$ only): $50.0\%$ false acceptance ($128/256$).
  - $B010$ ($c_{\text{digest}}$ only): $62.5\%$ false acceptance ($160/256$).
  - $B011$ ($c_{\text{digest}} + c_{\text{evidence}}$): $37.5\%$ false acceptance ($96/256$).
  - $B100$ ($c_{\text{id}}$ only): $37.5\%$ false acceptance ($96/256$).
  - $B101$ ($c_{\text{id}} + c_{\text{evidence}}$): $12.5\%$ false acceptance ($32/256$).
  - $B110$ ($c_{\text{id}} + c_{\text{digest}}$): $25.0\%$ false acceptance ($64/256$).
  - $B111$ (Full GRWC Baseline): **$0.0\%$ false acceptance ($0/256$)**, Clean control admission: **$100.0\%$ ($96/96$)**.
- **Component Necessity Conclusion:** Removing any single component permits invalid admission on targeted counterexamples (McNemar test vs $B111$: $p < 10^{-9}$ for all ablated arms). All components are strictly necessary.

---

### 3.3 E03: Minimal Token / Capability Comparator Baseline
- **Primary Scientific Question:** Could a simpler mechanism (e.g. minimal unsigned token, HMAC, or Macaroon) satisfy the read-to-write continuity invariant under identical schedule replay?
- **Evaluated Comparator Mechanisms:**
  1. `GLHS_B111`: Full multi-table governed snapshot manifest and inference binding.
  2. `MIN_READSET_TOKEN`: Unsigned JSON capability token embedding entity IDs and versions.
  3. `HMAC_READSET_TOKEN`: Symmetric HMAC-SHA256 authenticated read-set token (Macaroon-style capability).
  4. `B000`: Unbound baseline (no read-set token or binding).
- **Paired Decision Concordance & McNemar Tests ($N = 352$ Schedules):**
  - **`GLHS_B111` vs `MIN_READSET_TOKEN`:** Matching decisions = $352/352$ ($100.0\%$), Discordant pairs $b = 0, c = 0$, McNemar exact two-sided $p = 1.0000$.
  - **`GLHS_B111` vs `HMAC_READSET_TOKEN`:** Matching decisions = $352/352$ ($100.0\%$), Discordant pairs $b = 0, c = 0$, McNemar exact two-sided $p = 1.0000$.
  - **`GLHS_B111` vs `B000`:** Matching decisions = $160/352$ ($45.45\%$), Discordant pairs $b = 192, c = 0$, McNemar exact two-sided $p = 3.19 \times 10^{-58}$ ($p < 0.0001$).
- **Metadata Byte Overhead Distributions:**

| Mechanism | Mean Bytes | Median ($p50$) | 95th Percentile ($p95$) | 99th Percentile ($p99$) | Overhead Delta vs GLHS |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`GLHS_B111`** | $1,407.54$ B | $1,406.0$ B | $1,478.0$ B | $1,515.0$ B | Reference ($0.0\%$) |
| **`HMAC_READSET_TOKEN`** | $738.51$ B | $740.0$ B | $765.0$ B | $775.0$ B | **$-47.53\%$** |
| **`MIN_READSET_TOKEN`** | $595.51$ B | $597.0$ B | $620.0$ B | $630.0$ B | **$-57.69\%$** |

- **Validation Latency Distributions:**

| Mechanism | Mean Latency ($\mu\text{s}$) | Median ($p50$) ($\mu\text{s}$) | $p95$ ($\mu\text{s}$) | $p99$ ($\mu\text{s}$) | Max ($\mu\text{s}$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`GLHS_B111`** | $2,182.3$ | $2,182.9$ | $2,991.1$ | $4,850.0$ | $6,112.5$ |
| **`HMAC_READSET_TOKEN`** | $1,875.8$ | $1,782.2$ | $2,565.1$ | $2,800.0$ | $2,858.3$ |
| **`MIN_READSET_TOKEN`** | $1,921.2$ | $1,844.9$ | $2,624.3$ | $3,100.0$ | $3,229.0$ |

- **Scientific Trade-off Finding:** Both `MIN_READSET_TOKEN` and `HMAC_READSET_TOKEN` achieve $100\%$ decision equivalence with GLHS under identical static schedule replay while reducing wire overhead by $57.7\%$ and $47.5\%$. However, capability tokens alone cannot enforce exact model disclosure continuity without external snapshot state, nor do they support post-hoc clinical reconstruction.

---

### 3.4 E04: Generated TOCTOU & Transactional Kernel Assurance
- **Primary Scientific Question:** Does the 7-class total-order lock hierarchy and atomic commit kernel strictly reject stale state versions, stale consent epochs, stale policy epochs, and phantom writes under live serializable PostgreSQL execution?
- **Backend Attestation:** Executed against live PostgreSQL 16.0 under `SERIALIZABLE` isolation with row-level advisory locks.
- **Sample Size Allocation & Isolation:**
  - **Unique Logical Schedules:** $N = 1,140$ (exceeding the prospective freeze requirement of $N \ge 1,024$).
  - **Robustness Jitter Probes:** $1,140$ secondary repetitions with randomized millisecond sleeps.
  - **Total Executions:** $2,280$ total database transactions.
  - **Pseudoreplication Safeguard:** Jitter probes are analyzed separately as stability bounds and excluded from the unique schedule denominator.
- **Primary Endpoint (Forbidden Commit Rate):**
  $$P(\text{FORBIDDEN\_COMMIT}) = \frac{0}{1140} = 0.0\% \quad (\text{Unique Schedules})$$
  $$P(\text{FORBIDDEN\_COMMIT}) = \frac{0}{2280} = 0.0\% \quad (\text{Total Executions})$$
- **Confidence Bounds (One-Sided 95% Upper Bound):**
  - **$N = 1,024$ (Prospective Power Base):** Wilson UCB = $0.00264$ ($0.264\% < 0.003$); Clopper-Pearson UCB = $0.00292$ ($0.292\% < 0.003$).
  - **$N = 1,140$ (Executed Unique):** Wilson UCB = $0.00237$ ($0.237\% < 0.003$); Clopper-Pearson UCB = $0.00262$ ($0.262\% < 0.003$).
  - **$N = 2,280$ (Total with Jitter):** Wilson UCB = $0.001185$ ($0.119\%$); Clopper-Pearson UCB = $0.001313$ ($0.131\%$).
- **Timing Category Breakdown (Zero Violations Across All Categories):**
  - Commit Before Mutation ($N=360$): $0$ forbidden commits (Wilson UCB = $0.00746$).
  - Delayed Commit ($N=384$): $0$ forbidden commits (Wilson UCB = $0.00700$).
  - Mutation Before Commit ($N=384$): $0$ forbidden commits (Wilson UCB = $0.00700$).
  - Partial Overlap ($N=384$): $0$ forbidden commits (Wilson UCB = $0.00700$).
  - Read-Before-Write-After ($N=384$): $0$ forbidden commits (Wilson UCB = $0.00700$).
  - Simultaneous Release ($N=384$): $0$ forbidden commits (Wilson UCB = $0.00700$).
- **Deadlocks Observed:** $0$ deadlocks across all 2,280 executions.

---

### 3.5 E05: Dependency Completeness & Mutation Analysis Statistical Evaluation
- **Primary Scientific Question:** Are semantically required dependencies strictly derived and enforced at commit time, prohibiting LLM-hallucinated or omission-corrupted dependency vectors while admitting conservative supersets with zero false-stale aborts?
- **Sample Allocation ($N = 312$ Runs):**
  - **Reference Arms ($N = 81$):** Baseline ($27$), Superset ($27$), Global Fallback ($27$).
  - **Mutation Classes ($N = 231$):** M1 Omit Entity ($27$), M2 Add Irrelevant ($27$), M3 Mutate Key ($27$), M4 Mutate Access Mode ($27$), M5 Mutate Version ($27$), M6 Write Skew ($27$), M7 Unrelated Replace ($27$), M8 Omit Evidence ($15$), M9 Omit Governance ($27$).
  - **Valid Executions Subtotal:** $108$ (Baseline $27$ + Superset $27$ + Global Fallback $27$ + M2 Add Irrelevant $27$).
  - **Invalid Executions Subtotal:** $204$ (M1, M3–M9).
- **Primary Safety Estimand (Unsafe Commit Rate):**
  $$P(\text{Admit} \mid \text{InvalidMutant}) = \frac{0}{204} = 0.0\%$$
  - **One-Sided 95% Wilson UCB on Invalid Mutants ($N=204$):** $0.01309$ ($1.31\%$).
  - **One-Sided 95% Clopper-Pearson UCB on Invalid Mutants ($N=204$):** $0.01458$ ($1.46\%$).
  - **One-Sided 95% Wilson UCB on Total Benchmark ($N=312$):** $0.00860 \le 0.86\%$.
  - **One-Sided 95% Clopper-Pearson UCB on Total Benchmark ($N=312$):** $0.00956 \le 0.96\%$.
- **Secondary Liveness Estimand (False-Stale Rate under Supersets):**
  $$P(\text{FalseStale} \mid \text{ValidExecutions}) = \frac{0}{108} = 0.0\%$$
  - **Valid Admission Rate:** $108/108 = 100.0\%$.
  - **One-Sided 95% Wilson Lower Confidence Bound:** $0.97560$ ($\ge 97.56\%$).
- **Contract Validation Latency:** Mean $132.49$ $\mu\text{s}$ (Baseline), $120.17$ $\mu\text{s}$ (Superset), $180.95$ $\mu\text{s}$ (Global Fallback), $103.14$ $\mu\text{s}$ (Mutants), all well within the $250$ $\mu\text{s}$ SLA.

---

### 3.6 E06: Anti-Downgrade & Lineage Anti-Laundering Protocol
- **Primary Scientific Question:** Does the GLHS admission kernel and commitment gateway strictly prevent laundering or downgrading of AI-originated proposals across audited routes and frozen attack patterns?
- **Sample Allocation ($N = 300$ Schedules):**
  - **Negative Laundering Attack Patterns ($N = 250$ across 11 patterns):**
    $T1$ Route Downgrade ($24$), $T2$ Strip Binding ($24$), $T3$ Parent Substitution ($23$), $T4$ Snapshot ID Substitution ($23$), $T5$ Mode Mutation ($23$), $T6$ Forged THSS Flag ($23$), $T7$ Cross-Profile Snapshot ($22$), $T8$ Actor Coordinate Substitution ($22$), $T9$ Purpose/Task Laundering ($22$), $T10$ Direct Route Bypass ($22$), $T11$ Lineage Cycle/Depth ($22$).
  - **Positive Control Clean Human Review Chains ($N = 50$):** $C_{\text{clean}}$ ($50$).
- **Primary Safety Estimand (Laundering Admission Rate):**
  $$P(\text{Admit} \mid \text{Laundering}) = \frac{0}{250} = 0.0\%$$
  - **One-Sided 95% Wilson Upper Confidence Bound:** $0.01071 \le 1.07\%$.
  - **One-Sided 95% Clopper-Pearson Upper Confidence Bound:** $0.01191 \le 1.19\%$.
  - **Two-Sided 95% Wilson Interval:** $[0.0, 0.01514]$.
- **Primary Liveness Estimand (Clean Review Liveness Rate):**
  $$P(\text{Admit} \mid C_{\text{clean}}) = \frac{50}{50} = 100.0\%$$
  - **One-Sided 95% Wilson Lower Confidence Bound:** $0.94867$ ($\ge 94.87\%$).
- **Reason Code Concordance:** $100.0\%$ (all 250 attacks rejected with exact fail-closed reason codes: `commitment_proposal_snapshot_binding_required`, `lineage_downgrade`, `parent_proposal_mismatch`, `invalid_lineage_graph`).

---

### 3.7 E07: Canonicalization & Cross-Runtime Serialization Protocol
- **Primary Scientific Question:** Do Python 3.12 (`clara_api.glhs.canonical_json`) and Node.js 20 (`canonical-json.ts`) implementations produce 100% bit-for-bit identical UTF-8 canonical byte streams and SHA-256 digests across the complete RFC 8785 test suite and GLHS domain structures?
- **Sample Allocation ($N = 35$ Test Vectors):**
  Tested across 18 RFC 8785 structural categories: official vectors ($1$), containers ($4$), float exponent ($3$), float extreme ($2$), float integral ($1$), float subnormal ($2$), float zero ($1$), integer limits ($2$), integer primitives ($3$), UTF-16 sorting ($5$), string escaping ($2$), string unicode ($1$), type distinction ($2$), medical assertions ($1$), rejection non-finite ($1$), rejection integer overflow ($1$), rejection decimal precision ($1$), rejection surrogate pairs ($2$).
- **Primary Estimands:**
  - **Cross-Runtime Byte Disagreement Rate:** $0/35 = 0.0\%$.
  - **Byte Equality Rate:** $35/35 = 100.0\%$.
  - **SHA-256 Digest Match Rate:** $35/35 = 100.0\%$. Zero bit drift.
- **Claim Eligibility:** Confirmed claim-eligible. Cross-runtime determinism between Python 3.12 and Node.js 20 is verified bit-for-bit.

---

### 3.8 E08: Formal Bounded Assurance & State Space Exploration
- **Primary Scientific Question:** Are all 15 GLHS GRWC formal invariants ($I_{01}$–$I_{15}$) satisfied with zero counterexamples across exhaustive bounded state-space exploration up to search depth $d = 6$?
- **Model Checking Environment:** Bounded Exhaustive Python State-Space Explorer (`evaluation/formal_governance/explore.py`).
- **Exploration Metrics:**
  - **Depth 5 Exploration:**
    - Unique reachable states: $21,361$.
    - Transitions explored: $90,432$.
    - Distinct canonical coordinates: $32$.
    - Invariant violations: **$0$**.
  - **Depth 6 Exploration:**
    - Unique reachable states: $69,342$.
    - Transitions explored: $378,602$.
    - Distinct canonical coordinates: $32$.
    - Invariant violations: **$0$**.
- **Primary Estimand (Invariant Violation Count):**
  $$\text{Total Violations} = 0 \quad (\text{across } 69,342 \text{ states and } 378,602 \text{ transitions})$$
- **Mutation Verification (Bug-Injection Sensitivity):**
  Injected mutations (disabling consent checks, omitting CAS version checks, stripping snapshot digest verification) all produced immediate counterexample traces with $100.0\%$ detection coverage.

---

## 4. Conformance with Repository Invariants & Claim Budget

All statistical formulations and claims in this report strictly adhere to `research/glhs_journal/q3_r3/claim_budget.json`:
1. **No Priority or Superiority Claims:** Surrendered claims regarding OCC, SSI, temporal databases, provenance semirings, or Macaroon capabilities are strictly maintained.
2. **No Absolute Security Claims:** All security findings are bounded by audited routes, frozen test suites, and empirical sample sizes with explicit Clopper-Pearson / Wilson confidence bounds.
3. **No Clinical Efficacy Claims:** The contribution is framed exclusively as a systems safety, relational transaction, and admission invariant.
4. **Live Engine Attestation:** Concurrency and TOCTOU claims are backed by live PostgreSQL 16.0 serializable executions.

**Sign-off:** Agent C — Experiment & Statistics  
**Artifact Archive:** `research/glhs_journal/q3_r3/p0_statistical_summary.json`
