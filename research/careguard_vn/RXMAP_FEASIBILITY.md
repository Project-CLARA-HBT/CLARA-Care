# CareGuard-VN RxMap feasibility disposition (CG-06 / G-008)

Status: **DISPOSITION RECORDED — `ASSET_GATED`**. No RxMap run was performed
and none is claimed. Re-probe before final freeze and again after the DAV gate
passes.

## What RxMap is

Korpela, E., Rubin, L. H., Dastgheyb, R. M., & Xu, Y. (2026). *RxMap: an
LLM-assisted tool for medication normalization.* JAMIA Open 9(3),
doi:10.1093/jamiaopen/ooag085. RxMap combines deterministic RxNorm candidate
generation, LLM-assisted parsing, ingredient-level reconciliation, and
confidence/review, and reports RxCUI F1 0.966 on 22,624 unique medication
strings. Per the CareGuard literature lock (`research/careguard_vn/literature_lock.md`)
it is the nearest-neighbor normalization comparator and must be attempted
faithfully or recorded as not reproducible — never emulated.

## Search evidence (repository audit, 2026-08-19)

`grep -ri rxmap` and `grep -ri rxnorm` across the repository:

- **No RxMap implementation, model, or reproduction exists anywhere in the
  repo.** All RxMap occurrences are literature references (specs, novelty
  matrix, `main.tex`, `references.bib`, `literature_lock.md`).
- **Existing RxNorm/RxNav code is ingestion/provenance, not a comparator:**
  - `services/ml/src/clara_ml/ingestion/connectors/rxnorm.py` — RxNav REST
    `/drugs.json` connector that seeds drug-concept entity records; no LLM
    parsing, no candidate scoring rubric, no mapping benchmark.
  - `services/api/src/clara_api/api/v1/endpoints/careguard.py` — DDI engine
    source labels `rxnav`/`rxnorm` (NLM knowledge base) for alert provenance;
    not a normalization comparator.
  - `services/api/src/clara_api/core/careguard_metrics.py`,
    `scripts/demo/mine_hard_negatives.py` — `rxnav` used as a DDI source label.
- None of these is a faithful RxMap reproduction and none may be labeled RxMap.

## External access status (2026-08-19)

- No pinned RxMap release/version, code repository, model weights, license, or
  API access terms are recorded in this repository.
- The publisher article page returned HTTP 403 to our fetcher; an official
  code repository was not located and not verified at R3.
- Therefore the RxMap asset (code/model) and its license/access are
  **gated/unverified** at this freeze.

## Disposition

- **Disposition: `ASSET_GATED`** — the comparator cannot be executed now
  because its code/license/access is not established; the DAV identity gate is
  also not passed, so no comparator inputs exist yet.
- **Not `TASK_MISMATCH`**: RxMap targets medication-string normalization, which
  is the identity-resolution stage CareGuard must compare against; the task is
  in scope, the asset is not.
- **Not `DIRECTLY_EXECUTABLE`**: no pinned asset or terms are available.
- Next action: before final freeze (and again after DAV delivery), attempt to
  locate the official RxMap code release and record version + license; if
  reproducible under terms, run it on the same frozen normalization units
  without final-test tuning; otherwise emit a sealed `NOT_RUN` feasibility
  record with version/URL/reason.

## Prohibited

Emulating RxMap with project-local heuristics (including the CareGuard
deterministic normalizer in `mapping_candidates.py`) and labeling that RxMap
is prohibited. `mapping_candidates.py` is CareGuard's own design-only
deterministic candidate generator, not an RxMap substitute or comparator.
