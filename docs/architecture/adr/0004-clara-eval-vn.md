# ADR 0004: CLARA-Eval VN is multi-track and evidence-first

Status: accepted for PR-13 implementation.

CLARA-Eval VN extends the existing active-eval loop. It reports nine tracks
separately and never fabricates an aggregate accuracy. Every metric records
dataset/model/prompt/retrieval provenance, sample size, CI when measured, and an
explicit `not_measured` reason plus runnable command otherwise. Judge artifacts
are generated HTML, Markdown, JSON and CSV from the same structured report.

Rollback: remove the additive workflow/job or use `run_active_eval_loop.sh`; no
production inference traffic or database schema depends on the evaluator.
