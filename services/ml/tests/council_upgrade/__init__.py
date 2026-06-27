"""Shared test support for the **CLARA Council upgrade** (ML side).

Feature: ``clara-council-upgrade``. This package hosts the reusable test harness
for the ML half of the Council upgrade — the SSE stage stream
(``clara_ml.main`` / ``clara_ml.agents.council*``), the ``ai_disclosure``
decoration on ``run_council`` / ``run_council_intake``, and the per-stage flow
events — all gated behind ``COUNCIL_*`` flags in ``clara_ml.config``.

The whole feature ships behind flags that default OFF ⇒ pre-feature behavior.
This harness exists so the two halves of every property are cheap to express:

* **flag-toggling** — :func:`harness.council_flags` flips the ML-side
  ``COUNCIL_*`` upgrade flags on the live ``settings`` object for the duration
  of a ``with`` block and always restores the previous values, so a single test
  can compare flag-OFF (legacy) against flag-ON without leaking ambient config.
* **flags-off baseline** — :func:`harness.assert_flags_off_baseline` pins that
  with no overrides every ML-side upgrade flag is ``False`` so ``run_council`` /
  ``run_council_intake`` emit their existing shapes (design Property P8;
  Requirements 9.1, 9.2).

The pre-existing ``COUNCIL_NEURAL_*`` flags remain the source of truth for
shadow-mode neural risk and are intentionally excluded from this inventory.

Only end-user-facing product copy is Vietnamese; this test code and its
identifiers are intentionally English.
"""
