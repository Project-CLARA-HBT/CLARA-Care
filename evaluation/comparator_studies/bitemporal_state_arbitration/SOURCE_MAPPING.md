# BTSA source mapping

Primary source: Zhao et al., *Beyond Retrieval: Bi-Temporal State Arbitration
for Longitudinal Healthcare Agents*, KnowFM 2026, ACL Anthology PDF.

| Paper capability | Repository implementation | Fidelity evidence |
| --- | --- | --- |
| Event/knowledge and valid-time cutoffs | `ArbitrationEvent` and `arbitrate` | `test_engine.py` |
| SUPPORT, REFINE, SUPERSEDE, BRANCH-CONFLICT | explicit `relation` values | `test_engine.py` |
| Non-destructive historical visibility | `historical_ids` | `test_engine.py` |
| CommitLoop packet adaptation | `adapter.py:btsa_context` invokes `arbitrate` | `test_adapter.py`, `test_solver_packets.py` |

The original detailed, section-level mapping remains in
`BTSA_IMPLEMENTATION_NOTES.md`.
