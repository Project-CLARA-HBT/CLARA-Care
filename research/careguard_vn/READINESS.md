# CareGuard-VN readiness

Status: **NOT RUN — external validation not started**.

No independent Vietnam product source, locked split, or oracle-identity execution currently exists. A controlled DDInter 2.0 positive-reference snapshot, a five-record DailyMed current-SPL regulatory-confirmation subset, and the official 2026-08-03 RxNorm Current Prescribable Content release are retained outside git with validated hash inventories. These are three distinct source roles only and cannot form a benchmark or negative set. The legacy DAVIDrug endpoint is currently unsuitable for acquisition (HTTP 404); the DAV public-service root later showed maintenance, and a separate official YDCT search portal is explicitly incomplete for current status. `evaluation/careguard_external/acquire_dav.py` awaits an operator-provided official DAV export and cannot scrape a portal. Its pending public redistribution review is metadata only: acquisition needs official access authorization, while raw data remains `raw_prohibited` outside Git. The RxNorm release was acquired only after the official NLM page supplied its exact URL and MD5; its full 6,183,895-record inventory is retained in the ignored controlled artifact store, while `rxnorm_prescribable_08032026_acquisition_receipt.json` is the tracked compact receipt. Historical DrugBank output remains stale same-source conformance only and is not evidence for this study.

No false-clear, automatic-coverage, accuracy, or clinical-coverage claim is permitted.

`evaluation/careguard_external/source_manifest.py` now rejects metadata probes,
unresolved terms, missing raw-retention locations, incomplete record-hash
inventories, a source set without all four independent roles, and duplicate
declared source identities, source URLs, or payload hashes across nominal
roles. It is an
acquisition gate only; the DDInter manifest passes individual-source validation,
but no complete four-role source set currently passes it.

The repository now has a fail-closed authorized-RxNorm acquisition path that
requires a real ZIP and published MD5 before emitting a source manifest with
full RRF-row inventory. It rejects the observed login HTML and has not acquired
an invalid payload; the Vietnam identity blocker remains unchanged.

`DAV_ACQUISITION_WORKFLOW.md` defines the official-export provenance,
normalization, reconciliation, source-set freeze, and Mode A/Mode B constraints.
No DAV receipt, normalization ledger, reconciliation ledger, split, or sealed
mode execution exists yet.

Literature lock: CrossDDI is the nearest DDI comparison point. CareGuard-VN
must not claim novelty for generic normalization, abstention, evidence-grounded
DDI reasoning, or standard DDI benchmark construction. Its only prospective
contribution is source-bound identity gating evaluated on independently frozen
Vietnam product identity and DDI oracle sources.
