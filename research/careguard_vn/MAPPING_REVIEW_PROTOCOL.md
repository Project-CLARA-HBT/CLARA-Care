# CareGuard-VN blinded mapping-review protocol (CG-05 / G-004)

Status: **PROTOCOL FROZEN**; execution **BLOCKED** (requires authorized DAV
identity frame + reviewer recruitment, G-005 MANUAL).

## Purpose

For ambiguous DAV → RxNorm mappings, adjudicate each candidate identity with a
frozen two-reviewer packet before the identity ledger is sealed. This protocol
defines reviewer background/qualification fields, blinding, rubric labels,
agreement statistic, and adjudication. It is a reviewer-protocol freeze, not a
completed review.

## Reviewer model (preferred)

Two independent blinded reviewers with pharmacist/medication-terminology
expertise. If two expert reviewers are unavailable, the qualification
shortfall is disclosed exactly (see Qualification disclosure) and the review
does not claim expert pharmacist agreement.

## Qualification fields (recorded per reviewer, frozen before review)

- `reviewer_id` — anonymous reviewer identifier (no names in outputs).
- `credential` — e.g. clinical pharmacist / pharmacist / pharmacy technician /
  physician / clinical pharmacologist / other (free text).
- `medication_terminology_experience_years` — integer.
- `rxnorm_familiarity` — none / basic / working / expert.
- `vietnam_drug_market_familiarity` — none / basic / working / expert.
- `pharmacovigilance_or_ddi_experience_years` — integer.
- `conflict_of_interest` — employer/funding relations to any source (DAV,
  RxNorm/NLM, DDInter, DailyMed) or to CLARA; `none` if absent.
- `certification_date_utc` — date the qualification record was frozen.

## Blinding

- Each reviewer sees the DAV raw string (product name, registration number,
  active ingredient, strength, form) and the deterministic candidate list
  (rxcui, name, tty, method, score) **only**.
- No Mode A / Mode B label, no downstream DDI outcome, no other reviewer's
  labels, no development-tuned aliases, and no cluster/aggregate result.
- Reviews are one-time; labels are timestamped and hash-bound into the review
  packet; no revision after unblinding.

## Rubric labels (single-label per candidate mapping)

| Label | Meaning |
| --- | --- |
| `ACCEPT` | candidate is a faithful current identity for the raw string |
| `AMBIGUOUS` | more than one plausible candidate; no defensible single choice |
| `UNRESOLVED` | no plausible candidate in the frozen terminology |
| `SOURCE_CONFLICT` | source fields contradict each other (e.g. registration vs ingredient) |

`ACCEPT` is the only label that forms an admissible identity; the others block
reassurance and count toward abstention. Rubric labels align with the mapping
ledger dispositions in `DAV_ACQUISITION_WORKFLOW.md`.

## Agreement statistic

- Statistic: **Cohen's kappa** over the 4-label rubric on the review sample,
  with per-label agreement and the raw disagreement count.
- Prespecified reference levels (planning only, not results): kappa ≥ 0.80 =
  acceptable; 0.61–0.79 = review and re-calibrate with an added reviewer;
  < 0.61 = do not seal the ledger, add a third reviewer and adjudicate all.
- Where assumptions for kappa are violated, report raw agreement and the
  disagreement matrix explicitly.

## Adjudication rule

- `ACCEPT`/`ACCEPT` → adopt.
- Non-`ACCEPT` agreement → adopt the shared label.
- Disagreement (`ACCEPT` vs non-`ACCEPT`, or any other mismatch) → third
  reviewer adjudicates; if a third reviewer is unavailable, the mapping is
  treated as `AMBIGUOUS` (fail-closed; blocks reassurance) and the
  disagreement is disclosed.
- All adjudicated mappings are written into the frozen identity ledger with
  reviewer packet hashes; no post-hoc relabeling after unblinding.

## Qualification disclosure (exact)

No pharmacist/medication-terminology reviewer has been recruited as of this
freeze (2026-08-19). When reviewers are recruited, the frozen packet must
include the qualification fields above verbatim. If expertise is unavailable
at review time, `READINESS.md` and the manuscript must state exactly:
"Mapping review was performed without a pharmacist or medication-terminology
expert; reviewer credential field = <actual>; no expert-agreement claim is
made." No project author substitutes as a reviewer unless separately recorded
in the same qualification fields.
