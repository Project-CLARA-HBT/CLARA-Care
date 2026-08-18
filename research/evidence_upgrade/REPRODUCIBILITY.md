# Evidence reproducibility — W11 CI/release + reproducibility

Exact commands and pinned artifacts to reproduce the four evidence analyses in
this workstream, at the revisions recorded below. This document is
**read-only**: it never mutates sealed artifacts, never touches the remote VPS,
CareGuard, or the running SOICT process, and makes no git commits.

Runtime: `services/api/.venv` (Python 3.11, frozen by `services/api/uv.lock`).
Raw sealed artifacts live under the gitignored `artifacts/` root; database-bound
steps require the attested isolated PostgreSQL operator environment and refuse
to run without it (fail-closed).

## Pinned revisions

| Analysis | Run / freeze ID | Source SHA | Commit context |
| --- | --- | --- | --- |
| RIVF final-003 | `2026-08-17-rivf-final-003` | `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb` | RIVF adapter/executor |
| GLHS v1 final run | `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01` | `2074f87550c5ee32302bde47bc0b9e6be6af36b5` | final frozen runner |
| GLHS v2 matrix | `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01` | `67e528b61512aabc201b344e54f9e3e724490e41` | executed source revision |
| SOICT sealed matrix | `govmut-soict-2026-final-v2` | `7c963153c5ad4b62bc9eb58b5ad976b233a3631f` | frozen M0–M3 final study |
| Formal assurance | — | `67a1b6fe…99f7` (recorded) / `8d370d51…` (re-run at HEAD) | `FORMAL_ASSURE_REPORT.md` |

The immutable binding between runs, code revisions, and artifact bytes is the
seal inventory `research/evidence_upgrade/audit/sealed_run_inventory.json` and
the per-run `artifact-sha256.json` files referenced below.

---

## 1. RIVF final-003 analysis (analysis-v2 from raw rows)

Frozen inputs (all bound to exact bytes by
`research/govred_rivf/provenance/final-003-reconciliation.json`):

| Input | Path |
| --- | --- |
| Frozen manifest | `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json` |
| Frozen statistics plan | `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_statistics_plan.json` |
| Raw rows (4 arms) | `artifacts/govred/2026-08-17-rivf-final-003/{UNBOUND,STATE_VERSION_ONLY,SNAPSHOT_BOUND_STATE_ONLY,GLHS_STRICT}/raw_results.csv` |
| Seal | `artifacts/govred/2026-08-17-rivf-final-003/artifact-sha256.json` |
| v2 analysis | `research/govred_rivf/results/final-003-analysis-v2.json` |

Verify the raw rows still match the frozen reconciliation bytes:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path(".")
rec = json.loads((root / "research/govred_rivf/provenance/final-003-reconciliation.json").read_text())
arms = ("UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT")
ok = True
for arm in arms:
    p = root / f"artifacts/govred/2026-08-17-rivf-final-003/{arm}/raw_results.csv"
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    declared = rec["raw_results_sha256"][arm]
    match = actual == declared
    ok = ok and match
    print(f"{arm}: match={match} sha={actual}")
assert ok, "raw rows drifted from reconciliation"
print("raw rows reconciled")
PY
```

Recompute the machine-verifiable analysis quantities from the raw rows
(all-executed, NOT_RUN, endpoint split, and the paired exact McNemar b/c):

```bash
python3 - <<'PY'
import csv
from pathlib import Path
root = Path("artifacts/govred/2026-08-17-rivf-final-003")
arms = ("UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT")

def load(arm):
    return {
        r["case_id"]: r
        for r in csv.DictReader((root / arm / "raw_results.csv").open())
        if r["run_status"] == "EXECUTED"
    }

rows = {a: load(a) for a in arms}
for arm, data in rows.items():
    invalid = sum(r["stale_or_unauthorized_commit"].strip() == "true" for r in data.values())
    print(arm, "all_executed_n=", len(data),
          "invalid_commit_acceptance=", invalid)

b = c = 0
for cid, strict in rows["GLHS_STRICT"].items():
    unbound = rows["UNBOUND"].get(cid)
    if unbound is None:
        continue
    sf = strict["stale_or_unauthorized_commit"].strip() == "true"
    uf = unbound["stale_or_unauthorized_commit"].strip() == "true"
    if uf and not sf: b += 1
    if sf and not uf: c += 1
print("paired exact McNemar: b=", b, "c=", c, "p_exact=", 2 * 0.5 ** b)
PY
```

Expected: `all_executed_n=270`, `NOT_RUN=180` per arm, GLHS_STRICT
`invalid_commit_acceptance=60`, paired exact McNemar `b=90`, `c=0`,
`p_exact=1.6155871338926322e-27` (never an underflowed zero). The canonical
primary denominator (210/arm) and family-stratified residual follow the frozen
manifest (`primary_family_ids`) and statistics plan; the primary rates
reproduce from those denominators exactly (e.g. GLHS_STRICT 30/210 = 0.142857).

Canonical machine verification (recomputes every declared rate from the
denominators, resolves seals, and rejects a top-level `SEALED` without a
resolvable seal):

```bash
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.evidence_program.render_status --repository-root .
```

---

## 2. GLHS v2 matrix (`executor_v2` on isolated PostgreSQL)

The v2 protocol is the execution boundary; see
`research/glhs_journal/protocol_v2/README.md` for the isolation contract.

| Input | Path |
| --- | --- |
| Frozen v2 protocol | `research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json` |
| Frozen v2 statistics plan | `research/glhs_journal/protocol_v2/statistics_plan_v2.json` |
| Raw v2 observations | `research/glhs_journal/protocol_v2/run_v2_raw.json` |
| v2 analysis | `research/glhs_journal/protocol_v2/analysis_v2.json` |
| Seal | `research/glhs_journal/protocol_v2/artifact-sha256.json` |

Prerequisites on the attested isolated-stack host: project
`clara-rivf-20260817-final001`, container
`clara-rivf-20260817-final001-postgres-1`, and a fresh operator-created database
`glhs_final_v2` (the executor refuses shared/default databases).

```bash
docker exec clara-rivf-20260817-final001-postgres-1 \
  psql -U <postgres_user> -c 'CREATE DATABASE glhs_final_v2;'

export GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH=1
export GLHS_TOCTOU_FINAL_DATABASE_URL='postgresql+psycopg://<user>:<pass>@127.0.0.1:5432/glhs_final_v2'

PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.glhs_postgres_toctou.executor_v2 \
  --protocol research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json \
  --output research/glhs_journal/protocol_v2/run_v2_raw.json
```

The executor refuses (exit 2, `{"status":"REFUSED",...}`) unless the isolation
attestation, a PostgreSQL URL, and a `FROZEN_FINAL_REVIEWED` protocol matching
the frozen isolation contract are all present. Observations are never
fabricated: each schedule runs through the real CLARA GLHS gateway and
persisted governance writers over `clara_api.db.models` rows.

Honest status note: the sealed `run_v2_raw.json` records
`status: EXECUTED_V2_OBSERVATION_MISMATCH` — the v2 matrix is **not
claim-eligible**. `classification_audit` shows two schedules
(`TOCTOU-V2-05`, `TOCTOU-V2-09`) whose observed classification differed from
the frozen expectation; `analysis_v2.json` reports 1 committed, 10 rejected,
0 indeterminate. Re-running the command above must reproduce the same raw
observations; do not recode a mismatch as safe.

Pure-Python validation gate (no database required):

```bash
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m pytest -q evaluation/glhs_postgres_toctou
```

---

## 3. SOICT sealed matrix (`final_validate` / `final_analyze` / `final_seal`)

| Input | Path |
| --- | --- |
| Final freeze | `research/assurance_soict/final_freeze.json` |
| Mutant catalog | `research/assurance_soict/mutation_site_candidates.json` |
| Statistics plan | `research/assurance_soict/statistics_plan.json` |
| Sealed run (v2 copy) | `research/assurance_soict/seal/govmut-soict-2026-final_run-v2` |
| Sealed analysis (v2 copy) | `research/assurance_soict/seal/govmut-soict-2026-final_analysis-v2` |
| Unmutated baseline | `research/assurance_soict/unmutated_preflight.json` |
| Seal root | `research/assurance_soict/seal/` |

Frozen contract: 45 reviewed non-equivalent mutants × 16 slots (M0 ×1 +
M1/M2/M3 × 5 seeds each) = 720 executions. Outcomes recorded:
`KILLED 161, SURVIVED 559, INFRASTRUCTURE_ERROR 0`.

```bash
RESULT_ROOT=/tmp/govmut-soict-final   # gitignored scratch root

PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.property_assurance.soict_final_runner \
  --repository-root . --output "$RESULT_ROOT/final_run.json"

PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.property_assurance.final_validate \
  --run "$RESULT_ROOT/final_run.json" --require-soict-coverage

PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.property_assurance.final_analyze \
  --run "$RESULT_ROOT/final_run.json" \
  --catalog research/assurance_soict/mutation_site_candidates.json \
  --output "$RESULT_ROOT/final_analysis.json"

PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.property_assurance.final_seal \
  --result-root "$RESULT_ROOT" --repository-root .
```

`final_validate` is read-only (never executes mutants), rejects duplicate or
missing slots, and never normalizes `INFRASTRUCTURE_ERROR` to KILLED/SURVIVED.
`final_seal` re-validates the run fail-closed, inventories `artifact-sha256.json`
against every pre-existing file under the result root, records the environment
(Hypothesis version, limits, source SHA) in `environment.json`, and derives
`claim_to_evidence.csv`. The sealed copies in `research/assurance_soict/seal/`
carry the `-v2` suffix; aggregation follows the frozen rule in
`research/assurance_soict/ANALYSIS_PLAN.md` (primary `detected_any_seed`,
robustness `detected_all_seeds`; seeds are deterministic streams, not
independent N).

Unmutated-baseline preflight (asserts no baseline failures recorded):

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("research/assurance_soict/unmutated_preflight.json")
pre = json.loads(p.read_text())
assert pre["status"] == "preflight_complete", pre["status"]
failed = [r["method"] for r in pre["results"] if r["outcome"] != "PASS"]
assert not failed, f"baseline failures recorded: {failed}"
print("preflight clean:", len(pre["results"]), "slots, all PASS")
PY
```

---

## 4. Formal assurance (`explore.py`)

Module: `evaluation/formal_governance/` (`model.py`, `transitions.py`,
`invariants.py`, `explore.py`). Report:
`research/evidence_upgrade/formal/FORMAL_ASSURE_REPORT.md`.

```bash
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.formal_governance.explore        # bounded BFS, default depth 5
```

and, for the deep enumeration (depth 6), from a Python REPL:

```python
from evaluation.formal_governance.explore import explore
explore(max_depth=6)
```

The enumerator is a deterministic bounded exhaustive BFS over the finite,
saturated coordinate domain (single subject/actor/task, roles/purposes in two
values, versions in {0,1}, evidence universe {e0,e1}). Recorded results at the
pinned revision: depth 5 → 21,361 unique states, 90,432 transitions, 0
violations; depth 6 → 69,342 states, 378,602 transitions, 0 violations.
Re-running at HEAD (`8d370d51…`) must reproduce 0 violations and 0 minimal
counterexamples. Bounded checking is not a universal proof; the limitation
statement in `FORMAL_ASSURE_REPORT.md` applies.

---

## Verification status

The workflow `.github/workflows/research-evidence.yml` runs the read-only,
committed-artifact checks (docs/status consistency, ruff, focused pytest,
secret-scan, govmut preflight, artifact schema). Database-bound steps
(Sections 1–3 raw execution) require the attested isolated-stack host and are
never executed inside CI; CI instead verifies the committed seals and the
reproducibility invariants that do not require a database.
