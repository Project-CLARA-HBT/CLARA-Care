# BTSA method card

Status: **mechanism-mapped, not a faithful end-to-end reproduction**.

This comparator maps Zhao et al.'s public bi-temporal state representation and
four arbitration operators. It is treated as a strong temporal/conflict
comparator for the capabilities it actually implements. It does not inherit
any GLHS policy, consent, concurrency, profile-scoping, or audit behavior.

The frozen boundary, paper mapping, and unavailable source components are in
`SOURCE_MAPPING.md` and `DEVIATIONS.md`. Operator/bitemporal fidelity tests are
in `test_engine.py`; `adapter.py` and `test_adapter.py` prove that the CommitLoop
packet condition executes the mechanism instead of merely naming it.
