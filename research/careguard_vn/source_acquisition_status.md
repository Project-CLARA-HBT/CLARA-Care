# CareGuard-VN source-acquisition status

Status: **two source roles acquired; no external benchmark may run**.

| Required role | Candidate official source | Access finding | Decision | Remaining gate |
| --- | --- | --- | --- | --- |
| Vietnam identity frame | DAV public registration/service portal | The repository's legacy DAVIDrug JSON endpoint returned HTTP 404 on 2026-08-16. On 2026-08-16 the DAV public-service root displayed a maintenance notice. A separate official YDCT search portal exposes registration/product/ingredient/form/strength/registrant/manufacturer fields, but says its entries are original grants and exclude later corrections, changes, supplements, and withdrawals. Its delivered UI bundle references a public paginated-search POST route, but no request was made and this does not establish export completeness or reuse rights. | Do not scrape, treat a search result as current marketed status, or substitute repository seed data. The discovery receipt is `sources/vietnam_official_portal_discovery_20260817.json`, not a source manifest. | Obtain an official current export/API route and written or published reuse terms; then record a versioned source manifest. |
| Terminology baseline | NLM RxNorm current prescribable content | The official RxNorm files page lists `RxNorm_full_prescribe_07062026.zip` as no-license-required. On 2026-08-16, both that dated URL and the generic `RxNorm_full_prescribe_current.zip` URL redirected (HTTP 302) to UTS login and then returned HTML; the full-current control behaved the same. No ZIP payload was downloaded. The discrepancy is retained in `sources/rxnorm_prescribable_access_probe_20260817.json`. | Not acquired; do not substitute ad-hoc REST answers or the release-page metadata for a frozen release. | Resolve the official access discrepancy or obtain authorized release delivery, retain one precise release outside git, then record checksum, row count, inventory, and terms. |
| Positive DDI reference | DDInter 2.0 | Official download page and terms page were reviewed; the eight published category CSVs were retrieved on 2026-08-16 into a controlled archive outside git. The archive has a complete 222,383-row canonical-hash inventory and a validated source manifest. | Acquired as one positive-reference role only; raw payload remains outside git under the stated CC BY-NC-SA 4.0 terms. | Map eligible positive pairs to frozen identities; do not infer negatives from absence; obtain the other three roles before any source-set freeze. |
| Regulatory confirmation | DailyMed SPL / FDA labels | A prespecified five-record current-SPL subset for the `warfarin` API query was acquired on 2026-08-16 into a controlled archive outside git. The source manifest records the current API database publication marker, payload SHA-256 and canonical per-record hashes. | Acquired as a regulatory-positive-confirmation source only. It carries no negative labels and cannot be a Vietnam identity frame or standalone benchmark. | Obtain the Vietnam identity frame and RxNorm terminology release, then map eligible external positives before source-set freeze. |

The DDInter receipt is
`sources/ddinter_2_0_acquisition_receipt_20260816.json`; its full inventory
manifest and raw CSV payload are retained outside git. This acquisition does not
authorize a benchmark run, source-set validation, negative labels, or any
false-clear/coverage result.
`sources/ddinter_2_0_archive_verification_20260817.json` records a subsequent
full archive-to-manifest verification without exposing source rows.

The failed DAV probe and the later maintenance/portal discovery are not negative
results and create no zero-row manifest. They establish only that the
hard-coded repository endpoint is not a usable acquisition route and that the
separate searchable official portal cannot presently support a current source
frame. Historical DrugBank data remains excluded.

`sources/dailymed_warfarin_subset_manifest_20260817.json` is the acquired
DailyMed regulatory-confirmation manifest. The five raw API records are retained
only under its controlled location; the repository contains hashes and source
identifiers, not label text. `validate_source_set` still rejects the current set
as incomplete because Vietnam identity and RxNorm terminology roles are absent.

`evaluation/careguard_external/acquire_rxnorm.py` is prepared for a future
authorized exact-release delivery. It requires an HTTPS URL, release label, and
published MD5; rejects non-ZIP/login payloads; inventories every retained RRF
row; and validates the resulting terminology manifest. It must not be run
against the current redirect response, and its existence does not change the
unacquired RxNorm status above.
