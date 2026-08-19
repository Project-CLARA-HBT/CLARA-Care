# CareGuard-VN pipeline specification (G-003 / G-006)

Status: **SPEC ONLY — DESIGN**. This specification describes deterministic
normalization, mapping-candidate generation, and DDInter positive-mapping
design. No execution is claimed and no DAV data is required for the design
artifacts. `mapping_candidates.py` implements the design module and runs
without DAV data (empty/synthetic input is valid).

The pipeline will only be executed after the CG-01 external MANUAL gate
(authorized DAV identity frame) passes and the four-role source set validates
(`evaluation/careguard_external/source_manifest.py`).

## Pipeline stages (design)

```text
DAV raw export
 -> hash-bound source manifest (G-001/G-002, SOURCE_GATE_CHECKLIST.md)
 -> deterministic normalization            (this spec, mapping_candidates.py)
 -> DAV-to-RxNorm mapping candidates        (this spec, mapping_candidates.py)
 -> blinded mapping review/adjudication     (CG-05, MAPPING_REVIEW_PROTOCOL.md)
 -> frozen identity ledger
 -> external DDInter positive mapping       (this spec, mapping_candidates.py)
 -> DailyMed confirmation linkage           (confirmation only)
 -> (negative subset: NONE — specificity UNSUPPORTED, NEGATIVE_REFERENCE.md)
 -> frozen split + statistics plan + baselines (G-010)
 -> Mode A raw identity pipeline
 -> Mode B oracle identity pipeline
 -> risk/coverage + error decomposition
 -> seal
```

Mode A and Mode B share the same DDI engine, source set, eligible pairs,
exclusions, release rule, and analysis; only the identity input boundary
differs (DAV_ACQUISITION_WORKFLOW.md).

## Deterministic normalization (G-003)

- Input: DAV-normalized mapping-input CSV (schema `careguard-vn.mapping-input.v1`)
  with columns: `source_record_id, source_record_hash, product_name,
  registration_number, active_ingredient_text, strength, dosage_form,
  manufacturer, registrant, release_label`.
- Deterministic, versioned normalizer: NFKC + casefold, whitespace and
  punctuation collapsing, strength parsing to (amount, unit); Vietnamese
  diacritics preserved with a separate lossy folded variant for candidate
  generation. Missing fields stay missing; the pipeline never infers a generic
  ingredient, current marketing status, or withdrawal state.
- Every normalized record is fingerprinted by a canonical digest
  (`record_digest`) for deterministic provenance. No LLM and no development
  data are used for normalization.

## Mapping-candidate generation (G-003)

- Candidates are generated against the frozen RxNorm release (2026-08-03
  prescribable) only, through the `TerminologyIndex` over name/synonym/tty.
- Deterministic methods, in priority order, each with a score:
  `exact_name` (1.0), `ingredient_level` (0.85), `diacritic_fold` (0.9),
  `token_jaccard` (≥ threshold, default 0.8), capped at k (default 10).
- No LLM ranking and no threshold tuning on locked-test rows.
- Candidate statuses per input record: `CANDIDATES`, `UNRESOLVED`,
  `NO_TERMINOLOGY` (no frozen terminology table supplied), `REJECTED_INPUT`
  (schema violation with reason).
- Candidates alone are not dispositions; review/adjudication assigns
  `ACCEPT` / `AMBIGUOUS` / `UNRESOLVED` / `SOURCE_CONFLICT`
  (MAPPING_REVIEW_PROTOCOL.md). Only `ACCEPT` forms an admissible identity.

## DDInter positive mapping design (G-006)

- Frozen DDInter positive table (CSV): `interaction_id, drug_name_a,
  drug_name_b, interaction_type, risk_level, rxcui_a, rxcui_b`.
- An eligible external positive pair exists when both sides resolve to
  accepted frozen identities; the pair is then matched to DDInter by canonical
  drug name (and RxCUI where present). Matches are recorded as positive links
  per identity with `interaction_id`, `risk_level`, and the generating
  candidate method.
- DDInter absence for a pair is `unknown`; unmatched pairs are recorded as
  unmatched without collapsing into negatives. DailyMed confirmation linkage is
  confirmation-only (never a negative set, per CG-07).
- The join is deterministic over frozen tables; it does not benchmark, review,
  or release any conclusion.

## Module contract (`mapping_candidates.py`)

- Runs without DAV data: `python research/careguard_vn/mapping_candidates.py
  --input <mapping-input.csv> [--rxnorm-table <rxnorm.csv>]
  [--ddinter-table <ddinter.csv>] --output <candidates.jsonl>`.
- JSONL output per input row: status, reason, normalized fields, candidates
  (rxcui/name/tty/method/score), and `ddinter_positive_links` when the frozen
  DDInter table is supplied.
- Validation: `test_mapping_candidates.py` (deterministic normalization,
  candidate generation, no-terminology fallback, missing-field rejection).

## Non-claims

No benchmark execution, no review/adjudication, no identity ledger, no split
assignment, and no CareGuard result are produced by this design or module.
