# PST · independently executable study implementation book

**Paper:** ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization

**Proposed contribution:** A formally defined *reconstruction-versus-linkability frontier* for AI health action receipts, separating proof of an event commitment from recovery of sensitive content under post-retention access privileges.

**Literature gap and competing explanation:** Hash chains, transparency logs, HMAC identifiers and encryption already exist; a useful contribution requires new quantitative evidence about audit decision reconstructability versus attacker attribute/linkage inference for longitudinal health workflows.

**Three research questions**

**RQ1: What fraction of legitimate forensic questions remain answerable under hash-only, encrypted, and selective retention receipts?**
**RQ2: Can linkage and attribute exposure be bounded under compromised read-only audit access, including auxiliary-data joins?**
**RQ3: What retention, key deletion and proof-generation costs emerge across audit volumes and retention epochs?**

**Falsification criterion:** If encrypted full logs with a well-managed retention policy dominate minimized receipts on privacy and reconstruction, reject novelty superiority claim.

**Method architecture:** Define forensic query set ex ante; preserve commitment and consent/policy epoch proofs while removing patient detail; test attacker with auxiliary linkage metadata and a realistic audit-reader privilege.

**Planned study population / resources:** Synthetic records/events with explicit correlation surfaces, varying log sizes, user identifiers, retention windows, backups; externality of key deletion declared in threat model.

**Independent oracle:** Trusted offline complete ledger retained only for evaluation; blinded authorized forensic queries and attacker inference tests.

**Required metrics:** forensic query answerability, record-level linkability risk, attribute inference risk, retained bytes, proof generation latency, authorized investigation recovery

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | full plaintext append-only log | utility upper bound / privacy lower bound |
| B1 | hash-only log or content digests | storage/privacy baseline, weak audit utility |
| B2 | encrypted log with role-gated decryption and deletion | strong confidentiality comparator |
| B3 | RFC 9162-like Merkle append-only integrity + authorized material retrieval | strong integrity baseline |
| B4 | proposed purpose-bound minimized receipt and retention map | candidate |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 4 tasks; see `PHASES/P03.md`.
- `P04`: 4 tasks; see `PHASES/P04.md`.
- `P05`: 5 tasks; see `PHASES/P05.md`.
- `P06`: 3 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue pst` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/pst/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
