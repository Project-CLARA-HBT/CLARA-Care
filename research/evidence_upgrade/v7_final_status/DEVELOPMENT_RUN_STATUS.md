# GLHS v7 Development Run Status

Status: **INCOMPLETE, UNSEALED, and not suitable for final inference**
Audit date: 2026-08-19
Scope: v7 development split only; no sealed-test execution is claimed.

## Finding

The last defensible checkpoint was **9,760 / 19,008 solver cells** for the
development split.

| Item | Last observed value |
|---|---:|
| Scientific subject count (`N`) | 192 |
| Frozen development case inventory | 1,056 |
| Frozen conditions | 9 |
| Frozen models | 2 |
| Expected solver cells | 19,008 |
| Completed checkpoint keys | 9,760 |
| Gemini completed | 9,504 / 9,504 |
| Claude completed or terminally failed | 256 / 9,504 |
| Claude successful output records | 253 |
| Claude terminal schema errors | 3 |
| Remaining keys at last checkpoint | 9,248 |
| Model-generation records | 0 |

The 1,056-case inventory is the 192-subject development cohort expanded with
the prespecified adversarial variants. It is not the scientific denominator.
The scientific unit remains 192 subjects. The 19,008 figure is an execution
cell/request inventory, not a clinical sample size.

The last observed state was Gemini-complete and Claude-partial. The three
Claude failures were retained as terminal `prediction_schema_invalid` records;
there is no basis to repair, impute, or score the missing remainder.

## Why The Directory Disappeared

There were two different deletions in the audit trail:

1. At `2026-08-19 04:47:10 +07`, the restart command explicitly ran
   `rm -rf /tmp/opencode/v7-cohort/dev-run` before launching PID 7589. This
   intentionally discarded the earlier attempt and is not evidence that PID
   7589 deleted its own output.
2. The run directory still existed for inspection at approximately
   `2026-08-19 13:59 +07`. The recorded checkpoint had 9,760 keys and the
   append ledgers had 9,757 successful outputs plus 3 errors.

The later disappearance is explained by the host reboot: boot began at
`2026-08-19 14:30:16 +07`, and `/tmp/opencode` was recreated at
`14:31:20 +07`. After boot, `/tmp/opencode/v7-cohort/dev-run` and the sibling
freeze/probe artifacts were absent. The post-boot process check showed PID
7589 absent and the artifact line count as `0 total`. No later `rm -rf` of the
v7 directory appears in the OpenCode audit log. Therefore the safest conclusion
is that the run was killed by reboot and its artifacts were lost with the
volatile `/tmp` filesystem; a clean runner exit cannot be asserted.

## Evidence That Survives

The complete run directory does **not** survive. In particular, no current
`checkpoint.json`, append ledger, `run_manifest.json`, `metrics.json`,
`validation_report.json`, or `checksums.sha256` can be verified on disk.

OpenCode's local database retains command-result excerpts and records the
following provenance:

- provider probe recorded at `2026-08-19T04:47:02.783928Z`;
- implementation/freeze Git SHA: `0a6c5940b164d5f262d1f82a9a7ad9a443275602`;
- frozen cohort: `glhs_bench_v7_confirmatory_768`;
- development subjects: 192;
- development cases: 1,056;
- development request budget: 19,008;
- checkpoint summary: 9,760 completed keys, split as Gemini 9,504 and Claude
  256;
- append-ledger summary: 9,757 outputs and 3 Claude schema errors.

These excerpts are an audit trace, not a substitute for the raw output
ledgers or a cryptographic seal. This report therefore does not promote the
run to a result, does not report accuracy, and does not modify any old seal.

## Safe Restart Or Resume

No router call was made during this audit. The following procedure is the
prescribed procedure for a future authorized execution.

1. Use persistent storage, never `/tmp`. Set a new run root and refuse to
   overwrite it:

   ```bash
   export RUN_ROOT="$HOME/glhs-v7-development-20260819"
   export WT="$HOME/glhs-v7-code-0a6c5940"
   export ORIG_ROOT="$HOME/Documents/CLARA-Care"
   test ! -e "$RUN_ROOT"
   test ! -e "$WT"
   git worktree add --detach "$WT" 0a6c5940b164d5f262d1f82a9a7ad9a443275602
   ```

2. Recreate the pre-provider freeze in that clean detached worktree. Do not
   run from the current dirty worktree, and do not alter the prior sealed run
   directories. The prior-run list below is the list used by the last known
   v7 freeze attempt:

   ```bash
   cd "$WT"
   PYTHONPATH=services/api/src:. "$ORIG_ROOT/services/api/.venv/bin/python" \
     -m evaluation.commitloop.v7_freeze \
     --output "$RUN_ROOT/freeze" \
     --repo-root "$WT" \
     --prior-run "$ORIG_ROOT/artifacts/commitloop/local-phase-a-v2" \
     --prior-run "$ORIG_ROOT/artifacts/commitloop/local-phase-a-v3" \
     --prior-run "$ORIG_ROOT/artifacts/commitloop/local-phase-a-v4" \
     --prior-run "$ORIG_ROOT/artifacts/commitloop/local-phase-a-v5" \
     --prior-run "$ORIG_ROOT/artifacts/commitloop/local-phase-a-v6"
   ```

   Set `ORIG_ROOT` to the actual original repository path if it differs from
   this checkout. Before proceeding, verify that `freeze.json` says
   `FROZEN_PRE_PROVIDER`, has
   `provider_calls_before_freeze: 0`, has Git SHA
   `0a6c5940b164d5f262d1f82a9a7ad9a443275602`, and reports 19,008 development
   requests.

3. Re-run the exact two-model provider probe into the persistent freeze
   directory, only after router access is explicitly authorized. Use the
   environment for the credential; never put a key in shell history or this
   report:

   ```bash
   export ROUTER_BASE_URL="https://router.theclaracare.com/v1"
   export CLARA_ROUTER_API_KEY="<provide-at-execution-time>"
   PYTHONPATH=services/api/src:. "$ORIG_ROOT/services/api/.venv/bin/python" - <<'PY'
   import os
   from pathlib import Path
   from evaluation.commitloop.http_transport import UrllibJsonTransport
   from evaluation.commitloop.provider import CONFIRMATORY_MODELS, EvaluationClient, RunLimits
   from evaluation.commitloop.v7_probe import probe_v7_models

   root = Path(os.environ["V7_RUN_ROOT"])
   limits = RunLimits(
       max_subjects=192, max_cases=192, max_requests=19008,
       max_concurrency=5, timeout_seconds=90, checkpoint_every=5,
       max_retries=5, retry_backoff_seconds=0.5,
   )
   clients = {
       model: EvaluationClient(
           base_url=os.environ["ROUTER_BASE_URL"],
           api_key=os.environ["CLARA_ROUTER_API_KEY"],
           transport=UrllibJsonTransport(), limits=limits,
       )
       for model in CONFIRMATORY_MODELS
   }
   probe_v7_models(
       freeze_path=root / "freeze/freeze.json",
       output_path=root / "freeze/provider_probe.json",
       clients=clients,
       repository_root=Path(os.environ["V7_WORKTREE"]),
   )
   PY
   ```

   Set `V7_RUN_ROOT` and `V7_WORKTREE` to the values from step 1 before this
   command. The probe must report both declared models, the declared reported
   model mapping, `fallback: false`, and temperature zero.

4. Start the development partition with an output directory that does not
   exist yet. Keep the command and log outside `/tmp`:

   ```bash
   export V7_RUN_ROOT="$HOME/glhs-v7-development-20260819"
   export V7_WORKTREE="$HOME/glhs-v7-code-0a6c5940"
   cd "$V7_WORKTREE"
   test ! -e "$V7_RUN_ROOT/dev-run"
   nohup env PYTHONPATH=services/api/src:. \
     ROUTER_BASE_URL="$ROUTER_BASE_URL" \
     CLARA_ROUTER_API_KEY="$CLARA_ROUTER_API_KEY" \
     "$ORIG_ROOT/services/api/.venv/bin/python" -m evaluation.commitloop.v7_cli \
     --freeze "$V7_RUN_ROOT/freeze/freeze.json" \
     --probe "$V7_RUN_ROOT/freeze/provider_probe.json" \
     --output "$V7_RUN_ROOT/dev-run" \
     --split development \
     --repository-root "$V7_WORKTREE" \
     > "$V7_RUN_ROOT/v7-dev.log" 2>&1 &
   printf '%s\n' "$!" > "$V7_RUN_ROOT/pid"
   ```

5. If that process is interrupted before completion, rerun the launch command
   with the same freeze, probe, worktree, and output directory, but omit the
   first-run `test ! -e "$V7_RUN_ROOT/dev-run"` guard. Do not use `rm -rf`, do
   not regenerate the cohort, and do not change model order, conditions,
   concurrency, retry policy, or request budget. The runner reads
   `checkpoint.json` and deduplicates the durable append ledgers, so this is the
   supported resume path. If `frozen_inputs/` already exists or a terminal
   `run_manifest.json` and `checksums.sha256` are present, stop and verify the
   existing run instead of launching a second process.

6. Before accepting the run, confirm all 19,008 keys are accounted for by
   successful outputs or declared terminal errors, verify the generated
   `checksums.sha256`, and retain the entire persistent run root. Only then may
   a separate analysis/reporting step be considered. The `sealed_test` split
   remains prohibited until its explicit final-candidate gate is satisfied.

## Disposition

This development execution is **not a final v7 result**. Its last-known
checkpoint may be cited only as an interrupted operational status:
**9,760 / 19,008 cells, scientific N=192, Gemini complete, Claude partial**.
No accuracy, superiority, clinical, or final-holdout claim is supported.
