# Sealed GovMut SOICT result root

- Freeze: `govmut-soict-2026-final-v2`
- Run schema: `govmut-final-run.v1`
- Source SHA: `7c963153c5ad4b62bc9eb58b5ad976b233a3631f`
- Hypothesis: `6.163.0`
- Limits: `{"hypothesis_max_examples": 1000, "hypothesis_stateful_step_count": 100, "pytest_timeout_seconds": 600}`
- Outcomes: `{"INFRASTRUCTURE_ERROR": 0, "KILLED": 161, "SURVIVED": 559}`
- Sealed at: `2026-08-18T02:13:03.990577+00:00`

## Artifacts

| Path | SHA-256 |
| --- | --- |
| `artifact-sha256.json` | `d7a26c46eb35e474f13afc2e81aeaf50cdb09126345d406464c65af87a10aa9a` |
| `claim_to_evidence.csv` | `451bcb60502b0dd5f62466bcee440adc4e5fba80308cf122dc93cb17339249f2` |
| `environment.json` | `9a4daa2aa370286c1779cf227d65a26e485af9307a3c5a36e70a3a253929ef45` |
| `govmut-soict-2026-final_analysis-v2` | `e3ab1832c42be2a745ddae4ab960697143688302f78f6f4c08e82ef379278a67` |
| `govmut-soict-2026-final_run-v2` | `c59768dced443bb9cde6ba78762b728522cc9f581e30556b008f4b054e7cb6ce` |
| `unmutated_preflight.json` | `432bd2ab66b707fd3de01d0ef5ce2830e0501c10801c21c51321a04f62b97db0` |

## Claims

See `claim_to_evidence.csv` for claim-to-evidence mapping.
Aggregation follows the frozen rule in `research/assurance_soict/ANALYSIS_PLAN.md` (primary `detected_any_seed`; robustness `detected_all_seeds`; seeds are deterministic streams, not independent N).

This work stream is not external clinical validation.
