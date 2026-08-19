# CareGuard-VN readiness

Status: **RESULT-INCOMPLETE — external validation not started**.

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

## External gate checklist (CG-01..CG-07) — 2026-08-19

| Gate | Requirement | Status |
| --- | --- | --- |
| CG-01 | Hard source gate: no final benchmark until an authorized, current Vietnam product identity frame passes source-manifest validation | **BLOCKED** — DAV identity frame NOT acquired (external MANUAL gate); four-role source set cannot validate |
| CG-02 | Freeze sample selection before model/system outputs: DAV cases, variants/clustering, eligible positive pairs, DailyMed confirmation, negatives, split, exclusions+reason codes | **RULES FROZEN** in `STATISTICS_PLAN_FROZEN.md` / `statistics_plan_freeze.json`; sample/split assignment **BLOCKED** until DAV is mapped |
| CG-03 | Precision target before locked testing: 95% interval for plausible 5–10% false-reassurance rate, ≤ 3pp half-width | **FROZEN** — required positive-reference N = 203 (p=0.05), 385 (p=0.10), planning target 385 (`precision_requirement.py`); achieved-precision fallback recorded |
| CG-04 | Primary denominator = all frozen externally positive cases; identity failure stays in denominator | **FROZEN** (rule recorded); execution blocked on CG-01 |
| CG-05 | Reviewer protocol: two blinded reviewers, background/qualification, blinding, rubric, kappa, adjudication; or disclose qualifications exactly | **PROTOCOL FROZEN** in `MAPPING_REVIEW_PROTOCOL.md`; execution **BLOCKED** (reviewers not yet recruited; expertise shortfall will be disclosed exactly) |
| CG-06 | RxMap feasibility: attempt faithful pinned comparator; record DIRECTLY_EXECUTABLE / ASSET_GATED / TASK_MISMATCH; never emulate and label it RxMap | **RECORDED** — disposition `ASSET_GATED` in `RXMAP_FEASIBILITY.md`; re-probe before final freeze |
| CG-07 | Negative reference: DDInter absence is not negative; add only independently supported negatives or leave specificity unsupported | **FROZEN** — specificity `UNSUPPORTED`, positive-case safety/risk-coverage focus (`NEGATIVE_REFERENCE.md`) |

**Gate G** (four-role source-set validation + statistics freeze) is **NOT
PASSED**: statistics plan is frozen, but the four-role source set is incomplete
(CG-01 BLOCKED). No final-test execution may start.

## Workstream G artifacts (2026-08-19, R3)

- `STATISTICS_PLAN_FROZEN.md` + `statistics_plan_freeze.json` (sha256 `09b4fbdf42a1755b08a49f38e36c433a423c24f46420a67d8262ea7de640a508`) — G-010.
- `precision_requirement.py` + `test_precision_requirement.py` — CG-03 sizing, reproducible.
- `MAPPING_REVIEW_PROTOCOL.md` — CG-05 / G-004.
- `RXMAP_FEASIBILITY.md` — CG-06 / G-008 (`ASSET_GATED`).
- `NEGATIVE_REFERENCE.md` — CG-07 / G-009 (specificity `UNSUPPORTED`).
- `PIPELINE_SPEC.md` + `mapping_candidates.py` + `test_mapping_candidates.py` — G-003 / G-006 (design only; runs without DAV data).
- `SOURCE_GATE_CHECKLIST.md` — G-001 / G-002 (used when DAV is delivered).
- Remaining external gates: **DAV acquisition (G-001 MANUAL, CG-01)** and **human mapping review (G-005 MANUAL, CG-05)**.
