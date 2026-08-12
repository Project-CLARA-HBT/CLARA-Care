# GLHS evidence program reproducibility index

## Current status

The current revision is not a clean final headline freeze. A non-headline MIMIC
Demo run exists at
`artifacts/evidence-program/2026-08-09-mimic-demo-no-annotation-v1/`: 31
development and 69 evaluation subjects are token-disjoint; 6,741 source-derived
tasks span medication, diagnosis/problem, and lab state. It has no independent
curator, clinical annotations, provider-model utility, deployed adversarial
run, PostgreSQL full-stack run, or clean source revision. Therefore no headline
clinical, privacy, utility, or superiority conclusion may be generated.

Existing Q2/Q3 outputs are developer-authored structural evidence only; see
[evaluation/glhs_q3/README.md](evaluation/glhs_q3/README.md) and
[claim-to-evidence matrix](docs/reports/glhs-q3-claim-to-evidence-matrix-2026-08-08.md).
The Demo run is sealed separately as
`sealed_nonheadline_not_claim_eligible`; its `artifact-sha256.json` hashes all
derived outputs without weakening the headline seal.

## Frozen-run contract

For each final run, create `artifacts/evidence-program/<run-id>/`. It must
contain environment, cohort/split/domain/annotation/adjudication/oracle/
comparator/model manifests; raw case and per-run outputs; domain/utility/
adversarial/human/fullstack/statistical/error CSVs; report; figures/tables; and
an artifact SHA-256 manifest.

Before execution, freeze and hash cohort/split, annotation guide/oracle,
policies, comparator, task/prompt/model/retrieval settings, endpoints, and
statistics plan. `evaluation.evidence_program.validate_statistics_plan` checks
the subject-clustered uncertainty and bounded-claim protocol, while
`evaluation.evidence_program.freeze.verify_freeze` rejects
an incomplete or non-independent freeze.

## Commands

Dataset foundation (metadata first; no command implies a dataset is clinically
validated):

```bash
python scripts/data/list_sources.py
python scripts/data/inspect.py --dataset <id>
python scripts/data/verify.py --dataset <id> --output /tmp/<id>-verification.json
python scripts/data/fetch.py --dataset <id> --accept-license
python scripts/data/fetch.py --dataset <id> --accept-license --resume
python scripts/data/normalize.py --dataset <id>
python scripts/data/freeze_manifest.py --dataset <id>
python scripts/data/verify_manifest.py --dataset <id>
python scripts/data/freeze_normalization_manifest.py --dataset <id>
python scripts/data/verify_normalization_manifest.py --dataset <id>
```

The eICU within-stay source-derived task freeze command is documented in
`evaluation/external_validation/README.md`. Its targets are source-offset
mechanics only and must not be relabelled as clinical correctness.
The same document gives the zero-provider-call production-primitive run and
validation commands. Protocol payload SHA-256 is
`3a29d0c02357ae2cc708284f7e0aff2f76474489ae73c25f1dd0111674beea65`;
the full execution remains `NOT_RUN` until that command completes unchanged.

`inspect` reports only presence and size. `verify` computes local SHA-256 and
archive integrity but does not claim canonical authenticity when the provider
does not supply a pinned checksum. `normalize` writes patient-level records only
under gitignored local paths. `freeze_manifest` refuses a dirty tracked
worktree, unresolved canonical source or existing manifest; it never imports
raw records into git. `verify_manifest` fails if the manifest self-hash,
registry hash, source commit, or current local source inventory has changed.
Interrupted downloads retain an atomic `.part` file and require explicit
`--resume`; partial-only directories remain `NOT_AVAILABLE` to every inspection
and verification command.

New freezes bind both the complete registry file and the selected dataset entry.
The manifest verifier accepts unrelated later registry additions only when the
dataset-entry hash is unchanged. Legacy freezes are checked against the exact
historical registry bytes at their recorded Git commit; changed dataset entries
still fail closed.

The local SyntheticMass FHIR v1 archive is 30,878,003,109 bytes with SHA-256
`c913774ac42f9c68a3f18e24e579e55a8b1a380bebe403b68cc67ff7226de127`.
The freezer and subsequent manifest verifier independently traversed 11 nested
archives, 1,307,771 FHIR bundles and 2,711,037 nested members, rejecting links
or traversal paths; both observed zero unsafe members. Its source-manifest
payload SHA-256 is
`384e9fc5669aceea0070cb6a11ee621f9e63f298a87893312bffe4073c8443cd`.
Canonical checksum status is `NOT_PROVIDED`; normalization and systems metrics
are not yet frozen, and the source is synthetic rather than clinical truth.

Current local MIMIC-IV Demo on FHIR adapter output contains 927,109 common
records for 100 deidentified source subjects and explicitly preserves missing
knowledge time for every record. It is a non-headline adapter/structural source,
not an independent clinical oracle. Its tracked manifest payload SHA-256 is
`e5257d01f07024cfc965f0f263484c49fac2c5728539de3d030db8b0eadec738`;
canonical checksum status remains `NOT_PROVIDED`.

The local Diabetes-130 normalized output contains 2,768,244 records derived
from 101,766 encounters and 71,518 source subjects. Its records SHA-256 is
`9962c20af14eab834680aa1a3d4c2beae784752ed48b63ca0e6a567613e78760`.
The source has no event/knowledge timestamps; the adapter leaves both unknown
and creates no estimated time. Its frozen manifest payload SHA-256 is
`0d8bdbd621e0e54a4acd15ec7461de5edcceb8376f4f413a2f2f125c64992ec8`.
These are adapter and structural counts only.

The local eICU Demo archive passed all 33 packaged provider SHA-256 entries.
Its selected-table output contains 540,237 source-linked records for 1,841
subjects and 2,520 stays; records SHA-256 is
`68b25539c09e64aca75ce1010b51787c7ba179ad5d0fffb7f961b9e242310756`.
The clean-SHA instrumented rerun was byte-identical and measured 24.764845
seconds wall-clock, 21,814.67 records/second, peak RSS 65,016 KiB and 5.7550x
storage amplification on this host. Source-manifest payload SHA-256 is
`169411ad4edb49ac4d10c9ffcb51952403ef8ccd15a92602d06f3c7346e186e2`.
The tracked normalized-evidence manifest is
`datasets/manifests/eicu_crd_demo_2_0_1.normalization.json`, with payload
SHA-256 `44f0e9253599d07fcf10f741c8d1f4db2325c3827b6a97eed9bae17cf5f56850`.
The eICU source-offset aggregate manifest is
`datasets/manifests/eicu_crd_demo_2_0_1.source-offset-tasks.json`; task SHA-256
is `0b125b72c9327450ad21b199b7e48482d918a1d06a1ec7a962edf6c32ddc31e4`.
The task rows remain gitignored and are regenerated from the frozen normalized
output before validation.

The frozen production-primitive run processed all 59,513 tasks and 343,537
events from 1,413 source subjects. Production GLHS reconstruction and the
strong valid-offset reference each selected 59,513/59,513 source-derived
targets; the input-order diagnostic selected 17,160/59,513. Missing outputs
and errors were zero. The tracked sanitized result is
`datasets/manifests/eicu_crd_demo_2_0_1.source-offset-glhs-result.json`, with
payload SHA-256
`31a8cd13a2697e403bcb30c92c37ed5186049b7b854ef3caa139c5e7a21eecf1`.
It binds the ignored raw/subject aggregates by SHA-256 and revalidates them
network-free. This establishes source-offset state-reconstruction mechanics on
SQLite/in-process production primitives, not clinical correctness or
HTTP/PostgreSQL performance.

New operator-supplied sources are isolated under ignored dataset roots. The
SynPUF OMOP 100K sample is registered separately from the approximately 2.3M
distribution. The latter currently fails closed because an extra
temporary-suffix LZO object is corrupt. Synthea Coherent is registered from its
bundled CC BY 4.0 README; its 9,228,105,262-byte ZIP has local SHA-256
`4e94373bade1106b5482e89274af7f4d59f8c9497dc899b579cfec445035c036`.
Neither source has a verified provider checksum or normalized evidence freeze.
The separately supplied Diabetes-130 ZIP is byte-identical to the already
frozen UCI archive and is not counted as independent evidence.

The registered SynPUF OMOP 100K source passed local integrity over 17 gzip
tables (914,865,701 bytes; inventory SHA-256
`11fd10d71452d19a620cedb96fd043bf5ca58808ada676ebad1281b143e40f35`). Its
streaming OMOP normalization emitted 39,573,534 records for 90,217 subjects;
the deterministic gzip output is 3,267,982,283 bytes with SHA-256
`69cef106cf1a64359111b910b16e39f815eb2e5fbd559eb7b3c833be5bc8cf3a`.
The run measured 2,159.45 seconds wall-clock, 18,325.74 records/second and
475,248 KiB peak RSS on this host. The tracked normalization aggregate is
`datasets/manifests/cms_de_synpuf_omop_100k.normalization.json`, payload
SHA-256 `40c2c0a2087918430edd1800de41acc02238a938a9d6ac338b4fcbdc29eba770`.
The source is synthetic and has no provider-pinned checksum; these are local
adapter/reproducibility metrics only.

Synthea Coherent passed full ZIP CRC/inventory verification: 2,488 entries
(2,484 files), 15,111,284,460 uncompressed bytes, source inventory SHA-256
`144a6c34e426509b2d29b8fec838ed540b1c45f687134437a15dcf3ffcbd4f57`, and
source archive SHA-256
`4e94373bade1106b5482e89274af7f4d59f8c9497dc899b579cfec445035c036`.
The minimized FHIR adapter emitted 1,297,901 records from 1,278 bundles and
subjects; its gzip output SHA-256 is
`5b6b600573d20534ad4008198aaa946e8d4a2cda9be968c017cc14b6506377d8`.
The tracked normalization aggregate is
`datasets/manifests/synthea_coherent.normalization.json`, payload SHA-256
`4f43cd5512121967297e198588da8c96798e28d0b74fa0a3bef8def080dec7f4`.
CSV, DICOM and DNA are inventory-only modalities; provider checksum and
cross-modality linkage validation remain absent.

Structural regression only:

```bash
services/api/.venv/bin/python -m pytest -q evaluation/glhs_q3/test_run.py
python3 -m evaluation.glhs_q3.run --output artifacts/glhs-q3/<structural-run-id>
```

MIMIC Demo source-derived run (requires the user-supplied Demo-on-FHIR archive
to be extracted locally and a secret salt outside git):

```bash
python3 -m evaluation.external_validation.prepare_mimic_demo_fhir \
  --fhir-root /secure/mimic-demo-fhir/fhir \
  --output artifacts/evidence-program/<run-id>/fhir-source-derived \
  --token-salt-file /secure/token-salt.bin \
  --lawful-access-attestation 'Demo access attestation' --freeze-id <freeze-id>
python3 -m evaluation.domain_portability.run_source_derived \
  --records artifacts/evidence-program/<run-id>/fhir-source-derived/records.jsonl \
  --output artifacts/evidence-program/<run-id>/domain-source-derived
python3 -m evaluation.evidence_program.report_demo_run --run-dir artifacts/evidence-program/<run-id>
python3 -m evaluation.evidence_program.seal_nonheadline --run-dir artifacts/evidence-program/<run-id>
```

Protocol validation (does not run a clinical evaluation):

```bash
python3 -m evaluation.external_validation.validate_manifest --manifest /secure/cohort.json --development-subjects /secure/dev-tokens.txt --test-subjects /secure/test-tokens.txt
python3 -m evaluation.independent_adjudication.validate_manifest --manifest /secure/annotation.json
python3 -m evaluation.downstream_utility.validate_manifest --tasks /secure/tasks.json --models /secure/models.json --freeze /secure/freeze.json
python3 -m evaluation.evidence_program.seal --run-dir artifacts/evidence-program/<run-id> --freeze /secure/freeze.json
python3 -m evaluation.evidence_program.status --output /tmp/evidence-readiness.json
```

## Paper mapping

| Paper evidence | Source version | Commands/manifests | Outputs |
| --- | --- | --- | --- |
| Structural GLHS mechanics | exact clean git SHA/tag required | Q3 command above | `artifacts/glhs-q3/<id>/` |
| Temporal comparator | comparator version + source mapping | comparator tests + frozen manifest | comparator manifest |
| MIMIC Demo source-derived mechanics | dirty SHA `76eb5c2f...`; non-headline only | Demo commands above | `artifacts/evidence-program/2026-08-09-mimic-demo-no-annotation-v1/` |
| External/adjudicated evidence | exact clean SHA/tag required | curator-owned frozen protocol | `artifacts/evidence-program/<id>/` |
| Tables/figures | same artifact SHA manifest | report generator only | frozen generated files |

Never place licensed EHR data, salts, credentials, patient text, or reviewer
identities in git. Reported numbers must be derived from frozen raw artifacts,
not copied manually.
