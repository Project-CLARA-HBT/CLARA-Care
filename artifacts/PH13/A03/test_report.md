# Test Report — PH13 / A03 (Wearable Dedup and Multi-Source Version Mapping)

- **Phase**: PH13 (Connected Health và wearables)
- **Agent**: A03 (Domain + GLHS services)
- **Branch**: `phase/ph13-a03`
- **Base SHA**: `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`
- **Worktree**: `/dev/shm/clara_worktrees/PH13_A03`
- **Environment**: Python 3.12.3, pytest 9.0.2, ruff 0.15.8, mypy (services/api `.venv`)

## Summary

| Check | Command | Exit |
|-------|---------|------|
| Bytecode compilation | `python3 -m compileall -q services/api/src/clara_api/lifemap services/api/src/clara_api/core` | 0 |
| Unit tests (16) | `PYTHONPATH=src python3 -m pytest src/clara_api/lifemap/test_wearable_dedup.py -q` | 0 |
| Lint | `ruff check .../wearable_dedup.py .../test_wearable_dedup.py .../core/config.py` | 0 |
| Type check | `mypy .../wearable_dedup.py --ignore-missing-imports` | 0 |
| Connected-health schema regression | `PYTHONPATH=src python3 -m pytest tests/test_connected_health_schemas.py -q` | 0 |
| Path ACL | `python3 scripts/ci/check_agent_path_acl.py -a A03 -p PH13` | 0 |

## 1. Bytecode compilation

```
$ python3 -m compileall -q services/api/src/clara_api/lifemap services/api/src/clara_api/core
compile_exit=0
```

## 2. Unit tests — pure logic, no DB

```
$ cd services/api && PYTHONPATH=src python3 -m pytest src/clara_api/lifemap/test_wearable_dedup.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /dev/shm/clara_worktrees/PH13_A03/services/api
configfile: pyproject.toml
plugins: hypothesis-6.163.0, asyncio-1.3.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False
collecting ... collected 16 items

src/clara_api/lifemap/test_wearable_dedup.py::test_flag_defaults_to_disabled_and_fails_closed PASSED [  6%]
src/clara_api/lifemap/test_wearable_dedup.py::test_flag_can_be_read_from_explicit_settings PASSED [ 12%]
src/clara_api/lifemap/test_wearable_dedup.py::test_dedup_key_is_deterministic_and_ignores_observed_order PASSED [ 18%]
src/clara_api/lifemap/test_wearable_dedup.py::test_exact_duplicate_is_skipped PASSED [ 25%]
src/clara_api/lifemap/test_wearable_dedup.py::test_new_record_is_accepted PASSED [ 31%]
src/clara_api/lifemap/test_wearable_dedup.py::test_newer_revision_supersedes_older_one PASSED [ 37%]
src/clara_api/lifemap/test_wearable_dedup.py::test_older_revision_is_superseded_by_existing PASSED [ 43%]
src/clara_api/lifemap/test_wearable_dedup.py::test_device_source_beats_cloud_on_conflict PASSED [ 50%]
src/clara_api/lifemap/test_wearable_dedup.py::test_lower_precedence_source_conflict_is_preserved_not_overwritten PASSED [ 56%]
src/clara_api/lifemap/test_wearable_dedup.py::test_cross_source_identical_value_is_duplicate_skipped PASSED [ 62%]
src/clara_api/lifemap/test_wearable_dedup.py::test_freshness_breaks_ties_within_same_source_class PASSED [ 68%]
src/clara_api/lifemap/test_wearable_dedup.py::test_batch_mapping_is_order_independent_and_preserves_conflicts PASSED [ 75%]
src/clara_api/lifemap/test_wearable_dedup.py::test_batch_mapping_marks_cross_source_echo_as_duplicate PASSED [ 81%]
src/clara_api/lifemap/test_wearable_dedup.py::test_batch_mapping_collapses_revisions_to_newest PASSED [ 87%]
src/clara_api/lifemap/test_wearable_dedup.py::test_source_class_override_is_honoured PASSED [ 93%]
src/clara_api/lifemap/test_wearable_dedup.py::test_naive_timestamps_are_rejected PASSED [100%]

============================== 16 passed in 0.44s ==============================
```

Coverage map against requirements:

- **deterministic idempotency/dedup key** — `test_dedup_key_is_deterministic_and_ignores_observed_order`,
  `test_exact_duplicate_is_skipped`, `test_naive_timestamps_are_rejected`.
- **version precedence across sources** — `test_newer_revision_supersedes_older_one`,
  `test_older_revision_is_superseded_by_existing`, `test_device_source_beats_cloud_on_conflict`,
  `test_freshness_breaks_ties_within_same_source_class`, `test_batch_mapping_collapses_revisions_to_newest`.
- **conflict preservation** — `test_lower_precedence_source_conflict_is_preserved_not_overwritten`,
  `test_batch_mapping_is_order_independent_and_preserves_conflicts`.
- **explicit outcomes (accepted / duplicate_skipped / superseded / conflict_preserved)** —
  asserted directly on `DedupOutcome` in every case above.
- **flag default False, fail-closed** — `test_flag_defaults_to_disabled_and_fails_closed`,
  `test_flag_can_be_read_from_explicit_settings`.

## 3. Lint

```
$ services/api/.venv/bin/ruff check services/api/src/clara_api/lifemap/wearable_dedup.py services/api/src/clara_api/lifemap/test_wearable_dedup.py services/api/src/clara_api/core/config.py
All checks passed!
ruff_exit=0
```

## 4. Type check

```
$ services/api/.venv/bin/mypy services/api/src/clara_api/lifemap/wearable_dedup.py --ignore-missing-imports
Success: no issues found in 1 source file
mypy_exit=0
```

## 5. Existing connected-health contract regression

```
$ cd services/api && PYTHONPATH=src python3 -m pytest tests/test_connected_health_schemas.py -q
..............                                                           [100%]
14 passed in 401.75s (0:06:41)
```

The canonical `CanonicalHealthRecord` contract was reused unchanged; the new
module imports it read-only.

## 6. Path ACL

```
$ python3 /home/clue/Documents/CLARA-Care/scripts/ci/check_agent_path_acl.py -a A03 -p PH13
================================================================================
PATH ACL CHECKER — PASSED (Agent: A03, Phase: PH13)
================================================================================
Evaluated Files : 0
Allowed Lanes   : 9
  - services/api/src/clara_api/glhs/
  - services/api/src/clara_api/lifemap/
  - services/api/src/clara_api/phr/
  - services/api/src/clara_api/compliance/
  - services/api/src/clara_api/core/
  - artifacts/PH13/A03/change_manifest.json
  - artifacts/PH13/A03/test_report.md
  - artifacts/PH13/A03/risk_register.md
  - artifacts/PH13/A03/
```

Re-run against the fixed base commit to include committed files:

```
$ python3 /home/clue/Documents/CLARA-Care/scripts/ci/check_agent_path_acl.py -a A03 -p PH13 --base bce92340e190c62208a24aa3304f188080f6fd58
================================================================================
PATH ACL CHECKER — PASSED (Agent: A03, Phase: PH13)
================================================================================
Evaluated Files : 3
...
Result: All touched files conform strictly to the designated path lane.
```

## Notes

- The documented base SHA `bce92340e1f7a0709a96e9526e0682fa0fcb1e32` is not an
  object in this worktree; the checked-out base commit is
  `bce92340e190c62208a24aa3304f188080f6fd58` (`feat(ph12): integrate lifemap
  longitudinal intelligence`), which the ACL check above used. This is an
  identifier transcription difference, not a divergent base.
- Tests are pure logic: no database, no network, no GPU. Determinism is asserted
  by comparing full batch `to_dict()` output between forward and reverse input
  orderings.
