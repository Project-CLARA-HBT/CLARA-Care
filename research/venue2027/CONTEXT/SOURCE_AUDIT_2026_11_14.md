# Source and reproducibility audit (as of 2026-11-14)

- GitHub default `main`: `81c024d74ea9201b31e22b5c02b1b6f852c0ce9e` (10 August 2026).
- Research branch `research/glhs-r4-novelty-hardening`: `bce92340e190c62208a24aa3304f188080f6fd58` (24 October 2026), more than 500 commits ahead of main at audit.
- Latest R4 gate run: https://github.com/Project-CLARA-HBT/CLARA-Care/actions/runs/40109179184 — secret scan, chronology audit and claim lint pass; test and E22 jobs fail.
- Focused pytest 57 passed / 4 failed. Failure signature: `ValueError: GLHS ledger rows are immutable; append a governed transition` from model update listener near `services/api/src/clara_api/db/models.py:3040`. Four failures span valid GRWC admission, comparator decision concordance, current-state insufficiency witness, and lineage review chain.
- Historical R4 E15--E19 experiment backend attestation identifies `sqlite:///:memory:`. It therefore does not validate the PostgreSQL-specific SSI concurrency claims expressed by the original prospective plan and manuscript.
- Historical release was sealed against `9006ac5c...` while working HEAD changed; any modern claim must identify which code was executed and establish rerun parity.
- Historical R4 E20 provider verifiable receipts were not executed (conditional `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`).
- Original manuscript and release report appear at `research/glhs_journal/q4_r4/release/`. RIVF GovRed and SOICT GovMut have separate publication-routing notes prohibiting reusing one frozen study as two independent conference papers.

## Exact source URLs

- https://github.com/Project-CLARA-HBT/CLARA-Care/tree/research/glhs-r4-novelty-hardening
- https://github.com/Project-CLARA-HBT/CLARA-Care/actions/runs/40109179184
- https://github.com/Project-CLARA-HBT/CLARA-Care/blob/research/glhs-r4-novelty-hardening/research/glhs_journal/q4_r4/release/MANUSCRIPT_MASTER_R4.md

This audit is limited to the inspected API tree, evidence manifests, workflows and logs. A full static security review or end-to-end reexecution was not performed in preparation of this package.
