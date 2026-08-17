# CareGuard-VN DAV acquisition and freeze workflow

## Scope and status

This is the only acquisition path for the Vietnam identity frame. It requires an
operator-provided, complete official DAV export or an official DAV API delivery.
`evaluation/careguard_external/acquire_dav.py` has no network client and must
not be extended to scrape a public portal or paginate a search UI. No DAV data
has been retrieved under this workflow as of 2026-08-17.

Acquisition permission and public redistribution are separate decisions. The
operator must record sufficient official access terms to retain and evaluate the
export. `redistribution_review_status: PENDING` is permitted metadata, not an
acquisition or source-manifest blocker; it requires `redistribution_policy:
raw_prohibited`. Raw DAV content, record inventories, normalized records,
mappings, splits, and case-level outputs remain in the controlled archive and
outside Git until a separate release review explicitly permits otherwise.

## Acquire and provenance

1. Obtain the exact official DAV export/API delivery and an acquisition
   authorization or published access statement. Do not use search results,
   historical seed data, or a zero-row substitute.
2. Store the received payload in an operator-controlled directory outside Git.
   Record the official delivery URL, retrieval time, release/version, export
   format, record-ID field, access terms, license statement when published, and
   public redistribution-review status in the acquisition log.
3. Run `python -m evaluation.careguard_external.acquire_dav` with the retained
   file, official `*.dav.gov.vn` URL, release label, stable source record-ID
   field, access terms, and output path in the controlled archive. The command
   accepts CSV, JSON, or JSONL, hashes the raw payload and each source record,
   rejects missing/duplicate IDs, and emits a `FROZEN_ACQUIRED` identity-frame
   manifest only after validation.
4. Track only a compact receipt or non-sensitive manifest digest in this
   repository. Do not commit the export, row inventory, normalized values,
   mapping tables, or source-derived labels.

## Normalize and reconcile

1. Preserve each source record ID and record hash. Normalize only observed DAV
   fields into a versioned controlled schema: product name, registration number,
   active ingredient text, strength, dosage form, manufacturer/registrant, and
   source release. Missing fields stay missing; the pipeline never infers a
   generic ingredient, current marketing status, or withdrawal state.
2. Produce a normalization manifest that binds the DAV source-manifest hash,
   normalizer revision/hash, input/output counts, rejected-record counts by
   reason, and a record-level source-to-normalized provenance link. Normalize
   before splitting and do not use locked-test rows to tune aliases or rules.
3. Reconcile DAV ingredients/products to the frozen RxNorm terminology through
   a separately versioned mapping ledger. Every candidate records both source
   IDs/hashes, terminology release/record ID/hash, mapping method/version, and
   disposition: `accepted`, `ambiguous`, `unresolved`, or `source_conflict`.
   Only `accepted` mappings may form an admissible identity. Ambiguous,
   unresolved, stale, or conflicting identities must not release reassurance.
4. Reconcile eligible accepted identities to DDInter positives and the DailyMed
   confirmation subset using their frozen manifests. DDInter absence is
   `unknown`, never a negative label; DailyMed is confirmation-only. Record
   unmatched and conflicting pairs without collapsing them into negatives.

## Freeze and reproducibility

1. Validate all four distinct source manifests with `validate_source_set`: DAV
   identity frame, RxNorm terminology, DDInter positive reference, and DailyMed
   regulatory confirmation. A source manifest requires acquisition access terms,
   not resolved public redistribution terms.
2. In the controlled archive, create one freeze ledger containing hashes of the
   four source manifests, raw payloads, normalization manifest/code revision,
   mapping/reconciliation ledger, development-only tuning ledger, split,
   baseline versions/configuration, statistics plan, and evaluation runner.
   Seal it before locked testing; any changed hash creates a new freeze.
3. Emit only aggregate, non-source-row results and a hash-only public receipt.
   A failed reconciliation, incomplete source set, unsealed ledger, or missing
   controlled artifact makes the run `NOT RUN`.

## Mode A and Mode B

Mode A measures the full path: frozen raw DAV product identity input -> SBMI
normalization/reconciliation -> DDI engine. Mode B supplies the independently
frozen accepted external identity to that same DDI engine. Mode B is an
oracle-identity decomposition, not an additional benchmark or a substitute for
Mode A.

Both modes must use the same sealed source set, case IDs, eligible pair set,
DDI engine revision/configuration, positive-reference mapping, exclusions,
statistics plan, and release rules. They may differ only at the stated identity
input boundary. No source refresh, alias/mapping adjustment, threshold change,
case exclusion, or baseline reconfiguration is allowed between modes or after
locked-test access. Report both modes with the frozen denominators and preserve
abstentions/unknown labels; never calculate specificity or negatives from
reference absence.
