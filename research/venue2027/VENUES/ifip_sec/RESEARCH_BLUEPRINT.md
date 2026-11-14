# IFIP_SEC · independently executable study implementation book

**Paper:** Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage

**Proposed contribution:** Study a *multi-principal interleaving* in which a valid consent-purpose receipt is delegated, refreshed and consumed across policy-epoch changes and concurrent replay. Define a consumed-once invariant and a tested provenance binding for delegated proposal chains.

**Literature gap and competing explanation:** Macaroons and Zanzibar already solve substantial parts of contextual authorization and consistency. A credible new claim must show a specific multi-hop lineage/replay counterexample against strong correctly configured caveat-token and versioned authorization baselines, not just signature checking.

**Three research questions**

**RQ1: Under which delegation and epoch interleavings do signed context-bound capability baselines admit an invalid replay or reject valid operations?**
**RQ2: Is the proposed consume-once transition linearizable under two or more real PostgreSQL sessions and revoked scope?**
**RQ3: What are token size, verification latency and legitimate operation rejection costs relative to well-configured Macaroons and Zanzibar-like policies?**

**Falsification criterion:** If a properly scoped Macaroon plus consistent authorization check is decision-equivalent on all attacks, state equivalence and do not claim stronger security.

**Method architecture:** Receipts are typed commitments: HMAC over actor, patient, tenant, purpose, task, consent/policy epoch, dispatch digest, nonce and parent reference. Verify the full delegation ancestry and atomically consume the nonce, not just signature equality.

**Planned study population / resources:** Distinct 900 adversarial interleavings in isolated synthetic accounts across delegation/revocation/retry/tenant switches; clean controls matched per threat family.

**Independent oracle:** Independent allow/deny oracle based on frozen principal graph and commit-time consent epoch, not candidate verifier output.

**Required metrics:** invalid replay admissions, valid control acceptance, duplicate consumption race, token bytes, p95 verify latency, authorization DB round trips

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | bearer signed receipt | weak control |
| B1 | Macaroon HMAC caveats: actor, purpose, task, expiry, nonce | strong token baseline, correct semantics |
| B2 | Zanzibar/OpenFGA with consistency token and fresh policy evaluation | strong relationship consistency baseline |
| B3 | Cedar/OPA policy decision with replay nonce registry | strong security-engineering comparator |
| B4 | proposed delegated lineage transition verifier | candidate |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 4 tasks; see `PHASES/P03.md`.
- `P04`: 5 tasks; see `PHASES/P04.md`.
- `P05`: 5 tasks; see `PHASES/P05.md`.
- `P06`: 2 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue ifip_sec` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/ifip_sec/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
