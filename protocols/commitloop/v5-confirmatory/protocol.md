# CommitLoop Phase B v5-confirmatory protocol

Status: `DRAFT_NOT_FROZEN`. Synthetic software evaluation only. Phase B v4 is
exploratory and is not an input cohort, confirmatory result, or tuning set.

## Research question

For independent held-out subjects, does `glhs_hybrid_thss_strict` improve
subject-level exact lifecycle/evidence/timeliness resolution over
`full_authorized_history` under the primary frozen model?

## Design

- Unit: one independently generated synthetic subject with one source case.
- Primary model: `antigravity/claude-sonnet-4-6`.
- Primary contrast: strict THSS minus authorization-only full history.
- Primary endpoint: all three state axes exactly match deterministic gold.
- Target enrollment: 384 analyzable subjects, balanced 48 per held-out stratum.
- Solver execution: eight bounded workers in frozen batches of five requests;
  concurrency and batch size are frozen before the first provider call and are
  recorded in the run manifest.
- Missing, malformed, wrong-model or failed outputs are incorrect, not excluded.
- Gemini, Naive RAG, LWW, bitemporal/provenance resolver and GST/THSS ablations
  are secondary or exploratory; their p-values cannot establish primary success.
- Construction, gold and acceptance rules are deterministic. Models may review
  construction but cannot author canonical gold.

## Evidence layers

1. Deterministic structural/conformance evaluation.
2. Adversarial, security, race, fault and recovery evaluation.
3. Frozen independent model-mediated evaluation.

## Freeze and execution gate

Before the first provider call, seal implementation SHA, dependency locks,
container digest, cohort and template-family inventory, oracle, prompts, schemas,
comparators, model mapping, exclusions, analysis code and environment manifest.
Validate the offline dry run and all checksums with networking disabled. Then
stop and obtain explicit approval for provider cost.

After approval, execute once without tuning. A benchmark-affecting defect,
freeze mismatch, cohort leakage, fallback, wrong reported model, or analysis
contract change invalidates the run and requires a documented new freeze and
fresh cohort. Provider/service failures remain failures unless the frozen retry
policy explicitly permits a retry.

## Success, failure and claim limits

Primary success requires a valid sealed run, all 384 subjects retained in the
denominator, a positive strict-minus-full-history effect, two-sided exact paired
sign `p < 0.05`, and a subject-bootstrap 95% CI with lower bound above zero.
Otherwise the primary result is failed or inconclusive as specified by the SAP;
the cohort cannot be tuned or rerun. Results remain synthetic software evidence,
not clinical safety, effectiveness, population or publication evidence.
