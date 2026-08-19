# CareGuard-VN negative-reference decision (CG-07 / G-009)

Status: **DECISION FROZEN — specificity is `UNSUPPORTED`**. Focus is
positive-case safety and risk-coverage. No negative/specificity claim is made.

## DDInter absence is not a negative label

DDInter 2.0 is a positive-DDI reference. A pair absent from the frozen DDInter
inventory is `unknown`, never a negative (no-interaction) label. DDInter
absence is excluded from any negative/specificity denominator
(`statistics_plan_freeze.json` → `unknown_label_rule`).

## Repository search for an independently supported negative/reference source

Audited candidates (2026-08-19):

| Candidate | Evidence in repo | Decision |
| --- | --- | --- |
| DDInter 2.0 absence | `sources/ddinter_*` manifests | Not a negative source (absence = unknown) |
| DailyMed SPL subset | `sources/dailymed_*` manifest (warfarin, 5 records) | Regulatory **positive-confirmation only**; carries no negative labels; never used as a negative set |
| RxNorm prescribable | `sources/rxnorm_prescribable_*` receipts | Terminology baseline only; no interaction labels |
| n2c2 2019 concept normalization | optional access-controlled material referenced in manuscript specs | **Not acquired**; access terms not established; cannot be a current-Vietnam negative reference |
| RABBITS-style brand/generic invariance | manuscript spec mentions as a stratum | An invariance **stratum within positive pairs**, not a negative set |
| Historical DrugBank 5.0 | excluded in `source_acquisition_status.md` | Same-source conformance only; excluded from this study's evidence |

No independently supported negative/reference source is acquired or
defensible for a current Vietnam identity frame.

## Decision

- **Specificity: `UNSUPPORTED`** for CareGuard-VN external validation. Do not
  report specificity, negative-pair accuracy, or a false-positive rate on
  external evidence.
- **Focus:** positive-case safety (end-to-end false reassurance, conditional
  DDI false-clear, identity accuracy, abstention) and risk-coverage grid —
  per `statistics_plan_freeze.json`.
- Any future negative/reference subset must be independently supported with a
  defensible source and an adjudication process, added prespecifically
  (CG-02/CG-07) — never inferred from reference absence.
