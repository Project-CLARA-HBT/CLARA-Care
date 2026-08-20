# CareGuard-VN arXiv draft package — literature-hardened v2

Files:
- `main.tex` — revised manuscript draft with literature-derived novelty boundary; external benchmark results remain intentionally pending.
- `references.bib` — bibliography including RxMap, ambiguity, selective prediction, RABBITS, MedGuard, and DDI-review nearest neighbors.
- `LITERATURE_NOVELTY_MATRIX.md` — locked nearest-neighbor matrix and allowed novelty claim.
- `CAREGUARD_EXTERNAL_BENCHMARK_MASTER_SPEC.md` — external-evidence implementation/evaluation spec.
- `CODEX_GOAL.md` — <=4000-character `/goal` for Codex.

Central novelty lock: **Source-Bound Medication Identity (SBMI) as a mandatory downstream DDI release precondition**, evaluated by false-clear / wrong-identity risk versus automatic coverage. Do not claim novelty for normalization, LLM parsing, ambiguity detection, human review, abstention, terminology versioning, DDI lookup, Vietnamese UI, or wrong-drug/LASA detection alone.

Scientific guardrail: the existing 242/250 DrugBank positive runtime result is same-source technical conformance, not external clinical validation. The manuscript becomes results-ready only after sealed external runs are completed.
