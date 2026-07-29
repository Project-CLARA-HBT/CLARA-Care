# Dataset card — CLARA-Eval VN fixtures

## Identity and purpose

- Dataset family: `clara-eval-vn-fixtures-v1`.
- Manifest: `evaluation/clara_eval/datasets/manifest.json`.
- Intended use: structural smoke, artifact-contract and release-gate validation
  for the nine CLARA-Eval VN tracks.
- Prohibited use: clinical quality claim, model selection, safety release
  approval, training, or human-performance comparison.

## Content and provenance

Every checked-in JSONL fixture is synthetic, short and purpose-labelled. The
manifest records file SHA-256, record count, track, synthetic status and
limitations. Fixtures contain no real patient record, contact information,
provider key, licensed DrugBank content, retrieval corpus or clinician rating.
The runner validates the manifest before it writes artifacts and fails if a
required track, checksum, measurement reason or command is missing.

## Coverage and known exclusions

The fixtures cover the contractual shapes of Vietnamese clinical understanding,
medical QA/patient communication, research RAG, CareGuard/DrugBank, Scribe/ASR,
LifeMap invariants, Council ablation, wording/usability, and routing/latency/
cost. They are deliberately not representative of Vietnamese patients,
dialects, acuity, medication inventory, ASR audio, retrieval evidence or live
provider performance. No score derived from them is a clinical metric.

## Access, privacy and retention

Fixtures are version-controlled source code and may be used only for the stated
test purpose. Do not add raw prompts, clinical conversations, names, email,
medication lists, recordings or external licensed data. Approved locked data
must live in the authorized evaluation store, with access control, retention,
de-identification review, immutable snapshot ID and separate governance record.
Judge artifacts are generated under `artifacts/judge-report/`, ignored by git,
and must be reviewed for PII before external sharing.

## Measurement and promotion boundary

The only measured fixture property is manifest integrity. All product metrics
remain `not_measured` until an approved immutable dataset, retrieval snapshot,
model/prompt manifest and execution evidence are supplied. To run the structural
suite:

```bash
make eval-smoke
make eval-judge-report
```

To request a real release decision, provision approved data out of band and run
the locked suite. A missing input must keep the release gate non-zero:

```bash
make eval-release
```

## Change control and rollback

Changing a fixture requires updating its checksum/count in the manifest,
reviewing the dataset-card limitations and adding a regression test. Do not
replace a prior immutable real snapshot in place. Pin a new version, retain the
previous snapshot reference and rollback by selecting the prior approved
manifest/snapshot in the evaluator configuration.
