# Model card — CLARA-Eval VN runtime evidence

- Stable artifact ID/version: `clara-eval-vn.report.v1`; runner version is
  captured in every `metrics.json`.
- Use case: record versioned evidence for routing and AI-adjacent CLARA
  surfaces; it is not a clinical decision model.
- Models/providers: the governed registry assigns DeepSeek V4 Pro to
  safety/reasoning contracts and V4 Flash to bounded extraction, reranking and
  query-planning contracts. No provider is invoked by the offline suite; its
  report records the manifest profile and only the presence of approved runtime
  environment variable names, never values or tokens.
- Intended use: PR fixture integrity, nightly evidence packaging, and a
  release gate once approved locked inputs are available.
- Forbidden use: diagnosis, dosing, access control, clinician replacement,
  or representing `not_measured` as a quality score.
- Calibration/subgroups/clinical performance: not measured by checked-in
  synthetic fixtures. Run `make eval-nightly` with approved reviewed data.
- Safety boundary: deterministic emergency, consent, RBAC, DrugBank and
  LifeMap truth-state controls remain outside evaluator/model output.
- Rollback: set `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=false` to restore
  the legacy `DEEPSEEK_MODEL` route, or select the explicit prior model through
  `MODEL_REGISTRY_ROLLBACK_MODEL` plus `MODEL_REGISTRY_FORCE_ROLLBACK=true`;
  redeploy, then run `make eval-smoke`.
- Known limitation: the foundation runner creates no live inference traces;
  release is designed to fail closed until those inputs are supplied.
