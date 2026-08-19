# W9 Execution Plan — GovMut follow-up corpus (freeze inputs + hardened review manifest)

Status: **inputs frozen; anchors verified; MANUAL human-review gate OPEN;
execution NOT started.** This file is the
execution checklist for the W9 corpus (11 mutants from
`W9_FOLLOWUP_CORPUS_PROPOSAL.json`). It does not modify, and must never modify,
the W8 sealed study (`seal/*`, `final_run.json`, `final_freeze.json`,
`results/final-analysis.json`) or the sealed runner
`evaluation/property_assurance/soict_final_runner.py`.

Inputs produced by this task (all in `research/assurance_soict/`):

| File | Role |
| --- | --- |
| `w9_catalog.json` | Machine catalog (11 entries, `mutation_site_candidates.json` format, status `anchor_verified_not_executed`) |
| `W9_MUTATION_CATALOG.json` | Full-fidelity catalog with proposal fields (layer/invariant/fault_family/reason_distinct) |
| `w9_review_manifest.json` | Frozen `clara-model-review-manifest.v2` manifest (11 cases, E1..E4 evidence) |
| `w9_freeze_input.json` | `govmut-final-freeze-input.v1` input, status `awaiting_manual_human_review` |
| `w9_anchor_verification.json` | Current-HEAD blob verification for all 11 anchors |

Prerequisites verified at input time:
- All 11 anchors are unique exact substrings (`count == 1`) in
  `services/api/src/clara_api` at revision
  `3263d011562e9246b6da6aa183e0ff2259d1d9cf` (re-verified by
  `test_w9_anchors_unique_in_verified_head_blob`).
- The method targets + `target_sha256`, hypothesis version `6.163.0`, ordered
  seeds `[17,23,41,97,271]`, and limits (600/1000/100) are byte-identical to
  the sealed `final_freeze.json` methods (re-verified by
  `test_w9_freeze_input_matches_sealed_methods_hypothesis_and_limits`).

## Decisions (documented deviations from the letter of W9_PROTOCOL.md)

1. **Freeze-input `study_id` is `assurance-soict-2026`**, not
   `assurance-soict-2026-w9`. `validate_final_freeze` (`final_freeze.py`, sealed,
   unmodified) binds `study_id` to `assurance-soict-2026`. The W9 corpus
   identity is carried by `freeze_id govmut-soict-w9-final-v1`, `w9_catalog.json`,
   and the w9 review manifest (`study_id assurance-soict-2026-w9`).
2. **Analysis schema remains `govmut-final-analysis.v1`** — the sealed analyzer
   `final_analyze.py` emits it and the seal gate requires it. The W9 run is
   distinguished by `freeze_id` and result-root location, not by a forked schema.
3. **`final_validate.py` runs WITHOUT `--require-soict-coverage`**: that flag
   binds the sealed W8 constants (45 mutants, 16 slots, 720 executions). The
   generic grid gate (derived from the run's own included ids and seed order)
   still enforces the full 11 x 16 = 176-slot Cartesian product for W9.
4. **No rerun of W8 and no reuse of W8 artifacts**: `w9_final_runner.py` reads
   only `w9_final_freeze.json`, `w9_catalog.json`, `statistics_plan.json`, and
   the w9 result root. `soict_final_runner.py` is not modified.

## Step 0 — Anchor re-verification gate (before any review call)

Re-run the anchor uniqueness check against the *promoted* code revision
(W9_PROTOCOL.md hardening #1, M02-B rebinding precedent):

```bash
python - <<'EOF'
import json, subprocess
catalog = json.load(open("research/assurance_soict/w9_catalog.json"))
for c in catalog["candidates"]:
    source = subprocess.run(
        ["git", "show", f"{c['anchor_verified_revision']}:{c['source_path']}"],
        check=True, capture_output=True, text=True,
    ).stdout
    n = source.count(c["anchor"])
    assert n == 1, f"{c['id']}: count {n}"
print("w9 anchors unique: 11/11")
EOF
```

Any anchor that fails uniqueness at execution time is an
`INFRASTRUCTURE_ERROR`/exclusion, never a kill (`mutation_overlay.py` rule).

## Step 1 — Hardened dual-model review (`run_v2`, not run in Workstream F)

No LLM call was made for this workstream. The commands below document the
separate auxiliary protocol only; they are not a substitute for the required
human review and are not an execution prerequisite for the current design
checkpoint.

Blinded independent reviews, both models, one call per case:

```bash
python -m evaluation.model_adjudication.run_v2 \
  --manifest research/assurance_soict/w9_review_manifest.json \
  --output-dir research/assurance_soict/model_review_run_w9
```

Produces `model_review_run_w9/model_review_results.json` + `raw/W9-*.json`
(`clara-model-review-run.v2`). Requires `CLARA_ROUTER_API_KEY`. Do not edit
`run_v2.py`; the manifest is validated strictly by its own loader before any
call.

## Step 2 — Reconciliation (`reconcile_v2`, exactly one round)

```bash
python -m evaluation.model_adjudication.reconcile_v2 \
  --raw-dir research/assurance_soict/model_review_run_w9/raw \
  --output-dir research/assurance_soict/model_review_run_w9/reconciled
```

Remaining disagreement stays `UNRESOLVED` (never retried a second time).

## Step 3 — Agreement analysis (`analyze_v2`)

```bash
python -m evaluation.model_adjudication.analyze_v2 \
  --data-dir research/assurance_soict/model_review_run_w9/reconciled \
  --output research/assurance_soict/model_review_run_w9/agreement.json
```

## Step 4 — Build the review artifact `govmut-dual-model-review.v1`

Build `research/assurance_soict/model_review_run_w9/dual_model_review.json`
with exactly the shape `final_freeze.py` requires:

```json
{
  "schema_version": "govmut-dual-model-review.v1",
  "model_ids": ["gemini-3.6-flash-high", "claude-sonnet-4-6"],
  "dispositions": [
    {"mutant_id": "W9-C01", "disposition": "<included|excluded_equivalent|excluded_unexecutable|unresolved>",
     "model_dispositions": {"gemini-3.6-flash-high": "<label>", "claude-sonnet-4-6": "<label>"}}
  ]
}
```

Disposition mapping (W7 `final_disposition_rule`): mutual `NON_EQUIVALENT`
(initial or after the one reconciliation round) -> `included`; mutual
`EQUIVALENT` -> `excluded_equivalent`; mutual `INVALID` ->
`excluded_unexecutable`; everything else (including `UNRESOLVED`) ->
`unresolved`, excluded transparently — never counted killed or survived.
All 11 mutants must appear exactly once; the artifact lives under
`research/assurance_soict/` so it satisfies the
`govmut_final_freeze_review_artifact_outside_manifest` constraint for the
promoted freeze.

## Step 5 — Promote the freeze (govmut-final-freeze-input.v1 -> govmut-final-freeze.v1)

Create `research/assurance_soict/w9_final_freeze.json` from
`w9_freeze_input.json`:

- `schema_version`: `govmut-final-freeze.v1`, `status`: `frozen`
- `freeze_id`: `govmut-soict-w9-final-v1`
- `code_revision`: **re-captured** with `git rev-parse HEAD` at promotion time
  (must equal the revision the review ran against; anchors re-verified in
  Step 0 against it)
- `catalog_sha256` / `statistics_plan_sha256`: recomputed for
  `w9_catalog.json` / `statistics_plan.json`
- `methods`, `hypothesis`, `limits`: carried over unchanged (already identical
  to the sealed W8 values)
- `non_equivalence_review`: `status: dual_model_reviewed`, `model_ids`,
  `artifact: model_review_run_w9/dual_model_review.json`,
  `results_sha256: sha256(artifact)`

Gate: `python -m evaluation.property_assurance.final_freeze --manifest
research/assurance_soict/w9_final_freeze.json --repository-root . --catalog
research/assurance_soict/w9_catalog.json --statistics-plan
research/assurance_soict/statistics_plan.json` must pass (it validates
revision, hashes, targets, seeds, limits, and the review artifact coverage).

## Step 6 — M0-M3 execution via the W9 runner wrapper

**Do NOT modify `soict_final_runner.py`.** The wrapper
`evaluation/property_assurance/w9_final_runner.py` mirrors it exactly but
points at the w9 paths (`w9_final_freeze.json`, `w9_catalog.json`,
`statistics_plan.json`) and refuses an unpromoted freeze
(`govmut_w9_final_freeze_not_promoted`). It delegates to
`final_runner.execute_final_run` unchanged.

```bash
python -m evaluation.property_assurance.w9_final_runner \
  --repository-root . \
  --output research/assurance_soict/w9_run/final_run.json
```

Expected grid: 11 included mutants (or fewer if any are excluded/unresolved) x
16 slots (M0 x1, M1/M2/M3 x5 seeds) = 176 executions for the full denominator.
This is the only step that executes mutants.

## Step 7 — Validate, analyze, seal the W9 result root

```bash
python -m evaluation.property_assurance.final_validate --run research/assurance_soict/w9_run/final_run.json
python -m evaluation.property_assurance.final_analyze \
  --run research/assurance_soict/w9_run/final_run.json \
  --catalog research/assurance_soict/w9_catalog.json \
  --output research/assurance_soict/w9_run/final_analysis.json
python -m evaluation.property_assurance.final_seal \
  --result-root research/assurance_soict/w9_run \
  --repository-root . --run-name final_run.json
```

Notes:
- No `--require-soict-coverage` (see Decisions #3).
- `final_analyze` stratifies by `family_seed`/`source_path`/`anchor` from the
  w9 catalog and emits mutant-level x method inference plus paired method
  comparisons, satisfying W9_PROTOCOL.md section 4 (per-mutant
  `detected_any_seed`, `detected_all_seeds`, `kill_fraction`,
  `seed_instability`, `first_killing_seed`, `time_to_first_kill_ms`, and
  exact two-sided McNemar p-values over the same mutant set).
- The seal writes into the **new** result root `research/assurance_soict/w9_run`
  (README, environment.json, artifact-sha256.json, claim_to_evidence.csv) and
  never touches `research/assurance_soict/seal/*`, `final_run.json`,
  `final_freeze.json`, or `results/final-analysis.json`.

## Step 8 — Post-execution follow-up

- Mutant-level paired method inference per layer (commitment gateway /
  governance-cache / persistence-reconstruction) answering whether
  replay/reconstruction faults are observable by M0 at all and whether M1/M2
  add detection over M0.
- `dual_model_review.json` and `final_analysis.json` recorded in the W9 seal.
- The API-layer gap (`api/v1/endpoints/*`) remains deliberately deferred
  (needs new route-level method targets outside the existing grid).

## W8 immutability statement

The W8 sealed 45-mutant study remains authoritative and immutable: `seal/*`,
`final_run.json`, `final_freeze.json`, `results/final-analysis.json` (M0 .356,
M1 .089, M2 .133, M3 .444). W9 is a distinct follow-up corpus; it revises no W8
number and weakens no W8 conclusion.
