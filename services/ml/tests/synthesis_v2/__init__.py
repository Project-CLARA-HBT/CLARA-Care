"""Shared test support for CLARA Pro answer-synthesis v2.

Feature: ``clara-pro-answer-synthesis``. This package hosts the reusable test
harness for the scope-aware length, reliable convergence, and de-templating
work on the ``deep_beta`` synthesis path
(``clara_ml.agents.research_tier2`` + ``clara_ml.config``).

The whole feature ships behind the persistent ``SYNTHESIS_V2_ENABLED`` flag
(default OFF ⇒ pre-feature behavior). The harness exists to make the two halves
of every property cheap to express:

* **flag-toggling** — :func:`harness.synthesis_v2_flag` flips
  ``settings.synthesis_v2_enabled`` for the duration of a ``with`` block and
  always restores the previous value, so a single test can compare flag-OFF
  (legacy) against flag-ON (v2) without leaking ambient config across tests.
* **flags-off baseline capture** — :func:`harness.capture_budget` and
  :func:`harness.capture_section_contract` snapshot the pure, network-free
  budget/contract decisions in a small comparable shape so "flag off ==
  pre-feature behavior" (design Property P8) reduces to an equality assertion.

The property tags ``P1..P10`` map 1:1 to the design's *Correctness Properties*;
:data:`harness.PROPERTY_TAGS` is the single source of truth shared by the
property-test modules.

Only end-user-facing product copy is Vietnamese; this test code and its
identifiers are intentionally English.
"""
